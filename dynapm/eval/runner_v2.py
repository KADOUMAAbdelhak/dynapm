"""Evaluation runner v2: snapshot-then-verify protocol.

Return dict includes optional policy audit fields: ``update_log`` (list of entries from
``method.update_log``), logical ``refresh_log`` events, and periodic/drift counts;
``decision_head_stats`` when the policy exposes a ``decision_head`` with ``stats()``.
Forward ground truth is exposed only after the verification horizon; it is
never passed back to a refresh policy."""
from __future__ import annotations

import pandas as pd

from dynapm.eval.replay import CAUSAL_PROTOCOL, prepare_vm_replay, iter_verified_snapshots


def run_method_on_vm(
    trace, vm_id, method_factory, *, lookback_steps=288, repo_root=None,
    predictor_factory=None,
) -> dict:
    options = {} if predictor_factory is None else {"predictor_factory": predictor_factory}
    replay = prepare_vm_replay(trace, vm_id, method_factory, repo_root=repo_root, **options)
    method = replay.method
    records = []
    for ts, snap, g in iter_verified_snapshots(replay, lookback_steps):
        records.append({
            "eval_timestamp": ts,
            "cpu_class_correct": int(snap.cpu_class == g["cpu_class"]),
            "memory_class_correct": int(snap.memory_class == g["memory_class"]),
            "cpu_p95_abs_err": abs(snap.predicted_cpu_p95_next_24h - g["p95_cpu_next_24h"]),
            "mem_p95_abs_err": abs(snap.predicted_mem_p95_next_24h - g["p95_mem_next_24h"]),
        })

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

    n_periodic = sum(r["reason"] == "periodic" for r in method.refresh_log)
    n_drift = sum(r["reason"] == "drift" for r in method.refresh_log)

    out = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "trace": trace,
        "vm_id": str(vm_id),
        **agg,
        "n_cpu_class_updates": n_field("cpu_class"),
        "n_memory_class_updates": n_field("memory_class"),
        "n_cpu_p95_updates": n_field("predicted_cpu_p95_next_24h"),
        "n_mem_p95_updates": n_field("predicted_mem_p95_next_24h"),
        "total_updates": int(len(log_df)),
        "n_refresh_events": len(method.refresh_log),
        "n_eval_points_verified": int(len(rec_df)),
        "snapshots_dropped_unverified": int(replay.snapshots_dropped_unverified),
        "n_streaming_steps": int(len(replay.observations)),
        "stream_days": replay.stream_days,
        "update_log": list(method.update_log),
        "refresh_log": list(method.refresh_log),
        "n_periodic_refreshes": n_periodic,
        "n_drift_refreshes": n_drift,
    }
    dh = getattr(method, "decision_head", None)
    if dh is not None and hasattr(dh, "stats"):
        out["decision_head_stats"] = dh.stats()
    return out
