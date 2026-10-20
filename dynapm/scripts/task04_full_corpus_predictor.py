#!/usr/bin/env python3
"""Task 4 full-corpus predictor run with parallel per-VM processing."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

REPO = Path(__file__).resolve().parent.parent.parent

import sys

sys.path.insert(0, str(REPO))

from dynapm.core.predictor import VMPredictor
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv

CPU_T = "CPU usage [%]"
MEM_T = "Memory usage [%]"

KEPT_PATH = REPO / "dynapm/data/kept_vms.json"
RESID_DIR = REPO / "dynapm/results/residuals_full"
SUMMARY_PATH = REPO / "dynapm/data/predictor_summary.parquet"
FAIL_PATH = REPO / "dynapm/data/predictor_failures.json"
META_PATH = REPO / "dynapm/data/predictor_run_meta.json"


def _vm_path(trace: str, vm_id: str) -> Path:
    return REPO / "data/raw" / trace / f"{vm_id}.csv"


def _process_vm(item: dict) -> dict:
    trace = item["trace"]
    vm_id = item["vm_id"]
    try:
        df = load_vm_csv(str(_vm_path(trace, vm_id)))
        df_b, df_s, _ = compute_split(df)

        p_cpu = VMPredictor(target=CPU_T)
        p_cpu.fit(df_b)
        out_cpu = p_cpu.predict_streaming(df_s)

        p_mem = VMPredictor(target=MEM_T)
        p_mem.fit(df_b)
        out_mem = p_mem.predict_streaming(df_s)

        if len(out_cpu) == 0 or len(out_mem) == 0:
            raise ValueError("empty residual stream after feature construction")

        out_cpu.to_parquet(RESID_DIR / f"{trace}__{vm_id}__cpu.parquet", index=True)
        out_mem.to_parquet(RESID_DIR / f"{trace}__{vm_id}__mem.parquet", index=True)

        ytc = out_cpu["y_true"].to_numpy(dtype=float)
        ypc = out_cpu["y_pred"].to_numpy(dtype=float)
        ytm = out_mem["y_true"].to_numpy(dtype=float)
        ypm = out_mem["y_pred"].to_numpy(dtype=float)

        return {
            "ok": True,
            "trace": trace,
            "vm_id": vm_id,
            "n_streaming_steps": int(min(len(out_cpu), len(out_mem))),
            "cpu_r2": float(r2_score(ytc, ypc)),
            "cpu_rmse": float(np.sqrt(mean_squared_error(ytc, ypc))),
            "cpu_mae": float(mean_absolute_error(ytc, ypc)),
            "mem_r2": float(r2_score(ytm, ypm)),
            "mem_rmse": float(np.sqrt(mean_squared_error(ytm, ypm))),
            "mem_mae": float(mean_absolute_error(ytm, ypm)),
        }
    except Exception as e:
        return {
            "ok": False,
            "trace": trace,
            "vm_id": vm_id,
            "error": repr(e),
        }


def main() -> int:
    RESID_DIR.mkdir(parents=True, exist_ok=True)

    with open(KEPT_PATH, encoding="utf-8") as f:
        kept = json.load(f)

    t0 = time.perf_counter()
    results = Parallel(n_jobs=8, backend="loky")(
        delayed(_process_vm)(item) for item in kept
    )
    elapsed = time.perf_counter() - t0

    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]

    df = pd.DataFrame(ok)
    if not df.empty:
        df = df[[
            "trace",
            "vm_id",
            "n_streaming_steps",
            "cpu_r2",
            "cpu_rmse",
            "cpu_mae",
            "mem_r2",
            "mem_rmse",
            "mem_mae",
        ]]
    df.to_parquet(SUMMARY_PATH, index=False)

    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        json.dump(fail, f, indent=2)

    meta = {
        "n_total": len(kept),
        "n_ok": len(ok),
        "n_failed": len(fail),
        "wall_seconds": elapsed,
        "summary_path": str(SUMMARY_PATH),
        "failures_path": str(FAIL_PATH),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
