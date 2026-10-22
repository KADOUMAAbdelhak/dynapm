"""Reconstruct signed bias/age for Static/PW/Full-Rewrite on the fixed 18 VMs.

Diagnostic reconstruction only: no new policies, no confirmatory VMs, no tuning.
Reconciles class/MAE/refresh counts against the corrected Phase 3A-R pilot.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
import json
import time

import numpy as np
import pandas as pd

from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.methods.baselines_v2 import (
    FullRewritePolicyV2,
    PeriodicPolicyV2,
    StaticPolicyV2,
)

REPO = Path(__file__).resolve().parents[2]
RUN = (
    REPO
    / "results/runs/6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682"
    / "2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe"
)
OUT = REPO / "results/analysis/v24g_nonadaptive_tradeoff"
METHODS = {
    "static": StaticPolicyV2,
    "pw_3h": partial(PeriodicPolicyV2, period_hours=3.0),
    "pw_6h": partial(PeriodicPolicyV2, period_hours=6.0),
    "pw_12h": partial(PeriodicPolicyV2, period_hours=12.0),
    "full_rewrite": FullRewritePolicyV2,
}


def dominates(a, b):
    better_or_eq = (
        a["klass"] >= b["klass"] - 1e-12
        and a["mae"] <= b["mae"] + 1e-12
        and a["cost"] <= b["cost"] + 1e-12
    )
    strictly = (
        a["klass"] > b["klass"] + 1e-12
        or a["mae"] < b["mae"] - 1e-12
        or a["cost"] < b["cost"] - 1e-12
    )
    return better_or_eq and strictly


def run_one(task):
    entity, method_id = task
    factory = METHODS[method_id]
    inputs = prepare_vm_inputs(
        entity["trace"],
        str(entity["vm_id"]),
        repo_root=REPO,
        with_predictors=False,
    )
    if inputs.predictors is not None or inputs.predictions is not None:
        raise ValueError("reconstruction must remain predictor-free")
    replay = replay_from_inputs(inputs, factory)
    result = evaluate_replay(replay, include_records=True)
    records = pd.DataFrame(result["evaluation_records"])
    return {
        "trace": entity["trace"],
        "vm_id": str(entity["vm_id"]),
        "volatility_tier": entity["volatility_tier"],
        "volatility": float(entity["volatility"]),
        "method_id": method_id,
        "cpu_class_accuracy": float(result["cpu_class_accuracy"]),
        "memory_class_accuracy": float(result["memory_class_accuracy"]),
        "cpu_p95_mae": float(result["cpu_p95_mae"]),
        "mem_p95_mae": float(result["mem_p95_mae"]),
        "cpu_p95_bias": float(records.cpu_p95_bias.mean()),
        "mem_p95_bias": float(records.mem_p95_bias.mean()),
        "n_refresh_events": int(result["n_refresh_events"]),
        "n_field_writes": int(result["n_field_writes"]),
        "n_field_value_changes": int(result["n_field_value_changes"]),
        "n_periodic_refreshes": int(result["n_periodic_refreshes"]),
        "n_full_rewrite_refreshes": int(result["n_full_rewrite_refreshes"]),
        "age_mean": float(records.profile_age_hours.mean()),
        "age_median": float(records.profile_age_hours.median()),
        "age_p95": float(np.quantile(records.profile_age_hours, 0.95)),
        "age_max": float(records.profile_age_hours.max()),
        "age_zero_pct": float(100 * (records.profile_age_seconds == 0).mean()),
        "n_eval_points": int(len(records)),
        "confirmatory_access": False,
    }


def analyze(frame: pd.DataFrame):
    methods = list(METHODS)
    macro = (
        frame.groupby("method_id")[
            [
                "cpu_class_accuracy",
                "memory_class_accuracy",
                "cpu_p95_mae",
                "mem_p95_mae",
                "cpu_p95_bias",
                "mem_p95_bias",
                "n_refresh_events",
                "n_field_writes",
                "n_field_value_changes",
                "age_mean",
                "age_median",
                "age_p95",
                "age_max",
                "age_zero_pct",
            ]
        ]
        .mean()
        .reindex(methods)
        .reset_index()
    )

    def front_membership(subset_methods):
        counts = {m: 0 for m in subset_methods}
        rows = []
        for (trace, vm), group in frame[frame.method_id.isin(subset_methods)].groupby(
            ["trace", "vm_id"]
        ):
            points = []
            for row in group.itertuples():
                points.append(
                    {
                        "method": row.method_id,
                        "klass": (row.cpu_class_accuracy + row.memory_class_accuracy) / 2,
                        "mae": (row.cpu_p95_mae + row.mem_p95_mae) / 2,
                        "cost": row.n_refresh_events,
                        "tier": row.volatility_tier,
                        "volatility": row.volatility,
                    }
                )
            for point in points:
                if not any(
                    dominates(other, point)
                    for other in points
                    if other["method"] != point["method"]
                ):
                    counts[point["method"]] += 1
                    rows.append(
                        {
                            "trace": trace,
                            "vm_id": vm,
                            "tier": point["tier"],
                            "volatility": point["volatility"],
                            "method_id": point["method"],
                            "mean_class": point["klass"],
                            "mean_mae": point["mae"],
                            "n_refresh_events": point["cost"],
                        }
                    )
        return counts, pd.DataFrame(rows)

    all_counts, all_front = front_membership(methods)
    cadence_counts, cadence_front = front_membership(
        ["static", "pw_3h", "pw_6h", "pw_12h"]
    )

    deltas = []
    indexed = frame.set_index(["trace", "vm_id", "method_id"])
    for left, right in [
        ("pw_3h", "pw_6h"),
        ("pw_6h", "pw_12h"),
        ("pw_3h", "pw_12h"),
        ("pw_6h", "static"),
        ("full_rewrite", "pw_3h"),
        ("full_rewrite", "pw_6h"),
        ("full_rewrite", "pw_12h"),
        ("full_rewrite", "static"),
    ]:
        rows = []
        for key in indexed.index.droplevel(2).unique():
            a = indexed.loc[(*key, left)]
            b = indexed.loc[(*key, right)]
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "d_cpu_class": float(a.cpu_class_accuracy - b.cpu_class_accuracy),
                    "d_mem_class": float(
                        a.memory_class_accuracy - b.memory_class_accuracy
                    ),
                    "d_cpu_mae": float(a.cpu_p95_mae - b.cpu_p95_mae),
                    "d_mem_mae": float(a.mem_p95_mae - b.mem_p95_mae),
                    "d_refresh": float(a.n_refresh_events - b.n_refresh_events),
                    "d_writes": float(a.n_field_writes - b.n_field_writes),
                }
            )
        block = pd.DataFrame(rows)
        deltas.append(
            {
                "contrast": f"{left}_minus_{right}",
                **{c: float(block[c].mean()) for c in block.columns if c.startswith("d_")},
            }
        )

    # Descriptive association: bootstrap volatility vs cadence membership (no fitted rule).
    association = []
    for method in ["static", "pw_3h", "pw_6h", "pw_12h"]:
        members = cadence_front[cadence_front.method_id == method]
        association.append(
            {
                "method_id": method,
                "front_vm_count": int(members.groupby(["trace", "vm_id"]).ngroups)
                if len(members)
                else 0,
                "front_mean_bootstrap_volatility": float(members.volatility.mean())
                if len(members)
                else None,
                "front_by_tier": members.tier.value_counts().to_dict()
                if len(members)
                else {},
            }
        )

    return macro, all_counts, all_front, cadence_counts, cadence_front, deltas, association


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cohort = pd.read_parquet(RUN / "outputs/pilot_cohort.parquet")
    if len(cohort) != 18:
        raise ValueError("exactly the fixed 18 development VMs required")
    tasks = [(entity, method) for entity in cohort.to_dict("records") for method in METHODS]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(run_one, tasks))
    frame = pd.DataFrame(rows)
    if len(frame) != 90:
        raise ValueError("exact 90 reconstructions required")

    archived = pd.read_parquet(RUN / "outputs/per_vm_results.parquet")
    archived = archived[archived.method_id.isin(METHODS)].copy()
    archived.vm_id = archived.vm_id.astype(str)
    merged = frame.merge(
        archived[
            [
                "trace",
                "vm_id",
                "method_id",
                "cpu_class_accuracy",
                "memory_class_accuracy",
                "cpu_p95_mae",
                "mem_p95_mae",
                "n_refresh_events",
                "n_field_writes",
                "n_field_value_changes",
            ]
        ],
        on=["trace", "vm_id", "method_id"],
        suffixes=("", "_arch"),
    )
    for column in [
        "cpu_class_accuracy",
        "memory_class_accuracy",
        "cpu_p95_mae",
        "mem_p95_mae",
        "n_refresh_events",
        "n_field_writes",
        "n_field_value_changes",
    ]:
        if (merged[column] - merged[f"{column}_arch"]).abs().max() > 1e-9:
            raise ValueError(f"reconstruction mismatch on {column}")

    macro, all_counts, all_front, cadence_counts, cadence_front, deltas, association = (
        analyze(frame)
    )
    frame.to_parquet(OUT / "per_vm_nonadaptive.parquet", index=False)
    macro.to_parquet(OUT / "macro_nonadaptive.parquet", index=False)
    all_front.to_parquet(OUT / "pareto_membership_all5.parquet", index=False)
    cadence_front.to_parquet(OUT / "pareto_membership_cadence.parquet", index=False)
    pd.DataFrame(deltas).to_parquet(OUT / "paired_contrasts.parquet", index=False)
    summary = {
        "purpose": "v2.4g-diagnostic-reconstruction",
        "source_pilot": str(RUN.relative_to(REPO)),
        "protocol": "causal-timeline-v3",
        "evaluation_grid": "phase-balanced-hourly-v1",
        "methods": list(METHODS),
        "n_vms": 18,
        "n_evaluations": 90,
        "wall_seconds": time.perf_counter() - started,
        "confirmatory_outcomes_accessed": False,
        "reconciled_with_archived_pilot_metrics": True,
        "macro": macro.to_dict("records"),
        "pareto_membership_counts_all5": all_counts,
        "pareto_membership_counts_cadence": cadence_counts,
        "paired_contrasts": deltas,
        "cadence_front_volatility_association": association,
        "tier_crosstab_cadence_front": (
            pd.crosstab(cadence_front.tier, cadence_front.method_id).to_dict()
            if len(cadence_front)
            else {}
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(json.dumps({"out": str(OUT), "wall_seconds": summary["wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
