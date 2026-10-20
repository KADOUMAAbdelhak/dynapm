"""Forecast-based baseline policies (v2)."""
from __future__ import annotations

import pandas as pd

from dynapm.core.predictor import HorizonPredictor, forecast_at_origin
from dynapm.core.forecasting import forecast_class_from_window, forecast_p95_from_window


def _window_last_hours(series: pd.Series, t: pd.Timestamp, hours: float) -> pd.Series:
    t = pd.Timestamp(t)
    start = t - pd.Timedelta(hours=float(hours))
    return series.loc[(series.index >= start) & (series.index <= t)]


class _BasePolicyV2:
    requires_predictors = False
    requires_residuals = False

    def __init__(self, profile, cpu_thresholds, mem_thresholds):
        self.profile = profile
        self.cpu_thresholds = cpu_thresholds
        self.mem_thresholds = mem_thresholds
        self._update_log = []

    @property
    def update_log(self):
        return self._update_log

    def _set_initial_forecast(self, cpu_values, mem_values, t: pd.Timestamp):
        self.profile.dynamic.cpu_class = forecast_class_from_window(cpu_values, self.cpu_thresholds)
        self.profile.dynamic.memory_class = forecast_class_from_window(mem_values, self.mem_thresholds)
        self.profile.dynamic.predicted_cpu_p95_next_24h = forecast_p95_from_window(cpu_values)
        self.profile.dynamic.predicted_mem_p95_next_24h = forecast_p95_from_window(mem_values)
        self.profile.last_updated["cpu_class"] = pd.Timestamp(t)
        self.profile.last_updated["memory_class"] = pd.Timestamp(t)
        self.profile.last_updated["predicted_cpu_p95_next_24h"] = pd.Timestamp(t)
        self.profile.last_updated["predicted_mem_p95_next_24h"] = pd.Timestamp(t)

    def _commit_forecast(self, t: pd.Timestamp, cpu_values, mem_values):
        t = pd.Timestamp(t)
        new_vals = {
            "cpu_class": forecast_class_from_window(cpu_values, self.cpu_thresholds),
            "memory_class": forecast_class_from_window(mem_values, self.mem_thresholds),
            "predicted_cpu_p95_next_24h": forecast_p95_from_window(cpu_values),
            "predicted_mem_p95_next_24h": forecast_p95_from_window(mem_values),
        }
        for field, new_value in new_vals.items():
            old_value = getattr(self.profile.dynamic, field)
            if (pd.isna(old_value) and pd.isna(new_value)) or old_value == new_value:
                continue
            setattr(self.profile.dynamic, field, new_value)
            self.profile.last_updated[field] = t
            self._update_log.append(
                {
                    "timestamp": t,
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "p_commit": 1.0,
                }
            )

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
    def __init__(self, profile, cpu_thresholds, mem_thresholds, *,
                 bootstrap_cpu_series, bootstrap_mem_series, period_hours=6.0):
        super().__init__(profile, cpu_thresholds, mem_thresholds)
        self._period_hours = float(period_hours)
        self._period = pd.Timedelta(hours=self._period_hours)
        cpu_boot = bootstrap_cpu_series
        mem_boot = bootstrap_mem_series
        t0 = pd.Timestamp(cpu_boot.index[-1])
        cpu_init = _window_last_hours(cpu_boot, t0, self._period_hours)
        mem_init = _window_last_hours(mem_boot, t0, self._period_hours)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)
        self._last_refresh = t0

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        if (t - self._last_refresh) < self._period:
            return
        self._commit_forecast(t, cpu_obs_window, mem_obs_window)
        self._last_refresh = t


class ReactiveThresholdPolicyV2(_BasePolicyV2):
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

        candidate_cpu_class = forecast_class_from_window(cpu_candidate, self.cpu_thresholds)
        candidate_mem_class = forecast_class_from_window(mem_candidate, self.mem_thresholds)
        if (
            candidate_cpu_class != self.profile.dynamic.cpu_class
            or candidate_mem_class != self.profile.dynamic.memory_class
        ):
            self._commit_forecast(t, cpu_candidate, mem_candidate)


