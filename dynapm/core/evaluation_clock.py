"""Evaluation timestamp clocks for streaming-segment checkpoints."""
from __future__ import annotations

import pandas as pd

from dynapm.core.temporal import MIN_OBSERVATIONS, forward_observations


def _compute_candidate_timestamps(
    streaming_index: pd.DatetimeIndex,
    period_hours: int = 1,
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
    period_hours: int = 1,
) -> pd.DatetimeIndex:
    """Legacy fixed-clock evaluation timestamps (candidate clock only)."""
    return _compute_candidate_timestamps(streaming_index, period_hours=period_hours, window_hours=24)


def compute_data_aware_evaluation_timestamps(
    df: pd.DataFrame,
    streaming_index: pd.DatetimeIndex,
    period_hours: int = 1,
    window_hours: int = 24,
    min_observations_in_window: int = MIN_OBSERVATIONS,
) -> tuple[pd.DatetimeIndex, dict]:
    """
    Nominal read grid with enough (t, t+window] targets, even without an observed origin.

    Missing observations do not remove or defer read events; periodic refreshes
    have a separate delivery rule. The candidate grid stays anchored at the
    first streaming timestamp. The complete wall-clock horizon must fit.

    """
    cand = _compute_candidate_timestamps(
        streaming_index,
        period_hours=period_hours,
        window_hours=window_hours,
    )
    keep = []
    for t in cand:
        t0 = pd.Timestamp(t)
        n = len(forward_observations(df, t0, window_hours))
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
