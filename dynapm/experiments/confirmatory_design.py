"""V2.5 confirmatory design freeze: load, validate, and hash frozen inputs.

No scientific run. Does not read confirmatory VM outcome tables.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_JSON = REPO_ROOT / "configs" / "materna_confirmatory_v1.json"
CONFIG_YAML = REPO_ROOT / "configs" / "materna_confirmatory_v1.yaml"
COHORT_JSON = REPO_ROOT / "configs" / "materna_confirmatory_cohort_v1.json"
KEPT_VMS = REPO_ROOT / "dynapm" / "data" / "kept_vms.json"

SCHEMA_VERSION = "materna-confirmatory-design-v1"
GATE_STATUS = "BLOCKED"
BLOCKER = "practical_effect_margins_unassigned"

PERMANENT_PILOT_EXCLUSIONS: tuple[tuple[str, str], ...] = (
    ("Materna-Trace-1", "143"),
    ("Materna-Trace-1", "213"),
    ("Materna-Trace-1", "374"),
    ("Materna-Trace-1", "64"),
    ("Materna-Trace-1", "76"),
    ("Materna-Trace-1", "96"),
    ("Materna-Trace-2", "11"),
    ("Materna-Trace-2", "207"),
    ("Materna-Trace-2", "388"),
    ("Materna-Trace-2", "396"),
    ("Materna-Trace-2", "398"),
    ("Materna-Trace-2", "516"),
    ("Materna-Trace-3", "127"),
    ("Materna-Trace-3", "133"),
    ("Materna-Trace-3", "151"),
    ("Materna-Trace-3", "212"),
    ("Materna-Trace-3", "224"),
    ("Materna-Trace-3", "83"),
)

PRIMARY_METHODS: tuple[str, ...] = (
    "static",
    "pw_12h",
    "pw_6h",
    "pw_3h",
    "full_rewrite",
)

COMPARISON_FAMILIES: dict[str, tuple[tuple[str, str], ...]] = {
    "F1_maintenance_vs_none": (
        ("pw_12h", "static"),
        ("pw_6h", "static"),
        ("pw_3h", "static"),
    ),
    "F2_cadence_increments": (
        ("pw_6h", "pw_12h"),
        ("pw_3h", "pw_6h"),
    ),
    "F3_high_cost_limit": (
        ("full_rewrite", "pw_3h"),
    ),
}

PRIMARY_FIDELITY_ENDPOINTS: tuple[str, ...] = (
    "cpu_class_correctness",
    "memory_class_correctness",
    "cpu_p95_profile_mae",
    "memory_p95_profile_mae",
)

PRIMARY_COST_ENDPOINT = "n_refresh_events"

SECONDARY_ENDPOINTS: tuple[str, ...] = (
    "n_field_writes",
    "n_field_value_changes",
    "profile_age_distribution",
    "refresh_eligibility_delays",
    "verified_evaluation_point_count",
    "bias",
)

PROTOCOL_EXCLUSION_CODES: tuple[str, ...] = (
    "insufficient_bootstrap_history",
    "insufficient_exact_grid_feature_or_window_validity",
    "insufficient_globally_verifiable_evaluation_origins",
    "corrupt_or_nonfinite_source_data",
    "protocol_invalid_timeline_or_schema",
)

# Outcome artifact patterns that must not be read by V2.5 tooling.
FORBIDDEN_OUTCOME_GLOBS: tuple[str, ...] = (
    "**/per_vm*.parquet",
    "**/policy_results*.parquet",
    "**/evaluation_snapshots*.parquet",
    "**/class_accuracy*",
    "**/profile_mae*",
)


def emit_yaml(value: Any, indent: int = 0) -> str:
    """Minimal YAML emitter for nested dict/list/scalars (no PyYAML dependency)."""
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return pad + "{}\n"
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(emit_yaml(item, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{pad}{key}: {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        if not value:
            return pad + "[]\n"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(emit_yaml(item, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return pad + _yaml_scalar(value) + "\n"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    text = str(value)
    if text == "" or any(ch in text for ch in ":#{}[],&*!|>'\"%@`") or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    return text


def design_document() -> dict[str, Any]:
    """Frozen confirmatory design object (margins intentionally unassigned)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "V2.5",
        "gate_status": GATE_STATUS,
        "blocker": BLOCKER,
        "blocker_rationale": (
            "Defensible numeric practical-benefit and acceptable-harm margins for the four "
            "primary fidelity endpoints cannot be established from metric semantics, profile "
            "resolution, or an external operational requirement without arbitrary round-number "
            "choices. Deriving margins from the 18-VM pilot effects is forbidden. Margins remain "
            "null; V3 execution stays blocked until a separate authorized margin freeze assigns "
            "them without confirmatory outcome access and without pilot-effect calibration."
        ),
        "withdrawn_claims": ["C1_forecasting_superiority", "C2_adaptive_refresh_superiority"],
        "branding": {
            "repository_name": "DynAPM",
            "continuity_note": (
                "Repository name may remain for continuity; manuscript framing must not imply "
                "validated adaptive or predictive functionality."
            ),
            "working_contribution": (
                "A rigorous empirical methodology and benchmark for application-profile "
                "maintenance, refresh cadence, freshness, cost, and downstream validity."
            ),
            "manuscript_title": None,
        },
        "research_questions": {
            "RQ1": "Does periodic observation-window profile maintenance materially improve profile fidelity over Static?",
            "RQ2": "How do 12h, 6h, and 3h periodic refresh cadences trade profile fidelity against maintenance cost?",
            "RQ3": "Does Full-Rewrite provide practically meaningful fidelity improvement over PW-3h sufficient to justify its much higher refresh/write cost?",
            "RQ4": "Are these conclusions consistent across traces, resources, and predefined volatility strata?",
        },
        "protocol": {
            "temporal": "causal-timeline-v3",
            "evaluation_grid": "phase-balanced-hourly-v1",
            "accounting": "refresh-accounting-v1",
            "observation_window": "paired-observation-window-24h-v1",
            "observation_window_semantics": "(t-24h,t], >=200/288 paired finite CPU+memory slots where refresh eligibility applies",
        },
        "cohort": {
            "corpus": "Materna",
            "retained_pool_source": "dynapm/data/kept_vms.json",
            "retained_pool_count": 1576,
            "permanent_pilot_exclusion_count": 18,
            "permanent_pilot_exclusions": [
                {"trace": t, "vm_id": v} for t, v in PERMANENT_PILOT_EXCLUSIONS
            ],
            "candidate_confirmatory_count_before_protocol_exclusions": 1558,
            "cohort_manifest": "configs/materna_confirmatory_cohort_v1.json",
            "gap_audit_199_flags": "diagnostic_only_not_automatic_exclusion",
            "protocol_exclusion_codes": list(PROTOCOL_EXCLUSION_CODES),
            "forbidden_exclusion_basis": [
                "method_performance",
                "favorable_or_unfavorable_effect_size",
                "post_hoc_gap_flag_without_protocol_rule",
            ],
            "statistical_unit": "vm",
        },
        "methods": {
            "primary": list(PRIMARY_METHODS),
            "excluded_from_primary_confirmation": [
                "periodic_predictor",
                "reactive",
                "dynapm_v3",
                "budget_matched",
                "adwin_trigger",
                "any_forecasting_or_adaptive_method",
            ],
            "shared_content_semantics": (
                "Identical observation-window content for Static/PW/Full-Rewrite: "
                "(t-24h,t], >=200/288 paired finite CPU+memory slots where refresh eligibility applies."
            ),
        },
        "endpoints": {
            "primary_fidelity": list(PRIMARY_FIDELITY_ENDPOINTS),
            "primary_maintenance_cost": PRIMARY_COST_ENDPOINT,
            "secondary_cost_diagnostic": list(SECONDARY_ENDPOINTS),
            "aggregation": "per_vm_then_paired_across_vms",
            "forbidden": "timestamp_level_pseudo_replication_as_statistical_unit",
        },
        "comparison_families": {
            name: [{"treatment": a, "control": b} for a, b in pairs]
            for name, pairs in COMPARISON_FAMILIES.items()
        },
        "practical_effect_margins": {
            "status": "UNASSIGNED",
            "blocks_v25_pass": True,
            "blocks_v3_execution": True,
            "source_policy": (
                "Must be justified from metric semantics, measurement/profile resolution, "
                "operational interpretation, and/or external domain rationale. Must NOT be "
                "derived from observed 18-VM pilot effect sizes or confirmatory outcomes."
            ),
            "cpu_class_correctness": {
                "practical_benefit_margin": None,
                "acceptable_harm_margin": None,
                "unit": "accuracy_fraction_points",
                "favorable_direction": "higher_is_better",
                "rationale_status": "insufficient_without_arbitrary_choice",
                "rationale": (
                    "Class correctness is the fraction of evaluation origins whose profile mean "
                    "utilization class (idle/low/medium/high/burst from bootstrap p20/p40/p60/p80 "
                    "gates) matches truth. Without a documented consumer that maps class errors to "
                    "operational cost, any numeric Δaccuracy margin is an arbitrary round number. "
                    "Pilot Static→PW gains are exploratory and must not calibrate this margin."
                ),
                "sources_consulted": [
                    "dynapm/core/discretization.py class gates",
                    "docs/protocol.md causal evaluation semantics",
                    "no engineering SLO or provisioning misclassification cost available in-repo",
                ],
            },
            "memory_class_correctness": {
                "practical_benefit_margin": None,
                "acceptable_harm_margin": None,
                "unit": "accuracy_fraction_points",
                "favorable_direction": "higher_is_better",
                "rationale_status": "insufficient_without_arbitrary_choice",
                "rationale": (
                    "Same class taxonomy and consumer gap as CPU class correctness; resource "
                    "identity alone does not supply a non-arbitrary margin."
                ),
                "sources_consulted": [
                    "dynapm/core/discretization.py class gates",
                    "docs/protocol.md causal evaluation semantics",
                ],
            },
            "cpu_p95_profile_mae": {
                "practical_benefit_margin": None,
                "acceptable_harm_margin": None,
                "unit": "utilization_percentage_points",
                "favorable_direction": "lower_is_better",
                "rationale_status": "insufficient_without_arbitrary_choice",
                "rationale": (
                    "p95-profile MAE is continuous utilization error. Measurement resolution does "
                    "not imply a practical threshold: rightsizing literature discusses capacity "
                    "headroom for allocation decisions, not a transferable MAE margin for offline "
                    "profile fidelity. Mapping capacity headroom to MAE requires an unstated "
                    "consumer model; inventing 0.5/1.0 pp would be arbitrary."
                ),
                "sources_consulted": [
                    "docs/protocol.md profile evaluation",
                    "no in-repo downstream resource-controller tolerance for profile MAE",
                ],
            },
            "memory_p95_profile_mae": {
                "practical_benefit_margin": None,
                "acceptable_harm_margin": None,
                "unit": "utilization_percentage_points",
                "favorable_direction": "lower_is_better",
                "rationale_status": "insufficient_without_arbitrary_choice",
                "rationale": (
                    "Same continuous-error and consumer-model gap as CPU p95-profile MAE."
                ),
                "sources_consulted": [
                    "docs/protocol.md profile evaluation",
                ],
            },
        },
        "statistics": {
            "unit": "vm",
            "paired_differences": "treatment_minus_control_per_vm",
            "report": [
                "median_effect",
                "mean_effect",
                "paired_bootstrap_95ci",
                "paired_nonparametric_test",
                "zero_and_tie_handling",
                "effect_size",
                "multiplicity_adjusted_p",
                "statistical_significance",
                "practical_significance",
            ],
            "bootstrap": {
                "repetitions": 10000,
                "seed": 20251022,
                "ci_level": 0.95,
                "method": "percentile_of_paired_mean_and_median_differences",
            },
            "paired_test": {
                "name": "wilcoxon_signed_rank",
                "zero_method": "wilcox",
                "tie_policy": "report_effective_n_and_use_documented_approximation_or_permutation",
                "all_ties_rule": "effect_zero_p_equals_1",
            },
            "effect_size": {
                "primary": "paired_median_difference",
                "standardized": "mean_difference_divided_by_sd_of_paired_differences",
                "undefined_when": "sd_of_paired_differences_equals_zero",
            },
            "multiplicity": {
                "method": "holm",
                "alpha": 0.05,
                "scope": "within_each_comparison_family_separately",
                "families": list(COMPARISON_FAMILIES.keys()),
            },
            "robustness_analyses": {
                "primary": False,
                "includes": [
                    "volatility_tier_strata",
                    "trace_strata",
                    "resource_specific_endpoints",
                ],
                "claim_rule": "no_subgroup_driven_primary_claims_unless_predefined_here",
            },
            "practical_significance_rule": (
                "Requires assigned practical_effect_margins. Until margins are assigned, "
                "practical significance is reported as NOT_EVALUABLE and cannot support GO."
            ),
        },
        "decision_logic": {
            "status": "TEMPLATES_FROZEN_MARGINS_REQUIRED",
            "rules": [
                {
                    "id": "R1_better_requires_practical_margin",
                    "text": (
                        "Declare a method 'better' on a fidelity endpoint only when the paired "
                        "effect is directionally favorable AND the practical-benefit margin "
                        "criterion is met (point estimate and/or CI rule as assigned with margins); "
                        "p-value alone is insufficient."
                    ),
                },
                {
                    "id": "R2_negligible_fidelity_blocks_added_cost",
                    "text": (
                        "Do not recommend an added-cost method when its fidelity improvement over "
                        "the cheaper comparator is practically negligible under the assigned margins."
                    ),
                },
                {
                    "id": "R3_full_rewrite_dominance",
                    "text": (
                        "Full-Rewrite is dominated if its incremental fidelity benefit over PW-3h "
                        "fails the practical-benefit criterion while requiring materially greater "
                        "refresh cost (n_refresh_events)."
                    ),
                },
                {
                    "id": "R4_negative_null_valid",
                    "text": (
                        "Negative and null findings are valid confirmatory outcomes and may support "
                        "NO-GO or narrowed claims."
                    ),
                },
                {
                    "id": "R5_no_expected_winners",
                    "text": "Do not encode expected winners; comparisons remain those frozen in F1–F3.",
                },
                {
                    "id": "R6_margins_gate",
                    "text": (
                        "While practical_effect_margins.status is UNASSIGNED, overall confirmatory "
                        "GO is impossible; V2.5 remains BLOCKED and V3 must not execute."
                    ),
                },
            ],
        },
        "future_gates": {
            "V3": "Materna confirmatory non-adaptive study",
            "V4": "independent production-corpus suitability/acquisition",
            "V5": "second-corpus replication, preferably Google ClusterData 2019 if suitability remains valid",
            "V6": "maintenance-cost/service benchmark",
            "V7": "Kubernetes profile→resource-management harness",
            "V8": "repeated operational/system validation",
            "V9": "final claim audit / venue decision",
            "claim_rule": "Do not claim C3–C6 before their corresponding gates pass.",
        },
        "execution_guards": {
            "scientific_run_in_v25": False,
            "access_confirmatory_outcomes": False,
            "new_predictor_trigger_selector_cadence_or_algorithm": False,
            "use_pilot_effects_to_choose_margins_or_hypotheses": False,
        },
    }


