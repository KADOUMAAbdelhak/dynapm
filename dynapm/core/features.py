"""Feature engineering for per-target VM predictors."""
from __future__ import annotations

import numpy as np
import pandas as pd

VALID_TARGETS = ("CPU usage [%]", "Memory usage [%]")
LAGS = (1, 2, 3, 6, 12, 24, 48)
ROLL_WINDOWS = (6, 12, 24, 48, 96)
MAX_CONTEXT = 96


def build_features(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    Build strictly causal target-aware lag/rolling/diff + cyclical features.

    At timestamp ``t``, rolling statistics and differences are computed from
    ``s.shift(1)`` (values at or before ``t-1``), so features never use the
    contemporaneous target ``u_t``. Calendar encodings use the timestamp only.

    Rows with incomplete context are dropped; output starts after the longest
    context window.
    """
    if target not in VALID_TARGETS:
        raise ValueError(f"Unsupported target {target!r}; expected one of {VALID_TARGETS}")

    s = df[target].astype(float)
    # Past-only series: value known at t is u_{t-1}.
    s_past = s.shift(1)
    out = pd.DataFrame(index=df.index)

    for lag in LAGS:
        out[f"target_lag_{lag}"] = s.shift(lag)

    for w in ROLL_WINDOWS:
        roll = s_past.rolling(window=w, min_periods=w)
        r_mean = roll.mean()
        r_std = roll.std(ddof=0)
        r_min = roll.min()
        r_max = roll.max()
        out[f"target_roll_mean_{w}"] = r_mean
        out[f"target_roll_std_{w}"] = r_std
        out[f"target_roll_min_{w}"] = r_min
        out[f"target_roll_max_{w}"] = r_max
        out[f"target_roll_range_{w}"] = r_max - r_min

    out["target_diff_1"] = s_past.diff(1)
    out["target_diff_12"] = s_past.diff(12)

    hour = df.index.hour.astype(float)
    dow = df.index.dayofweek.astype(float)
    out["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * dow / 7.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * dow / 7.0)

    out = out.iloc[MAX_CONTEXT:]
    out = out.dropna(axis=0, how="any")
    return out
