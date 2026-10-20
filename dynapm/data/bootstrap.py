"""Bootstrap vs streaming split on VM time series."""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

import pandas as pd

LOCKED_BOOTSTRAP_FRACTION = 0.30


def compute_split(
    df: pd.DataFrame,
    bootstrap_fraction: float = LOCKED_BOOTSTRAP_FRACTION,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Split ``df`` into bootstrap (first ``floor(n * bootstrap_fraction)`` rows)
    and streaming (remainder). Index must be sortable time order (ascending).
    """
    if bootstrap_fraction != LOCKED_BOOTSTRAP_FRACTION:
        raise ValueError(
            f"bootstrap_fraction must be {LOCKED_BOOTSTRAP_FRACTION} unless explicitly reviewed; got {bootstrap_fraction}"
        )
    n_total = len(df)
    n_boot = int(math.floor(n_total * bootstrap_fraction))
    df_bootstrap = df.iloc[:n_boot].copy()
    df_streaming = df.iloc[n_boot:].copy()

    if n_boot == 0:
        raise ValueError("bootstrap segment empty")
    if len(df_streaming) == 0:
        raise ValueError("streaming segment empty")

    bs_idx = df_bootstrap.index
    st_idx = df_streaming.index
    bootstrap_start = pd.Timestamp(bs_idx.min())
    streaming_end = pd.Timestamp(st_idx.max())
    # Boundary timestamp: first row of streaming (same instant as end of bootstrap window label).
    cut = pd.Timestamp(df.index[n_boot])
    bootstrap_end = cut
    streaming_start = cut

    bd_days = (pd.Timestamp(bs_idx.max()) - bootstrap_start).total_seconds() / 86400.0
    sd_days = (streaming_end - streaming_start).total_seconds() / 86400.0

    info: Dict[str, Any] = {
        "n_total": n_total,
        "n_bootstrap": n_boot,
        "n_streaming": len(df_streaming),
        "bootstrap_start": bootstrap_start,
        "bootstrap_end": bootstrap_end,
        "streaming_start": streaming_start,
        "streaming_end": streaming_end,
        "bootstrap_duration_days": bd_days,
        "streaming_duration_days": sd_days,
    }
    return df_bootstrap, df_streaming, info
