"""Per-VM percentile thresholds and value classification."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_thresholds(df_bootstrap: pd.DataFrame, metric: str) -> dict[str, float]:
    """Percentiles p20..p95 on bootstrap segment for ``metric``."""
    s = df_bootstrap[metric].astype(float)
    out = {
        "p20": float(np.percentile(s, 20)),
        "p40": float(np.percentile(s, 40)),
        "p60": float(np.percentile(s, 60)),
        "p80": float(np.percentile(s, 80)),
        "p95": float(np.percentile(s, 95)),
    }
    return out


def classify_value(value: float, thresholds: dict[str, float]) -> str:
    """Map scalar to discrete class using frozen percentile gates."""
    p20 = thresholds["p20"]
    p40 = thresholds["p40"]
    p60 = thresholds["p60"]
    p80 = thresholds["p80"]
    if value < p20:
        return "idle"
    if p20 <= value < p40:
        return "low"
    if p40 <= value < p60:
        return "medium"
    if p60 <= value < p80:
        return "high"
    return "burst"
