"""Provisioned CPU/RAM extraction from VM frames."""
from __future__ import annotations

import sys
from collections import Counter
from typing import Any

import pandas as pd

_CPU_COL = "CPU cores"
_RAM_KB_COL = "Memory capacity provisioned [KB]"


def extract_provisioning(df: pd.DataFrame) -> dict[str, Any]:
    """
    Return modal provisioned cores and RAM (GB) across rows (defensive against noise).
    Warns on stderr if modal mass < 99%.
    """
    if _CPU_COL not in df.columns or _RAM_KB_COL not in df.columns:
        raise ValueError(f"Expected columns {_CPU_COL!r} and {_RAM_KB_COL!r}")

    cores_s = df[_CPU_COL].dropna()
    ram_s = df[_RAM_KB_COL].dropna()

    def mode_val(series: pd.Series) -> float:
        vals = series.tolist()
        if not vals:
            raise ValueError("empty series for mode")
        cnt = Counter(vals)
        max_c = max(cnt.values())
        candidates = sorted([k for k, v in cnt.items() if v == max_c])
        return float(candidates[0])

    mode_cores = mode_val(cores_s)
    mode_ram_kb = mode_val(ram_s)

    n = len(df)
    frac_cores = float((cores_s == mode_cores).sum()) / max(len(cores_s), 1)
    frac_ram = float((ram_s == mode_ram_kb).sum()) / max(len(ram_s), 1)

    if frac_cores < 0.99 or frac_ram < 0.99:
        print(
            f"[dynapm.provisioning] warning: mode coverage <99% "
            f"(cpu_frac={frac_cores:.4f}, ram_frac={frac_ram:.4f}, n_rows={n})",
            file=sys.stderr,
        )

    return {
        "provisioned_cpu_cores": int(round(mode_cores)),
        "provisioned_ram_gb": float(mode_ram_kb) / (1024.0 * 1024.0),
    }