class FullRewritePolicyV2(_BasePolicyV2):
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
        self._commit_forecast(t, cpu_now, mem_now)


class PeriodicPredictorPolicyV2(_BasePolicyV2):
    """
    Same refresh cadence as PeriodicPolicyV2 (every ``period_hours``) but
    forecasts from a causal multi-step predictor horizon
    ``{û_{t+k|t}}_{k=1..288}``, not from recent observed windows.
    """

    requires_predictors = True

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
        self._period = pd.Timedelta(hours=self._period_hours)
        t0 = pd.Timestamp(bootstrap_cpu_series.index[-1])
        cpu_init = _window_last_hours(bootstrap_cpu_series, t0, self._period_hours)
        mem_init = _window_last_hours(bootstrap_mem_series, t0, self._period_hours)
        self._set_initial_forecast(cpu_init, mem_init, t=t0)
        self._last = t0

    def _causal_windows(self, t: pd.Timestamp):
        return (
            forecast_at_origin(self._cpu_predictor, self._cpu_obs_full, t),
            forecast_at_origin(self._mem_predictor, self._mem_obs_full, t),
        )

    def step(self, t, cpu_obs_window, mem_obs_window):
        t = pd.Timestamp(t)
        if (t - self._last) < self._period:
            return

        cpu_lookahead, mem_lookahead = self._causal_windows(t)
        if len(cpu_lookahead) == 0 or len(mem_lookahead) == 0:
            return

        old_cpu_cls = self.profile.dynamic.cpu_class
        old_mem_cls = self.profile.dynamic.memory_class
        old_cpu_p95 = self.profile.dynamic.predicted_cpu_p95_next_24h
        old_mem_p95 = self.profile.dynamic.predicted_mem_p95_next_24h

        new_cpu_cls = forecast_class_from_window(cpu_lookahead, self.cpu_thresholds)
        new_mem_cls = forecast_class_from_window(mem_lookahead, self.mem_thresholds)
        new_cpu_p95 = forecast_p95_from_window(cpu_lookahead)
        new_mem_p95 = forecast_p95_from_window(mem_lookahead)

        self.profile.dynamic.cpu_class = new_cpu_cls
        self.profile.dynamic.memory_class = new_mem_cls
        self.profile.dynamic.predicted_cpu_p95_next_24h = new_cpu_p95
        self.profile.dynamic.predicted_mem_p95_next_24h = new_mem_p95

        self.profile.last_updated["cpu_class"] = t
        self.profile.last_updated["memory_class"] = t
        self.profile.last_updated["predicted_cpu_p95_next_24h"] = t
        self.profile.last_updated["predicted_mem_p95_next_24h"] = t

        self._last = t

        if old_cpu_cls != new_cpu_cls:
            self._update_log.append(
                {
                    "timestamp": t,
                    "field": "cpu_class",
                    "old_value": old_cpu_cls,
                    "new_value": new_cpu_cls,
                    "p_commit": 1.0,
                }
            )
        if old_mem_cls != new_mem_cls:
            self._update_log.append(
                {
                    "timestamp": t,
                    "field": "memory_class",
                    "old_value": old_mem_cls,
                    "new_value": new_mem_cls,
                    "p_commit": 1.0,
                }
            )
        self._update_log.append(
            {
                "timestamp": t,
                "field": "predicted_cpu_p95_next_24h",
                "old_value": old_cpu_p95,
                "new_value": new_cpu_p95,
                "p_commit": 1.0,
            }
        )
        self._update_log.append(
            {
                "timestamp": t,
                "field": "predicted_mem_p95_next_24h",
                "old_value": old_mem_p95,
                "new_value": new_mem_p95,
                "p_commit": 1.0,
            }
        )
