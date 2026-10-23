"""V4B.3 zero-cost Google 2019 acquisition plan freeze.

Dry-run / metadata redesign only. Never executes query-processing jobs.
Scientific V4A/V4B population semantics are unchanged; cell scope is narrowed
by outcome-blind cost ranking under the 900 GiB free-tier headroom cap.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_acquisition import (
    GIB,
    ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
    cumulative_executed_bytes,
)
from dynapm.experiments.replication_corpus import frozen_hashes as v4a_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_JSON = REPO_ROOT / "configs" / "google2019_zero_cost_plan_v1.json"
PLAN_YAML = REPO_ROOT / "configs" / "google2019_zero_cost_plan_v1.yaml"
COST_MATRIX_JSON = REPO_ROOT / "configs" / "google2019_v4b3_cost_matrix.json"
METADATA_SUMMARY_JSON = REPO_ROOT / "configs" / "google2019_v4b3_table_metadata_summary.json"
V4B3_QUERY_ROOT = REPO_ROOT / "queries" / "google2019" / "v4b3"

SCHEMA_VERSION = "google2019-zero-cost-plan-v1"
DISPOSITION = "READY_FOR_ZERO_COST_ACQUISITION"
CHOSEN_CELLS = ("e", "g")
TEMPLATE_FILES = (
    "20_usage_minimal.sql",
    "21_events_minimal.sql",
)


def template_hashes() -> dict[str, str]:
    return {name: file_sha256(V4B3_QUERY_ROOT / name) for name in TEMPLATE_FILES}


def load_plan() -> dict[str, Any]:
    return read_json(PLAN_JSON)


def validate_zero_cost_plan(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = doc if doc is not None else load_plan()
    if doc["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported zero-cost plan schema")
    if doc["disposition"] != DISPOSITION:
        raise ValueError("unexpected zero-cost plan disposition")
    if doc["v4a_protocol_fingerprint"] != v4a_hashes()["protocol_fingerprint"]:
        raise ValueError("V4A protocol fingerprint mismatch")
    if doc["cumulative_execution_cap_bytes"] != ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise ValueError("cumulative cap must remain 900 GiB")
    if doc["cell_selection"]["chosen_cells"] != list(CHOSEN_CELLS):
        raise ValueError("chosen cells must be e,g")
    if doc["tablesample_forbidden_for_scientific_corpus"] is not True:
        raise ValueError("TABLESAMPLE remains forbidden")
    if doc["plan_execution_authorized"] is not False:
        raise ValueError("V4B.3 must not authorize execution")
    if doc["method_outcomes_computed"] is not False:
        raise ValueError("method outcomes forbidden")
    if doc["executed_bytes_this_task"] != 0:
        raise ValueError("V4B.3 must record zero executed bytes")
    if cumulative_executed_bytes() != 0:
        raise ValueError("V4 acquisition ledger must remain at zero executed bytes")
    if doc["templates"] != template_hashes():
        raise ValueError("V4B.3 template hash mismatch")
    worst = int(doc["expected_cumulative_processed_bytes"])
    if worst > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise ValueError("frozen plan exceeds zero-cost cap")
    if worst != sum(int(q["expected_processed_bytes"]) for q in doc["queries"]):
        raise ValueError("query byte sum mismatch")
    for query in doc["queries"]:
        if int(query["maximum_bytes_billed"]) != int(query["expected_processed_bytes"]):
            raise ValueError("per-query guard must equal frozen dry-run bytes")
        if int(query["maximum_bytes_billed"]) > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
            raise ValueError("per-query guard exceeds monthly cap")
    if doc["strategy"]["time_predicates_reduce_bytes"] is not False:
        raise ValueError("time predicates must not be treated as cost reductions")
    if not doc["frozen_ab_pair_feasible"] and doc["frozen_ab_pair_bytes"] <= (
        ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES
    ):
        raise ValueError("a,b feasibility flag inconsistent with bytes")
    pop = doc["population_semantics_unchanged"]
    if pop["collection_type"] != 1 or pop["cadence_seconds"] != 300:
        raise ValueError("population semantics drift")
    return {
        "plan_fingerprint": fingerprint(doc),
        "disposition": doc["disposition"],
        "chosen_cells": list(CHOSEN_CELLS),
        "expected_cumulative_gib": doc["expected_cumulative_gib"],
        "headroom_gib": doc["projected_free_tier_headroom_gib"],
        "plan_json_sha256": file_sha256(PLAN_JSON),
        "plan_yaml_sha256": file_sha256(PLAN_YAML),
        "cost_matrix_sha256": file_sha256(COST_MATRIX_JSON),
        "metadata_summary_sha256": file_sha256(METADATA_SUMMARY_JSON),
        "template_sha256": template_hashes(),
    }


def render_plan_query(template_name: str, cell: str) -> str:
    if template_name not in TEMPLATE_FILES:
        raise ValueError("unknown V4B.3 template")
    if cell not in CHOSEN_CELLS:
        raise ValueError("cell not in frozen zero-cost plan")
    text = (V4B3_QUERY_ROOT / template_name).read_text(encoding="utf-8")
    rendered = text.replace("{{CELL}}", cell)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("unresolved template")
    return rendered


def cell_cost_ranking(matrix: dict[str, Any] | None = None) -> list[str]:
    matrix = matrix if matrix is not None else read_json(COST_MATRIX_JSON)
    return list(matrix["ranking_ascending_minimal_pair"])


def select_cells_under_cap(
    *,
    cap_bytes: int = ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
    matrix: dict[str, Any] | None = None,
) -> list[str]:
    """Outcome-blind longest prefix of ascending cost ranking under the cap."""
    matrix = matrix if matrix is not None else read_json(COST_MATRIX_JSON)
    chosen: list[str] = []
    total = 0
    for cell in cell_cost_ranking(matrix):
        add = int(matrix["cells"][cell]["minimal_pair_bytes"])
        if total + add > cap_bytes:
            break
        chosen.append(cell)
        total += add
    return chosen
