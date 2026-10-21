"""Evaluation runner v2: snapshot-then-verify protocol.

Results expose canonical initialization, refresh, write, and value-change counters.
Event traces are optional audit detail; analysis consumes counters directly.
Forward ground truth is exposed only after the verification horizon; it is
never passed back to a refresh policy."""
from __future__ import annotations

import pandas as pd

from dynapm.core.accounting import ACCOUNTING_SCHEMA, FIELD_CHANGE_METRICS
from dynapm.eval.replay import CAUSAL_PROTOCOL, prepare_vm_replay, iter_verified_snapshots


def run_method_on_vm(
    trace, vm_id, method_factory, *, lookback_steps=288, repo_root=None,
    predictor_factory=None,
) -> dict:
    options = {} if predictor_factory is None else {"predictor_factory": predictor_factory}
    replay = prepare_vm_replay(trace, vm_id, method_factory, repo_root=repo_root, **options)
    return evaluate_replay(replay, lookback_steps=lookback_steps)


def evaluate_replay(replay, *, lookback_steps=288, include_records=False):
    """One aggregation path for standalone and shared-input managed evaluations."""
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

    out = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "trace": method.profile.static.trace_name,
        "vm_id": str(method.profile.static.vm_id),
        **agg,
        "accounting_schema": ACCOUNTING_SCHEMA,
        **method.accounting_metrics(),
        **{name: sum(field in e.fields_changed for e in method.accounting.refresh_events)
           for name, field in FIELD_CHANGE_METRICS.items()},
        "n_eval_points_verified": int(len(rec_df)),
        "snapshots_dropped_unverified": int(replay.snapshots_dropped_unverified),
        "n_streaming_steps": int(len(replay.observations)),
        "stream_days": replay.stream_days,
        "initialization_log": [e.to_dict() for e in method.accounting.initialization_events],
        "refresh_log": [e.to_dict() for e in method.accounting.refresh_events],
    }
    dh = getattr(method, "decision_head", None)
    if dh is not None and hasattr(dh, "stats"):
        out["decision_head_stats"] = dh.stats()
    if include_records:
        out["evaluation_records"] = records
    return out
