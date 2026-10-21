#!/usr/bin/env python3
"""Aggregate corpus-wide ground-truth distributions for Task 4 report."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
OUT_JSON = REPO / "dynapm/data/ground_truth_stats.json"
GT_DIR = REPO / "dynapm/results/ground_truth"


from dynapm.core.run_store import refuse_unmanaged_workflow

def _q(s: pd.Series) -> dict[str, float]:
    return {
        "min": float(s.min()),
        "p25": float(s.quantile(0.25)),
        "median": float(s.quantile(0.5)),
        "p75": float(s.quantile(0.75)),
        "max": float(s.max()),
    }


def main() -> int:
    refuse_unmanaged_workflow()  # Explicitly retired unversioned corpus/result layout.
    rows = []
    per_vm = []
    for p in sorted(GT_DIR.glob("*.parquet")):
        df = pd.read_parquet(p)
        stem = p.stem
        trace, vm_id = stem.split("__", 1)
        df["trace"] = trace
        df["vm_id"] = vm_id
        rows.append(df)
        per_vm.append(
            {
                "trace": trace,
                "vm_id": vm_id,
                "cpu_distinct": int(df["cpu_class"].nunique()),
                "mem_distinct": int(df["memory_class"].nunique()),
            }
        )

    all_df = pd.concat(rows, ignore_index=True)
    vm_df = pd.DataFrame(per_vm)

    stats = {
        "n_points": int(len(all_df)),
        "cpu_class_proportions": all_df["cpu_class"].value_counts(normalize=True).to_dict(),
        "memory_class_proportions": all_df["memory_class"].value_counts(normalize=True).to_dict(),
        "p95_cpu_next_24h_mean": float(all_df["p95_cpu_next_24h"].mean()),
        "p95_cpu_next_24h_std": float(all_df["p95_cpu_next_24h"].std(ddof=0)),
        "p95_mem_next_24h_mean": float(all_df["p95_mem_next_24h"].mean()),
        "p95_mem_next_24h_std": float(all_df["p95_mem_next_24h"].std(ddof=0)),
        "cpu_distinct_count_dist": _q(vm_df["cpu_distinct"]),
        "mem_distinct_count_dist": _q(vm_df["mem_distinct"]),
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(json.dumps({"stats_json": str(OUT_JSON), "n_points": len(all_df)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
