from __future__ import annotations

import numpy as np
import pandas as pd

from dynapm.core.evaluation_clock import (
    compute_data_aware_evaluation_timestamps,
    compute_evaluation_timestamps,
)


def test_compute_evaluation_timestamps_12h():
    idx = pd.date_range("2020-01-01 00:00:00", periods=10 * 24 * 12, freq="5min")
    out = compute_evaluation_timestamps(idx, period_hours=12)
    assert len(out) > 0
    assert out[0] == idx[0]
    assert (out[1] - out[0]).total_seconds() == 12 * 3600
    assert out[-1] <= idx[-1] - pd.Timedelta(hours=24)
    assert out.is_monotonic_increasing


def test_data_aware_clock_no_gaps():
    idx = pd.date_range("2021-01-01", periods=20 * 24 * 12, freq="5min")
    df = pd.DataFrame({"x": np.arange(len(idx))}, index=idx)
    out, info = compute_data_aware_evaluation_timestamps(df, idx, period_hours=12, window_hours=24, min_observations_in_window=200)
    assert len(out) > 0
    assert info["n_dropped"] == 0
    assert info["n_kept"] == info["n_candidates"]


def test_data_aware_clock_with_gap():
    idx = pd.date_range("2021-01-01", periods=20 * 24 * 12, freq="5min")
    gap_start = pd.Timestamp("2021-01-07 00:00:00")
    gap_end = gap_start + pd.Timedelta(hours=36)
    mask = ~((idx >= gap_start) & (idx < gap_end))
    idx2 = idx[mask]
    df = pd.DataFrame({"x": np.arange(len(idx2))}, index=idx2)
    out, info = compute_data_aware_evaluation_timestamps(df, idx2, period_hours=12, window_hours=24, min_observations_in_window=200)
    assert info["n_dropped"] > 0
    dropped = set(compute_evaluation_timestamps(idx2, 12)) - set(out)
    assert len(dropped) > 0
