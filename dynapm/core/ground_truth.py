"""Forward labels on exactly the same nominal target grid as recursive forecasts."""
from __future__ import annotations

import pandas as pd

from dynapm.core.discretization import classify_value
from dynapm.core.temporal import MIN_OBSERVATIONS, forward_observations

CPU_METRIC = "CPU usage [%]"
MEM_METRIC = "Memory usage [%]"


def derive_ground_truth_at_t(
    df: pd.DataFrame, t: pd.Timestamp, window_hours: int = 24,
    cpu_thresholds: dict | None = None, mem_thresholds: dict | None = None,
    min_observations_in_window: int = MIN_OBSERVATIONS,
) -> dict:
    """Class and p95 over available targets in (t, t+window_hours].

    The full wall-clock horizon must have elapsed and at least 200 target slots
    must be observed by default. Sparse eligible windows use their observed
    subset; unknown utilization is never imputed. Thresholds are bootstrap-only.
    """
    if cpu_thresholds is None or mem_thresholds is None:
        raise ValueError("cpu_thresholds and mem_thresholds are required")
    if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_unique:
        raise ValueError("ground truth requires unique datetime timestamps")
    if df.empty or df.index.max() < pd.Timestamp(t) + pd.Timedelta(hours=window_hours):
        raise ValueError("ground-truth horizon has not elapsed")
    w = forward_observations(df, t, window_hours)
    if len(w) < max(1, min_observations_in_window):
        raise ValueError("insufficient observed targets in the forward horizon")
    return {
        "cpu_class": classify_value(float(w[CPU_METRIC].mean()), cpu_thresholds),
        "memory_class": classify_value(float(w[MEM_METRIC].mean()), mem_thresholds),
        "p95_cpu_next_24h": float(w[CPU_METRIC].quantile(0.95)),
        "p95_mem_next_24h": float(w[MEM_METRIC].quantile(0.95)),
    }


def derive_ground_truth_at_t_v2(
    df: pd.DataFrame, t: pd.Timestamp, backward_window_hours: float = 1.0,
    forward_window_hours: int = 24, cpu_thresholds: dict | None = None,
    mem_thresholds: dict | None = None,
    min_observations_in_window: int = MIN_OBSERVATIONS,
) -> dict:
    """Compatibility signature; both names use one canonical forward window."""
    del backward_window_hours
    return derive_ground_truth_at_t(df, t, forward_window_hours,
        cpu_thresholds, mem_thresholds, min_observations_in_window)
