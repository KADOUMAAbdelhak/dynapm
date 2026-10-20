"""Forecasting helpers for window-based profile fields."""
from __future__ import annotations

import numpy as np

from dynapm.core.discretization import classify_value


def forecast_class_from_window(values, thresholds: dict) -> str:
    """
    Given a 1-D array-like of observations and per-VM bootstrap thresholds,
    return the class of the MEAN of the observations.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return "idle"
    return classify_value(float(arr.mean()), thresholds)


def forecast_p95_from_window(values) -> float:
    """Empirical p95 over the window. Returns NaN if window empty."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.quantile(arr, 0.95))
