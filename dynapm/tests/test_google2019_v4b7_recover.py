"""V4B.7 recovery / Storage Read unit tests (no live BigQuery execution)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dynapm.experiments.google2019_acquisition import GIB
from dynapm.experiments.google2019_acquisition_monitor import build_heartbeat, read_status
from dynapm.experiments.google2019_storage_read import (
    StorageReadBlocked,
    TempTableRef,
    verify_storage_read_zero_spend,
)
from dynapm.experiments.google2019_v4b7_recover_e import (
    CONSERVATIVE_MONTHLY_BEFORE_RETRY,
    EXPECTED_E_USAGE,
    FAILED_E_USAGE_BYTES,
    PROJECTED_AFTER_RETRY,
    CAP_BYTES,
)


def test_projected_retry_bytes_match_specified_budget():
    assert FAILED_E_USAGE_BYTES == 363_453_673_016
    assert abs(CONSERVATIVE_MONTHLY_BEFORE_RETRY / GIB - 406.595805) < 1e-5
    assert abs(PROJECTED_AFTER_RETRY / GIB - 745.088416) < 1e-5
    assert PROJECTED_AFTER_RETRY <= CAP_BYTES
    assert EXPECTED_E_USAGE == FAILED_E_USAGE_BYTES


def test_storage_read_refuses_non_anonymous_table(monkeypatch):
    monkeypatch.setattr(
        "dynapm.experiments.google2019_storage_read.require_zero_cost_project",
        lambda p: MagicMock(billing_enabled=False, zero_spend_guaranteed=True),
    )
    with pytest.raises(StorageReadBlocked, match="non_anonymous"):
        verify_storage_read_zero_spend(
            "proj",
            TempTableRef(project="proj", dataset_id="permanent_ds", table_id="t"),
        )


def test_storage_read_accepts_anonymous_temp(monkeypatch):
    monkeypatch.setattr(
        "dynapm.experiments.google2019_storage_read.require_zero_cost_project",
        lambda p: MagicMock(billing_enabled=False, zero_spend_guaranteed=True),
    )
    out = verify_storage_read_zero_spend(
        "proj",
        TempTableRef(project="proj", dataset_id="_anon123", table_id="tmp"),
    )
    assert out["temporary_anonymous_table"] is True
    assert out["billing_enabled"] is False


def test_monitor_heartbeat_writes_status(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dynapm.experiments.google2019_acquisition_monitor.MONITOR_ROOT", tmp_path
    )
    monkeypatch.setattr(
        "dynapm.experiments.google2019_acquisition_monitor.STATUS_JSON",
        tmp_path / "status.json",
    )
    monkeypatch.setattr(
        "dynapm.experiments.google2019_acquisition_monitor.MONITOR_LOG",
        tmp_path / "monitor.log",
    )
    body = build_heartbeat(
        phase="test",
        rows_downloaded=100,
        expected_rows=200,
        rows_per_sec=10.0,
        eta_seconds=10.0,
        ttl_remaining_seconds=80_000,
    )
    assert body["pct_complete"] == 50.0
    assert (tmp_path / "status.json").is_file()
    assert (tmp_path / "monitor.log").is_file()
    assert read_status()["phase"] == "test"
