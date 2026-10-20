"""Diurnal / weekly pattern labels and burst profiling."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAG_24H = 288
LAG_7D = 288 * 7


def derive_diurnal_pattern(series: pd.Series) -> str:
    """
    Label coarse temporal structure from a (typically bootstrap) series.

    Utility only: this is not part of the active dynamic-field set after Task 5.
    Uses autocorrelation at 24h (lag 288) and 7d (lag 2016) for 5-minute sampling.
    """
    s = pd.Series(series).astype(float).dropna()
    n = len(s)
    if n < 2:
        return "irregular"

    m = float(s.mean())
    sd = float(s.std(ddof=0))
    if abs(m) > 1e-12:
        if sd / abs(m) < 0.10:
            return "flat"
    else:
        if sd < 1e-12:
            return "flat"

    ac24 = s.autocorr(lag=LAG_24H) if n > LAG_24H else np.nan
    ac2016 = s.autocorr(lag=LAG_7D) if n > LAG_7D else np.nan

    def ok(x: float) -> bool:
        return bool(np.isfinite(x))

    # Weekly wins only when long history supports lag 2016 and weekly rhythm dominates.
    if ok(ac2016) and ok(ac24) and ac2016 > 0.5 and ac2016 > ac24:
        return "weekly"
    # Diurnal: strong 24h periodicity; if weekly lag undefined or weaker than daily, prefer diurnal.
    if ok(ac24) and ac24 > 0.5:
        if not ok(ac2016) or ac24 > ac2016:
            return "diurnal"
    return "irregular"


def derive_burst_profile(series: pd.Series, p95: float) -> str:
    """Fraction of timesteps strictly above bootstrap ``p95`` threshold.

    Utility only: this is not part of the active dynamic-field set after Task 3.
    """
    s = pd.Series(series).astype(float).dropna()
    if len(s) == 0:
        return "none"
    frac = float((s > p95).sum()) / len(s)
    if frac < 0.001:
        return "none"
    if frac < 0.01:
        return "occasional"
    return "frequent"
