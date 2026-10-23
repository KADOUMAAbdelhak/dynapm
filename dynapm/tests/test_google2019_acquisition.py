"""V4B acquisition guard and canonical preprocessing tests."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_acquisition import (
    BLOCKER_CODE,
    CADENCE_US,
    CONFIG_JSON,
    CONFIG_YAML,
    DISPOSITION,
    AcquisitionBlocked,
    canonicalize_extract,
    dry_run_query,
    estimate_on_demand_cost_usd,
    frozen_hashes,
    inspect_access,
    acquisition_document,
    query_hashes,
    render_cell_query,
    validate_acquisition_document,
    write_canonical_artifacts,
)


def source_frame(n=2017):
    start = np.arange(n, dtype=np.int64) * CADENCE_US
    request_cpu = np.where(np.arange(n) < n // 2, 2.0, 4.0)
    request_mem = np.where(np.arange(n) < n // 2, 8.0, 16.0)
    return pd.DataFrame(
        {
            "cell": "a",
            "collection_id": 7,
            "instance_index": 0,
            "collection_type": 1,
            "start_time": start,
            "end_time": start + CADENCE_US,
            "average_cpu": np.where(np.arange(n) == 3, 3.0, 1.0),
            "average_memory": 4.0,
            "request_cpu": request_cpu,
            "request_memory": request_mem,
            "request_event_time": np.where(
                np.arange(n) < n // 2, 0, start[n // 2]
            ),
            "usage_source_table": (
                "google.com:google-cluster-data.clusterdata_2019_a.instance_usage"
            ),
            "request_source_table": (
                "google.com:google-cluster-data.clusterdata_2019_a.instance_events"
            ),
        }
    )


def test_config_frozen_blocked_without_fabricated_estimates():
    doc = acquisition_document()
    assert doc["disposition"] == DISPOSITION == "ACQUISITION_BLOCKED"
    assert doc["blocker"]["code"] == BLOCKER_CODE
    assert doc["budget_guard"]["dry_run_records"] == []
    assert doc["budget_guard"]["estimated_processed_bytes"] is None
    assert doc["budget_guard"]["estimated_cost_usd"] is None
    validate_acquisition_document(doc)


def test_query_files_hash_and_safe_cell_rendering():
    hashes = query_hashes()
    assert len(hashes) == 5
    rendered = render_cell_query("04_full_cell_population.sql", "c")
    assert "{{CELL}}" not in rendered
    assert "clusterdata_2019_c.instance_usage" in rendered
    with pytest.raises(ValueError, match="cell must"):
        render_cell_query("04_full_cell_population.sql", "z")


def test_normalization_causal_requests_changes_and_no_clipping():
    canonical, entities, details = canonicalize_extract(source_frame())
    assert len(canonical) == 2017
    assert entities.iloc[0]["eligible"]
    assert entities.iloc[0]["request_states"] == 2
    assert entities.iloc[0]["has_request_change"]
    # 3 NCU / 2 NCU request = 1.5; preserve >1 rather than clip.
    assert canonical.iloc[3]["cpu_utilization"] == 1.5
    assert canonical["cpu_utilization"].max() > 1.0
    assert details["diagnostics"]["utilization_above_one_cpu_rows"] == 1
    assert details["diagnostics"]["method_outcomes_computed"] is False


def test_invalid_request_and_future_alignment_rejected():
    frame = source_frame(10)
    frame.loc[0, "request_cpu"] = 0
    frame.loc[1, "request_event_time"] = frame.loc[1, "start_time"] + 1
    canonical, _, details = canonicalize_extract(frame)
    reasons = set(details["rejected"]["exclusion_reason"])
    assert "missing_positive_resource_request" in reasons
    assert "request_event_after_usage_window" in reasons
    assert len(canonical) == 8


def test_duplicate_rule_is_deterministic():
    frame = source_frame(2017)
    duplicate = frame.iloc[[5]].copy()
    duplicate["end_time"] = duplicate["end_time"] - 1
    duplicate["average_cpu"] = 99.0
    canonical, _, details = canonicalize_extract(
        pd.concat([frame, duplicate], ignore_index=True)
    )
    row = canonical[canonical.timestamp_us == 5 * CADENCE_US].iloc[0]
    assert row["average_cpu_ncu"] == 1.0  # greatest end_time wins
    assert details["diagnostics"]["duplicate_rows"] == 1


def test_missing_slot_is_recorded_not_imputed():
    frame = source_frame(2018).drop(index=100).reset_index(drop=True)
    canonical, entities, _ = canonicalize_extract(frame)
    assert len(canonical) == 2017
    assert entities.iloc[0]["expected_slots"] == 2018
    assert entities.iloc[0]["missing_slots"] == 1
    assert entities.iloc[0]["eligible"]


def test_immutable_manifest_and_relative_scientific_paths(tmp_path):
    out = tmp_path / "canonical"
    manifest = write_canonical_artifacts(
        source_frame(),
        out,
        query_name="03_bounded_validation_extract.sql",
        extraction_timestamp="2026-10-23T00:00:00Z",
    )
    assert manifest["row_count"] == 2017
    assert manifest["eligible_entity_count"] == 1
    assert manifest["query"]["path"].startswith("queries/google2019/")
    assert not manifest["query"]["path"].startswith("/")
    assert (out / "manifest.json").is_file()
    with pytest.raises(FileExistsError, match="immutable"):
        write_canonical_artifacts(
            source_frame(),
            out,
            query_name="03_bounded_validation_extract.sql",
        )


def test_access_blocker_stops_dry_run_when_unavailable():
    status = inspect_access()
    if status.dry_run_possible:
        pytest.skip("BigQuery dry-run access is present on this machine")
    assert status.blocker_code == BLOCKER_CODE
    with pytest.raises(AcquisitionBlocked, match=BLOCKER_CODE):
        dry_run_query("SELECT 1", billing_project="unavailable-test-project")


def test_acquisition_module_does_not_compute_method_outcomes():
    src = Path(__file__).resolve().parents[1] / "experiments" / "google2019_acquisition.py"
    text = src.read_text(encoding="utf-8")
    for needle in (
        "StaticPolicy",
        "PeriodicPolicy",
        "FullRewrite",
        "evaluate_replay",
        "cpu_class_accuracy",
        "n_refresh_events",
    ):
        assert needle not in text
    sql_root = Path(__file__).resolve().parents[2] / "queries" / "google2019"
    joined = "\n".join(p.read_text(encoding="utf-8") for p in sql_root.glob("*.sql"))
    for needle in ("evaluate_replay", "cpu_class_accuracy", "n_refresh_events", "pw_3h"):
        assert needle not in joined


def test_cost_formula_and_frozen_file_hashes():
    assert estimate_on_demand_cost_usd(1024**4) == 6.25
    doc = read_json(CONFIG_JSON)
    assert doc == acquisition_document()
    hashes = frozen_hashes()
    assert hashes["config_fingerprint"] == fingerprint(doc)
    assert hashes["config_json_sha256"] == file_sha256(CONFIG_JSON)
    assert hashes["config_yaml_sha256"] == file_sha256(CONFIG_YAML)
