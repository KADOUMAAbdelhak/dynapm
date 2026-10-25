"""V4B.6 streaming executor unit tests (no live BigQuery execution)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dynapm.experiments.google2019_acquisition import CADENCE_US, canonicalize_extract
from dynapm.experiments.google2019_streaming_execute import (
    EXECUTION_ORDER,
    build_request_index,
    causal_request_lookup,
    join_usage_batch,
    recover_or_start_query,
    validate_cell_artifacts,
    write_cell_canonical_from_joined,
)
from dynapm.tests.test_google2019_acquisition import source_frame


def test_execution_order_is_events_before_usage_per_cell():
    assert EXECUTION_ORDER == (
        ("e", "21_events_minimal.sql"),
        ("e", "20_usage_minimal.sql"),
        ("g", "21_events_minimal.sql"),
        ("g", "20_usage_minimal.sql"),
    )


def test_maximum_bytes_billed_uses_one_percent_tolerance_band():
    from dynapm.experiments.google2019_streaming_execute import maximum_bytes_billed_for

    assert maximum_bytes_billed_for(100) == 101
    assert maximum_bytes_billed_for(73125247840) >= 73125593088


def test_causal_request_lookup_picks_latest_not_after_start(tmp_path):
    events = pd.DataFrame(
        {
            "time": [0, 100, 500],
            "collection_id": [1, 1, 1],
            "instance_index": [0, 0, 0],
            "request_cpu": [2.0, 4.0, 8.0],
            "request_memory": [1.0, 2.0, 4.0],
        }
    )
    path = tmp_path / "events.parquet"
    events.to_parquet(path, index=False)
    index = build_request_index(path)
    assert causal_request_lookup(index, 1, 0, 100) == (4.0, 2.0, 100)
    assert causal_request_lookup(index, 1, 0, 99) == (2.0, 1.0, 0)
    assert causal_request_lookup(index, 1, 0, -1) is None
    assert causal_request_lookup(index, 9, 0, 100) is None


def test_join_and_canonicalize_match_frozen_semantics(tmp_path):
    # Build events + usage that reconstruct source_frame alignment.
    n = 50
    start = np.arange(n, dtype=np.int64) * CADENCE_US
    events = pd.DataFrame(
        {
            "time": [0, int(start[n // 2])],
            "collection_id": [7, 7],
            "instance_index": [0, 0],
            "request_cpu": [2.0, 4.0],
            "request_memory": [8.0, 16.0],
        }
    )
    ep = tmp_path / "events.parquet"
    events.to_parquet(ep, index=False)
    index = build_request_index(ep)
    usage_batch = [
        {
            "collection_id": 7,
            "instance_index": 0,
            "collection_type": 1,
            "start_time": int(start[i]),
            "end_time": int(start[i] + CADENCE_US),
            "average_cpu": 3.0 if i == 3 else 1.0,
            "average_memory": 4.0,
        }
        for i in range(n)
    ]
    joined, counts = join_usage_batch(usage_batch, cell="e", index=index)
    assert counts["missing_request"] == 0
    frame = pd.DataFrame(joined)
    # Compare to direct canonicalize on equivalent pre-joined frame.
    direct = source_frame(n)
    direct["cell"] = "e"
    c1, e1, d1 = canonicalize_extract(frame)
    c2, e2, d2 = canonicalize_extract(direct)
    assert len(c1) == len(c2)
    assert list(c1["cpu_utilization"]) == list(c2["cpu_utilization"])
    assert c1.iloc[3]["cpu_utilization"] == 1.5


def test_recover_or_start_does_not_resubmit_done_job():
    prior = {
        "queries": {
            "e:21_events_minimal.sql": {
                "job_id": "job-abc",
                "query_sha256": "x",
                "expected_bytes": 1,
            }
        }
    }
    fake_job = MagicMock()
    fake_job.job_id = "job-abc"
    fake_job.state = "DONE"
    fake_job.error_result = None
    fake_job.total_bytes_processed = 100

    client = MagicMock()
    client.get_job.return_value = fake_job

    with patch(
        "dynapm.experiments.google2019_streaming_execute._client",
        return_value=(client, MagicMock()),
    ), patch(
        "dynapm.experiments.google2019_streaming_execute.render_plan_query",
        return_value="SELECT 1",
    ), patch(
        "dynapm.experiments.google2019_streaming_execute.expected_bytes_map",
        return_value={("e", "21_events_minimal.sql"): 100},
    ):
        job, meta = recover_or_start_query(
            billing_project="proj",
            cell="e",
            template="21_events_minimal.sql",
            checkpoint=prior,
        )
    assert job is fake_job
    assert meta["recovered"] is True
    assert meta["resubmitted"] is False
    client.query.assert_not_called()


def test_write_canonical_from_joined_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "dynapm.experiments.google2019_streaming_execute.CANONICAL_ROOT",
        tmp_path / "canonical",
    )
    frame = source_frame(2017)
    frame["cell"] = "e"
    joined = tmp_path / "joined.parquet"
    frame.to_parquet(joined, index=False)
    manifest = write_cell_canonical_from_joined(joined, "e")
    assert manifest["row_count"] == 2017
    assert manifest["eligible_entity_count"] == 1
    # Point validate_cell_artifacts at the temp canonical root.
    monkeypatch.setattr(
        "dynapm.experiments.google2019_streaming_execute.cell_canonical_dir",
        lambda cell: tmp_path / "canonical" / cell,
    )
    validation = validate_cell_artifacts("e")
    assert validation["passed"] is True
    assert validation["utilization_above_one_cpu_rows"] == 1
