"""Candidate architecture: shared observation content, timing-only differences.

Legacy predictor-content policies remain available for prior development studies,
not as the candidate architecture. Residual RF is not a content dependency.
"""
import math
import numpy as np
import pandas as pd
from dynapm.core.accounting import Trigger
from dynapm.core.drift import ADWINDetector
from dynapm.core.temporal import (PeriodicGrid, trailing_targets, MIN_OBSERVATIONS,
                                  history_valid, SAMPLE_STEP)
from dynapm.methods.baselines_v2 import _BasePolicyV2

CONTENT_VERSION = 'paired-observation-window-24h-v1'


def paired_content_window(cpu, memory, origin):
    """Finite paired actual slots in (t-24h,t], no filling or history extension."""
    targets = trailing_targets(origin)
    c = cpu.reindex(targets).to_numpy(dtype=float)
    m = memory.reindex(targets).to_numpy(dtype=float)
    valid = np.isfinite(c) & np.isfinite(m)
    return pd.DataFrame({'cpu':c[valid], 'memory':m[valid]}, index=targets[valid])


class WindowPeriodicPolicy(_BasePolicyV2):
    """PW-6h candidate: paired-window content eligibility, no RF requirement."""
    allowed_triggers = (Trigger.PERIODIC,)

    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series, period_hours=6):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self.periodic_grid = PeriodicGrid(profile.static.bootstrap_end, period_hours)
        self.ineligible_content_observations = 0
        t0 = bootstrap_cpu_series.index[-1]
        window = paired_content_window(bootstrap_cpu_series, bootstrap_mem_series, t0)
        if len(window) < MIN_OBSERVATIONS:
            raise ValueError('initial profile requires 200 paired trailing slots')
        self._set_initial_forecast(window.cpu, window.memory, t=t0)

    def _commit_window(self, t, window, trigger, nominal=None):
        if len(window) < MIN_OBSERVATIONS:
            raise ValueError('ineligible observation content commit')
        self._commit_forecast(t, window.cpu, window.memory, trigger=trigger,
                              nominal_scheduled_time=nominal)

    def _process_periodic(self, t, window):
        eligible = len(window) >= MIN_OBSERVATIONS
        if not eligible:
            self.ineligible_content_observations += 1
        nominal = self.periodic_grid.pop_due(t, eligible)
        if nominal is None:
            return False
        self._commit_window(t, window, Trigger.PERIODIC, nominal)
        return True

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        self._process_periodic(t, paired_content_window(cpu_obs_window, mem_obs_window, t))


class AdaptiveResidualPolicy(WindowPeriodicPolicy):
    """Same PW content; RF one-step residuals feed frozen ADWIN timing only."""
    requires_residuals = True
    requires_predictors = False  # content must never receive forecasting models
    allowed_triggers = (Trigger.PERIODIC, Trigger.DRIFT)

    def __init__(self, *args, drift_delta=.002, **kwargs):
        super().__init__(*args, **kwargs)
        self._cpu_drift = ADWINDetector(delta=float(drift_delta))
        self._mem_drift = ADWINDetector(delta=float(drift_delta))
        self.unavailable_residuals = self.ineligible_drift_signals = 0

    def step(self, t, cpu_obs_window, mem_obs_window, *, cpu_prediction=None, mem_prediction=None):
        t = pd.Timestamp(t)
        if cpu_obs_window.index[-1] != t or mem_obs_window.index[-1] != t:
            raise ValueError('residual observations must align with current time')
        signal = False
        valid = history_valid(cpu_obs_window, t-SAMPLE_STEP) and history_valid(mem_obs_window, t-SAMPLE_STEP)
        if not valid or cpu_prediction is None or mem_prediction is None:
            self.unavailable_residuals += 1  # pause, do not reset detectors
        else:
            if not math.isfinite(cpu_prediction) or not math.isfinite(mem_prediction):
                raise ValueError('nonfinite one-step prediction')
            # Update both detectors, without boolean short-circuiting.
            cpu_drift = self._cpu_drift.update(float(cpu_obs_window.iloc[-1])-cpu_prediction)
            mem_drift = self._mem_drift.update(float(mem_obs_window.iloc[-1])-mem_prediction)
            signal = cpu_drift or mem_drift
        window = paired_content_window(cpu_obs_window, mem_obs_window, t)
        if self._process_periodic(t, window):
            return  # periodic precedence, no grid shift, exactly one commit
        if signal:
            if len(window) >= MIN_OBSERVATIONS:
                self._commit_window(t, window, Trigger.DRIFT)
            else:
                self.ineligible_drift_signals += 1  # consumed, never latched


class BudgetMatchedWindowPolicy(WindowPeriodicPolicy):
    """Analysis-only K-count counterfactual; schedule has no drift-time input."""
    allowed_triggers = (Trigger.PERIODIC, Trigger.BUDGET_EXTRA)

    def __init__(self, *args, extra_times, **kwargs):
        super().__init__(*args, **kwargs)
        times = pd.DatetimeIndex(extra_times)
        if not times.is_unique:
            raise ValueError('duplicate budget extras')
        self.extra_times = frozenset(times)

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        window = paired_content_window(cpu_obs_window, mem_obs_window, t)
        committed = self._process_periodic(t, window)
        if t in self.extra_times:
            if committed:
                raise ValueError('budget extra collides with periodic commit')
            self._commit_window(t, window, Trigger.BUDGET_EXTRA)
