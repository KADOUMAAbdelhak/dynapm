"""Managed Materna confirmatory estimation study (V3).

Bound exactly to configs/materna_confirmatory_v1_1. Observation-window methods only.
Requires clean committed source. purpose=claim.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import shutil
import tempfile
import time

import pandas as pd

from dynapm.core.provenance import SourceProvenance, canonical_json, prepare_experiment
from dynapm.core.run_store import OutputSpec, RunSession, check_cache, write_json
from dynapm.data.manifests import check_dataset, materna_manifest
from dynapm.experiments.confirmatory_design import (
    PRIMARY_METHODS,
    design_document,
    frozen_hashes,
    validate_cohort_manifest,
)
from dynapm.experiments.confirmatory_estimation import (
    analyze_families,
    pareto_relations,
    robustness_summaries,
)
from dynapm.experiments.confirmatory_execution import (
    assert_pilots_excluded,
    build_execution_cohort,
    confirmatory_config,
    design_binding_record,
    load_volatility_tiers,
    run_confirmatory_vm,
    validate_confirmatory_config,
)

OUTPUTS = {
    "design_binding.json": "frozen-v25a-design-binding",
    "eligible_cohort.json": "protocol-eligible-confirmatory-cohort",
    "protocol_exclusions.parquet": "protocol-validity-exclusion-accounting",
    "protocol_exclusions.json": "exclusion-summary-by-code",
    "per_vm_results.parquet": "confirmatory-method-vm-estimation-results",
    "paired_effects.parquet": "per-vm-paired-treatment-minus-control",
    "family_inference.parquet": "f1-f2-f3-estimation-inference",
    "family_inference.json": "f1-f2-f3-estimation-summary",
    "pareto_tradeoff.json": "strict-fidelity-cost-pareto-labels",
    "robustness_summary.json": "secondary-rq4-strata",
    "cost_accounting_summary.json": "canonical-refresh-write-change-summaries",
    "confirmatory_diagnostics.json": "runtime-and-invariant-diagnostics",
    "estimation_summary.json": "rq1-rq4-estimation-record",
}


def integrity_probes(path, exp):
    exact = check_cache(path, exp, "claim")
    from dataclasses import replace

    altered_policy = replace(exp.config.policies[0], method_id="static_altered")
    altered = replace(
        exp,
        config=replace(exp.config, policies=(altered_policy, *exp.config.policies[1:])),
    )
    mutation = check_cache(path, altered, "claim")
    pilot_req = check_cache(path, exp, "pilot")
    with tempfile.TemporaryDirectory(prefix="dynapm-confirm-tamper-") as tmp:
        copy = Path(tmp) / "run"
        shutil.copytree(path, copy)
        target = copy / "outputs/estimation_summary.json"
        target.write_bytes(target.read_bytes() + b" ")
        tamper = check_cache(copy, exp, "claim")
    assert exact.reusable and not mutation.reusable and not tamper.reusable
    assert not pilot_req.reusable
    return {
        "exact_claim": exact.reusable,
        "changed_config": mutation.reasons,
        "tampered_copy": tamper.reasons,
        "pilot_request": pilot_req.reasons,
    }


def execute(repo, *, workers=4, max_vms=None):
    repo = Path(repo).resolve()
    source = SourceProvenance.capture(repo)
    if source.dirty:
        raise ValueError("confirmatory claim run requires clean committed source")
    if not 1 <= workers <= 8:
        raise ValueError("confirmatory permits 1..8 VM workers")
    config = confirmatory_config()
    validate_confirmatory_config(config)
    validate_cohort_manifest()
    hashes = frozen_hashes()
    if hashes["design_fingerprint"] != "62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296":
        raise ValueError("frozen design fingerprint mismatch")
    preparation_start = time.perf_counter()
    raw = repo / "data/raw"
    dataset = materna_manifest(raw)
    check_dataset(raw, dataset)
    cohort, included, excluded = build_execution_cohort(repo, dataset)
    vol = load_volatility_tiers(repo, dataset, config)
    included = included.merge(vol, on=["trace", "vm_id"], how="left", validate="one_to_one")
    if included[["volatility", "volatility_tier"]].isna().any().any():
        raise ValueError("volatility tier join incomplete")
    assert_pilots_excluded(included)
    if max_vms is not None:
        included = included.sort_values(["trace", "vm_id"]).head(int(max_vms))
    entities = included.to_dict("records")
    n_eligible = len(entities)
    n_excluded = int(len(excluded))
    attempted = n_eligible * len(PRIMARY_METHODS)
    exp, env = prepare_experiment(
        repo,
        raw,
        config,
        dataset,
        cohort,
        {
            "statistics": config.statistics.bootstrap_seed,
            "design": hashes["design_fingerprint"],
        },
    )
    required = [OutputSpec(f"outputs/{name}", role) for name, role in OUTPUTS.items()]
    required += [
        OutputSpec(f"logs/{r['trace']}__{r['vm_id']}.json", "per-vm-attempt-progress")
        for r in entities
    ]
    with RunSession(
        repo / "results",
        exp,
        env,
        repo=repo,
        dataset_root=raw,
        purpose="claim",
        required_outputs=required,
    ) as run:
        out = run.path / "outputs"
        write_json(out / "design_binding.json", design_binding_record())
        write_json(
            out / "eligible_cohort.json",
            {
                "manifest": cohort,
                "candidate_count_before_protocol_exclusions": 1558,
                "eligible_count": n_eligible if max_vms is None else len(included),
                "excluded_count": n_excluded,
                "hashes": hashes,
                "entities": [
                    {"trace": e.trace, "vm_id": e.entity_id, "included": e.included, "exclusion_reason": e.exclusion_reason}
                    for e in cohort.entities
                ],
            },
        )
        excluded.to_parquet(out / "protocol_exclusions.parquet", index=False)
        excl_summary = {
            "n_excluded": n_excluded,
            "by_code": excluded.groupby("exclusion_code").size().astype(int).to_dict()
            if n_excluded
            else {},
            "note": "199 gap-audit review flags are diagnostics only and were not used as automatic exclusions",
        }
        write_json(out / "protocol_exclusions.json", excl_summary)
        print(
            canonical_json(
                {
                    "run_path": str(run.path),
                    "fingerprint": exp.fingerprint,
                    "run_id": run.manifest.run_id,
                    "source_commit": source.commit,
                    "design_fingerprint": hashes["design_fingerprint"],
                    "eligible": n_eligible,
                    "excluded": n_excluded,
                    "attempted_method_vm": attempted,
                }
            ),
            flush=True,
        )
        compute_start = time.perf_counter()
        answers = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for row in entities:
                log = run.path / "logs" / f"{row['trace']}__{row['vm_id']}.json"
                write_json(
                    log,
                    {
                        "trace": row["trace"],
                        "vm_id": row["vm_id"],
                        "status": "SUBMITTED",
                        "methods": 5,
                    },
                )
                futures[executor.submit(run_confirmatory_vm, row, str(repo))] = (row, log)
            for future in as_completed(futures):
                row, log = futures[future]
                try:
                    answer = future.result()
                except Exception as error:
                    write_json(
                        log,
                        {
                            "trace": row["trace"],
                            "vm_id": row["vm_id"],
                            "status": "FAILED",
                            "error_type": type(error).__name__,
                            "message": str(error),
                        },
                    )
                    for pending in futures:
                        pending.cancel()
                    raise
                answers.append(answer)
                write_json(log, {"status": "COMPLETED", **answer["diagnostics"]})
                print(
                    canonical_json(
                        {"completed_vms": len(answers), **answer["diagnostics"]}
                    ),
                    flush=True,
                )
        rows = [r for a in answers for r in a["rows"]]
        expected_rows = n_eligible * 5
        if len(rows) != expected_rows:
            raise ValueError(f"expected {expected_rows} method×VM rows, got {len(rows)}")
        frame = pd.DataFrame(rows).sort_values(["trace", "vm_id", "method_id"])
        assert_pilots_excluded(frame)
        if frame.duplicated(["trace", "vm_id", "method_id"]).any():
            raise ValueError("duplicate method×VM rows")
        # Shared evaluation stamps across methods within each VM.
        stamp_check = frame.groupby(["trace", "vm_id"])["evaluation_stamp_fingerprint"].nunique()
        if not stamp_check.eq(1).all():
            raise ValueError("evaluation timestamps differ across methods for some VMs")
        frame.to_parquet(out / "per_vm_results.parquet", index=False)
        paired, inference, family_summary = analyze_families(frame)
        paired.to_parquet(out / "paired_effects.parquet", index=False)
        inference.to_parquet(out / "family_inference.parquet", index=False)
        write_json(out / "family_inference.json", family_summary)
        pareto = pareto_relations(inference)
        write_json(out / "pareto_tradeoff.json", {"relations": pareto})
        write_json(out / "robustness_summary.json", robustness_summaries(frame, paired))
        cost_cols = [
            "n_refresh_events",
            "n_field_writes",
            "n_field_value_changes",
            "n_periodic_refreshes",
            "n_full_rewrite_refreshes",
            "refresh_delay_mean_seconds",
            "refresh_delay_max_seconds",
            "age_mean_hours",
            "age_median_hours",
            "age_p95_hours",
        ]
        cost_summary = {
            str(method): {
                f"{col}__mean": float(g[col].mean()) for col in cost_cols if col in g
            }
            for method, g in frame.groupby("method_id")
        }
        write_json(out / "cost_accounting_summary.json", cost_summary)
        wall = time.perf_counter() - compute_start
        diagnostics = {
            "purpose": "claim",
            "gate": "V3",
            "source_commit": source.commit,
            "experiment_fingerprint": exp.fingerprint,
            "run_id": run.manifest.run_id,
            "design_fingerprint": hashes["design_fingerprint"],
            "candidate_count": 1558,
            "eligible_count": n_eligible,
            "excluded_count": n_excluded,
            "attempted_method_vm": attempted,
            "completed_method_vm": int(len(rows)),
            "preparation_seconds": compute_start - preparation_start,
            "compute_wall_seconds": wall,
            "workers": workers,
            "execution_invariants": "PASS",
            "invalidated_attempts": [],
            "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
            "c4_status": "UNPROVEN",
            "c3_status": "UNPROVEN",
        }
        write_json(out / "confirmatory_diagnostics.json", diagnostics)
        estimation = {
            "study_framing": "estimation_first",
            "research_questions": design_document()["research_questions"],
            "eligible_vms": n_eligible,
            "excluded_vms": n_excluded,
            "exclusions_by_code": excl_summary["by_code"],
            "method_macro_means": {
                str(method): {
                    "cpu_class_accuracy": float(g.cpu_class_accuracy.mean()),
                    "memory_class_accuracy": float(g.memory_class_accuracy.mean()),
                    "cpu_p95_mae": float(g.cpu_p95_mae.mean()),
                    "mem_p95_mae": float(g.mem_p95_mae.mean()),
                    "n_refresh_events": float(g.n_refresh_events.mean()),
                }
                for method, g in frame.groupby("method_id")
            },
            "family_inference": family_summary["families"],
            "pareto": pareto,
            "claims": {
                "supported_by_v3_execution": [
                    "frozen Materna estimation study executed",
                    "paired effects/CIs/tests/Holm reported for F1–F3",
                ],
                "unproven": [
                    "C3 cross-corpus generalization",
                    "C4 operational/practical benefit",
                    "profile-level practical significance thresholds",
                ],
                "withdrawn": ["C1 forecasting superiority", "C2 adaptive-refresh superiority"],
            },
        }
        write_json(out / "estimation_summary.json", estimation)
        exclusion_records = [
            {
                "trace": r.trace,
                "vm_id": str(r.vm_id),
                "exclusion_reason": r.exclusion_code,
            }
            for r in excluded.itertuples()
        ]
        run.complete(failures=(), exclusions=exclusion_records)
        probes = integrity_probes(run.path, exp)
        report = {
            **diagnostics,
            "integrity_probes": probes,
            "output_manifest_sha256": run.manifest.output_manifest_sha256,
        }
        write_json(repo / "results" / "materna-confirmatory-verification.json", report)
        print(canonical_json(report), flush=True)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--max-vms",
        type=int,
        default=None,
        help="optional smoke limit; omit for full confirmatory cohort",
    )
    parser.add_argument(
        "--write-config-fingerprint",
        action="store_true",
        help="print confirmatory config fingerprint and exit",
    )
    args = parser.parse_args(argv)
    if args.write_config_fingerprint:
        cfg = confirmatory_config()
        print(canonical_json({"experiment_config_sha256": cfg.sha256, "hashes": frozen_hashes()}))
        return
    execute(args.repo, workers=args.workers, max_vms=args.max_vms)


if __name__ == "__main__":
    main()
