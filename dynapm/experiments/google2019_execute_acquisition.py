"""V4B.4 zero-cost Google 2019 acquisition executor.

Streams query results to gitignored local Parquet. Never creates BigQuery
destination tables. Refuses execution when billing is enabled, dry-runs diverge
from the frozen plan, the 900 GiB cap would be exceeded, or local disk is unsafe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import shutil
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, utc_now
from dynapm.experiments.google2019_acquisition import (
    GIB,
    ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
    cumulative_executed_bytes,
    record_executed_bytes,
    require_zero_cost_project,
)
from dynapm.experiments.google2019_zero_cost_plan import (
    CHOSEN_CELLS,
    load_plan,
    render_plan_query,
    template_hashes,
    validate_zero_cost_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
RAW_ROOT = MANAGED_ROOT / "raw"
CANONICAL_ROOT = MANAGED_ROOT / "canonical"
LEDGER_ROOT = MANAGED_ROOT / "execution"
DISK_SAFETY_FACTOR = 1.2
DRY_RUN_TOLERANCE = 0.01
FROZEN_PLAN_FINGERPRINT = (
    "f9f4bb846adfe9a303eb3d63f2efba84f7aa233ae4b990eb0b292cb30d76cfba"
)

# V4B.4 sequential order (usage then events; validate between cells in the CLI).
EXECUTION_ORDER = (
    ("e", "20_usage_minimal.sql"),
    ("e", "21_events_minimal.sql"),
    ("g", "20_usage_minimal.sql"),
    ("g", "21_events_minimal.sql"),
)


class AcquisitionExecutionBlocked(RuntimeError):
    """Safe stop before or during zero-cost acquisition."""


@dataclass(frozen=True)
class DiskStatus:
    free_bytes: int
    free_gib: float
    required_bytes: int
    required_gib: float
    safe: bool


def expected_bytes_map(plan: dict[str, Any] | None = None) -> dict[tuple[str, str], int]:
    plan = plan if plan is not None else load_plan()
    out: dict[tuple[str, str], int] = {}
    for query in plan["queries"]:
        name = Path(query["template"]).name
        out[(query["cell"], name)] = int(query["expected_processed_bytes"])
    return out


def cell_uncompressed_upper_bound(cell: str, plan: dict[str, Any] | None = None) -> int:
    expected = expected_bytes_map(plan)
    return int(expected[(cell, "20_usage_minimal.sql")] + expected[(cell, "21_events_minimal.sql")])


def assess_disk_for_cells(
    cells: tuple[str, ...] | list[str],
    *,
    path: Path | None = None,
    safety_factor: float = DISK_SAFETY_FACTOR,
    plan: dict[str, Any] | None = None,
) -> DiskStatus:
    root = path or REPO_ROOT
    free = int(shutil.disk_usage(root).free)
    required = int(sum(cell_uncompressed_upper_bound(c, plan) for c in cells) * safety_factor)
    return DiskStatus(
        free_bytes=free,
        free_gib=round(free / GIB, 6),
        required_bytes=required,
        required_gib=round(required / GIB, 6),
        safe=free >= required,
    )


def preflight(
    *,
    billing_project: str,
    cells: tuple[str, ...] = CHOSEN_CELLS,
) -> dict[str, Any]:
    """Verify billing, plan identity, dry-runs, ledger, and disk before any execution."""
    plan_info = validate_zero_cost_plan()
    if plan_info["plan_fingerprint"] != FROZEN_PLAN_FINGERPRINT:
        raise AcquisitionExecutionBlocked("frozen_plan_fingerprint_mismatch")
    billing = require_zero_cost_project(billing_project)
    if billing.billing_enabled:
        raise AcquisitionExecutionBlocked("BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED")
    if template_hashes() != load_plan()["templates"]:
        raise AcquisitionExecutionBlocked("sql_template_hash_mismatch")
    ledger = cumulative_executed_bytes()
    expected = expected_bytes_map()
    projected = ledger + sum(
        expected[(cell, tmpl)] for cell, tmpl in EXECUTION_ORDER if cell in cells
    )
    if projected > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise AcquisitionExecutionBlocked("projected_cumulative_exceeds_900gib_cap")

    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    dry_runs = []
    for cell, tmpl in EXECUTION_ORDER:
        if cell not in cells:
            continue
        sql = render_plan_query(tmpl, cell)
        exp = expected[(cell, tmpl)]
        job_config = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
            maximum_bytes_billed=exp,
        )
        job = client.query(sql, job_config=job_config, location="US")
        got = int(job.total_bytes_processed or 0)
        rel = abs(got - exp) / exp if exp else 0.0
        dry_runs.append(
            {
                "cell": cell,
                "template": tmpl,
                "expected_bytes": exp,
                "fresh_dry_run_bytes": got,
                "rel_abs_delta": rel,
                "within_tolerance": rel <= DRY_RUN_TOLERANCE,
                "query_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            }
        )
        if rel > DRY_RUN_TOLERANCE:
            raise AcquisitionExecutionBlocked(
                f"dry_run_mismatch_{cell}_{tmpl}:{got}_vs_{exp}"
            )

    disk = assess_disk_for_cells(cells)
    payload = {
        "timestamp": utc_now(),
        "billing_enabled": False,
        "quota_project_configured": True,
        "plan_fingerprint": plan_info["plan_fingerprint"],
        "ledger_executed_bytes": ledger,
        "projected_cumulative_bytes": projected,
        "cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
        "fresh_dry_runs": dry_runs,
        "disk": asdict(disk),
        "execution_authorized": bool(disk.safe),
        "blocker": (
            None
            if disk.safe
            else "insufficient_local_disk_for_frozen_extract_uncompressed_upper_bound"
        ),
    }
    if not disk.safe:
        raise AcquisitionExecutionBlocked(payload["blocker"])
    return payload


def stream_query_to_parquet(
    *,
    billing_project: str,
    cell: str,
    template: str,
    output_path: Path,
    page_rows: int = 100_000,
) -> dict[str, Any]:
    """Execute one frozen query and stream Arrow record batches to Parquet."""
    if output_path.exists():
        raise FileExistsError(f"immutable output exists: {output_path}")
    # Re-check billing immediately before the paid-capable API call.
    billing = require_zero_cost_project(billing_project)
    expected = expected_bytes_map()[(cell, template)]
    sql = render_plan_query(template, cell)
    # Fresh dry-run must still match before execution.
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    dry_cfg = bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, maximum_bytes_billed=expected
    )
    dry_job = client.query(sql, job_config=dry_cfg, location="US")
    dry_bytes = int(dry_job.total_bytes_processed or 0)
    if abs(dry_bytes - expected) / expected > DRY_RUN_TOLERANCE:
        raise AcquisitionExecutionBlocked(
            f"pre_exec_dry_run_mismatch:{dry_bytes}_vs_{expected}"
        )
    if cumulative_executed_bytes() + dry_bytes > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise AcquisitionExecutionBlocked("cumulative_cap_would_be_exceeded")

    require_zero_cost_project(billing_project)
    job_config = bigquery.QueryJobConfig(
        dry_run=False,
        use_query_cache=False,
        maximum_bytes_billed=expected,
    )
    started = utc_now()
    job = client.query(sql, job_config=job_config, location="US")
    result = job.result(page_size=page_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer: pq.ParquetWriter | None = None
    rows = 0
    try:
        # Prefer Arrow batches when available; fall back to row pages.
        to_arrow = getattr(result, "to_arrow", None)
        if callable(to_arrow):
            table = result.to_arrow(create_bqstorage_client=False)
            # Add cell/provenance columns.
            n = table.num_rows
            table = table.append_column("cell", pa.array([cell] * n))
            table = table.append_column(
                "source_template", pa.array([template] * n)
            )
            writer = pq.ParquetWriter(output_path, table.schema, compression="zstd")
            writer.write_table(table)
            rows = n
        else:
            batch_rows: list[dict[str, Any]] = []
            for row in result:
                item = dict(row.items())
                item["cell"] = cell
                item["source_template"] = template
                batch_rows.append(item)
                if len(batch_rows) >= page_rows:
                    batch = pa.Table.from_pylist(batch_rows)
                    if writer is None:
                        writer = pq.ParquetWriter(
                            output_path, batch.schema, compression="zstd"
                        )
                    writer.write_table(batch)
                    rows += len(batch_rows)
                    batch_rows = []
            if batch_rows:
                batch = pa.Table.from_pylist(batch_rows)
                if writer is None:
                    writer = pq.ParquetWriter(
                        output_path, batch.schema, compression="zstd"
                    )
                writer.write_table(batch)
                rows += len(batch_rows)
    finally:
        if writer is not None:
            writer.close()

    executed = int(job.total_bytes_processed or 0)
    ledger = record_executed_bytes(
        query_name=f"{cell}:{template}",
        executed_bytes=executed,
        job_id=job.job_id,
    )
    manifest = {
        "cell": cell,
        "template": template,
        "template_sha256": template_hashes()[template],
        "query_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "job_id": job.job_id,
        "dry_run_bytes": dry_bytes,
        "execution_bytes": executed,
        "maximum_bytes_billed": expected,
        "row_count": rows,
        "started_at": started,
        "finished_at": utc_now(),
        "output": {
            "path": str(output_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": file_sha256(output_path),
        },
        "cumulative_executed_bytes": ledger["cumulative_executed_bytes"],
        "billing_enabled_at_execution": False,
        "method_outcomes_computed": False,
    }
    side = output_path.with_suffix(output_path.suffix + ".manifest.json")
    side.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def write_blocked_acquisition_record(
    reason: str,
    preflight_payload: dict[str, Any] | None = None,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Persist a tracked, secret-free blocked-acquisition summary."""
    plan = load_plan()
    disk = assess_disk_for_cells(CHOSEN_CELLS)
    doc = {
        "schema_version": "google2019-v4b4-acquisition-record-v1",
        "gate": "V4B.4",
        "disposition": "ACQUISITION_BLOCKED",
        "blocker": reason,
        "plan_fingerprint": FROZEN_PLAN_FINGERPRINT,
        "plan_path": "configs/google2019_zero_cost_plan_v1.json",
        "chosen_cells": list(CHOSEN_CELLS),
        "billing_enabled": False,
        "executed_query_bytes": cumulative_executed_bytes(),
        "projected_plan_gib": plan["expected_cumulative_gib"],
        "cap_gib": 900,
        "disk": asdict(disk),
        "preflight": preflight_payload,
        "raw_artifacts_written": False,
        "canonical_artifacts_written": False,
        "cohort_frozen": False,
        "method_outcomes_computed": False,
        "recorded_at": utc_now(),
    }
    path = (
        Path(output_path)
        if output_path is not None
        else REPO_ROOT / "configs" / "google2019_v4b4_acquisition_record.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(doc) + "\n", encoding="utf-8")
    rel = (
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if path.is_relative_to(REPO_ROOT)
        else path.name
    )
    return {**doc, "record_sha256": file_sha256(path), "path": rel}
