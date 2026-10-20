"""Materna per-VM CSV loading and full-corpus iteration."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import pandas as pd

# Locked schema: Timestamp + 12 numeric fields (order as in source files)
TIMESTAMP_COL = "Timestamp"
SCHEMA_COLUMNS: tuple[str, ...] = (
    "Timestamp",
    "CPU cores",
    "CPU capacity provisioned [MHZ]",
    "CPU usage [MHZ]",
    "CPU usage [%]",
    "Memory capacity provisioned [KB]",
    "Memory usage [KB]",
    "Memory usage [%]",
    "Disk read throughput [KB/s]",
    "Disk write throughput [KB/s]",
    "Disk size [GB]",
    "Network received throughput [KB/s]",
    "Network transmitted throughput [KB/s]",
)

_INFO_SKIP = "00-Trace-Info.txt"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def default_corpus_parent() -> Path:
    """Parent directory containing ``Materna-Trace-1`` … ``Materna-Trace-3``."""
    return _repo_root() / "data" / "raw"


def load_vm_csv(path: str) -> pd.DataFrame:
    """
    Load one VM trace CSV: semicolon-separated, comma decimals, quoted header,
    day-first timestamps; numeric columns as float; sorted DatetimeIndex.
    """
    p = Path(path)
    df = pd.read_csv(
        p,
        sep=";",
        decimal=",",
        quotechar='"',
        dtype=str,
        engine="python",
    )
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    if TIMESTAMP_COL not in df.columns:
        raise ValueError(f"Missing '{TIMESTAMP_COL}' column in {path}")

    numeric_cols = [c for c in df.columns if c != TIMESTAMP_COL]
    if len(numeric_cols) != 12:
        raise ValueError(
            f"Expected 12 numeric columns plus Timestamp in {path}, got {len(numeric_cols)} numerics"
        )

    ts = pd.to_datetime(df[TIMESTAMP_COL], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    if ts.isna().any():
        bad = int(ts.isna().sum())
        raise ValueError(f"Failed to parse {bad} Timestamp value(s) in {path}")

    for col in numeric_cols:
        s = df[col].astype(str).str.strip().str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(s, errors="coerce")

    out = df.drop(columns=[TIMESTAMP_COL])
    out.index = ts
    out.index.name = TIMESTAMP_COL
    out = out.sort_index(ascending=True)
    return out


def iter_corpus(
    root: str | Path | None = None,
) -> Iterator[Tuple[str, str, pd.DataFrame]]:
    """
    Yield ``(trace_name, vm_id, df)`` for every VM CSV under the three Materna traces.

    *root* is the parent of ``Materna-Trace-1``, ``Materna-Trace-2``, ``Materna-Trace-3``
    (default: ``<repo>/data/raw``). Skips non-``*.csv`` and ``00-Trace-Info.txt``.
    """
    if root is None:
        base = default_corpus_parent()
        trace_dirs = [base / f"Materna-Trace-{i}" for i in (1, 2, 3)]
    else:
        base = Path(root)
        trace_dirs = [base / f"Materna-Trace-{i}" for i in (1, 2, 3)]

    for trace_dir in trace_dirs:
        if not trace_dir.is_dir():
            continue
        trace_name = trace_dir.name
        for csv_path in sorted(trace_dir.iterdir()):
            if not csv_path.is_file():
                continue
            if csv_path.suffix.lower() != ".csv":
                continue
            if csv_path.name == _INFO_SKIP:
                continue
            vm_id = csv_path.stem
            yield trace_name, vm_id, load_vm_csv(str(csv_path))
