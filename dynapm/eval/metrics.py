"""Shared evaluation utilities (aggregation, churn, effect sizes)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from dynapm.core.accounting import ACCOUNTING_METRICS, require_accounting_metrics


def summarize_accounting(frame: pd.DataFrame) -> pd.DataFrame:
    """VM-level means/medians of canonical counters, never reconstructed logs."""
    require_accounting_metrics(frame)
    ok = frame[frame.run_status == "ok"] if "run_status" in frame else frame
    result = ok.groupby("method")[list(ACCOUNTING_METRICS)].agg(["mean", "median"])
    result.columns = [f"{stat}_{metric}" for metric, stat in result.columns]
    return result.reset_index()


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
