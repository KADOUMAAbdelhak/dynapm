"""V4B.5 streaming plan and disk-guard tests (no BigQuery execution)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_acquisition import GIB
from dynapm.experiments.google2019_streaming import (
    CANONICAL_AUDIT_COLUMNS,
    DEFAULT_MIN_FREE_RESERVE_GIB,
    DISPOSITION,
    STREAM_PLAN_JSON,
    STREAM_PLAN_YAML,
    STORAGE_ESTIMATE_JSON,
    ChunkedParquetWriter,
    StreamingPlanError,
    assess_disk_guard,
    load_storage_estimate,
    load_streaming_plan,
    peak_requirement_for_stage,
    streaming_preflight_disk,
    validate_streaming_plan,
    write_checkpoint,
    read_checkpoint,
)


def test_streaming_plan_frozen_and_rejects_bytes_processed_as_size():
    doc = load_streaming_plan()
    assert doc["disposition"] == DISPOSITION == "READY_FOR_STREAMING_ACQUISITION"
    assert doc["cells"] == ["e", "g"]
    assert doc["executed_bytes_this_task"] == 0
    assert doc["storage_estimation"]["rejects_bytes_processed_as_local_size"] is True
    assert set(doc["retained_audit_fields_in_canonical"]) == set(CANONICAL_AUDIT_COLUMNS)
    info = validate_streaming_plan(doc)
    assert info["plan_fingerprint"] == fingerprint(doc)
    assert info["plan_json_sha256"] == file_sha256(STREAM_PLAN_JSON)
    assert info["plan_yaml_sha256"] == file_sha256(STREAM_PLAN_YAML)


def test_corrected_storage_estimate_far_below_old_bytes_processed_bound():
    est = load_storage_estimate()
    summary = est["summary"]
    assert summary["old_required_gib_eg_with_1_2x"] > 900
    assert summary["peak_during_g_with_e_canonical_point_gib"] < 100
    assert summary["peak_e_point_gib"] < 20
    assert summary["min_free_reserve_gib"] == DEFAULT_MIN_FREE_RESERVE_GIB
    # Point estimate fits usable disk; conservative band may not.
    assert summary["eg_peak_fits_usable_point"] is True
    assert summary["e_fits_usable_conservative"] is True


def test_disk_guard_reserves_minimum_free_space(tmp_path):
    class Usage:
        free = 50 * GIB
        total = 200 * GIB
        used = 150 * GIB

    with patch(
        "dynapm.experiments.google2019_streaming.shutil.disk_usage",
        return_value=Usage(),
    ):
        ok = assess_disk_guard(10.0, path=tmp_path, min_free_reserve_gib=20.0)
        bad = assess_disk_guard(40.0, path=tmp_path, min_free_reserve_gib=20.0)
    assert ok.usable_gib == 30.0
    assert ok.safe is True
    assert bad.safe is False


def test_chunked_writer_flushes_and_finalizes_atomically(tmp_path):
    out = tmp_path / "part.parquet"
    writer = ChunkedParquetWriter(out, chunk_rows=3, min_free_reserve_gib=0.0)
    writer.write_rows(
        [
            {"a": 1, "b": 0.5},
            {"a": 2, "b": 0.5},
            {"a": 3, "b": 0.5},
            {"a": 4, "b": 0.5},
        ]
    )
    assert not out.exists()
    assert writer.temp_path.exists()
    meta = writer.finalize()
    assert out.exists()
    assert not writer.temp_path.exists()
    assert meta["rows"] == 4
    assert Path(meta["path"]).name == "part.parquet" or meta["sha256"]


def test_chunked_writer_refuses_when_disk_guard_trips(tmp_path):
    out = tmp_path / "blocked.parquet"
    writer = ChunkedParquetWriter(out, chunk_rows=2, min_free_reserve_gib=20.0)

    class Usage:
        free = 21 * GIB  # usable = 1 GiB after 20 GiB reserve
        total = 100 * GIB
        used = 79 * GIB

    with patch(
        "dynapm.experiments.google2019_streaming.shutil.disk_usage",
        return_value=Usage(),
    ):
        # upcoming 2 rows * 512 bytes is tiny, but force required peak high via patch
        with patch(
            "dynapm.experiments.google2019_streaming.assess_disk_guard",
            return_value=type(
                "S",
                (),
                {
                    "safe": False,
                    "usable_gib": 1.0,
                },
            )(),
        ):
            with pytest.raises(StreamingPlanError, match="disk_guard_refuse"):
                writer.write_rows([{"a": 1}, {"a": 2}])
    writer.cleanup_temp()


def test_checkpoint_roundtrip(tmp_path):
    with patch(
        "dynapm.experiments.google2019_streaming.CHECKPOINT_ROOT",
        tmp_path,
    ):
        write_checkpoint(
            "e",
            {"stage": "events_complete", "events_rows": 10, "job_id": "job-1"},
        )
        doc = read_checkpoint("e")
    assert doc["cell"] == "e"
    assert doc["stage"] == "events_complete"
    assert doc["events_rows"] == 10


def test_streaming_preflight_disk_for_cell_e():
    payload = streaming_preflight_disk("cell_e")
    assert payload["stage"] == "cell_e"
    assert payload["required_peak_gib"] == peak_requirement_for_stage("cell_e")
    assert "disk" in payload


def test_no_method_outcomes_in_streaming_module():
    text = Path("dynapm/experiments/google2019_streaming.py").read_text(encoding="utf-8")
    for needle in ("StaticPolicy", "evaluate_replay", "pw_3h", "n_refresh_events"):
        assert needle not in text
    plan = STREAM_PLAN_JSON.read_text(encoding="utf-8")
    assert "refresh_token" not in plan
    assert "/Users/" not in plan
