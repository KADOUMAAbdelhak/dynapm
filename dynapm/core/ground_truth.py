"""Ground-truth labels for profile evaluation at a snapshot time *t*."""
from __future__ import annotations

import pandas as pd

from dynapm.core.discretization import classify_value

CPU_METRIC = "CPU usage [%]"
MEM_METRIC = "Memory usage [%]"


def derive_ground_truth_at_t(
    df: pd.DataFrame,
    t: pd.Timestamp,
    window_hours: int = 24,
    cpu_thresholds: dict | None = None,
    mem_thresholds: dict | None = None,
) -> dict:
    """
    Forward-24h ground truth for class and p95 fields.

    Prefer ``derive_ground_truth_at_t_v2``, which uses the same forward-window
    semantics (retained name for call-site compatibility).
    """
    if cpu_thresholds is None or mem_thresholds is None:
        raise ValueError("cpu_thresholds and mem_thresholds are required")

    t0 = pd.Timestamp(t)
    t1 = t0 + pd.Timedelta(hours=window_hours)
    w = df.loc[(df.index >= t0) & (df.index < t1)]
    if len(w) == 0:
        raise ValueError(f"empty window for t={t0}, window_hours={window_hours}")

    cpu_s = w[CPU_METRIC]
    mem_s = w[MEM_METRIC]
    mean_cpu = float(cpu_s.mean())
    mean_mem = float(mem_s.mean())

    return {
        "cpu_class": classify_value(mean_cpu, cpu_thresholds),
        "memory_class": classify_value(mean_mem, mem_thresholds),
        "p95_cpu_next_24h": float(cpu_s.quantile(0.95)),
        "p95_mem_next_24h": float(mem_s.quantile(0.95)),
    }


def derive_ground_truth_at_t_v2(
    df: pd.DataFrame,
    t: pd.Timestamp,
    backward_window_hours: float = 1.0,
    forward_window_hours: int = 24,
    cpu_thresholds: dict | None = None,
    mem_thresholds: dict | None = None,
) -> dict:
    """
    Snapshot-and-verify ground truth aligned to the profile forecast horizon.

    Both class and p95 labels are derived from the same forward window
    ``[t, t+forward_window_hours)``, matching how predictor-grounded methods
    populate profile fields from the predicted next-24h window:

    - cpu_class/memory_class: classify the mean over the forward window
    - p95_cpu_next_24h/p95_mem_next_24h: empirical p95 over the forward window

    ``backward_window_hours`` is retained for call-site compatibility but is
    unused: an earlier mismatched protocol used a backward 1h mean for class
    labels while profiles predicted a forward 24h class.
    """
    if cpu_thresholds is None or mem_thresholds is None:
        raise ValueError("cpu_thresholds and mem_thresholds are required")

    del backward_window_hours  # unused; kept for API compatibility

    t0 = pd.Timestamp(t)
    f1 = t0 + pd.Timedelta(hours=int(forward_window_hours))
    wf = df.loc[(df.index >= t0) & (df.index < f1)]
    if len(wf) == 0:
        raise ValueError(f"empty forward window for t={t0}, window_hours={forward_window_hours}")

    cpu_f = wf[CPU_METRIC]
    mem_f = wf[MEM_METRIC]

    return {
        "cpu_class": classify_value(float(cpu_f.mean()), cpu_thresholds),
        "memory_class": classify_value(float(mem_f.mean()), mem_thresholds),
        "p95_cpu_next_24h": float(cpu_f.quantile(0.95)),
        "p95_mem_next_24h": float(mem_f.quantile(0.95)),
    }
