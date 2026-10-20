"""DynAPM v3: periodic predictor refresh + drift-augmented extra refreshes."""
from __future__ import annotations

import pandas as pd

from dynapm.core.drift import ADWINDetector
from dynapm.core.forecasting import forecast_class_from_window, forecast_p95_from_window
from dynapm.methods.baselines_v2 import _BasePolicyV2


class DynAPMPolicyV3(_BasePolicyV2):
    """
    DynAPM v3 = Periodic-Predictor + Drift augmentation.

    Refresh at every ``period_hours`` tick OR on any ADWIN drift on CPU/memory
    residuals. Each refresh recomputes all dynamic fields from a causal
    multi-step predictor horizon. No decision head, churn, or alpha.
    """

    def __init__(
        self,
        profile,
        cpu_thresholds,
        mem_thresholds,
        bootstrap_cpu_series,
        bootstrap_mem_series,
        cpu_pred_full,
        mem_pred_full,
        cpu_predictor,
        mem_predictor,
        cpu_obs_full,
        mem_obs_full,
        period_hours: float = 6.0,
        drift_delta: float = 0.002,
    ):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self._cpu_pred_full = cpu_pred_full
        self._mem_pred_full = mem_pred_full
        self._cpu_predictor = cpu_predictor
        self._mem_predictor = mem_predictor
        self._cpu_obs_full = cpu_obs_full
        self._mem_obs_full = mem_obs_full
        self._period = pd.Timedelta(hours=float(period_hours))
        self._cpu_drift = ADWINDetector(delta=float(drift_delta))
        self._mem_drift = ADWINDetector(delta=float(drift_delta))
        self._last: pd.Timestamp | None = None
        self._set_initial_forecast(bootstrap_cpu_series, bootstrap_mem_series)

    def _set_initial_forecast(self, boot_cpu, boot_mem):
        t0 = pd.Timestamp(self.profile.static.bootstrap_end)
        self.profile.dynamic.cpu_class = forecast_class_from_window(boot_cpu, self.cpu_thresholds)
        self.profile.dynamic.memory_class = forecast_class_from_window(boot_mem, self.mem_thresholds)
        self.profile.dynamic.predicted_cpu_p95_next_24h = forecast_p95_from_window(boot_cpu)
        self.profile.dynamic.predicted_mem_p95_next_24h = forecast_p95_from_window(boot_mem)
        for f in ("cpu_class", "memory_class", "predicted_cpu_p95_next_24h", "predicted_mem_p95_next_24h"):
            self.profile.last_updated[f] = t0

    def _causal_windows(self, t: pd.Timestamp):
        hist_cpu = self._cpu_obs_full.loc[:t]
        hist_mem = self._mem_obs_full.loc[:t]
        return (
            self._cpu_predictor.predict_causal_horizon(hist_cpu, n_steps=288),
            self._mem_predictor.predict_causal_horizon(hist_mem, n_steps=288),
        )

    def _refresh_from_predictor(self, t: pd.Timestamp, reason: str) -> None:
        t = pd.Timestamp(t)
        cpu_lookahead, mem_lookahead = self._causal_windows(t)
        if len(cpu_lookahead) == 0:
            return

        old = (
            self.profile.dynamic.cpu_class,
            self.profile.dynamic.memory_class,
            self.profile.dynamic.predicted_cpu_p95_next_24h,
            self.profile.dynamic.predicted_mem_p95_next_24h,
        )

        new_cpu_cls = forecast_class_from_window(cpu_lookahead, self.cpu_thresholds)
        new_mem_cls = forecast_class_from_window(mem_lookahead, self.mem_thresholds)
        new_cpu_p95 = forecast_p95_from_window(cpu_lookahead)
        new_mem_p95 = forecast_p95_from_window(mem_lookahead)

        self.profile.dynamic.cpu_class = new_cpu_cls
        self.profile.dynamic.memory_class = new_mem_cls
        self.profile.dynamic.predicted_cpu_p95_next_24h = new_cpu_p95
        self.profile.dynamic.predicted_mem_p95_next_24h = new_mem_p95

        for f in ("cpu_class", "memory_class", "predicted_cpu_p95_next_24h", "predicted_mem_p95_next_24h"):
            self.profile.last_updated[f] = t

        meta = {"timestamp": t, "p_commit": 1.0, "reason": reason}
        self._update_log.append({**meta, "field": "cpu_class", "old_value": old[0], "new_value": new_cpu_cls})
        self._update_log.append({**meta, "field": "memory_class", "old_value": old[1], "new_value": new_mem_cls})
        self._update_log.append(
            {**meta, "field": "predicted_cpu_p95_next_24h", "old_value": old[2], "new_value": new_cpu_p95}
        )
        self._update_log.append(
            {**meta, "field": "predicted_mem_p95_next_24h", "old_value": old[3], "new_value": new_mem_p95}
        )

    def step(self, t, cpu_obs_window, mem_obs_window, cpu_pred_window, mem_pred_window):
        t = pd.Timestamp(t)

        cpu_resid = float(cpu_obs_window.iloc[-1]) - float(cpu_pred_window.iloc[-1])
        mem_resid = float(mem_obs_window.iloc[-1]) - float(mem_pred_window.iloc[-1])
        cpu_drift = self._cpu_drift.update(cpu_resid)
        mem_drift = self._mem_drift.update(mem_resid)

        periodic_due = self._last is None or (t - self._last) >= self._period
        drift_event = cpu_drift or mem_drift

        if periodic_due:
            self._refresh_from_predictor(t, reason="periodic")
            self._last = t
        elif drift_event:
            self._refresh_from_predictor(t, reason="drift")
