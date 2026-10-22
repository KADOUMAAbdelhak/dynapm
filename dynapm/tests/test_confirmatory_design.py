"""V2.5A estimation-first confirmatory design validation — no scientific run."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dynapm.core.provenance import fingerprint, file_sha256, read_json
from dynapm.experiments.confirmatory_design import (
    AMENDMENT,
    COHORT_ENTITIES_FINGERPRINT,
    COHORT_FILE_SHA256,
    COHORT_JSON,
    COMPARISON_FAMILIES,
    CONFIG_JSON,
    CONFIG_YAML,
    GATE_STATUS,
    KEPT_VMS,
    LEGACY_CONFIG_JSON,
    LEGACY_CONFIG_JSON_SHA256,
    LEGACY_CONFIG_YAML,
    LEGACY_CONFIG_YAML_SHA256,
    LEGACY_DESIGN_FINGERPRINT,
    PERMANENT_PILOT_EXCLUSIONS,
    PRIMARY_FIDELITY_ENDPOINTS,
    PRIMARY_METHODS,
    PROTOCOL_EXCLUSION_CODES,
    SCHEMA_VERSION,
    build_candidate_cohort_from_kept,
    design_document,
    emit_yaml,
    frozen_hashes,
    validate_cohort_manifest,
    validate_design,
    validate_legacy_provenance,
)

REPO = Path(__file__).resolve().parents[2]


def test_gate_pass_estimation_first_no_numeric_margins():
    design = design_document()
    assert design["gate_status"] == GATE_STATUS == "PASS"
    assert design["amendment"] == AMENDMENT == "V2.5A"
    assert design["blocker"] is None
    assert design["study_framing"] == "estimation_first"
    assert design["practical_significance"]["status"] == "NOT_DEFINED_AT_PROFILE_LEVEL"
    assert design["practical_significance"]["numeric_margins"] == "not_invented"
    for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
        block = design["practical_significance"]["per_endpoint"][endpoint]
        assert block["practical_benefit_margin"] is None
        assert block["acceptable_harm_margin"] is None


def test_amended_rqs_are_estimation_worded():
    rqs = design_document()["research_questions"]
    forbidden = ("materially", "practically meaningful", "practically better")
    for text in rqs.values():
        lower = text.lower()
        for word in forbidden:
            assert word not in lower
    assert "magnitude and uncertainty" in rqs["RQ1"]
    assert "cadence increments" in rqs["RQ2"]
    assert "Full-Rewrite" in rqs["RQ3"] and "PW-3h" in rqs["RQ3"]
    assert "volatility strata" in rqs["RQ4"]


def test_method_comparison_statistics_unchanged_from_v25():
    design = design_document()
    assert design["methods"]["primary"] == list(PRIMARY_METHODS)
    assert set(design["comparison_families"]) == set(COMPARISON_FAMILIES)
    assert len(COMPARISON_FAMILIES["F1_maintenance_vs_none"]) == 3
    assert len(COMPARISON_FAMILIES["F2_cadence_increments"]) == 2
    assert len(COMPARISON_FAMILIES["F3_high_cost_limit"]) == 1
    stats = design["statistics"]["bootstrap"]
    assert stats["repetitions"] == 10000
    assert stats["seed"] == 20251022
    assert stats["ci_level"] == 0.95
    assert design["statistics"]["paired_test"]["name"] == "wilcoxon_signed_rank"
    assert design["statistics"]["paired_test"]["zero_method"] == "wilcox"
    assert design["statistics"]["multiplicity"]["method"] == "holm"
    validate_design(design)


def test_cohort_excludes_pilots_and_has_1558_candidates_unchanged():
    info = validate_cohort_manifest()
    assert info["candidate_count"] == 1558
    assert info["entities_fingerprint"] == COHORT_ENTITIES_FINGERPRINT
    assert info["cohort_file_sha256"] == COHORT_FILE_SHA256
    entities = build_candidate_cohort_from_kept()
    assert len(entities) == 1558
    entity_ids = {(e["trace"], e["vm_id"]) for e in entities}
    assert entity_ids.isdisjoint(set(PERMANENT_PILOT_EXCLUSIONS))
    assert len(PERMANENT_PILOT_EXCLUSIONS) == 18
    kept = json.loads(KEPT_VMS.read_text(encoding="utf-8"))
    assert len(kept) == 1576


def test_legacy_v25_freeze_preserved_byte_identical():
    legacy = validate_legacy_provenance()
    assert legacy["legacy_design_fingerprint"] == LEGACY_DESIGN_FINGERPRINT
    assert file_sha256(LEGACY_CONFIG_JSON) == LEGACY_CONFIG_JSON_SHA256
    assert file_sha256(LEGACY_CONFIG_YAML) == LEGACY_CONFIG_YAML_SHA256
    design = read_json(LEGACY_CONFIG_JSON)
    assert design["gate_status"] == "BLOCKED"
    assert design["schema_version"] == "materna-confirmatory-design-v1"


def test_frozen_v11_config_files_match_design_and_hashes():
    assert CONFIG_JSON.is_file() and CONFIG_YAML.is_file() and COHORT_JSON.is_file()
    design = read_json(CONFIG_JSON)
    assert design == design_document()
    validate_design(design)
    hashes = frozen_hashes()
    assert hashes["design_fingerprint"] == fingerprint(design)
    assert hashes["config_json_sha256"] == file_sha256(CONFIG_JSON)
    assert hashes["config_yaml_sha256"] == file_sha256(CONFIG_YAML)
    assert hashes["gate_status"] == "PASS"
    assert hashes["blocker"] is None
    assert hashes["amendment"] == "V2.5A"
    assert CONFIG_YAML.read_text(encoding="utf-8").startswith("# Frozen by V2.5A")
    assert f"schema_version: {SCHEMA_VERSION}" in emit_yaml(design)


def test_protocol_exclusion_codes_predefined_and_performance_forbidden():
    design = design_document()
    codes = design["cohort"]["protocol_exclusion_codes"]
    assert codes == list(PROTOCOL_EXCLUSION_CODES)
    assert "method_performance" in design["cohort"]["forbidden_exclusion_basis"]
    assert design["cohort"]["gap_audit_199_flags"] == "diagnostic_only_not_automatic_exclusion"


def test_c1_c2_withdrawn_c4_unproven_estimation_decision_rules():
    design = design_document()
    assert "C1_forecasting_superiority" in design["withdrawn_claims"]
    assert "C2_adaptive_refresh_superiority" in design["withdrawn_claims"]
    assert design["claim_status"]["C4"] == "UNPROVEN"
    rule_ids = {r["id"] for r in design["decision_logic"]["rules"]}
    assert "R2_no_p_value_operational_superiority" in rule_ids
    assert "R3_no_cadence_recommendation_from_p" in rule_ids
    assert "R4_pareto_dominance" in rule_ids
    assert "R5_operational_benefit_is_c4" in rule_ids
    assert design["execution_guards"]["scientific_run_in_v25_or_v25a"] is False
    assert design["execution_guards"]["access_confirmatory_outcomes"] is False
    assert design["execution_guards"]["invent_numeric_practical_margins"] is False


def test_no_confirmatory_outcome_tables_touched_by_freeze_module():
    src = (REPO / "dynapm" / "experiments" / "confirmatory_design.py").read_text(encoding="utf-8")
    for needle in (
        "per_vm_nonadaptive",
        "selection_pool.parquet",
        "results/runs/",
        "read_parquet",
        "pd.read_csv",
    ):
        assert needle not in src
    cohort = read_json(COHORT_JSON)
    assert set(cohort["entities"][0]) == {"trace", "vm_id"}
    assert "cpu_class_correctness" not in cohort
    assert "mae" not in json.dumps(cohort).lower()


def test_validate_rejects_invented_margins_and_wrong_status():
    design = design_document()
    design["practical_significance"]["per_endpoint"]["cpu_class_correctness"][
        "practical_benefit_margin"
    ] = 0.01
    with pytest.raises(ValueError, match="margins must remain null"):
        validate_design(design)
    design = design_document()
    design["gate_status"] = "BLOCKED"
    with pytest.raises(ValueError, match="gate_status must be PASS"):
        validate_design(design)
