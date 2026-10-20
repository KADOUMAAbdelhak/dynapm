"""Shared evaluation utilities (aggregation, churn, effect sizes)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def count_unique_refresh_timestamps(update_log: list[Any]) -> int:
    """
    Count distinct refresh events from an update_log.
    A refresh event = unique timestamp in the log, regardless
    of how many fields were logged at that timestamp.
    """
    if not update_log:
        return 0
    timestamps: set[str] = set()
    for entry in update_log:
        if not isinstance(entry, dict) or "timestamp" not in entry:
            continue
        timestamps.add(str(pd.Timestamp(entry["timestamp"])))
    return len(timestamps)


def cohen_d_paired(x_method: np.ndarray, y_method: np.ndarray) -> float:
    """Effect size for paired samples: Cohen's d on (x − y)."""
    x_method = np.asarray(x_method, dtype=np.float64)
    y_method = np.asarray(y_method, dtype=np.float64)
    if x_method.shape != y_method.shape:
        raise ValueError("x_method and y_method must have identical shape")
    d = x_method - y_method
    finite = np.isfinite(d)
    dn = d[finite]
    if dn.size < 2:
        return float("nan")
    m = float(np.mean(dn))
    s = float(np.std(dn, ddof=1))
    if not np.isfinite(m) or not np.isfinite(s) or s <= 0:
        return float("nan")
    return m / s
