"""Evaluation timestamp clocks for streaming-segment checkpoints."""
from __future__ import annotations

import pandas as pd


def _compute_candidate_timestamps(
    streaming_index: pd.DatetimeIndex,
    period_hours: int = 12,
    window_hours: int = 24,
) -> pd.DatetimeIndex:
    if len(streaming_index) == 0:
        return pd.DatetimeIndex([], dtype="datetime64[ns]")

    idx = pd.DatetimeIndex(streaming_index).sort_values()
    start = pd.Timestamp(idx[0])
    last_allowed = pd.Timestamp(idx[-1]) - pd.Timedelta(hours=window_hours)
    if last_allowed < start:
        return pd.DatetimeIndex([], dtype="datetime64[ns]")

    ts = pd.date_range(start=start, end=last_allowed, freq=f"{period_hours}h")
    return pd.DatetimeIndex(ts).sort_values()


def compute_evaluation_timestamps(
    streaming_index: pd.DatetimeIndex,
    period_hours: int = 12,
) -> pd.DatetimeIndex:
    """Legacy fixed-clock evaluation timestamps (candidate clock only)."""
    return _compute_candidate_timestamps(streaming_index, period_hours=period_hours, window_hours=24)


def compute_data_aware_evaluation_timestamps(
    df: pd.DataFrame,
    streaming_index: pd.DatetimeIndex,
    period_hours: int = 12,
    window_hours: int = 24,
    min_observations_in_window: int = 200,
) -> tuple[pd.DatetimeIndex, dict]:
    """
    Data-aware clock: keeps only candidate eval times with enough observed rows in [t, t+window_hours).
    """
    cand = _compute_candidate_timestamps(
        streaming_index,
        period_hours=period_hours,
        window_hours=window_hours,
    )
    keep = []
    for t in cand:
        t0 = pd.Timestamp(t)
        t1 = t0 + pd.Timedelta(hours=window_hours)
        n = int(((df.index >= t0) & (df.index < t1)).sum())
        if n >= min_observations_in_window:
            keep.append(t0)

    out = pd.DatetimeIndex(keep).sort_values()
    info = {
        "n_candidates": int(len(cand)),
        "n_kept": int(len(out)),
        "n_dropped": int(len(cand) - len(out)),
        "dropped_fraction": float((len(cand) - len(out)) / len(cand)) if len(cand) else 0.0,
    }
    return out, info
