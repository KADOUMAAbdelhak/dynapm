"""Tests for Materna CSV loader and corpus filter."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dynapm.data.filter import vm_passes_min_timesteps
from dynapm.data.loader import SCHEMA_COLUMNS, TIMESTAMP_COL, load_vm_csv

REPO = Path(__file__).resolve().parents[2]
TRACE1 = str(REPO / "data/raw/Materna-Trace-1/501.csv")
T1 = str(REPO / "data/raw/Materna-Trace-1/501.csv")
T2 = str(REPO / "data/raw/Materna-Trace-2/58.csv")
T3 = str(REPO / "data/raw/Materna-Trace-3/238.csv")


@pytest.mark.skipif(not Path(TRACE1).is_file(), reason="optional local Materna CSV fixture absent")
def test_load_one_csv():
    df = load_vm_csv(TRACE1)
    assert len(df) == 8064
    assert df.index.name == TIMESTAMP_COL
    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == [c for c in SCHEMA_COLUMNS if c != TIMESTAMP_COL]
    cpu = df["CPU usage [%]"]
    assert cpu.dtype == np.float64 or cpu.dtype == float
    assert not cpu.isna().all()


@pytest.mark.skipif(not all(Path(p).is_file() for p in [T1, T2, T3]), reason="optional local Materna CSV fixtures absent")
def test_load_two_csvs_different_traces():
    a = load_vm_csv(T1)
    b = load_vm_csv(T2)
    c = load_vm_csv(T3)
    assert list(a.columns) == list(b.columns) == list(c.columns)


def test_filter_drops_short():
    df = pd.DataFrame({"x": range(1000)})
    assert not vm_passes_min_timesteps(df, 2000)
    assert vm_passes_min_timesteps(df, 500)
