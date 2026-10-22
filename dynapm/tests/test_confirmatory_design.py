"""V2.5 confirmatory design freeze validation — no scientific run, no outcomes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dynapm.core.provenance import fingerprint, file_sha256, read_json
from dynapm.experiments.confirmatory_design import (
    BLOCKER,
    COHORT_JSON,
    COMPARISON_FAMILIES,
    CONFIG_JSON,
    CONFIG_YAML,
    GATE_STATUS,
    KEPT_VMS,
    PERMANENT_PILOT_EXCLUSIONS,
    PRIMARY_FIDELITY_ENDPOINTS,
    PRIMARY_METHODS,
    PROTOCOL_EXCLUSION_CODES,
    build_candidate_cohort_from_kept,
    design_document,
    emit_yaml,
    frozen_hashes,
    validate_cohort_manifest,
    validate_design,
)

REPO = Path(__file__).resolve().parents[2]


def test_gate_blocked_on_unassigned_margins():
    design = design_document()
    assert design["gate_status"] == GATE_STATUS == "BLOCKED"
    assert design["blocker"] == BLOCKER
    assert design["practical_effect_margins"]["status"] == "UNASSIGNED"
    for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
        block = design["practical_effect_margins"][endpoint]
        assert block["practical_benefit_margin"] is None
        assert block["acceptable_harm_margin"] is None


def test_method_and_comparison_matrices_complete():
    design = design_document()
    assert design["methods"]["primary"] == list(PRIMARY_METHODS)
    assert set(design["comparison_families"]) == set(COMPARISON_FAMILIES)
    assert len(COMPARISON_FAMILIES["F1_maintenance_vs_none"]) == 3
    assert len(COMPARISON_FAMILIES["F2_cadence_increments"]) == 2
    assert len(COMPARISON_FAMILIES["F3_high_cost_limit"]) == 1
    validate_design(design)


def test_cohort_excludes_pilots_and_has_1558_candidates():
    info = validate_cohort_manifest()
    assert info["candidate_count"] == 1558
    entities = build_candidate_cohort_from_kept()
    assert len(entities) == 1558
    entity_ids = {(e["trace"], e["vm_id"]) for e in entities}
    assert entity_ids.isdisjoint(set(PERMANENT_PILOT_EXCLUSIONS))
    assert len(PERMANENT_PILOT_EXCLUSIONS) == 18
    kept = json.loads(KEPT_VMS.read_text(encoding="utf-8"))
    assert len(kept) == 1576


def test_frozen_config_files_match_design_and_hashes():
    assert CONFIG_JSON.is_file() and CONFIG_YAML.is_file() and COHORT_JSON.is_file()
    design = read_json(CONFIG_JSON)
    assert design == design_document()
    validate_design(design)
    hashes = frozen_hashes()
    assert hashes["design_fingerprint"] == fingerprint(design)
    assert hashes["config_json_sha256"] == file_sha256(CONFIG_JSON)
    assert hashes["config_yaml_sha256"] == file_sha256(CONFIG_YAML)
    assert hashes["gate_status"] == "BLOCKED"
    # YAML is a deterministic emission of the same design object (JSON keys sorted).
    assert CONFIG_YAML.read_text(encoding="utf-8").startswith("# Frozen by V2.5")
    assert "schema_version: materna-confirmatory-design-v1" in emit_yaml(design)
    assert emit_yaml(design) == emit_yaml(read_json(CONFIG_JSON))


def test_protocol_exclusion_codes_predefined_and_performance_forbidden():
    design = design_document()
    codes = design["cohort"]["protocol_exclusion_codes"]
    assert codes == list(PROTOCOL_EXCLUSION_CODES)
    assert "method_performance" in design["cohort"]["forbidden_exclusion_basis"]
    assert design["cohort"]["gap_audit_199_flags"] == "diagnostic_only_not_automatic_exclusion"


def test_statistics_bootstrap_frozen():
    stats = design_document()["statistics"]["bootstrap"]
    assert stats["repetitions"] == 10000
    assert stats["seed"] == 20251022
    assert stats["ci_level"] == 0.95


def test_c1_c2_withdrawn_and_no_adaptive_primary():
    design = design_document()
    assert "C1_forecasting_superiority" in design["withdrawn_claims"]
    assert "C2_adaptive_refresh_superiority" in design["withdrawn_claims"]
    excluded = design["methods"]["excluded_from_primary_confirmation"]
    assert "any_forecasting_or_adaptive_method" in excluded
    assert design["execution_guards"]["scientific_run_in_v25"] is False
    assert design["execution_guards"]["access_confirmatory_outcomes"] is False


def test_no_confirmatory_outcome_tables_touched_by_freeze_module():
    """Freeze tooling may read ID manifests only — not per-VM fidelity outcomes."""
    src = (REPO / "dynapm" / "experiments" / "confirmatory_design.py").read_text(encoding="utf-8")
    for needle in (
        "per_vm_nonadaptive",
        "selection_pool.parquet",
        "results/runs/",
        "read_parquet",
        "pd.read_csv",
    ):
        assert needle not in src
    # Cohort path is ID-only JSON under configs/.
    cohort = read_json(COHORT_JSON)
    assert set(cohort["entities"][0]) == {"trace", "vm_id"}
    assert "cpu_class_correctness" not in cohort
    assert "mae" not in json.dumps(cohort).lower()


def test_validate_rejects_assigned_margins():
    design = design_document()
    design["practical_effect_margins"]["cpu_class_correctness"]["practical_benefit_margin"] = 0.01
    with pytest.raises(ValueError, match="margins must be null"):
        validate_design(design)
