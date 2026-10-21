"""Forecast-based baseline policies (v2)."""
from __future__ import annotations

import pandas as pd

from dynapm.core.temporal import (PeriodicGrid, trailing_observations, eligibility, MIN_OBSERVATIONS, MIN_REACTIVE_OBSERVATIONS)
from dynapm.core.accounting import ProfileCommitter, Trigger
from dynapm.core.predictor import HorizonPredictor, forecast_at_origin
from dynapm.core.forecasting import forecast_class_from_window, forecast_p95_from_window


def _window_last_hours(series: pd.Series, t: pd.Timestamp, hours: float) -> pd.Series:
    return trailing_observations(series, t, hours)


class _BasePolicyV2:
    requires_predictors = False
    requires_residuals = False

    def __init__(self, profile, cpu_thresholds, mem_thresholds):
        self.profile = profile
        self.cpu_thresholds = cpu_thresholds
        self.mem_thresholds = mem_thresholds
        self.accounting = ProfileCommitter(profile, self.allowed_triggers)

    allowed_triggers = ()

    @property
    def refresh_log(self):
        return [e.as_record() for e in self.accounting.refresh_events]

    def accounting_metrics(self):
        grid = getattr(self, "periodic_grid", None)
        return self.accounting.counters(grid.nominal_ticks_due if grid is not None else 0)

    def _forecast_values(self, cpu_values, mem_values):
        return {
            "cpu_class": forecast_class_from_window(cpu_values, self.cpu_thresholds),
            "memory_class": forecast_class_from_window(mem_values, self.mem_thresholds),
            "predicted_cpu_p95_next_24h": forecast_p95_from_window(cpu_values),
            "predicted_mem_p95_next_24h": forecast_p95_from_window(mem_values),
        }

    def _set_initial_forecast(self, cpu_values, mem_values, t):
        self.accounting.initialize(t, self._forecast_values(cpu_values, mem_values))

    def _commit_forecast(self, t, cpu_values, mem_values, *, trigger, nominal_scheduled_time=None):
        self.accounting.commit(t, self._forecast_values(cpu_values, mem_values),
            trigger=trigger, nominal_scheduled_time=nominal_scheduled_time)

    def step(self, t, cpu_obs_window, mem_obs_window):
        raise NotImplementedError


class StaticPolicyV2(_BasePolicyV2):
    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        cpu_boot = bootstrap_cpu_series
        mem_boot = bootstrap_mem_series
        self._set_initial_forecast(cpu_boot, mem_boot, t=profile.static.bootstrap_end)

    def step(self, t, cpu_obs_window, mem_obs_window):
        return


class PeriodicPolicyV2(_BasePolicyV2):
    allowed_triggers = (Trigger.PERIODIC,)

    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series, period_hours=6.0):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self._period_hours = float(period_hours)
        self.periodic_grid = PeriodicGrid(profile.static.bootstrap_end, self._period_hours)
        cpu_boot = bootstrap_cpu_series
        mem_boot = bootstrap_mem_series
        t0 = pd.Timestamp(cpu_boot.index[-1])
        cpu_init = _window_last_hours(cpu_boot, t0, self._period_hours)
        mem_init = _window_last_hours(mem_boot, t0, self._period_hours)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        nominal = self.periodic_grid.pop_due(t, eligibility(cpu_obs_window, mem_obs_window, t))
        if nominal is not None:
            self._commit_forecast(t,
                _window_last_hours(cpu_obs_window, t, 24),
                _window_last_hours(mem_obs_window, t, 24),
                trigger=Trigger.PERIODIC, nominal_scheduled_time=nominal)


class ReactiveThresholdPolicyV2(_BasePolicyV2):
    allowed_triggers = (Trigger.REACTIVE,)

    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        cpu_boot = bootstrap_cpu_series
        mem_boot = bootstrap_mem_series
        t0 = pd.Timestamp(cpu_boot.index[-1])
        cpu_init = _window_last_hours(cpu_boot, t0, 24.0)
        mem_init = _window_last_hours(mem_boot, t0, 24.0)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        cpu_candidate = _window_last_hours(cpu_obs_window, t, 6.0)
        mem_candidate = _window_last_hours(mem_obs_window, t, 6.0)

        if len(cpu_candidate.index.intersection(mem_candidate.index)) < MIN_REACTIVE_OBSERVATIONS:
            return
        candidate_cpu_class = forecast_class_from_window(cpu_candidate, self.cpu_thresholds)
        candidate_mem_class = forecast_class_from_window(mem_candidate, self.mem_thresholds)
        if (
            candidate_cpu_class != self.profile.dynamic.cpu_class
            or candidate_mem_class != self.profile.dynamic.memory_class
        ):
            self._commit_forecast(t, cpu_candidate, mem_candidate, trigger=Trigger.REACTIVE)


class FullRewritePolicyV2(_BasePolicyV2):
    allowed_triggers = (Trigger.FULL_REWRITE,)

    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        cpu_boot = bootstrap_cpu_series
        mem_boot = bootstrap_mem_series
        t0 = pd.Timestamp(cpu_boot.index[-1])
        cpu_init = _window_last_hours(cpu_boot, t0, 24.0)
        mem_init = _window_last_hours(mem_boot, t0, 24.0)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        cpu_now = _window_last_hours(cpu_obs_window, t, 24.0)
        mem_now = _window_last_hours(mem_obs_window, t, 24.0)
        if len(cpu_now.index.intersection(mem_now.index)) >= MIN_OBSERVATIONS:
            self._commit_forecast(t, cpu_now, mem_now, trigger=Trigger.FULL_REWRITE)


class PeriodicPredictorPolicyV2(_BasePolicyV2):
    """
    Same refresh cadence as PeriodicPolicyV2 (every ``period_hours``) but
    forecasts from a causal multi-step predictor horizon
    ``{û_{t+k|t}}_{k=1..288}``, not from recent observed windows.
    """

    requires_predictors = True
    allowed_triggers = (Trigger.PERIODIC,)

    def __init__(
        self, profile, cpu_thresholds, mem_thresholds, *,
        bootstrap_cpu_series: pd.Series, bootstrap_mem_series: pd.Series,
        cpu_predictor: HorizonPredictor, mem_predictor: HorizonPredictor,
        cpu_obs_full: pd.Series, mem_obs_full: pd.Series,
        period_hours: float = 6.0,
    ):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self._cpu_predictor = cpu_predictor
        self._mem_predictor = mem_predictor
        self._cpu_obs_full = cpu_obs_full
        self._mem_obs_full = mem_obs_full
        self._period_hours = float(period_hours)
        self.periodic_grid = PeriodicGrid(profile.static.bootstrap_end, self._period_hours)
        t0 = pd.Timestamp(bootstrap_cpu_series.index[-1])
        cpu_init = _window_last_hours(bootstrap_cpu_series, t0, self._period_hours)
        mem_init = _window_last_hours(bootstrap_mem_series, t0, self._period_hours)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)

    def _causal_windows(self, t: pd.Timestamp):
        return (
            forecast_at_origin(self._cpu_predictor, self._cpu_obs_full, t),
            forecast_at_origin(self._mem_predictor, self._mem_obs_full, t),
        )

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        nominal = self.periodic_grid.pop_due(t, eligibility(cpu_obs_window, mem_obs_window, t))
        if nominal is None:
            return
        cpu_lookahead, mem_lookahead = self._causal_windows(t)
        self._commit_forecast(t, cpu_lookahead, mem_lookahead,
            trigger=Trigger.PERIODIC, nominal_scheduled_time=nominal)
