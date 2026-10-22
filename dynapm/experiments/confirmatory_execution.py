"""Managed Materna confirmatory execution bound to frozen V2.5A design.

Observation-window methods only. No predictors/adaptive policies.
Protocol-validity exclusions only — never performance-based.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dynapm.core.accounting import ACCOUNTING_METRICS, require_accounting_metrics
from dynapm.core.provenance import (
    CohortEntity,
    CohortManifest,
    DataConfig,
    ExperimentConfigProvenance,
    ModelConfig,
    PolicyConfig,
    StatisticsConfig,
    canonical_json,
    fingerprint,
    read_json,
    utc_now,
)
from dynapm.core.temporal import FEATURE_HISTORY_SLOTS, TEMPORAL_PROTOCOL, EVALUATION_GRID
from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.experiments.confirmatory_design import (
    COMPARISON_FAMILIES,
    CONFIG_JSON,
    COHORT_JSON,
    PERMANENT_PILOT_EXCLUSIONS,
    PRIMARY_METHODS,
    PROTOCOL_EXCLUSION_CODES,
    SCHEMA_VERSION,
    design_document,
    frozen_hashes,
    validate_cohort_manifest,
    validate_design,
)
from dynapm.experiments.gap_eligibility import audit_frame
from dynapm.methods.baselines_v2 import (
    FullRewritePolicyV2,
    PeriodicPolicyV2,
    StaticPolicyV2,
)
from dynapm.data.loader import load_vm_csv

REPO_ROOT = Path(__file__).resolve().parents[2]
FILTERING_RULE_VERSION = "materna-confirmatory-protocol-exclusions-v1"
MATRIX_VERSION = "materna-confirmatory-nonadaptive-v1"

METHOD_FACTORIES = {
    "static": StaticPolicyV2,
    "pw_12h": partial(PeriodicPolicyV2, period_hours=12.0),
    "pw_6h": partial(PeriodicPolicyV2, period_hours=6.0),
    "pw_3h": partial(PeriodicPolicyV2, period_hours=3.0),
    "full_rewrite": FullRewritePolicyV2,
}

ENDPOINT_COLUMNS = {
    "cpu_class_correctness": "cpu_class_accuracy",
    "memory_class_correctness": "memory_class_accuracy",
    "cpu_p95_profile_mae": "cpu_p95_mae",
    "memory_p95_profile_mae": "mem_p95_mae",
}


def confirmatory_config() -> ExperimentConfigProvenance:
    """Build ExperimentConfigProvenance exactly matching the frozen design."""
    design = design_document()
    validate_design(design)
    policies = []
    for method_id in PRIMARY_METHODS:
        if method_id == "static":
            policies.append(PolicyConfig("static"))
        elif method_id == "full_rewrite":
            policies.append(PolicyConfig("full_rewrite"))
        elif method_id.startswith("pw_"):
            hours = float(method_id.split("_")[1].replace("h", ""))
            policies.append(PolicyConfig(method_id, periodic_interval_hours=hours))
        else:
            raise ValueError(f"unsupported confirmatory method: {method_id}")
    hashes = frozen_hashes()
    return ExperimentConfigProvenance(
        DataConfig("materna"),
        ModelConfig(family="unused-observation-only"),
        tuple(policies),
        StatisticsConfig(
            bootstrap_repetitions=10000,
            bootstrap_seed=20251022,
            confidence_level=0.95,
            test_specification={
                "paired_unit": "VM",
                "test": "wilcoxon",
                "zero_method": "wilcox",
                "multiplicity": "holm",
                "study_framing": "estimation_first",
            },
        ),
        preprocessing={
            "cohort_manifest": "configs/materna_confirmatory_cohort_v1.json",
            "pilot_exclusion": "permanent-18-development-vms",
            "predictors": False,
        },
        analysis={
            "matrix_version": MATRIX_VERSION,
            "purpose": "claim",
            "gate": "V3",
            "design_schema": SCHEMA_VERSION,
            "design_fingerprint": hashes["design_fingerprint"],
            "config_json": "configs/materna_confirmatory_v1_1.json",
            "study_framing": "estimation_first",
            "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
            "comparison_families": {
                name: [{"treatment": a, "control": b} for a, b in pairs]
                for name, pairs in COMPARISON_FAMILIES.items()
            },
            "lookback_steps": 288,
            "evaluation_grid": EVALUATION_GRID,
            "temporal_protocol": TEMPORAL_PROTOCOL,
        },
    )


def validate_confirmatory_config(config: ExperimentConfigProvenance) -> None:
    frozen = confirmatory_config()
    if [p.method_id for p in config.policies] != list(PRIMARY_METHODS):
        raise ValueError("confirmatory requires exact five-method matrix")
    if canonical_json(config) != canonical_json(frozen):
        raise ValueError("confirmatory config must match frozen design binding")
    if any(p.method_id.startswith(("pp_", "reactive", "v3", "budget")) for p in config.policies):
        raise ValueError("predictor/adaptive policies forbidden in confirmatory primary matrix")


def factory_for(method_id: str):
    if method_id not in METHOD_FACTORIES:
        raise ValueError(f"unknown confirmatory method: {method_id}")
    return METHOD_FACTORIES[method_id]


def assert_pilots_excluded(entities: list[dict[str, str]] | pd.DataFrame) -> None:
    if isinstance(entities, pd.DataFrame):
        ids = {(r.trace, str(r.vm_id)) for r in entities.itertuples()}
    else:
        ids = {(e["trace"], str(e["vm_id"])) for e in entities}
    overlap = ids & set(PERMANENT_PILOT_EXCLUSIONS)
    if overlap:
        raise ValueError(f"pilot VMs present in confirmatory set: {sorted(overlap)}")


def load_volatility_tiers(repo: Path, dataset, config: ExperimentConfigProvenance) -> pd.DataFrame:
    """Bootstrap CPU std tertiles on the retained pool (input-only; same definition as pilot)."""
    from dynapm.experiments.pilot_design import characterize_inputs

    pool, _ = characterize_inputs(repo / "data/raw", dataset, config)
    if len(pool) != 1576:
        raise ValueError(f"retained volatility pool must be 1576, got {len(pool)}")
    vol = pool[["trace", "vm_id", "volatility"]].copy()
    vol["vm_id"] = vol["vm_id"].astype(str)
    vol["trace"] = vol["trace"].astype(str)
    q1, q2 = vol["volatility"].quantile([1 / 3, 2 / 3])
    vol["volatility_tier"] = np.where(
        vol.volatility <= q1,
        "low",
        np.where(vol.volatility <= q2, "medium", "high"),
    )
    vol.attrs["tier_cutoffs"] = {"q1": float(q1), "q2": float(q2)}
    return vol.sort_values(["trace", "vm_id"]).reset_index(drop=True)


def classify_protocol_exclusion(row: dict[str, Any]) -> str | None:
    """Map metadata-only audit fields to frozen exclusion codes. Performance-blind."""
    if row.get("corrupt_or_nonfinite"):
        return "corrupt_or_nonfinite_source_data"
    if row.get("protocol_invalid_timeline"):
        return "protocol_invalid_timeline_or_schema"
    if int(row.get("bootstrap_observations", 0)) < FEATURE_HISTORY_SLOTS:
        return "insufficient_bootstrap_history"
    if int(row.get("globally_verifiable_opportunities", 0)) <= 0:
        return "insufficient_globally_verifiable_evaluation_origins"
    if int(row.get("window24_eligible", 0)) <= 0 or int(row.get("valid_feature_rows", 0)) < 0:
        # valid_feature_rows < 0 is impossible; window24==0 is the hard gate.
        if int(row.get("window24_eligible", 0)) <= 0:
            return "insufficient_exact_grid_feature_or_window_validity"
    # Do NOT exclude on potential_eligibility_review / <95% fractions alone.
    return None


def audit_candidate(repo: Path, trace: str, vm_id: str, bootstrap_fraction: float = 0.30) -> dict[str, Any]:
    path = repo / "data/raw" / trace / f"{vm_id}.csv"
    try:
        frame = load_vm_csv(str(path))
    except Exception as exc:  # noqa: BLE001 — map load failures to protocol codes
        msg = str(exc).lower()
        code = (
            "protocol_invalid_timeline_or_schema"
            if "timestamp" in msg or "schema" in msg or "column" in msg
            else "corrupt_or_nonfinite_source_data"
        )
        return {
            "trace": trace,
            "vm_id": str(vm_id),
            "exclusion_code": code,
            "detail": f"{type(exc).__name__}: {exc}",
            "corrupt_or_nonfinite": code == "corrupt_or_nonfinite_source_data",
            "protocol_invalid_timeline": code == "protocol_invalid_timeline_or_schema",
            "bootstrap_observations": 0,
            "globally_verifiable_opportunities": 0,
            "window24_eligible": 0,
            "valid_feature_rows": 0,
            "observation_count": 0,
            "first_timestamp": None,
            "last_timestamp": None,
        }
    if frame.empty or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        return {
            "trace": trace,
            "vm_id": str(vm_id),
            "exclusion_code": "protocol_invalid_timeline_or_schema",
            "detail": "non-unique or non-monotonic timestamps",
            "corrupt_or_nonfinite": False,
            "protocol_invalid_timeline": True,
            "bootstrap_observations": 0,
            "globally_verifiable_opportunities": 0,
            "window24_eligible": 0,
            "valid_feature_rows": 0,
            "observation_count": int(len(frame)),
            "first_timestamp": None if frame.empty else str(frame.index[0]),
            "last_timestamp": None if frame.empty else str(frame.index[-1]),
        }
    metrics = ["CPU usage [%]", "Memory usage [%]"]
    values = frame[metrics].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        return {
            "trace": trace,
            "vm_id": str(vm_id),
            "exclusion_code": "corrupt_or_nonfinite_source_data",
            "detail": "nonfinite CPU/memory values",
            "corrupt_or_nonfinite": True,
            "protocol_invalid_timeline": False,
            "bootstrap_observations": 0,
            "globally_verifiable_opportunities": 0,
            "window24_eligible": 0,
            "valid_feature_rows": 0,
            "observation_count": int(len(frame)),
            "first_timestamp": str(frame.index[0]),
            "last_timestamp": str(frame.index[-1]),
        }
    row = audit_frame(frame, trace, vm_id, bootstrap_fraction)
    row["corrupt_or_nonfinite"] = False
    row["protocol_invalid_timeline"] = False
    row["observation_count"] = int(len(frame))
    row["first_timestamp"] = str(frame.index[0])
    row["last_timestamp"] = str(frame.index[-1])
    row["exclusion_code"] = classify_protocol_exclusion(row)
    row["detail"] = None if row["exclusion_code"] is None else "protocol-validity metadata gate"
    return row


def build_execution_cohort(repo: Path, dataset) -> tuple[CohortManifest, pd.DataFrame, pd.DataFrame]:
    """Apply protocol-validity exclusions to the frozen 1,558-candidate set."""
    validate_cohort_manifest()
    candidates = read_json(COHORT_JSON)["entities"]
    assert_pilots_excluded(candidates)
    if len(candidates) != 1558:
        raise ValueError("candidate confirmatory cohort must be exactly 1558 before exclusions")
    rows = [audit_candidate(repo, e["trace"], e["vm_id"]) for e in candidates]
    table = pd.DataFrame(rows)
    if len(table) != 1558:
        raise ValueError("exclusion audit must cover every candidate")
    codes = set(table["exclusion_code"].dropna().unique())
    if not codes <= set(PROTOCOL_EXCLUSION_CODES):
        raise ValueError(f"unknown exclusion codes: {codes - set(PROTOCOL_EXCLUSION_CODES)}")
    entities = []
    for row in table.sort_values(["trace", "vm_id"]).itertuples():
        excluded = pd.notna(row.exclusion_code)
        code = None if not excluded else str(row.exclusion_code)
        entities.append(
            CohortEntity(
                row.trace,
                str(row.vm_id),
                not excluded,
                code,
                int(row.observation_count),
                None if pd.isna(row.first_timestamp) else str(row.first_timestamp),
                None if pd.isna(row.last_timestamp) else str(row.last_timestamp),
            )
        )
    included = table[table.exclusion_code.isna()].copy()
    excluded = table[table.exclusion_code.notna()].copy()
    assert_pilots_excluded(included)
    manifest = CohortManifest(
        dataset.dataset_id,
        dataset.sha256,
        FILTERING_RULE_VERSION,
        {
            "minimum_observations": 2000,
            "candidate_source": "configs/materna_confirmatory_cohort_v1.json",
            "candidate_count_before_protocol_exclusions": 1558,
            "protocol_exclusion_codes": list(PROTOCOL_EXCLUSION_CODES),
            "gap_audit_199_flags": "diagnostic_only_not_automatic_exclusion",
            "design_fingerprint": frozen_hashes()["design_fingerprint"],
        },
        tuple(entities),
        utc_now(),
    )
    return manifest, included, excluded


def _periodic_delay_stats(refresh_log: list[dict]) -> dict[str, float]:
    delays = []
    for event in refresh_log:
        nominal = event.get("nominal_scheduled_time")
        actual = event.get("actual_commit_time")
        if nominal and actual:
            delays.append(
                (pd.Timestamp(actual) - pd.Timestamp(nominal)).total_seconds()
            )
    if not delays:
        return {
            "refresh_delay_mean_seconds": 0.0,
            "refresh_delay_max_seconds": 0.0,
            "n_delayed_refreshes": 0,
        }
    arr = np.asarray(delays, dtype=float)
    return {
        "refresh_delay_mean_seconds": float(arr.mean()),
        "refresh_delay_max_seconds": float(arr.max()),
        "n_delayed_refreshes": int((arr > 0).sum()),
    }


def run_confirmatory_vm(entity: dict, repo_root: str | Path) -> dict[str, Any]:
    """Evaluate all five frozen methods on one eligible VM."""
    repo_root = Path(repo_root)
    trace, vm_id = entity["trace"], str(entity["vm_id"])
    start = pd.Timestamp.utcnow()
    inputs = prepare_vm_inputs(trace, vm_id, repo_root=repo_root, with_predictors=False)
    if inputs.predictors is not None or inputs.predictions is not None:
        raise ValueError("confirmatory execution must remain predictor-free")
    if inputs.ground_truth is None or len(inputs.ground_truth) == 0:
        raise ValueError("insufficient_globally_verifiable_evaluation_origins")
    rows = []
    eval_fingerprints = []
    for method_id in PRIMARY_METHODS:
        replay = replay_from_inputs(inputs, factory_for(method_id))
        result = evaluate_replay(replay, include_records=True)
        records = pd.DataFrame(result["evaluation_records"])
        if len(records) == 0:
            raise ValueError("insufficient_globally_verifiable_evaluation_origins")
        stamps = tuple(pd.Timestamp(ts).isoformat() for ts in records["eval_timestamp"])
        eval_fingerprints.append(fingerprint(stamps))
        for col in ("cpu_class_accuracy", "memory_class_accuracy", "cpu_p95_mae", "mem_p95_mae"):
            if not np.isfinite(result[col]):
                raise ValueError(f"nonfinite endpoint {col}")
        delay = _periodic_delay_stats(result["refresh_log"])
        row = {
            "trace": trace,
            "vm_id": vm_id,
            "volatility_tier": entity.get("volatility_tier"),
            "volatility": entity.get("volatility"),
            "method_id": method_id,
            "run_status": "ok",
            "causal_protocol": result["causal_protocol"],
            "accounting_schema": result["accounting_schema"],
            "cpu_class_accuracy": float(result["cpu_class_accuracy"]),
            "memory_class_accuracy": float(result["memory_class_accuracy"]),
            "cpu_p95_mae": float(result["cpu_p95_mae"]),
            "mem_p95_mae": float(result["mem_p95_mae"]),
            "cpu_p95_bias": float(records.cpu_p95_bias.mean()),
            "mem_p95_bias": float(records.mem_p95_bias.mean()),
            "n_eval_points_verified": int(result["n_eval_points_verified"]),
            "age_mean_hours": float(records.profile_age_hours.mean()),
            "age_median_hours": float(records.profile_age_hours.median()),
            "age_p95_hours": float(np.quantile(records.profile_age_hours.to_numpy(dtype=float), 0.95)),
            "age_max_hours": float(records.profile_age_hours.max()),
            "age_zero_pct": float(100.0 * (records.profile_age_seconds == 0).mean()),
            **{name: int(result[name]) for name in ACCOUNTING_METRICS if name in result},
            **delay,
            "evaluation_stamp_fingerprint": eval_fingerprints[-1],
        }
        rows.append(row)
    if len(set(eval_fingerprints)) != 1:
        raise ValueError("methods must share identical verified evaluation timestamps")
    require_accounting_metrics(pd.DataFrame(rows))
    elapsed = (pd.Timestamp.utcnow() - start).total_seconds()
    return {
        "rows": rows,
        "diagnostics": {
            "trace": trace,
            "vm_id": vm_id,
            "methods": 5,
            "n_eval_points_verified": rows[0]["n_eval_points_verified"],
            "evaluation_stamp_fingerprint": eval_fingerprints[0],
            "wall_seconds": float(elapsed),
            "status": "COMPLETED",
        },
    }


def design_binding_record() -> dict[str, Any]:
    hashes = frozen_hashes()
    design = read_json(CONFIG_JSON)
    config = confirmatory_config()
    return {
        "schema_version": design["schema_version"],
        "amendment": design["amendment"],
        "study_framing": design["study_framing"],
        "gate_status": design["gate_status"],
        "hashes": hashes,
        "methods": list(PRIMARY_METHODS),
        "comparison_families": {
            name: [{"treatment": a, "control": b} for a, b in pairs]
            for name, pairs in COMPARISON_FAMILIES.items()
        },
        "experiment_config_sha256": config.sha256,
    }
