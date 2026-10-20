"""Evaluation runner v2: snapshot-then-verify protocol.

Return dict includes optional policy audit fields: ``update_log`` (list of entries from
``method.update_log``), ``n_periodic_refreshes``, ``n_drift_refreshes`` when the log records
reasons; ``decision_head_stats`` when the policy exposes a ``decision_head`` with ``stats()``.
Policies may implement ``verify_pending_commits``, invoked at evaluation timestamps along the
ground-truth grid before snapshots are finalized."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from dynapm.core.predictor import VMPredictor
from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv
from dynapm.eval.runner import _thresholds

CPU_T = "CPU usage [%]"
MEM_T = "Memory usage [%]"

REPO = Path(__file__).resolve().parent.parent.parent
RESID_FULL = REPO / "dynapm/results/residuals_full"
GT_DIR = REPO / "dynapm/results/ground_truth"


def _series_window(series: pd.Series, pos: int, lookback_steps: int) -> pd.Series:
    start = max(0, pos - lookback_steps + 1)
    return series.iloc[start : pos + 1]


def run_method_on_vm(trace, vm_id, method_factory, **kwargs) -> dict:
    lookback_steps = int(kwargs.get("lookback_steps", 288))

    path = REPO / "data/raw" / trace / f"{vm_id}.csv"
    df = load_vm_csv(str(path))
    df_boot, df_stream, info = compute_split(df)

    cpu_th, mem_th, prov = _thresholds(trace, vm_id)
    b_end = pd.Timestamp(info["bootstrap_end"])

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
        dynamic=DynamicFields(
            cpu_class="idle",
            memory_class="idle",
            predicted_cpu_p95_next_24h=float("nan"),
            predicted_mem_p95_next_24h=float("nan"),
        ),
        last_updated={
            "cpu_class": b_end,
            "memory_class": b_end,
            "predicted_cpu_p95_next_24h": b_end,
            "predicted_mem_p95_next_24h": b_end,
        },
    )

    cpu_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__cpu.parquet")
    mem_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__mem.parquet")
    cpu_resid.index = pd.to_datetime(cpu_resid.index)
    mem_resid.index = pd.to_datetime(mem_resid.index)

    gt = pd.read_parquet(GT_DIR / f"{trace}__{vm_id}.parquet")
    gt["eval_timestamp"] = pd.to_datetime(gt["eval_timestamp"])
    gt_map = gt.set_index("eval_timestamp").sort_index()

    common_idx = cpu_resid.index.intersection(mem_resid.index).sort_values()
    cpu_resid = cpu_resid.loc[common_idx]
    mem_resid = mem_resid.loc[common_idx]

    cpu_obs_s = cpu_resid["y_true"]
    mem_obs_s = mem_resid["y_true"]
    cpu_pred_s = cpu_resid["y_pred"]
    mem_pred_s = mem_resid["y_pred"]

    factory_name = getattr(method_factory, "__name__", "")
    obs_only = factory_name in {
        "_fact_static_v2",
        "_fact_periodic_6h",
        "_fact_reactive",
        "_fact_full_rewrite",
    }
    if obs_only:
        cpu_predictor = mem_predictor = None
    else:
        cpu_predictor = VMPredictor(target=CPU_T)
        cpu_predictor.fit(df_boot)
        mem_predictor = VMPredictor(target=MEM_T)
        mem_predictor.fit(df_boot)

    method = method_factory(
        profile,
        cpu_th,
        mem_th,
        bootstrap_cpu_series=df_boot[CPU_T],
        bootstrap_mem_series=df_boot[MEM_T],
        cpu_pred_full=cpu_pred_s,
        mem_pred_full=mem_pred_s,
        cpu_predictor=cpu_predictor,
        mem_predictor=mem_predictor,
        cpu_obs_full=df[CPU_T],
        mem_obs_full=df[MEM_T],
    )

    eval_set = set(gt_map.index)
    snapshot_queue = []
    records = []
    verifier = getattr(method, "verify_pending_commits", None)

    for pos, t in enumerate(common_idx):
        cpu_obs_window = _series_window(cpu_obs_s, pos, lookback_steps)
        mem_obs_window = _series_window(mem_obs_s, pos, lookback_steps)
        cpu_pred_window = _series_window(cpu_pred_s, pos, lookback_steps)
        mem_pred_window = _series_window(mem_pred_s, pos, lookback_steps)

        method.step(
            t=t,
            cpu_obs_window=cpu_obs_window,
            mem_obs_window=mem_obs_window,
            cpu_pred_window=cpu_pred_window,
            mem_pred_window=mem_pred_window,
        )

        if verifier is not None and t in eval_set:
            gx = gt_map.loc[t]
            if isinstance(gx, pd.DataFrame):
                gx = gx.iloc[0]
            verifier(
                t,
                {"cpu_class": gx["cpu_class"], "memory_class": gx["memory_class"]},
            )

        if t in eval_set:
            snapshot_queue.append(
                {
                    "eval_timestamp": pd.Timestamp(t),
                    "snapshot": deepcopy(profile.dynamic),
                }
            )

        now_t = pd.Timestamp(t)
        keep = []
        for row in snapshot_queue:
            verify_t = pd.Timestamp(row["eval_timestamp"]) + pd.Timedelta(hours=24)
            if now_t < verify_t:
                keep.append(row)
                continue
            ts = pd.Timestamp(row["eval_timestamp"])
            if ts not in gt_map.index:
                continue
            g = gt_map.loc[ts]
            if isinstance(g, pd.DataFrame):
                g = g.iloc[0]
            snap = row["snapshot"]
            records.append(
                {
                    "eval_timestamp": ts,
                    "cpu_class_correct": int(snap.cpu_class == g["cpu_class"]),
                    "memory_class_correct": int(snap.memory_class == g["memory_class"]),
                    "cpu_p95_abs_err": float(abs(float(snap.predicted_cpu_p95_next_24h) - float(g["p95_cpu_next_24h"]))),
                    "mem_p95_abs_err": float(abs(float(snap.predicted_mem_p95_next_24h) - float(g["p95_mem_next_24h"]))),
                }
            )
        snapshot_queue = keep

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

    n_periodic = 0
    n_drift = 0
    if len(log_df) > 0 and "reason" in log_df.columns:
        rr = log_df[["timestamp", "reason"]].drop_duplicates()
        n_periodic = int((rr["reason"] == "periodic").sum())
        n_drift = int((rr["reason"] == "drift").sum())

    out = {
        "trace": trace,
        "vm_id": str(vm_id),
        **agg,
        "n_cpu_class_updates": n_field("cpu_class"),
        "n_memory_class_updates": n_field("memory_class"),
        "n_cpu_p95_updates": n_field("predicted_cpu_p95_next_24h"),
        "n_mem_p95_updates": n_field("predicted_mem_p95_next_24h"),
        "total_updates": int(len(log_df)),
        "n_eval_points_verified": int(len(rec_df)),
        "snapshots_dropped_unverified": int(len(snapshot_queue)),
        "n_streaming_steps": int(len(common_idx)),
        "stream_days": stream_days,
        "update_log": list(method.update_log),
        "n_periodic_refreshes": n_periodic,
        "n_drift_refreshes": n_drift,
    }
    dh = getattr(method, "decision_head", None)
    if dh is not None and hasattr(dh, "stats"):
        out["decision_head_stats"] = dh.stats()
    return out
