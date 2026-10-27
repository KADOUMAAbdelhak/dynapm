"""V4B.4 acquisition executor gates (no live BigQuery execution in unit tests)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from dynapm.core.provenance import read_json
from dynapm.experiments.google2019_acquisition import GIB
from dynapm.experiments.google2019_execute_acquisition import (
    DISK_SAFETY_FACTOR,
    AcquisitionExecutionBlocked,
    assess_disk_for_cells,
    cell_uncompressed_upper_bound,
    expected_bytes_map,
    write_blocked_acquisition_record,
)
from dynapm.experiments.google2019_zero_cost_plan import CHOSEN_CELLS


def test_expected_bytes_match_frozen_plan():
    expected = expected_bytes_map()
    assert expected[("e", "20_usage_minimal.sql")] > 300 * GIB
    assert expected[("e", "21_events_minimal.sql")] > 60 * GIB
    assert expected[("g", "20_usage_minimal.sql")] > 300 * GIB
    e = cell_uncompressed_upper_bound("e")
    g = cell_uncompressed_upper_bound("g")
    assert e + g > 800 * GIB


def test_disk_assessment_detects_insufficient_space(tmp_path):
    class Usage:
        free = 10 * GIB
        total = 100 * GIB
        used = 90 * GIB

    with patch(
        "dynapm.experiments.google2019_execute_acquisition.shutil.disk_usage",
        return_value=Usage(),
    ):
        status = assess_disk_for_cells(CHOSEN_CELLS, path=tmp_path)
    assert status.safe is False
    assert status.required_bytes == int(
        (cell_uncompressed_upper_bound("e") + cell_uncompressed_upper_bound("g"))
        * DISK_SAFETY_FACTOR
    )
    assert status.free_gib == 10.0


def test_current_workspace_disk_is_unsafe_for_frozen_plan():
    status = assess_disk_for_cells(CHOSEN_CELLS)
    # This workstation currently has ~100 GiB free vs ~990 GiB required.
    # If a future machine has enough disk, this assertion should be updated.
    if status.free_bytes < status.required_bytes:
        assert status.safe is False
    else:
        assert status.safe is True


def test_blocked_record_is_tracked_and_secret_free(tmp_path):
    out = tmp_path / "acquisition_record.json"
    # Unit records describe a supplied ledger state, not the live workstation.
    for previous_bytes in (0, 123456):
        with patch("dynapm.experiments.google2019_execute_acquisition.cumulative_executed_bytes", return_value=previous_bytes):
            record = write_blocked_acquisition_record(
                "insufficient_local_disk_for_cell_e_uncompressed_upper_bound",
                preflight_payload={"all_dry_runs_match_within_1pct": True},
                output_path=out,
            )
        assert record["disposition"] == "ACQUISITION_BLOCKED"
        assert record["executed_query_bytes"] == previous_bytes
    assert record["method_outcomes_computed"] is False
    assert record["cohort_frozen"] is False
    assert record["raw_artifacts_written"] is False
    body = out.read_text(encoding="utf-8")
    doc = read_json(out)
    assert doc["blocker"].startswith("insufficient_local_disk")
    assert "refresh_token" not in body
    assert "/Users/" not in body
    assert "private_key" not in body


def test_executor_module_has_no_method_outcomes():
    src = Path("dynapm/experiments/google2019_execute_acquisition.py").read_text(
        encoding="utf-8"
    )
    for needle in ("StaticPolicy", "PeriodicPolicy", "evaluate_replay", "pw_3h"):
        assert needle not in src
