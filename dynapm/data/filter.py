"""Corpus filtering by minimum timesteps per VM."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dynapm.data.loader import iter_corpus

KEPT_VMS_PATH = Path(__file__).resolve().parent / "kept_vms.json"


def vm_passes_min_timesteps(df, min_timesteps: int) -> bool:
    """Return True iff the VM series has at least ``min_timesteps`` rows."""
    return len(df) >= min_timesteps


def filter_corpus(min_timesteps: int = 2000) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    """
    Keep VMs with row count >= ``min_timesteps``. Returns (kept list, stats dict).

    Persists ``kept`` to ``dynapm/data/kept_vms.json`` as
    ``[{"trace": ..., "vm_id": ...}, ...]``.
    """
    kept: List[Tuple[str, str]] = []
    dropped_list: List[Dict[str, Any]] = []
    total_seen = 0

    for trace_name, vm_id, df in iter_corpus():
        total_seen += 1
        n = len(df)
        if vm_passes_min_timesteps(df, min_timesteps):
            kept.append((trace_name, vm_id))
        else:
            dropped_list.append(
                {"trace": trace_name, "vm_id": vm_id, "row_count": n}
            )

    stats: Dict[str, Any] = {
        "total_seen": total_seen,
        "kept": len(kept),
        "dropped": len(dropped_list),
        "dropped_list": dropped_list,
    }

    payload = [{"trace": t, "vm_id": v} for t, v in kept]
    KEPT_VMS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return kept, stats
