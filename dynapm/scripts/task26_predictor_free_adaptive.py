"""Managed fixed-18 predictor-free adaptive-trigger investigation."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import time

import numpy as np
import pandas as pd

from dynapm.core.provenance import (
    SourceProvenance,
    canonical_json,
    experiment_from_dict,
    prepare_experiment,
    read_json,
)
from dynapm.core.run_store import OutputSpec, RunSession, check_cache, write_json
from dynapm.experiments.pilot_design import guard_cohort
from dynapm.experiments.predictor_free_adaptive import (
    ADAPTIVE_MATCHES,
    METHODS,
    run_vm,
    study_config,
    validate_config,
)

PARENT = (
    "6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/"
    "2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe"
)
FIELDS = [
    "cpu_class_accuracy",
    "memory_class_accuracy",
    "cpu_p95_mae",
    "mem_p95_mae",
    "cpu_p95_bias",
    "mem_p95_bias",
    "n_refresh_events",
    "n_periodic_refreshes",
    "n_drift_refreshes",
    "n_reactive_refreshes",
    "n_budget_extra_refreshes",
    "n_field_writes",
    "n_field_value_changes",
    "profile_age_mean_hours",
    "profile_age_p95_hours",
    "total_trigger_signals",
    "cpu_trigger_signals",
    "mem_trigger_signals",
    "ineligible_trigger_signals",
    "periodic_coincident_trigger_signals",
]


def analyze(rows):
    deltas = []
    for (trace, vm), group in rows.groupby(["trace", "vm_id"]):
        indexed = group.set_index("method_id")
        for adaptive, matched in ADAPTIVE_MATCHES.items():
            candidate = indexed.loc[adaptive]
            for reference_type, reference in (
                ("matched", matched),
                ("pw", "pw_6h"),
            ):
                baseline = indexed.loc[reference]
                deltas.append(
                    {
                        "trace": trace,
                        "vm_id": vm,
                        "tier": candidate.tier,
                        "adaptive_method_id": adaptive,
                        "reference_type": reference_type,
                        "reference_method_id": reference,
                        **{
                            name: float(candidate[name] - baseline[name])
                            for name in FIELDS
                        },
                    }
                )
    deltas = pd.DataFrame(deltas)
    effects = []
    keys = ["adaptive_method_id", "reference_type", "reference_method_id"]
    for key, group in deltas.groupby(keys):
        for name in FIELDS:
            values = group[name].to_numpy(float)
            effects.append(
                {
                    **dict(zip(keys, key)),
                    "metric": name,
                    "mean": float(values.mean()),
                    "median": float(np.median(values)),
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                    "positive_delta_count": int((values > 1e-12).sum()),
                    "negative_delta_count": int((values < -1e-12).sum()),
                    "ties": int((np.abs(values) <= 1e-12).sum()),
                }
            )
    effects = pd.DataFrame(effects)
    tiers = (
        deltas.groupby(
            ["adaptive_method_id", "reference_type", "reference_method_id", "tier"]
        )[FIELDS]
        .mean()
        .reset_index()
    )
    return deltas, effects, tiers


def execute(repo, workers=2):
    repo = Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:
        raise ValueError("clean committed source required")
    parent = repo / "results/runs" / PARENT
    old = experiment_from_dict(read_json(parent / "manifest.json")["experiment"])
    if not check_cache(parent, old, "pilot").reusable:
        raise ValueError("invalid managed cohort provenance")
    selected = pd.DataFrame(old.cohort.filtering_config["selection_records"])
    guard_cohort(selected)
    expected = {
        "Materna-Trace-1": {"374", "213", "96", "64", "143", "76"},
        "Materna-Trace-2": {"396", "207", "388", "398", "516", "11"},
        "Materna-Trace-3": {"212", "151", "83", "133", "224", "127"},
    }
    actual = {
        trace: set(group.vm_id.astype(str))
        for trace, group in selected.groupby("trace")
    }
    if actual != expected:
        raise ValueError("only the fixed 18 development VMs may execute")
    config = study_config(old.config)
    validate_config(config)
    experiment, environment = prepare_experiment(
        repo, repo / "data/raw", config, old.dataset, old.cohort, {"model": 42}
    )
    outputs = [
        "cohort.parquet",
        "per_vm_results.parquet",
        "refresh_events.parquet",
        "evaluation_records.parquet",
        "budget_schedule.parquet",
        "trigger_events.parquet",
        "paired_effects.parquet",
        "effect_summary.parquet",
        "tier_metrics.parquet",
        "tier_effects.parquet",
        "diagnostics.json",
        "summary.json",
    ]
    started = time.perf_counter()
    with RunSession(
        repo / "results",
        experiment,
        environment,
        repo=repo,
        dataset_root=repo / "data/raw",
        purpose="pilot",
        required_outputs=[
            OutputSpec(
                "outputs/" + name,
                "exploratory-predictor-free-" + name.split(".")[0],
            )
            for name in outputs
        ],
    ) as run:
        print(
            canonical_json(
                {"run_path": str(run.path), "fingerprint": experiment.fingerprint}
            ),
            flush=True,
        )
        with ProcessPoolExecutor(max_workers=workers) as pool:
            answers = list(
                pool.map(
                    run_vm,
                    [(repo, entity, config) for entity in selected.to_dict("records")],
                )
            )
        rows, events, records, schedules, triggers = [
            pd.DataFrame([row for answer in answers for row in answer[index]])
            for index in range(5)
        ]
        diagnostics = [answer[5] for answer in answers]
        expected_rows = len(selected) * len(METHODS)
        if (
            len(rows) != expected_rows
            or not rows.groupby(["trace", "vm_id"])
            .method_id.nunique()
            .eq(len(METHODS))
            .all()
        ):
            raise ValueError(f"exact {expected_rows} completed evaluations required")
        if not np.isfinite(rows[FIELDS].to_numpy(float)).all():
            raise ValueError("nonfinite metrics")
        deltas, effects, tier_effects = analyze(rows)
        tier_metrics = (
            rows.groupby(["tier", "method_id"])[FIELDS].mean().reset_index()
        )
        frames = {
            "cohort": selected,
            "per_vm_results": rows,
            "refresh_events": events,
            "evaluation_records": records,
            "budget_schedule": schedules,
            "trigger_events": triggers,
            "paired_effects": deltas,
            "effect_summary": effects,
            "tier_metrics": tier_metrics,
            "tier_effects": tier_effects,
        }
        for name, frame in frames.items():
            frame.to_parquet(run.path / "outputs" / f"{name}.parquet", index=False)
        write_json(run.path / "outputs/diagnostics.json", diagnostics)
        summary = {
            "purpose": "pilot",
            "source_commit": experiment.source.commit,
            "fingerprint": experiment.fingerprint,
            "run_id": run.manifest.run_id,
            "cohort_sha256": old.cohort.sha256,
            "methods": METHODS,
            "attempted": expected_rows,
            "completed": expected_rows,
            "wall_seconds": time.perf_counter() - started,
            "macro_vm": rows.groupby("method_id")[FIELDS]
            .mean()
            .reset_index()
            .to_dict("records"),
            "descriptive_paired_effects": effects.to_dict("records"),
            "confirmed_equal_reactive_budgets": 18,
            "confirmed_equal_adwin_budgets": 18,
            "confirmed_identical_periodic_bases": 18,
            "confirmed_content_function": "paired-observation-window-24h-v1",
            "predictor_fits": 0,
            "prediction_calls": 0,
            "recursive_forecast_calls": 0,
            "numeric_causal_failures": 0,
            "no_confirmatory_outcomes": True,
            "no_tuning": True,
            "decision_scope": (
                "architectural exploratory disposition; no retrospective "
                "meaningful-margin or inference"
            ),
        }
        write_json(run.path / "outputs/summary.json", summary)
        run.complete()
    assert check_cache(run.path, experiment, "pilot").reusable
    print(
        canonical_json(
            {
                "run_path": str(run.path),
                "fingerprint": experiment.fingerprint,
                "output_manifest_sha256": read_json(run.path / "manifest.json")[
                    "output_manifest_sha256"
                ],
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    execute(args.repo, args.workers)


if __name__ == "__main__":
    main()
