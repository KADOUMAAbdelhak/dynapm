#!/usr/bin/env python3
"""Task 4 ground-truth derivation time series for all kept VMs."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

REPO = Path(__file__).resolve().parent.parent.parent
import sys

sys.path.insert(0, str(REPO))

from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.core.ground_truth import derive_ground_truth_at_t_v2
from dynapm.core.temporal import TEMPORAL_PROTOCOL
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv

KEPT_PATH = REPO / "dynapm/data/kept_vms.json"
BOOT_SUM_PATH = REPO / "dynapm/data/bootstrap_summary.parquet"
OUT_DIR = REPO / "dynapm/results/ground_truth"
META_PATH = REPO / "dynapm/data/ground_truth_run_meta.json"
FAIL_PATH = REPO / "dynapm/data/ground_truth_failures.json"


from dynapm.core.run_store import refuse_unmanaged_workflow

def _norm_vm_id(v: str) -> str:
    t = str(v)
    if t.isdigit():
        return str(int(t))
    return t


def _threshold_map() -> dict[tuple[str, str], dict]:
    refuse_unmanaged_workflow()  # No unversioned bootstrap thresholds.
    bs = pd.read_parquet(BOOT_SUM_PATH)
    out = {}
    for _, r in bs.iterrows():
        out[(r["trace_name"], _norm_vm_id(r["vm_id"]))] = {
            "cpu": {k: float(r[f"cpu_{k}"]) for k in ("p20", "p40", "p60", "p80", "p95")},
            "mem": {k: float(r[f"mem_{k}"]) for k in ("p20", "p40", "p60", "p80", "p95")},
        }
    return out


def _process(item: dict, tmap: dict) -> dict:
    trace = item["trace"]
    vm_id = item["vm_id"]
    try:
        p = REPO / "data/raw" / trace / f"{vm_id}.csv"
        df = load_vm_csv(str(p))
        _, df_s, _ = compute_split(df)
        eval_ts, clock_info = compute_data_aware_evaluation_timestamps(
            df=df,
            streaming_index=df_s.index,
            period_hours=12,
            window_hours=24,
            min_observations_in_window=200,
        )

        th = tmap[(trace, _norm_vm_id(vm_id))]
        rows = []
        skipped_empty = 0
        for t in eval_ts:
            try:
                gt = derive_ground_truth_at_t_v2(
                    df,
                    t,
                    backward_window_hours=1.0,
                    forward_window_hours=24,
                    cpu_thresholds=th["cpu"],
                    mem_thresholds=th["mem"],
                )
                rows.append({"eval_timestamp": pd.Timestamp(t), "causal_protocol": TEMPORAL_PROTOCOL, **gt})
            except ValueError:
                skipped_empty += 1

        gtdf = pd.DataFrame(rows)
        out_path = OUT_DIR / f"{trace}__{vm_id}.parquet"
        gtdf.to_parquet(out_path, index=False)
        return {
            "ok": True,
            "trace": trace,
            "vm_id": vm_id,
            "n_eval": len(gtdf),
            "n_skipped_empty": skipped_empty,
            "n_candidates": int(clock_info["n_candidates"]),
            "n_kept_clock": int(clock_info["n_kept"]),
            "n_dropped_clock": int(clock_info["n_dropped"]),
        }
    except Exception as e:
        return {"ok": False, "trace": trace, "vm_id": vm_id, "error": repr(e)}


def main() -> int:
    refuse_unmanaged_workflow()  # Explicitly retired unversioned corpus/result layout.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(KEPT_PATH, encoding="utf-8") as f:
        kept = json.load(f)
    tmap = _threshold_map()

    t0 = time.perf_counter()
    res = Parallel(n_jobs=8, backend="loky")(delayed(_process)(item, tmap) for item in kept)
    elapsed = time.perf_counter() - t0

    ok = [x for x in res if x["ok"]]
    fail = [x for x in res if not x["ok"]]

    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        json.dump(fail, f, indent=2)

    meta = {
        "causal_protocol": TEMPORAL_PROTOCOL,
        "n_total": len(kept),
        "n_ok": len(ok),
        "n_failed": len(fail),
        "wall_seconds": elapsed,
        "mean_eval_points": float(pd.Series([x["n_eval"] for x in ok], dtype=float).mean()) if ok else 0.0,
        "total_skipped_empty_windows": int(sum(x.get("n_skipped_empty", 0) for x in ok)),
        "n_candidates_total": int(sum(x.get("n_candidates", 0) for x in ok)),
        "n_kept_total": int(sum(x.get("n_kept_clock", 0) for x in ok)),
        "n_dropped_total": int(sum(x.get("n_dropped_clock", 0) for x in ok)),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
