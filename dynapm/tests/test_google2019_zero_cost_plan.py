"""V4B.3 zero-cost plan freeze tests (no BigQuery execution)."""
from __future__ import annotations

from pathlib import Path

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_acquisition import (
    ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
    cumulative_executed_bytes,
)
from dynapm.experiments.google2019_zero_cost_plan import (
    CHOSEN_CELLS,
    COST_MATRIX_JSON,
    DISPOSITION,
    PLAN_JSON,
    PLAN_YAML,
    cell_cost_ranking,
    load_plan,
    render_plan_query,
    select_cells_under_cap,
    template_hashes,
    validate_zero_cost_plan,
)


def test_plan_frozen_ready_under_cap(tmp_path, monkeypatch):
    ledger = tmp_path / "isolated_empty_ledger.json"
    monkeypatch.setattr("dynapm.experiments.google2019_zero_cost_plan.cumulative_executed_bytes", lambda: cumulative_executed_bytes(ledger))
    doc = load_plan()
    assert doc["disposition"] == DISPOSITION == "READY_FOR_ZERO_COST_ACQUISITION"
    assert doc["cell_selection"]["chosen_cells"] == list(CHOSEN_CELLS)
    assert doc["expected_cumulative_processed_bytes"] <= ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES
    assert doc["frozen_ab_pair_feasible"] is False
    assert doc["frozen_ab_pair_bytes"] > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES
    assert doc["plan_execution_authorized"] is False
    assert doc["executed_bytes_this_task"] == 0
    assert cumulative_executed_bytes(ledger) == 0
    info = validate_zero_cost_plan(doc)
    assert info["plan_fingerprint"] == fingerprint(doc)
    assert info["plan_json_sha256"] == file_sha256(PLAN_JSON)
    assert info["plan_yaml_sha256"] == file_sha256(PLAN_YAML)


def test_cost_ranking_selects_e_g_not_a_b():
    matrix = read_json(COST_MATRIX_JSON)
    ranking = cell_cost_ranking(matrix)
    assert ranking[0] == "e"
    assert ranking[1] == "g"
    assert "a" in ranking and "b" in ranking
    assert select_cells_under_cap(matrix=matrix) == ["e", "g"]
    # a,b alone exceed the cap when forced as a pair.
    ab = (
        matrix["cells"]["a"]["minimal_pair_bytes"]
        + matrix["cells"]["b"]["minimal_pair_bytes"]
    )
    assert ab > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES


def test_templates_render_only_chosen_cells_and_leaf_columns():
    hashes = template_hashes()
    assert set(hashes) == {"20_usage_minimal.sql", "21_events_minimal.sql"}
    usage = render_plan_query("20_usage_minimal.sql", "e")
    events = render_plan_query("21_events_minimal.sql", "g")
    assert "clusterdata_2019_e.instance_usage" in usage
    assert "clusterdata_2019_g.instance_events" in events
    assert "average_usage.cpus" in usage and "average_usage.memory" in usage
    assert "average_usage," not in usage.replace("average_usage.cpus", "").replace(
        "average_usage.memory", ""
    )
    assert "\nSELECT *" not in usage and not usage.strip().startswith("SELECT *")
    assert "\nSELECT *" not in events and not events.strip().startswith("SELECT *")
    assert "TABLESAMPLE" not in usage and "TABLESAMPLE" not in events
    try:
        render_plan_query("20_usage_minimal.sql", "a")
        raise AssertionError("cell a must be rejected")
    except ValueError as exc:
        assert "not in frozen" in str(exc)


def test_plan_forbids_method_outcomes_and_secrets_paths():
    doc = load_plan()
    text = Path(PLAN_JSON).read_text(encoding="utf-8")
    assert doc["method_outcomes_computed"] is False
    assert "StaticPolicy" not in text
    assert "refresh_token" not in text
    assert "private_key" not in text
    assert "/Users/" not in text
