"""DynAPM v3: periodic predictor refresh + drift-augmented extra refreshes."""
from __future__ import annotations

import math

import pandas as pd

from dynapm.core.temporal import PeriodicGrid, eligibility, history_valid, SAMPLE_STEP
from dynapm.core.accounting import Trigger
from dynapm.core.predictor import HorizonPredictor, forecast_at_origin

from dynapm.core.drift import ADWINDetector
from dynapm.methods.baselines_v2 import _BasePolicyV2


class DynAPMPolicyV3(_BasePolicyV2):
    """
    DynAPM v3 = Periodic-Predictor + Drift augmentation.

    Refresh at every ``period_hours`` tick OR on any ADWIN drift on CPU/memory
    residuals. Each refresh recomputes all dynamic fields from a causal
    multi-step predictor horizon. No decision head, churn, or alpha.
    """

    requires_predictors = True
    requires_residuals = True
    allowed_triggers = (Trigger.PERIODIC, Trigger.DRIFT)

    def __init__(
        self,
        profile,
        cpu_thresholds,
        mem_thresholds,
        *,
        bootstrap_cpu_series,
        bootstrap_mem_series,
        cpu_predictor: HorizonPredictor,
        mem_predictor: HorizonPredictor,
        cpu_obs_full,
        mem_obs_full,
        period_hours: float = 6.0,
        drift_delta: float = 0.002,
    ):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self._cpu_predictor = cpu_predictor
        self._mem_predictor = mem_predictor
        self._cpu_obs_full = cpu_obs_full
        self._mem_obs_full = mem_obs_full
        self.periodic_grid = PeriodicGrid(profile.static.bootstrap_end, period_hours)
        self.unavailable_residuals = 0
        self.ineligible_drift_signals = 0
        self._cpu_drift = ADWINDetector(delta=float(drift_delta))
        self._mem_drift = ADWINDetector(delta=float(drift_delta))
        self._set_initial_forecast(bootstrap_cpu_series, bootstrap_mem_series, t=profile.static.bootstrap_end)

    def _causal_windows(self, t: pd.Timestamp):
        return (
            forecast_at_origin(self._cpu_predictor, self._cpu_obs_full, t),
            forecast_at_origin(self._mem_predictor, self._mem_obs_full, t),
        )

    def _refresh_from_predictor(self, t, trigger, nominal=None):
        cpu_lookahead, mem_lookahead = self._causal_windows(t)
        self._commit_forecast(t, cpu_lookahead, mem_lookahead,
            trigger=trigger, nominal_scheduled_time=nominal)

    def step(self, t, cpu_obs_window, mem_obs_window, *, cpu_prediction: float | None = None, mem_prediction: float | None = None):
        """Consume current yhat(t|t-1) scalars only; refreshes never use them."""
        t = pd.Timestamp(t)

        if cpu_obs_window.index[-1] != t or mem_obs_window.index[-1] != t:
            raise ValueError("residual observations must be aligned to the current timestamp")
        cpu_drift = mem_drift = False
        residual_history_ok = history_valid(cpu_obs_window, t-SAMPLE_STEP) and history_valid(mem_obs_window, t-SAMPLE_STEP)
        if cpu_prediction is None or mem_prediction is None or not residual_history_ok:
            # Missing history pauses the detectors; their state is not reset.
            self.unavailable_residuals += 1
        else:
            if not math.isfinite(cpu_prediction) or not math.isfinite(mem_prediction):
                raise ValueError("residual predictions must be finite")
            cpu_drift = self._cpu_drift.update(float(cpu_obs_window.iloc[-1])-cpu_prediction)
            mem_drift = self._mem_drift.update(float(mem_obs_window.iloc[-1])-mem_prediction)

        # ADWIN has consumed r_t before triggers are resolved. A periodic tick
        # wins on coincidence; a drift refresh never changes the wall-clock grid.
        nominal = self.periodic_grid.pop_due(t, eligibility(cpu_obs_window, mem_obs_window, t))
        if nominal is not None:
            self._refresh_from_predictor(t, trigger=Trigger.PERIODIC, nominal=nominal)
        elif cpu_drift or mem_drift:
            if history_valid(cpu_obs_window, t) and history_valid(mem_obs_window, t):
                self._refresh_from_predictor(t, trigger=Trigger.DRIFT)
            else:
                # River's current signal is consumed, not latched or replayed.
                self.ineligible_drift_signals += 1