def build_candidate_cohort_from_kept(kept_path: Path = KEPT_VMS) -> list[dict[str, str]]:
    kept = json.loads(kept_path.read_text(encoding="utf-8"))
    pairs = sorted((e["trace"], str(e["vm_id"])) for e in kept)
    if len(pairs) != 1576:
        raise ValueError(f"retained pool must be 1576, got {len(pairs)}")
    pilot = set(PERMANENT_PILOT_EXCLUSIONS)
    if not pilot.issubset(set(pairs)):
        missing = sorted(pilot - set(pairs))
        raise ValueError(f"pilot exclusions missing from retained pool: {missing}")
    return [{"trace": t, "vm_id": v} for t, v in pairs if (t, v) not in pilot]


def load_cohort_manifest(path: Path = COHORT_JSON) -> dict[str, Any]:
    return read_json(path)


def validate_cohort_manifest(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest if manifest is not None else load_cohort_manifest()
    entities = manifest["entities"]
    if len(entities) != 1558:
        raise ValueError(f"expected 1558 confirmatory candidates, got {len(entities)}")
    rebuilt = build_candidate_cohort_from_kept()
    if entities != rebuilt:
        raise ValueError("cohort entities do not match kept_vms minus permanent pilots")
    if fingerprint(entities) != manifest["entities_fingerprint"]:
        raise ValueError("entities_fingerprint mismatch")
    pilot_ids = {(e["trace"], e["vm_id"]) for e in manifest["permanent_pilot_exclusions"]}
    if pilot_ids != set(PERMANENT_PILOT_EXCLUSIONS):
        raise ValueError("permanent pilot exclusion set mismatch")
    entity_ids = {(e["trace"], e["vm_id"]) for e in entities}
    if pilot_ids & entity_ids:
        raise ValueError("pilot IDs present in confirmatory candidate cohort")
    return {
        "candidate_count": len(entities),
        "entities_fingerprint": manifest["entities_fingerprint"],
        "cohort_file_sha256": file_sha256(COHORT_JSON),
    }


def validate_design(design: dict[str, Any] | None = None) -> dict[str, Any]:
    design = design if design is not None else design_document()
    if design["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported design schema")
    if design["gate_status"] != GATE_STATUS:
        raise ValueError("gate_status must remain BLOCKED while margins are unassigned")
    if design["practical_effect_margins"]["status"] != "UNASSIGNED":
        raise ValueError("margins must be UNASSIGNED for this freeze")
    for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
        block = design["practical_effect_margins"][endpoint]
        if block["practical_benefit_margin"] is not None or block["acceptable_harm_margin"] is not None:
            raise ValueError(f"{endpoint} margins must be null in this freeze")
    methods = design["methods"]["primary"]
    if methods != list(PRIMARY_METHODS):
        raise ValueError("primary method matrix mismatch")
    for family, pairs in COMPARISON_FAMILIES.items():
        frozen = [
            (row["treatment"], row["control"])
            for row in design["comparison_families"][family]
        ]
        if tuple(frozen) != pairs:
            raise ValueError(f"comparison family mismatch: {family}")
    stats = design["statistics"]["bootstrap"]
    if stats["repetitions"] != 10000 or stats["seed"] != 20251022:
        raise ValueError("bootstrap repetitions/seed mismatch")
    return {
        "design_fingerprint": fingerprint(design),
        "gate_status": design["gate_status"],
        "blocker": design["blocker"],
    }


def write_frozen_config_files(root: Path = REPO_ROOT) -> dict[str, str]:
    design = design_document()
    json_path = root / "configs" / "materna_confirmatory_v1.json"
    yaml_path = root / "configs" / "materna_confirmatory_v1.yaml"
    json_path.write_text(canonical_json(design) + "\n", encoding="utf-8")
    yaml_path.write_text(
        "# Frozen by V2.5 — authoritative twin is materna_confirmatory_v1.json\n"
        + emit_yaml(design),
        encoding="utf-8",
    )
    cohort_info = validate_cohort_manifest()
    design_info = validate_design(design)
    return {
        "design_fingerprint": design_info["design_fingerprint"],
        "config_json_sha256": file_sha256(json_path),
        "config_yaml_sha256": file_sha256(yaml_path),
        "cohort_entities_fingerprint": cohort_info["entities_fingerprint"],
        "cohort_file_sha256": cohort_info["cohort_file_sha256"],
        "kept_vms_sha256": file_sha256(KEPT_VMS),
        "gate_status": design_info["gate_status"],
        "blocker": design_info["blocker"],
    }


def frozen_hashes() -> dict[str, str]:
    if not CONFIG_JSON.is_file():
        raise FileNotFoundError(CONFIG_JSON)
    design = read_json(CONFIG_JSON)
    design_info = validate_design(design)
    cohort_info = validate_cohort_manifest()
    return {
        "design_fingerprint": design_info["design_fingerprint"],
        "config_json_sha256": file_sha256(CONFIG_JSON),
        "config_yaml_sha256": file_sha256(CONFIG_YAML),
        "cohort_entities_fingerprint": cohort_info["entities_fingerprint"],
        "cohort_file_sha256": cohort_info["cohort_file_sha256"],
        "kept_vms_sha256": file_sha256(KEPT_VMS),
        "gate_status": design_info["gate_status"],
        "blocker": design_info["blocker"],
    }
