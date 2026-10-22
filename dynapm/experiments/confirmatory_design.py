"""V2.5 / V2.5A confirmatory design freeze: load, validate, and hash frozen inputs.

Current authoritative design is estimation-first amendment v1.1 (V2.5A).
The original superiority-margin freeze v1 is preserved under configs/materna_confirmatory_v1.*
for provenance and must not be rewritten.

No scientific run. Does not read confirmatory VM outcome tables.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json

REPO_ROOT = Path(__file__).resolve().parents[2]

# Current authoritative amendment (V2.5A).
CONFIG_JSON = REPO_ROOT / "configs" / "materna_confirmatory_v1_1.json"
CONFIG_YAML = REPO_ROOT / "configs" / "materna_confirmatory_v1_1.yaml"

# Immutable V2.5 original freeze (blocked on margins) — provenance only.
LEGACY_CONFIG_JSON = REPO_ROOT / "configs" / "materna_confirmatory_v1.json"
LEGACY_CONFIG_YAML = REPO_ROOT / "configs" / "materna_confirmatory_v1.yaml"

COHORT_JSON = REPO_ROOT / "configs" / "materna_confirmatory_cohort_v1.json"
KEPT_VMS = REPO_ROOT / "dynapm" / "data" / "kept_vms.json"

SCHEMA_VERSION = "materna-confirmatory-design-v1.1"
LEGACY_SCHEMA_VERSION = "materna-confirmatory-design-v1"
AMENDMENT = "V2.5A"
GATE_STATUS = "PASS"
BLOCKER = None

# Provenance hashes of the original V2.5 freeze (must remain byte-identical).
LEGACY_DESIGN_FINGERPRINT = "d3c94bcdcf9cb626d915187ca8d5071c26197464ad6154e3f527f1f4d79bac26"
LEGACY_CONFIG_JSON_SHA256 = "4ce8fb3a68005717a0a4062ea535d647b3e6a8cf75bc61bda3404cd682131caa"
LEGACY_CONFIG_YAML_SHA256 = "4a27b96b71a9ad7c14cef1ca3cb2255461edc1b9f42a5361c09f8cf5828e7e5d"
COHORT_ENTITIES_FINGERPRINT = "3a590437f108493b085f1cb34765e76bd5f10fa233a48c2e96f6bf3bd54b7939"
COHORT_FILE_SHA256 = "9adac57a35af69bf83ce5ee0751818ec242d04138d983d95f3441d0c278e02cd"

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

FORBIDDEN_OUTCOME_GLOBS: tuple[str, ...] = (
    "**/per_vm*.parquet",
    "**/policy_results*.parquet",
    "**/evaluation_snapshots*.parquet",
    "**/class_accuracy*",
    "**/profile_mae*",
)

EXTERNAL_RATIONALE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "asa_pvalues_2016",
        "citation": (
            "Wasserstein, R. L., & Lazar, N. A. (2016). The ASA Statement on p-Values: "
            "Context, Process, and Purpose. The American Statistician, 70(2), 129–133."
        ),
        "doi": "10.1080/00031305.2016.1154108",
        "url": "https://doi.org/10.1080/00031305.2016.1154108",
        "use": (
            "Scientific conclusions and policy decisions must not rest on p-value thresholds "
            "alone; effect sizes and uncertainty are required. Separates statistical "
            "distinguishability from practical/operational superiority."
        ),
        "role": "external_methodology_rationale_not_dynapm_evidence",
    },
    {
        "id": "kubernetes_hpa_resource_utilization",
        "citation": "Kubernetes documentation — Horizontal Pod Autoscaling (resource metrics).",
        "url": "https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/",
        "use": (
            "Operational CPU/memory utilization is defined relative to configured resource "
            "requests and controller targets; mapping offline profile-utilization error to "
            "autoscaling/SLO outcomes therefore depends on capacity, request/limit mapping, "
            "and controller policy — not a universal profile-level margin."
        ),
        "role": "external_systems_rationale_not_dynapm_evidence",
    },
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
    """Current frozen confirmatory design (V2.5A estimation-first amendment)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "V2.5",
        "amendment": AMENDMENT,
        "gate_status": GATE_STATUS,
        "blocker": BLOCKER,
        "study_framing": "estimation_first",
        "amends": {
            "previous_schema_version": LEGACY_SCHEMA_VERSION,
            "previous_config_json": "configs/materna_confirmatory_v1.json",
            "previous_config_yaml": "configs/materna_confirmatory_v1.yaml",
            "previous_design_fingerprint": LEGACY_DESIGN_FINGERPRINT,
            "previous_config_json_sha256": LEGACY_CONFIG_JSON_SHA256,
            "previous_config_yaml_sha256": LEGACY_CONFIG_YAML_SHA256,
            "change_summary": (
                "Replace practical-superiority / numeric-margin GO criteria with a "
                "pre-specified estimation study. Cohort, methods, endpoints, F1–F3, "
                "bootstrap B/seed, Wilcoxon, and Holm remain unchanged. Numeric practical "
                "margins are not invented; profile-level practical significance is "
                "NOT_DEFINED_AT_PROFILE_LEVEL. Operational benefit remains C4."
            ),
        },
        "withdrawn_claims": ["C1_forecasting_superiority", "C2_adaptive_refresh_superiority"],
        "claim_status": {
            "C3": "UNPROVEN",
            "C4": "UNPROVEN",
            "C5": "UNPROVEN",
            "C6": "UNPROVEN",
        },
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
            "RQ1": (
                "What are the magnitude and uncertainty of paired fidelity and cost effects "
                "of periodic observation-window maintenance (PW-12h, PW-6h, PW-3h) relative "
                "to Static?"
            ),
            "RQ2": (
                "What are the magnitude and uncertainty of paired fidelity and cost effects "
                "for successive cadence increments (PW-6h vs PW-12h; PW-3h vs PW-6h)?"
            ),
            "RQ3": (
                "What is the incremental fidelity effect of Full-Rewrite relative to PW-3h, "
                "and what is the associated incremental refresh, write, and change cost?"
            ),
            "RQ4": (
                "Are the estimated effects directionally and quantitatively consistent across "
                "predefined traces, resources, and volatility strata?"
            ),
        },
        "protocol": {
            "temporal": "causal-timeline-v3",
            "evaluation_grid": "phase-balanced-hourly-v1",
            "accounting": "refresh-accounting-v1",
            "observation_window": "paired-observation-window-24h-v1",
            "observation_window_semantics": (
                "(t-24h,t], >=200/288 paired finite CPU+memory slots where refresh "
                "eligibility applies"
            ),
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
                "(t-24h,t], >=200/288 paired finite CPU+memory slots where refresh "
                "eligibility applies."
            ),
        },
        "endpoints": {
            "primary_fidelity": list(PRIMARY_FIDELITY_ENDPOINTS),
            "primary_maintenance_cost": PRIMARY_COST_ENDPOINT,
            "secondary_cost_diagnostic": list(SECONDARY_ENDPOINTS),
            "aggregation": "per_vm_then_paired_across_vms",
            "forbidden": "timestamp_level_pseudo_replication_as_statistical_unit",
            "favorable_directions": {
                "cpu_class_correctness": "higher_is_better",
                "memory_class_correctness": "higher_is_better",
                "cpu_p95_profile_mae": "lower_is_better",
                "memory_p95_profile_mae": "lower_is_better",
                "n_refresh_events": "lower_is_better_for_cost",
            },
        },
        "comparison_families": {
            name: [{"treatment": a, "control": b} for a, b in pairs]
            for name, pairs in COMPARISON_FAMILIES.items()
        },
        "practical_significance": {
            "status": "NOT_DEFINED_AT_PROFILE_LEVEL",
            "numeric_margins": "not_invented",
            "blocks_v25_pass": False,
            "blocks_v3_execution": False,
            "interpretation": (
                "V3 reports estimation quantities only. Profile-level numeric practical-"
                "benefit / acceptable-harm margins are explicitly not defined. Statistical "
                "distinguishability must never be translated into operational superiority."
            ),
            "rationale_why_numeric_margins_unavailable": {
                "profile_error_units": (
                    "Primary fidelity errors are utilization percentages / class fractions "
                    "on offline profiles, not SLO or capacity outcomes."
                ),
                "operational_dependence": (
                    "Any operational effect depends on resource capacity, request/limit "
                    "mapping, controller policy, and SLO definitions."
                ),
                "no_universal_conversion": (
                    "No validated universal conversion from profile MAE/class error to "
                    "operational benefit currently exists for this study."
                ),
                "pilot_derived_margins_forbidden": (
                    "Deriving margins from the 18-VM pilot effects would be outcome-driven "
                    "and is forbidden."
                ),
                "deferral": (
                    "Operational meaningfulness must be calibrated and validated in later "
                    "system-validation gates (C4 / V7–V8), not invented before V3."
                ),
                "external_sources": [dict(s) for s in EXTERNAL_RATIONALE_SOURCES],
                "separation_from_dynapm_evidence": (
                    "External sources justify methodology and systems semantics only; they "
                    "are not DynAPM empirical evidence of benefit."
                ),
            },
            "per_endpoint": {
                endpoint: {
                    "practical_benefit_margin": None,
                    "acceptable_harm_margin": None,
                    "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
                }
                for endpoint in PRIMARY_FIDELITY_ENDPOINTS
            },
        },
        "statistics": {
            "unit": "vm",
            "study_type": "pre_specified_estimation",
            "paired_differences": "treatment_minus_control_per_vm",
            "report": [
                "median_effect",
                "mean_effect",
                "paired_bootstrap_95ci",
                "paired_nonparametric_test",
                "zero_and_tie_handling",
                "effect_size",
                "multiplicity_adjusted_p",
                "statistical_distinguishability",
                "refresh_write_change_costs",
                "pareto_fidelity_cost_relationships",
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
                "Profile-level practical significance is NOT_DEFINED_AT_PROFILE_LEVEL. "
                "Do not invent numeric margins. Do not infer operational superiority from "
                "statistical significance."
            ),
        },
        "decision_logic": {
            "status": "ESTIMATION_FIRST_FROZEN",
            "v3_may_establish": [
                "direction",
                "magnitude",
                "uncertainty",
                "statistical_distinguishability",
            ],
            "rules": [
                {
                    "id": "R1_estimation_scope",
                    "text": (
                        "V3 may establish direction, magnitude, uncertainty, and statistical "
                        "distinguishability for the frozen F1–F3 contrasts and endpoints."
                    ),
                },
                {
                    "id": "R2_no_p_value_operational_superiority",
                    "text": (
                        "Statistical significance alone must never imply practical or "
                        "operational superiority."
                    ),
                },
                {
                    "id": "R3_no_cadence_recommendation_from_p",
                    "text": (
                        "Do not recommend a refresh cadence solely from p-values."
                    ),
                },
                {
                    "id": "R4_pareto_dominance",
                    "text": (
                        "Call a method strictly Pareto-dominated only when the predefined "
                        "fidelity/cost evidence satisfies dominance on all four primary "
                        "fidelity endpoints (favorable directions) and primary cost "
                        "(n_refresh_events), using both paired median and paired mean "
                        "effects: the dominating method is nowhere worse and strictly "
                        "better on at least one fidelity endpoint or cost. Otherwise "
                        "report the fidelity–cost trade-off without a dominance label."
                    ),
                },
                {
                    "id": "R5_operational_benefit_is_c4",
                    "text": (
                        "Operational/practical benefit remains claim C4 and is deferred to "
                        "system-validation gates (V7–V8)."
                    ),
                },
                {
                    "id": "R6_negative_null_small_publishable",
                    "text": (
                        "Negative, null, and small effects remain valid and publishable "
                        "estimation findings."
                    ),
                },
                {
                    "id": "R7_no_expected_winners",
                    "text": (
                        "Do not encode expected winners; comparisons remain those frozen "
                        "in F1–F3."
                    ),
                },
                {
                    "id": "R8_no_materially_better_without_ops",
                    "text": (
                        "Do not use wording such as 'materially better' or 'practically "
                        "meaningful improvement' for profile endpoints unless later "
                        "operational evidence (C4) supports that language."
                    ),
                },
            ],
        },
        "future_gates": {
            "V3": "Materna confirmatory estimation study (non-adaptive)",
            "V4": "independent production-corpus suitability/acquisition",
            "V5": "second-corpus replication, preferably Google ClusterData 2019 if suitability remains valid",
            "V6": "maintenance-cost/service benchmark",
            "V7": "Kubernetes profile→resource-management harness",
            "V8": "repeated operational/system validation",
            "V9": "final claim audit / venue decision",
            "claim_rule": "Do not claim C3–C6 before their corresponding gates pass.",
            "v3_status_after_v25a": "NEXT",
        },
        "execution_guards": {
            "scientific_run_in_v25_or_v25a": False,
            "access_confirmatory_outcomes": False,
            "new_predictor_trigger_selector_cadence_or_algorithm": False,
            "use_pilot_effects_to_choose_margins_or_hypotheses": False,
            "invent_numeric_practical_margins": False,
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
    if manifest["entities_fingerprint"] != COHORT_ENTITIES_FINGERPRINT:
        raise ValueError("cohort entities fingerprint drifted from V2.5 freeze")
    if file_sha256(COHORT_JSON) != COHORT_FILE_SHA256:
        raise ValueError("cohort file sha256 drifted from V2.5 freeze")
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


def validate_legacy_provenance() -> dict[str, str]:
    if not LEGACY_CONFIG_JSON.is_file() or not LEGACY_CONFIG_YAML.is_file():
        raise FileNotFoundError("legacy V2.5 configs missing")
    legacy = read_json(LEGACY_CONFIG_JSON)
    if legacy.get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise ValueError("legacy schema_version mismatch")
    if fingerprint(legacy) != LEGACY_DESIGN_FINGERPRINT:
        raise ValueError("legacy design fingerprint mismatch")
    if file_sha256(LEGACY_CONFIG_JSON) != LEGACY_CONFIG_JSON_SHA256:
        raise ValueError("legacy config JSON sha256 mismatch")
    if file_sha256(LEGACY_CONFIG_YAML) != LEGACY_CONFIG_YAML_SHA256:
        raise ValueError("legacy config YAML sha256 mismatch")
    if legacy.get("gate_status") != "BLOCKED":
        raise ValueError("legacy freeze must remain BLOCKED for provenance")
    return {
        "legacy_design_fingerprint": LEGACY_DESIGN_FINGERPRINT,
        "legacy_config_json_sha256": LEGACY_CONFIG_JSON_SHA256,
        "legacy_config_yaml_sha256": LEGACY_CONFIG_YAML_SHA256,
    }


def _validate_shared_matrices(design: dict[str, Any]) -> None:
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
    if design["statistics"]["paired_test"]["name"] != "wilcoxon_signed_rank":
        raise ValueError("paired test mismatch")
    if design["statistics"]["paired_test"]["zero_method"] != "wilcox":
        raise ValueError("wilcoxon zero_method mismatch")
    if design["statistics"]["multiplicity"]["method"] != "holm":
        raise ValueError("multiplicity method mismatch")
    if design["endpoints"]["primary_fidelity"] != list(PRIMARY_FIDELITY_ENDPOINTS):
        raise ValueError("primary fidelity endpoints mismatch")
    if design["endpoints"]["primary_maintenance_cost"] != PRIMARY_COST_ENDPOINT:
        raise ValueError("primary cost endpoint mismatch")


def validate_design(design: dict[str, Any] | None = None) -> dict[str, Any]:
    design = design if design is not None else design_document()
    if design["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported design schema")
    if design.get("amendment") != AMENDMENT:
        raise ValueError("amendment must be V2.5A")
    if design["gate_status"] != GATE_STATUS:
        raise ValueError("gate_status must be PASS after V2.5A estimation amendment")
    if design.get("blocker") is not None:
        raise ValueError("blocker must be null after V2.5A")
    if design["study_framing"] != "estimation_first":
        raise ValueError("study_framing must be estimation_first")
    ps = design["practical_significance"]
    if ps["status"] != "NOT_DEFINED_AT_PROFILE_LEVEL":
        raise ValueError("practical significance must be NOT_DEFINED_AT_PROFILE_LEVEL")
    if ps.get("numeric_margins") != "not_invented":
        raise ValueError("numeric margins must remain not_invented")
    for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
        block = ps["per_endpoint"][endpoint]
        if block["practical_benefit_margin"] is not None or block["acceptable_harm_margin"] is not None:
            raise ValueError(f"{endpoint} margins must remain null")
    _validate_shared_matrices(design)
    if design["claim_status"]["C4"] != "UNPROVEN":
        raise ValueError("C4 must remain UNPROVEN")
    for claim in ("C1_forecasting_superiority", "C2_adaptive_refresh_superiority"):
        if claim not in design["withdrawn_claims"]:
            raise ValueError(f"{claim} must remain withdrawn")
    return {
        "design_fingerprint": fingerprint(design),
        "gate_status": design["gate_status"],
        "blocker": design["blocker"],
        "amendment": design["amendment"],
        "study_framing": design["study_framing"],
    }


def write_frozen_config_files(root: Path = REPO_ROOT) -> dict[str, str]:
    design = design_document()
    json_path = root / "configs" / "materna_confirmatory_v1_1.json"
    yaml_path = root / "configs" / "materna_confirmatory_v1_1.yaml"
    json_path.write_text(canonical_json(design) + "\n", encoding="utf-8")
    yaml_path.write_text(
        "# Frozen by V2.5A estimation amendment — authoritative twin is "
        "materna_confirmatory_v1_1.json\n"
        "# Previous V2.5 freeze preserved at materna_confirmatory_v1.{json,yaml}\n"
        + emit_yaml(design),
        encoding="utf-8",
    )
    cohort_info = validate_cohort_manifest()
    legacy = validate_legacy_provenance()
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
        "amendment": design_info["amendment"],
        **legacy,
    }


def frozen_hashes() -> dict[str, Any]:
    if not CONFIG_JSON.is_file():
        raise FileNotFoundError(CONFIG_JSON)
    design = read_json(CONFIG_JSON)
    design_info = validate_design(design)
    cohort_info = validate_cohort_manifest()
    legacy = validate_legacy_provenance()
    return {
        "design_fingerprint": design_info["design_fingerprint"],
        "config_json_sha256": file_sha256(CONFIG_JSON),
        "config_yaml_sha256": file_sha256(CONFIG_YAML),
        "cohort_entities_fingerprint": cohort_info["entities_fingerprint"],
        "cohort_file_sha256": cohort_info["cohort_file_sha256"],
        "kept_vms_sha256": file_sha256(KEPT_VMS),
        "gate_status": design_info["gate_status"],
        "blocker": design_info["blocker"],
        "amendment": design_info["amendment"],
        "study_framing": design_info["study_framing"],
        **legacy,
    }
