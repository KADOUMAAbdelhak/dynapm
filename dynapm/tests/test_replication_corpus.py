"""V4A independent corpus selection / protocol-fit validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from dynapm.core.provenance import fingerprint, file_sha256, read_json
from dynapm.experiments.confirmatory_design import PRIMARY_METHODS
from dynapm.experiments.replication_corpus import (
    CONFIG_JSON,
    CONFIG_YAML,
    DISPOSITION,
    PREFERRED_CORPUS,
    SCHEMA_VERSION,
    frozen_hashes,
    protocol_document,
    validate_protocol,
)

REPO = Path(__file__).resolve().parents[2]


def test_disposition_ready_for_acquisition():
    doc = protocol_document()
    assert doc["disposition"] == DISPOSITION == "CORPUS READY FOR ACQUISITION"
    assert doc["preferred_corpus_id"] == PREFERRED_CORPUS
    assert doc["materna_confirmatory_redesign"] is False
    assert doc["second_corpus_outcome_access"] is False
    assert doc["ranking_policy"] == "protocol_fit_and_reproducibility_not_expected_effects"


def test_v3_matrix_and_stats_inherited():
    inherited = protocol_document()["inherited_from_v3_unchanged"]
    assert inherited["methods"] == list(PRIMARY_METHODS)
    assert inherited["study_framing"] == "estimation_first"
    assert inherited["practical_significance"] == "NOT_DEFINED_AT_PROFILE_LEVEL"
    assert inherited["statistics"]["bootstrap_repetitions"] == 10000
    assert inherited["statistics"]["bootstrap_seed"] == 20251022


def test_adaptation_does_not_claim_materna_percent_equivalence():
    adapt = protocol_document()["adaptation"]
    assert adapt["nominal_cadence"]["target_seconds"] == 300
    assert adapt["units_and_normalization"]["materna_percent_equivalence"] is False
    assert "request_normalized" in adapt["units_and_normalization"]["profile_utilization_definition"]
    assert adapt["canonical_entity"]["key"] == ["cell", "collection_id", "instance_index"]


def test_frozen_files_match_and_hashes():
    assert CONFIG_JSON.is_file() and CONFIG_YAML.is_file()
    doc = read_json(CONFIG_JSON)
    assert doc == protocol_document()
    validate_protocol(doc)
    hashes = frozen_hashes()
    assert hashes["protocol_fingerprint"] == fingerprint(doc)
    assert hashes["config_json_sha256"] == file_sha256(CONFIG_JSON)
    assert hashes["config_yaml_sha256"] == file_sha256(CONFIG_YAML)
    assert hashes["disposition"] == DISPOSITION
    assert CONFIG_YAML.read_text(encoding="utf-8").startswith("# Frozen by V4A")
    assert f"schema_version: {SCHEMA_VERSION}" in CONFIG_YAML.read_text(encoding="utf-8")


def test_no_outcome_or_download_in_module():
    src = (REPO / "dynapm" / "experiments" / "replication_corpus.py").read_text(encoding="utf-8")
    for needle in ("bigquery.Client", "read_parquet", "results/runs", "per_vm_results"):
        assert needle not in src


def test_validate_rejects_materna_redesign_or_wrong_methods():
    doc = protocol_document()
    doc["materna_confirmatory_redesign"] = True
    with pytest.raises(ValueError, match="must not redesign"):
        validate_protocol(doc)
    doc = protocol_document()
    doc["inherited_from_v3_unchanged"]["methods"] = ["static"]
    with pytest.raises(ValueError, match="methods must match"):
        validate_protocol(doc)
