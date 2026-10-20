"""Evaluation runner for update methods on a single VM."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from dynapm.core.discretization import classify_value
from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv

REPO = Path(__file__).resolve().parent.parent.parent
BOOT_SUM = REPO / "dynapm/data/bootstrap_summary.parquet"
RESID_FULL = REPO / "dynapm/results/residuals_full"
GT_DIR = REPO / "dynapm/results/ground_truth"


def _norm(v):
    s = str(v)
    return str(int(s)) if s.isdigit() else s


def _thresholds(trace: str, vm_id: str):
    df = pd.read_parquet(BOOT_SUM)
    m = df[(df["trace_name"] == trace) & (df["vm_id"].astype(str).map(_norm) == _norm(vm_id))]
    if m.empty:
        raise ValueError(f"threshold row not found for {trace}/{vm_id}")
    r = m.iloc[0]
    cpu = {k: float(r[f"cpu_{k}"]) for k in ("p20", "p40", "p60", "p80", "p95")}
    mem = {k: float(r[f"mem_{k}"]) for k in ("p20", "p40", "p60", "p80", "p95")}
    prov = {
        "provisioned_cpu_cores": int(r["provisioned_cpu_cores"]),
        "provisioned_ram_gb": float(r["provisioned_ram_gb"]),
    }
    return cpu, mem, prov


def _p95_pred_window(pred_series: pd.Series, t: pd.Timestamp, steps: int = 288) -> float:
    pos = pred_series.index.searchsorted(pd.Timestamp(t))
    w = pred_series.iloc[pos : pos + steps]
    if len(w) == 0:
        return float("nan")
    return float(w.quantile(0.95))


def run_method_on_vm(trace, vm_id, method_factory, **kwargs) -> dict:
    path = REPO / "data/raw" / trace / f"{vm_id}.csv"
    df = load_vm_csv(str(path))
    df_boot, df_stream, info = compute_split(df)

    cpu_th, mem_th, prov = _thresholds(trace, vm_id)

    # initialize profile dynamic fields from bootstrap-end snapshot using thresholds and future-like p95 on bootstrap tail
    b_end = pd.Timestamp(info["bootstrap_end"])
    b_tail = df_boot.tail(288)
    init_dynamic = DynamicFields(
        cpu_class=classify_value(float(df_boot["CPU usage [%]"].iloc[-1]), cpu_th),
        memory_class=classify_value(float(df_boot["Memory usage [%]"].iloc[-1]), mem_th),
        predicted_cpu_p95_next_24h=float(b_tail["CPU usage [%]"].quantile(0.95)) if len(b_tail) else 0.0,
        predicted_mem_p95_next_24h=float(b_tail["Memory usage [%]"].quantile(0.95)) if len(b_tail) else 0.0,
    )
    profile = ProfileInstance(
        static=StaticFields(
            vm_id=str(vm_id),
            trace_name=trace,
            provisioned_cpu_cores=prov["provisioned_cpu_cores"],
            provisioned_ram_gb=prov["provisioned_ram_gb"],
            bootstrap_start=pd.Timestamp(info["bootstrap_start"]),
            bootstrap_end=b_end,
            n_total_timesteps=int(info["n_total"]),
        ),
        dynamic=init_dynamic,
        last_updated={
            "cpu_class": b_end,
            "memory_class": b_end,
            "predicted_cpu_p95_next_24h": b_end,
            "predicted_mem_p95_next_24h": b_end,
        },
    )

    method = method_factory(profile, cpu_th, mem_th)

    cpu_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__cpu.parquet")
    mem_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__mem.parquet")
    cpu_resid.index = pd.to_datetime(cpu_resid.index)
    mem_resid.index = pd.to_datetime(mem_resid.index)

    gt = pd.read_parquet(GT_DIR / f"{trace}__{vm_id}.parquet")
    gt["eval_timestamp"] = pd.to_datetime(gt["eval_timestamp"])
    gt_map = gt.set_index("eval_timestamp")

    common_idx = cpu_resid.index.intersection(mem_resid.index)
    cpu_resid = cpu_resid.loc[common_idx]
    mem_resid = mem_resid.loc[common_idx]

    # prepare for fast predicted p95 approximations at eval points
    cpu_pred = cpu_resid["y_pred"]
    mem_pred = mem_resid["y_pred"]

    eval_points = list(gt_map.index)
    eval_set = set(eval_points)

    records = []
    skipped_eval_points = 0

    for t in common_idx:
        method.step(
            t=t,
            cpu_residual=float(cpu_resid.at[t, "residual"]),
            mem_residual=float(mem_resid.at[t, "residual"]),
            cpu_obs=float(cpu_resid.at[t, "y_true"]),
            mem_obs=float(mem_resid.at[t, "y_true"]),
            cpu_pred=float(cpu_resid.at[t, "y_pred"]),
            mem_pred=float(mem_resid.at[t, "y_pred"]),
        )

        if t in eval_set:
            p95_cpu = _p95_pred_window(cpu_pred, t, steps=288)
            p95_mem = _p95_pred_window(mem_pred, t, steps=288)
            method.step_continuous(t, p95_cpu, p95_mem)

            if t not in gt_map.index:
                skipped_eval_points += 1
                continue

            g = gt_map.loc[t]
            if hasattr(method, "verify_pending_commits"):
                method.verify_pending_commits(
                    pd.Timestamp(t),
                    {
                        "cpu_class": g["cpu_class"],
                        "memory_class": g["memory_class"],
                    },
                )
            records.append(
                {
                    "eval_timestamp": pd.Timestamp(t),
                    "cpu_class_correct": int(profile.dynamic.cpu_class == g["cpu_class"]),
                    "memory_class_correct": int(profile.dynamic.memory_class == g["memory_class"]),
                    "cpu_p95_abs_err": float(abs(profile.dynamic.predicted_cpu_p95_next_24h - float(g["p95_cpu_next_24h"]))),
                    "mem_p95_abs_err": float(abs(profile.dynamic.predicted_mem_p95_next_24h - float(g["p95_mem_next_24h"]))),
                }
            )

    rec_df = pd.DataFrame(records)
    if len(rec_df) == 0:
        agg = {
            "cpu_class_accuracy": float("nan"),
            "memory_class_accuracy": float("nan"),
            "cpu_p95_mae": float("nan"),
            "mem_p95_mae": float("nan"),
        }
    else:
        agg = {
            "cpu_class_accuracy": float(rec_df["cpu_class_correct"].mean()),
            "memory_class_accuracy": float(rec_df["memory_class_correct"].mean()),
            "cpu_p95_mae": float(rec_df["cpu_p95_abs_err"].mean()),
            "mem_p95_mae": float(rec_df["mem_p95_abs_err"].mean()),
        }

    log_df = pd.DataFrame(method.update_log)
    def n_field(field: str) -> int:
        if len(log_df) == 0:
            return 0
        return int((log_df["field"] == field).sum())

    stream_days = float((pd.Timestamp(df_stream.index[-1]) - pd.Timestamp(df_stream.index[0])).total_seconds() / 86400.0)

    return {
        "trace": trace,
        "vm_id": str(vm_id),
        "per_eval_records": records,
        **agg,
        "n_cpu_class_updates": n_field("cpu_class"),
        "n_memory_class_updates": n_field("memory_class"),
        "n_cpu_p95_updates": n_field("predicted_cpu_p95_next_24h"),
        "n_mem_p95_updates": n_field("predicted_mem_p95_next_24h"),
        "total_updates": int(len(log_df)),
        "n_eval_points": int(len(rec_df)),
        "skipped_eval_points": int(skipped_eval_points),
        "eval_density": float(len(rec_df) / stream_days) if stream_days > 0 else float("nan"),
    }
