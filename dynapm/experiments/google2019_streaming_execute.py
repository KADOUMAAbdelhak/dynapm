"""V4B.6 zero-cost streaming Google 2019 acquisition executor.

Per-cell order: events → request index → usage stream → local causal join /
canonicalize → validate. Never creates destination tables or GCS exports.
Never resubmits a completed/active BigQuery job; recovers by job ID first.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.experiments.google2019_acquisition import (
    CADENCE_US,
    CANONICAL_COLUMNS,
    GIB,
    MIN_SPAN_US,
    MIN_VALID_SLOTS,
    ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
    canonicalize_extract,
    cumulative_executed_bytes,
    load_byte_ledger,
    record_executed_bytes,
    require_zero_cost_project,
)
from dynapm.experiments.google2019_execute_acquisition import (
    DRY_RUN_TOLERANCE,
    FROZEN_PLAN_FINGERPRINT,
    expected_bytes_map,
)
from dynapm.experiments.google2019_streaming import (
    DEFAULT_CHUNK_ROWS,
    DEFAULT_MIN_FREE_RESERVE_GIB,
    ChunkedParquetWriter,
    StreamingPlanError,
    assess_disk_guard,
    load_storage_estimate,
    load_streaming_plan,
    peak_requirement_for_stage,
    read_checkpoint,
    write_checkpoint,
)
from dynapm.experiments.google2019_zero_cost_plan import (
    CHOSEN_CELLS,
    load_plan,
    render_plan_query,
    template_hashes,
)
from dynapm.experiments.replication_corpus import frozen_hashes as v4a_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
RAW_ROOT = MANAGED_ROOT / "raw"
CANONICAL_ROOT = MANAGED_ROOT / "canonical"
EXECUTION_ROOT = MANAGED_ROOT / "execution"
COHORT_ROOT = MANAGED_ROOT / "cohort"
RECORD_JSON = REPO_ROOT / "configs" / "google2019_v4b6_acquisition_record.json"

# V4B.5/V4B.6 order: events before usage (local causal join).
EXECUTION_ORDER = (
    ("e", "21_events_minimal.sql"),
    ("e", "20_usage_minimal.sql"),
    ("g", "21_events_minimal.sql"),
    ("g", "20_usage_minimal.sql"),
)

SOURCE_USAGE = "google.com:google-cluster-data.clusterdata_2019_{cell}.instance_usage"
SOURCE_EVENTS = "google.com:google-cluster-data.clusterdata_2019_{cell}.instance_events"


class StreamingAcquisitionBlocked(RuntimeError):
    """Safe stop before or during streaming acquisition."""


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def maximum_bytes_billed_for(expected_bytes: int) -> int:
    """Per-query billed cap: frozen expectation within the plan's 1% dry-run band.

    BigQuery dry-runs can under-estimate actual bytes billed by a tiny margin.
    Raising the per-query cap to ceil(expected * 1.01) matches the already-frozen
    dry-run tolerance without expanding the 900 GiB cumulative ledger cap.
    """
    return int(math.ceil(int(expected_bytes) * (1.0 + DRY_RUN_TOLERANCE)))


def usage_source(cell: str) -> str:
    return SOURCE_USAGE.format(cell=cell)


def events_source(cell: str) -> str:
    return SOURCE_EVENTS.format(cell=cell)


def query_output_path(cell: str, template: str) -> Path:
    stem = "events" if "events" in template else "usage"
    return RAW_ROOT / cell / f"{stem}.parquet"


def joined_staging_path(cell: str) -> Path:
    return MANAGED_ROOT / "staging" / cell / "joined.parquet"


def cell_canonical_dir(cell: str) -> Path:
    return CANONICAL_ROOT / cell


def streaming_preflight(*, billing_project: str) -> dict[str, Any]:
    """Fresh dry-runs, billing, plan identity, ledger, and streaming disk guards.

    Unlike V4B.3 plan validation, the live ledger may already be non-zero when
    resuming mid-acquisition; remaining projected bytes must still fit the cap.
    """
    plan = load_plan()
    from dynapm.core.provenance import fingerprint as _fp

    if _fp(plan) != FROZEN_PLAN_FINGERPRINT:
        raise StreamingAcquisitionBlocked("frozen_plan_fingerprint_mismatch")
    stream = load_streaming_plan()
    if stream["cells"] != list(CHOSEN_CELLS):
        raise StreamingAcquisitionBlocked("cells_must_remain_e_g")
    if stream["v4a_protocol_fingerprint"] != v4a_hashes()["protocol_fingerprint"]:
        raise StreamingAcquisitionBlocked("v4a_protocol_fingerprint_mismatch")
    if plan["v4a_protocol_fingerprint"] != v4a_hashes()["protocol_fingerprint"]:
        raise StreamingAcquisitionBlocked("plan_v4a_protocol_fingerprint_mismatch")
    billing = require_zero_cost_project(billing_project)
    if billing.billing_enabled:
        raise StreamingAcquisitionBlocked("BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED")
    if template_hashes() != plan["templates"]:
        raise StreamingAcquisitionBlocked("sql_template_hash_mismatch")

    ledger = cumulative_executed_bytes()
    expected = expected_bytes_map(plan)
    # Project only queries not yet recorded in the ledger.
    recorded = {
        e.get("query_name") for e in load_byte_ledger().get("executed_entries", [])
    }
    remaining = sum(
        expected[(c, t)]
        for c, t in EXECUTION_ORDER
        if f"{c}:{t}" not in recorded
    )
    projected = ledger + remaining
    if projected > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise StreamingAcquisitionBlocked("projected_cumulative_exceeds_900gib_cap")

    disk_e = assess_disk_guard(
        peak_requirement_for_stage("cell_e"),
        min_free_reserve_gib=float(stream["disk_guards"]["min_free_reserve_gib"]),
    )
    if not disk_e.safe:
        raise StreamingAcquisitionBlocked("insufficient_disk_for_cell_e_streaming_peak")

    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    dry_runs = []
    for cell, tmpl in EXECUTION_ORDER:
        sql = render_plan_query(tmpl, cell)
        exp = expected[(cell, tmpl)]
        require_zero_cost_project(billing_project)
        billed_cap = maximum_bytes_billed_for(exp)
        job_config = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
            maximum_bytes_billed=billed_cap,
        )
        job = client.query(sql, job_config=job_config, location="US")
        got = int(job.total_bytes_processed or 0)
        rel = abs(got - exp) / exp if exp else 0.0
        dry_runs.append(
            {
                "cell": cell,
                "template": tmpl,
                "expected_bytes": exp,
                "maximum_bytes_billed": billed_cap,
                "fresh_dry_run_bytes": got,
                "rel_abs_delta": rel,
                "within_tolerance": rel <= DRY_RUN_TOLERANCE,
                "query_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            }
        )
        if rel > DRY_RUN_TOLERANCE:
            raise StreamingAcquisitionBlocked(
                f"dry_run_mismatch_{cell}_{tmpl}:{got}_vs_{exp}"
            )

    return {
        "timestamp": utc_now(),
        "billing_enabled": False,
        "plan_fingerprint": FROZEN_PLAN_FINGERPRINT,
        "streaming_plan_fingerprint": fingerprint(stream),
        "ledger_executed_bytes": ledger,
        "remaining_projected_bytes": remaining,
        "projected_cumulative_bytes": projected,
        "cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
        "fresh_dry_runs": dry_runs,
        "disk_cell_e": asdict(disk_e),
        "execution_authorized": True,
        "method_outcomes_computed": False,
    }


def _client(billing_project: str):
    from google.cloud import bigquery  # type: ignore[import-not-found]

    billing = require_zero_cost_project(billing_project)
    return bigquery.Client(project=billing.project_id), billing


def recover_or_start_query(
    *,
    billing_project: str,
    cell: str,
    template: str,
    checkpoint: dict[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    """Return (job, meta). Never resubmit an active/completed job for this query."""
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client, _ = _client(billing_project)
    expected = expected_bytes_map()[(cell, template)]
    sql = render_plan_query(template, cell)
    query_sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    key = f"{cell}:{template}"
    prior = (checkpoint or {}).get("queries", {}).get(key)

    billed_cap = maximum_bytes_billed_for(expected)
    if prior and prior.get("job_id"):
        job = client.get_job(prior["job_id"], location="US")
        state = job.state
        if state in ("RUNNING", "PENDING"):
            return job, {
                "recovered": True,
                "resubmitted": False,
                "job_id": job.job_id,
                "state": state,
                "query_sha256": query_sha,
                "expected_bytes": expected,
                "maximum_bytes_billed": billed_cap,
                "sql": sql,
            }
        if state == "DONE" and not job.error_result:
            return job, {
                "recovered": True,
                "resubmitted": False,
                "job_id": job.job_id,
                "state": state,
                "query_sha256": query_sha,
                "expected_bytes": expected,
                "maximum_bytes_billed": billed_cap,
                "sql": sql,
                "execution_bytes": int(job.total_bytes_processed or 0),
            }
        # Failed prior job (e.g. exact-cap under-estimate): do not reuse; allow a
        # single new submission under the tolerance-banded billed cap. Never
        # resubmit while RUNNING/PENDING/DONE-success.
        if state == "DONE" and job.error_result:
            reason = (job.error_result or {}).get("reason")
            if reason != "bytesBilledLimitExceeded" or prior.get("retried_after_limit"):
                raise StreamingAcquisitionBlocked(
                    f"prior_job_failed_{key}:{job.error_result}"
                )
            # fall through to new submission
        else:
            raise StreamingAcquisitionBlocked(f"prior_job_unusable_state_{state}")

    require_zero_cost_project(billing_project)
    dry_cfg = bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, maximum_bytes_billed=billed_cap
    )
    dry_job = client.query(sql, job_config=dry_cfg, location="US")
    dry_bytes = int(dry_job.total_bytes_processed or 0)
    if abs(dry_bytes - expected) / expected > DRY_RUN_TOLERANCE:
        raise StreamingAcquisitionBlocked(
            f"pre_exec_dry_run_mismatch:{dry_bytes}_vs_{expected}"
        )
    if cumulative_executed_bytes() + dry_bytes > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise StreamingAcquisitionBlocked("cumulative_cap_would_be_exceeded")

    require_zero_cost_project(billing_project)
    job_config = bigquery.QueryJobConfig(
        dry_run=False,
        use_query_cache=False,
        maximum_bytes_billed=billed_cap,
    )
    job = client.query(sql, job_config=job_config, location="US")
    return job, {
        "recovered": False,
        "resubmitted": bool(prior and prior.get("job_id")),
        "retried_after_limit": bool(prior and prior.get("job_id")),
        "job_id": job.job_id,
        "state": job.state,
        "query_sha256": query_sha,
        "expected_bytes": expected,
        "maximum_bytes_billed": billed_cap,
        "dry_run_bytes": dry_bytes,
        "sql": sql,
    }


def iter_query_row_batches(job: Any, *, page_rows: int = DEFAULT_CHUNK_ROWS) -> Iterator[list[dict[str, Any]]]:
    """Paginate job results without loading the full Arrow table into memory."""
    result = job.result(page_size=page_rows)
    batch: list[dict[str, Any]] = []
    for row in result:
        batch.append(dict(row.items()))
        if len(batch) >= page_rows:
            yield batch
            batch = []
    if batch:
        yield batch


def stream_job_to_parquet(
    job: Any,
    output_path: Path,
    *,
    cell: str,
    template: str,
    page_rows: int = DEFAULT_CHUNK_ROWS,
    min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB,
) -> dict[str, Any]:
    """Stream paginated query rows into compressed Parquet with disk guards."""
    if output_path.exists():
        # Immutable resume: already materialized.
        return {
            "path": _rel(output_path),
            "sha256": file_sha256(output_path),
            "rows": int(pq.ParquetFile(output_path).metadata.num_rows),
            "resumed_existing": True,
        }
    writer = ChunkedParquetWriter(
        output_path,
        chunk_rows=page_rows,
        min_free_reserve_gib=min_free_reserve_gib,
    )
    try:
        for batch in iter_query_row_batches(job, page_rows=page_rows):
            status = assess_disk_guard(0.25, min_free_reserve_gib=min_free_reserve_gib)
            if not status.safe:
                writer.cleanup_temp()
                raise StreamingAcquisitionBlocked(
                    f"disk_guard_during_stream_usable_{status.usable_gib}"
                )
            for row in batch:
                row["cell"] = cell
                row["source_template"] = template
            writer.write_rows(batch)
            if writer.rows_written % (page_rows * 10) < page_rows:
                print(
                    f"[stream] {cell}/{template} rows={writer.rows_written} "
                    f"usable_gib={status.usable_gib}",
                    flush=True,
                )
        meta = writer.finalize()
    except Exception:
        writer.cleanup_temp()
        raise
    return meta


def build_request_index(events_path: Path) -> dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Map (collection_id, instance_index) → sorted (time, request_cpu, request_memory)."""
    from dynapm.experiments.google2019_requests import prepare_request_history
    table = pq.read_table(events_path, columns=["time", "collection_id", "instance_index", "request_cpu", "request_memory"])
    frame, _, _, _ = prepare_request_history(table.to_pandas())
    buckets: dict[tuple[int, int], list[tuple[int, float, float]]] = defaultdict(list)
    for row in frame.itertuples(index=False):
        key = (int(row.collection_id), int(row.instance_index))
        buckets[key].append((int(row.time), float(row.request_cpu), float(row.request_memory)))
    index: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for key, items in buckets.items():
        items.sort(key=lambda x: x[0])
        times = np.fromiter((x[0] for x in items), dtype=np.int64, count=len(items))
        cpus = np.fromiter((x[1] for x in items), dtype=np.float64, count=len(items))
        mems = np.fromiter((x[2] for x in items), dtype=np.float64, count=len(items))
        index[key] = (times, cpus, mems)
    return index


def causal_request_lookup(
    index: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]],
    collection_id: int,
    instance_index: int,
    start_time: int,
) -> tuple[float, float, int] | None:
    """Latest request event with time <= usage start_time."""
    hist = index.get((collection_id, instance_index))
    if hist is None:
        return None
    times, cpus, mems = hist
    i = int(times.searchsorted(start_time, side="right")) - 1
    if i < 0:
        return None
    return float(cpus[i]), float(mems[i]), int(times[i])


def join_usage_batch(
    batch: list[dict[str, Any]],
    *,
    cell: str,
    index: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Attach causal request fields; count rows with no usable request."""
    joined: list[dict[str, Any]] = []
    missing = 0
    u_src = usage_source(cell)
    e_src = events_source(cell)
    for row in batch:
        cid = int(row["collection_id"])
        idx = int(row["instance_index"])
        start = int(row["start_time"])
        hit = causal_request_lookup(index, cid, idx, start)
        if hit is None:
            missing += 1
            continue
        req_cpu, req_mem, req_time = hit
        joined.append(
            {
                "cell": cell,
                "collection_id": cid,
                "instance_index": idx,
                "collection_type": int(row.get("collection_type") or 1),
                "start_time": start,
                "end_time": int(row["end_time"]),
                "average_cpu": float(row["average_cpu"]),
                "average_memory": float(row["average_memory"]),
                "request_cpu": req_cpu,
                "request_memory": req_mem,
                "request_event_time": req_time,
                "usage_source_table": u_src,
                "request_source_table": e_src,
            }
        )
    return joined, {"missing_request": missing}


def stream_usage_to_joined(
    job: Any,
    *,
    cell: str,
    index: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray]],
    output_path: Path,
    page_rows: int = DEFAULT_CHUNK_ROWS,
    min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB,
) -> dict[str, Any]:
    """Stream usage pages, causal-join, write compressed joined staging Parquet."""
    if output_path.exists():
        return {
            "path": _rel(output_path),
            "sha256": file_sha256(output_path),
            "rows": int(pq.ParquetFile(output_path).metadata.num_rows),
            "resumed_existing": True,
            "missing_request": None,
        }
    writer = ChunkedParquetWriter(
        output_path, chunk_rows=page_rows, min_free_reserve_gib=min_free_reserve_gib
    )
    missing_total = 0
    raw_usage_rows = 0
    try:
        for batch in iter_query_row_batches(job, page_rows=page_rows):
            status = assess_disk_guard(0.5, min_free_reserve_gib=min_free_reserve_gib)
            if not status.safe:
                writer.cleanup_temp()
                raise StreamingAcquisitionBlocked(
                    f"disk_guard_during_usage_usable_{status.usable_gib}"
                )
            raw_usage_rows += len(batch)
            joined, counts = join_usage_batch(batch, cell=cell, index=index)
            missing_total += counts["missing_request"]
            if joined:
                writer.write_rows(joined)
            if raw_usage_rows % (page_rows * 10) < page_rows:
                print(
                    f"[usage] {cell} raw={raw_usage_rows} joined={writer.rows_written} "
                    f"missing_req={missing_total} usable_gib={status.usable_gib}",
                    flush=True,
                )
        meta = writer.finalize()
    except Exception:
        writer.cleanup_temp()
        raise
    return {
        **meta,
        "raw_usage_rows": raw_usage_rows,
        "missing_request": missing_total,
        "resumed_existing": False,
    }


def _write_canonical_bundle(
    cell: str,
    canonical: pd.DataFrame,
    entities: pd.DataFrame,
    rejected: pd.DataFrame,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    out = cell_canonical_dir(cell)
    if out.exists():
        raise FileExistsError(f"immutable canonical exists: {out}")
    out.mkdir(parents=True)
    canonical_path = out / "canonical_usage.parquet"
    entities_path = out / "entity_manifest.parquet"
    rejected_path = out / "rejected_rows.parquet"
    canonical = canonical.sort_values(
        ["cell", "collection_id", "instance_index", "timestamp_us"], kind="mergesort"
    ).reset_index(drop=True)
    entities = entities.sort_values(
        ["cell", "collection_id", "instance_index"], kind="mergesort"
    ).reset_index(drop=True)
    canonical.to_parquet(canonical_path, index=False)
    entities.to_parquet(entities_path, index=False)
    rejected.to_parquet(rejected_path, index=False)
    continuity = {
        "entities_with_missing_slots": int((entities["missing_slots"] > 0).sum())
        if len(entities)
        else 0,
        "entities_with_request_change": int(entities["has_request_change"].sum())
        if len(entities)
        else 0,
        "total_missing_slots": int(entities["missing_slots"].sum()) if len(entities) else 0,
        "min_timestamp_us": int(canonical["timestamp_us"].min()) if len(canonical) else None,
        "max_timestamp_us": int(canonical["timestamp_us"].max()) if len(canonical) else None,
        "cadence_us": CADENCE_US,
    }
    manifest = {
        "cell": cell,
        "schema_version": "google2019-streaming-canonical-v1",
        "row_count": int(len(canonical)),
        "entity_count": int(len(entities)),
        "eligible_entity_count": int(entities["eligible"].sum()) if len(entities) else 0,
        "diagnostics": diagnostics,
        "continuity": continuity,
        "artifacts": {
            "canonical_usage": {
                "path": _rel(canonical_path),
                "sha256": file_sha256(canonical_path),
            },
            "entity_manifest": {
                "path": _rel(entities_path),
                "sha256": file_sha256(entities_path),
            },
            "rejected_rows": {
                "path": _rel(rejected_path),
                "sha256": file_sha256(rejected_path),
            },
        },
        "method_outcomes_computed": False,
        "written_at": utc_now(),
    }
    (out / "manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def write_cell_canonical_from_joined(
    joined_path: Path,
    cell: str,
    *,
    max_in_memory_rows: int = 25_000_000,
    n_parts: int = 64,
) -> dict[str, Any]:
    """Run frozen canonicalize_extract; partition when joined rows exceed memory budget."""
    n_rows = int(pq.ParquetFile(joined_path).metadata.num_rows)
    if n_rows <= max_in_memory_rows:
        frame = pd.read_parquet(joined_path)
        canonical, entities, details = canonicalize_extract(frame)
        return _write_canonical_bundle(
            cell, canonical, entities, details["rejected"], details["diagnostics"]
        )

    # Entity-hash partitions: each entity wholly in one part → eligibility unchanged.
    part_dir = joined_path.parent / "parts"
    if part_dir.exists():
        for p in part_dir.glob("*.parquet"):
            p.unlink()
    else:
        part_dir.mkdir(parents=True)
    writers: dict[int, ChunkedParquetWriter] = {}
    pf = pq.ParquetFile(joined_path)
    for batch in pf.iter_batches(batch_size=DEFAULT_CHUNK_ROWS):
        frame = batch.to_pandas()
        keys = (
            frame["collection_id"].astype("int64") * 1_000_003
            + frame["instance_index"].astype("int64")
        ) % n_parts
        for part_id, group in frame.groupby(keys, sort=False):
            pid = int(part_id)
            if pid not in writers:
                writers[pid] = ChunkedParquetWriter(
                    part_dir / f"part_{pid:03d}.parquet",
                    chunk_rows=DEFAULT_CHUNK_ROWS,
                    min_free_reserve_gib=DEFAULT_MIN_FREE_RESERVE_GIB,
                )
            writers[pid].write_rows(group.to_dict(orient="records"))
    for w in writers.values():
        w.finalize()

    out = cell_canonical_dir(cell)
    if out.exists():
        raise FileExistsError(f"immutable canonical exists: {out}")
    out.mkdir(parents=True)
    canonical_path = out / "canonical_usage.parquet"
    entities_path = out / "entity_manifest.parquet"
    rejected_path = out / "rejected_rows.parquet"
    canon_writer: pq.ParquetWriter | None = None
    ent_parts: list[pd.DataFrame] = []
    rej_parts: list[pd.DataFrame] = []
    diag_acc = {
        "input_rows": 0,
        "canonical_rows": 0,
        "rejected_rows": 0,
        "duplicate_rows": 0,
        "entities": 0,
        "eligible_entities": 0,
        "cells": [cell],
        "utilization_above_one_cpu_rows": 0,
        "utilization_above_one_memory_rows": 0,
        "method_outcomes_computed": False,
    }
    min_ts = None
    max_ts = None
    try:
        for part_path in sorted(part_dir.glob("part_*.parquet")):
            part_frame = pd.read_parquet(part_path)
            canonical, entities, details = canonicalize_extract(part_frame)
            if len(canonical):
                table = pa.Table.from_pandas(canonical, preserve_index=False)
                if canon_writer is None:
                    canon_writer = pq.ParquetWriter(
                        canonical_path, table.schema, compression="zstd"
                    )
                canon_writer.write_table(table)
                cmin = int(canonical["timestamp_us"].min())
                cmax = int(canonical["timestamp_us"].max())
                min_ts = cmin if min_ts is None else min(min_ts, cmin)
                max_ts = cmax if max_ts is None else max(max_ts, cmax)
            ent_parts.append(entities)
            rej_parts.append(details["rejected"])
            d = details["diagnostics"]
            for k in (
                "input_rows",
                "canonical_rows",
                "rejected_rows",
                "duplicate_rows",
                "entities",
                "eligible_entities",
                "utilization_above_one_cpu_rows",
                "utilization_above_one_memory_rows",
            ):
                diag_acc[k] += int(d[k])
            part_path.unlink()
    finally:
        if canon_writer is not None:
            canon_writer.close()
    if part_dir.exists():
        try:
            part_dir.rmdir()
        except OSError:
            pass
    entities = (
        pd.concat(ent_parts, ignore_index=True)
        .sort_values(["cell", "collection_id", "instance_index"], kind="mergesort")
        .reset_index(drop=True)
        if ent_parts
        else pd.DataFrame()
    )
    rejected = pd.concat(rej_parts, ignore_index=True) if rej_parts else pd.DataFrame()
    if not canonical_path.exists():
        # No rows: still write empty parquet with schema via empty canonicalize.
        empty = pd.DataFrame(columns=list(CANONICAL_COLUMNS))
        empty.to_parquet(canonical_path, index=False)
    entities.to_parquet(entities_path, index=False)
    rejected.to_parquet(rejected_path, index=False)
    continuity = {
        "entities_with_missing_slots": int((entities["missing_slots"] > 0).sum())
        if len(entities)
        else 0,
        "entities_with_request_change": int(entities["has_request_change"].sum())
        if len(entities)
        else 0,
        "total_missing_slots": int(entities["missing_slots"].sum()) if len(entities) else 0,
        "min_timestamp_us": min_ts,
        "max_timestamp_us": max_ts,
        "cadence_us": CADENCE_US,
    }
    manifest = {
        "cell": cell,
        "schema_version": "google2019-streaming-canonical-v1",
        "row_count": int(diag_acc["canonical_rows"]),
        "entity_count": int(len(entities)),
        "eligible_entity_count": int(entities["eligible"].sum()) if len(entities) else 0,
        "diagnostics": diag_acc,
        "continuity": continuity,
        "partitioned": True,
        "n_parts": n_parts,
        "artifacts": {
            "canonical_usage": {
                "path": _rel(canonical_path),
                "sha256": file_sha256(canonical_path),
            },
            "entity_manifest": {
                "path": _rel(entities_path),
                "sha256": file_sha256(entities_path),
            },
            "rejected_rows": {
                "path": _rel(rejected_path),
                "sha256": file_sha256(rejected_path),
            },
        },
        "method_outcomes_computed": False,
        "written_at": utc_now(),
    }
    (out / "manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def validate_cell_artifacts(cell: str, *, sample_n: int = 1000) -> dict[str, Any]:
    """Full per-cell scientific validation (outcome-blind; streaming-safe)."""
    out = cell_canonical_dir(cell)
    canon_path = out / "canonical_usage.parquet"
    entities = pd.read_parquet(out / "entity_manifest.parquet")
    findings: list[str] = []
    pf = pq.ParquetFile(canon_path)
    n_rows = int(pf.metadata.num_rows)
    schema_names = set(pf.schema_arrow.names)
    if set(CANONICAL_COLUMNS) - schema_names:
        findings.append("missing_canonical_columns")
    if n_rows == 0:
        findings.append("empty_canonical")

    above_one = 0
    request_after = False
    nonfinite = False
    bad_cadence = False
    # Reservoir sample for independent normalization reconstruction.
    rng = np.random.default_rng(0)
    sample_rows: list[dict[str, Any]] = []
    seen = 0
    for batch in pf.iter_batches(
        batch_size=DEFAULT_CHUNK_ROWS,
        columns=[
            "timestamp_us",
            "cpu_utilization",
            "memory_utilization",
            "average_cpu_ncu",
            "average_memory_normalized_ram",
            "request_cpu_ncu",
            "request_memory_normalized_ram",
            "request_event_time_us",
        ],
    ):
        frame = batch.to_pandas()
        if not (frame["timestamp_us"] % CADENCE_US == 0).all():
            bad_cadence = True
        if not np.isfinite(
            frame[["cpu_utilization", "memory_utilization"]].to_numpy(dtype=float)
        ).all():
            nonfinite = True
        # Causal rule (frozen canonicalize): request_event_time <= start_time.
        # timestamp_us = floor(start_time / CADENCE); start_time ∈ [timestamp, timestamp+CADENCE).
        # So a valid request may be > timestamp_us but still < timestamp_us + CADENCE_US.
        if (frame["request_event_time_us"] >= frame["timestamp_us"] + CADENCE_US).any():
            request_after = True
        above_one += int((frame["cpu_utilization"] > 1).sum())
        for row in frame.to_dict(orient="records"):
            seen += 1
            if len(sample_rows) < sample_n:
                sample_rows.append(row)
            else:
                j = int(rng.integers(0, seen))
                if j < sample_n:
                    sample_rows[j] = row

    if bad_cadence:
        findings.append("timestamp_not_on_300s_cadence")
    if nonfinite:
        findings.append("nonfinite_utilization")
    if request_after:
        findings.append("request_after_usage_timestamp")

    if sample_rows:
        sample = pd.DataFrame(sample_rows)
        cpu_re = sample["average_cpu_ncu"] / sample["request_cpu_ncu"]
        mem_re = sample["average_memory_normalized_ram"] / sample[
            "request_memory_normalized_ram"
        ]
        if not np.allclose(sample["cpu_utilization"], cpu_re, rtol=0, atol=1e-12):
            findings.append("cpu_normalization_mismatch")
        if not np.allclose(sample["memory_utilization"], mem_re, rtol=0, atol=1e-12):
            findings.append("memory_normalization_mismatch")

    # Duplicate check on a bounded in-memory path when small; else trust
    # canonicalize_extract partition invariants + spot-check first row group.
    if n_rows and n_rows <= 25_000_000:
        keys = pd.read_parquet(
            canon_path,
            columns=["cell", "collection_id", "instance_index", "timestamp_us"],
        )
        if keys.duplicated(
            ["cell", "collection_id", "instance_index", "timestamp_us"], keep=False
        ).any():
            findings.append("duplicate_canonical_buckets")
    elif n_rows:
        first = next(
            pf.iter_batches(
                batch_size=min(DEFAULT_CHUNK_ROWS, n_rows),
                columns=["cell", "collection_id", "instance_index", "timestamp_us"],
            )
        ).to_pandas()
        if first.duplicated(
            ["cell", "collection_id", "instance_index", "timestamp_us"], keep=False
        ).any():
            findings.append("duplicate_canonical_buckets")

    if len(entities):
        bad_elig = entities.loc[
            entities["eligible"]
            & (
                (entities["observed_slots"] < MIN_VALID_SLOTS)
                | (
                    (entities["last_timestamp_us"] - entities["first_timestamp_us"])
                    < MIN_SPAN_US
                )
            )
        ]
        if len(bad_elig):
            findings.append("eligible_entities_violate_thresholds")

    gaps = int(entities["missing_slots"].sum()) if len(entities) else 0
    return {
        "cell": cell,
        "passed": len(findings) == 0,
        "findings": findings,
        "canonical_rows": n_rows,
        "entities": int(len(entities)),
        "eligible_entities": int(entities["eligible"].sum()) if len(entities) else 0,
        "utilization_above_one_cpu_rows": above_one,
        "total_missing_slots": gaps,
        "sample_normalization_rows": int(len(sample_rows)),
    }


def measure_path_gib(path: Path) -> float:
    if path.is_file():
        return path.stat().st_size / GIB
    if not path.exists():
        return 0.0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total / GIB


def disk_safe_for_g_after_e(*, min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB) -> dict[str, Any]:
    """Re-assess g peak using actual e retained size + planning g peak components."""
    est = load_storage_estimate()
    e_canon = measure_path_gib(cell_canonical_dir("e"))
    e_events = measure_path_gib(query_output_path("e", "21_events_minimal.sql"))
    # Peak during g ≈ retained e artifacts + planned g streaming peak (point),
    # substituting actual e canonical for the planned retained e slice.
    planned_e_retained = float(
        est["cells"]["e"]["point_mean_fraction"]["retained_canonical_gib"]
    )
    planned_g_peak = float(est["summary"]["peak_g_point_gib"])
    # g peak already includes its own scratch; add actual e retained (canonical+events audit).
    required = planned_g_peak + e_canon + e_events
    # Also compare against frozen eg peak adjusted by e size delta.
    planned_eg = float(est["summary"]["peak_during_g_with_e_canonical_point_gib"])
    adjusted_eg = planned_eg - planned_e_retained + e_canon + e_events
    required = max(required, adjusted_eg)
    status = assess_disk_guard(required, min_free_reserve_gib=min_free_reserve_gib)
    return {
        "required_peak_gib": round(required, 6),
        "e_canonical_gib": round(e_canon, 6),
        "e_events_gib": round(e_events, 6),
        "disk": asdict(status),
        "safe": status.safe,
    }


def acquire_cell(
    *,
    billing_project: str,
    cell: str,
    page_rows: int = DEFAULT_CHUNK_ROWS,
) -> dict[str, Any]:
    """Run events→index→usage→canonicalize→validate for one cell."""
    if cell not in CHOSEN_CELLS:
        raise StreamingAcquisitionBlocked("cell_not_in_frozen_plan")
    reserve = float(load_streaming_plan()["disk_guards"]["min_free_reserve_gib"])
    cp = read_checkpoint(cell) or {"queries": {}, "stage": "start"}
    query_ledger: list[dict[str, Any]] = list(cp.get("query_ledger") or [])

    # --- events ---
    events_path = query_output_path(cell, "21_events_minimal.sql")
    if not events_path.exists():
        require_zero_cost_project(billing_project)
        job, meta = recover_or_start_query(
            billing_project=billing_project,
            cell=cell,
            template="21_events_minimal.sql",
            checkpoint=cp,
        )
        cp.setdefault("queries", {})[f"{cell}:21_events_minimal.sql"] = {
            "job_id": meta["job_id"],
            "query_sha256": meta["query_sha256"],
            "expected_bytes": meta["expected_bytes"],
            "maximum_bytes_billed": meta.get("maximum_bytes_billed"),
            "retried_after_limit": bool(meta.get("retried_after_limit")),
        }
        write_checkpoint(cell, {**cp, "stage": "events_running"})
        started = utc_now()
        job.result()  # wait if recovered mid-flight
        require_zero_cost_project(billing_project)
        out_meta = stream_job_to_parquet(
            job,
            events_path,
            cell=cell,
            template="21_events_minimal.sql",
            page_rows=page_rows,
            min_free_reserve_gib=reserve,
        )
        executed = int(job.total_bytes_processed or 0)
        already = any(e.get("job_id") == job.job_id for e in query_ledger)
        if not already:
            ledger = record_executed_bytes(
                query_name=f"{cell}:21_events_minimal.sql",
                executed_bytes=executed,
                job_id=job.job_id,
            )
            entry = {
                "cell": cell,
                "template": "21_events_minimal.sql",
                "template_sha256": template_hashes()["21_events_minimal.sql"],
                "query_sha256": meta["query_sha256"],
                "job_id": job.job_id,
                "dry_run_bytes": meta.get("dry_run_bytes") or meta["expected_bytes"],
                "execution_bytes": executed,
                "started_at": started,
                "finished_at": utc_now(),
                "status": "DONE",
                "artifact": out_meta,
                "cumulative_executed_bytes": ledger["cumulative_executed_bytes"],
                "recovered": meta.get("recovered", False),
            }
            query_ledger.append(entry)
        cp = {
            **cp,
            "stage": "events_done",
            "query_ledger": query_ledger,
            "events_artifact": out_meta,
        }
        write_checkpoint(cell, cp)
    else:
        out_meta = {
            "path": _rel(events_path),
            "sha256": file_sha256(events_path),
            "rows": int(pq.ParquetFile(events_path).metadata.num_rows),
            "resumed_existing": True,
        }
        cp = {**cp, "stage": "events_done", "events_artifact": out_meta, "query_ledger": query_ledger}
        write_checkpoint(cell, cp)

    # --- usage → joined (build request index only if still needed) ---
    joined_path = joined_staging_path(cell)
    canon_done = (cell_canonical_dir(cell) / "manifest.json").exists()
    if not joined_path.exists() and not canon_done:
        index = build_request_index(events_path)
        cp = {**cp, "stage": "index_done", "request_index_entities": len(index)}
        write_checkpoint(cell, cp)
        require_zero_cost_project(billing_project)
        job, meta = recover_or_start_query(
            billing_project=billing_project,
            cell=cell,
            template="20_usage_minimal.sql",
            checkpoint=cp,
        )
        cp.setdefault("queries", {})[f"{cell}:20_usage_minimal.sql"] = {
            "job_id": meta["job_id"],
            "query_sha256": meta["query_sha256"],
            "expected_bytes": meta["expected_bytes"],
            "maximum_bytes_billed": meta.get("maximum_bytes_billed"),
            "retried_after_limit": bool(meta.get("retried_after_limit")),
        }
        write_checkpoint(cell, {**cp, "stage": "usage_running"})
        started = utc_now()
        job.result()
        require_zero_cost_project(billing_project)
        join_meta = stream_usage_to_joined(
            job,
            cell=cell,
            index=index,
            output_path=joined_path,
            page_rows=page_rows,
            min_free_reserve_gib=reserve,
        )
        del index
        executed = int(job.total_bytes_processed or 0)
        already = any(e.get("job_id") == job.job_id for e in query_ledger)
        if not already:
            ledger = record_executed_bytes(
                query_name=f"{cell}:20_usage_minimal.sql",
                executed_bytes=executed,
                job_id=job.job_id,
            )
            entry = {
                "cell": cell,
                "template": "20_usage_minimal.sql",
                "template_sha256": template_hashes()["20_usage_minimal.sql"],
                "query_sha256": meta["query_sha256"],
                "job_id": job.job_id,
                "dry_run_bytes": meta.get("dry_run_bytes") or meta["expected_bytes"],
                "execution_bytes": executed,
                "started_at": started,
                "finished_at": utc_now(),
                "status": "DONE",
                "artifact": join_meta,
                "cumulative_executed_bytes": ledger["cumulative_executed_bytes"],
                "recovered": meta.get("recovered", False),
            }
            query_ledger.append(entry)
        cp = {
            **cp,
            "stage": "joined_done",
            "query_ledger": query_ledger,
            "joined_artifact": join_meta,
        }
        write_checkpoint(cell, cp)
    elif joined_path.exists():
        join_meta = {
            "path": _rel(joined_path),
            "sha256": file_sha256(joined_path),
            "rows": int(pq.ParquetFile(joined_path).metadata.num_rows),
            "resumed_existing": True,
        }
    else:
        join_meta = None

    # --- canonicalize ---
    if not (cell_canonical_dir(cell) / "manifest.json").exists():
        canon_manifest = write_cell_canonical_from_joined(joined_path, cell)
        # Remove joined staging (not needed after canonical; audit fields retained).
        if joined_path.exists():
            joined_path.unlink()
        staging_dir = joined_path.parent
        if staging_dir.exists() and not any(staging_dir.iterdir()):
            staging_dir.rmdir()
        cp = {**cp, "stage": "canonical_done", "canonical_manifest": canon_manifest}
        write_checkpoint(cell, cp)
    else:
        canon_manifest = read_json(cell_canonical_dir(cell) / "manifest.json")

    validation = validate_cell_artifacts(cell)
    if not validation["passed"]:
        raise StreamingAcquisitionBlocked(f"cell_{cell}_validation_failed:{validation['findings']}")
    cp = {**cp, "stage": "validated", "validation": validation, "query_ledger": query_ledger}
    write_checkpoint(cell, cp)
    return {
        "cell": cell,
        "checkpoint_stage": cp["stage"],
        "canonical": canon_manifest,
        "validation": validation,
        "query_ledger": query_ledger,
        "disk_gib": {
            "events": round(measure_path_gib(events_path), 6),
            "canonical": round(measure_path_gib(cell_canonical_dir(cell)), 6),
        },
    }


def freeze_cohort(cells: tuple[str, ...] | list[str] = CHOSEN_CELLS) -> dict[str, Any]:
    """Freeze eligible entities using existing outcome-blind eligibility rules only."""
    COHORT_ROOT.mkdir(parents=True, exist_ok=True)
    frames = []
    exclusions = []
    for cell in cells:
        entities = pd.read_parquet(cell_canonical_dir(cell) / "entity_manifest.parquet")
        frames.append(entities.loc[entities["eligible"]].copy())
        exclusions.append(entities.loc[~entities["eligible"]].copy())
    cohort = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    excluded = pd.concat(exclusions, ignore_index=True) if exclusions else pd.DataFrame()
    cohort_path = COHORT_ROOT / "replication_cohort.parquet"
    excl_path = COHORT_ROOT / "exclusion_manifest.parquet"
    if cohort_path.exists() or excl_path.exists():
        raise FileExistsError("immutable cohort artifacts exist")
    cohort.to_parquet(cohort_path, index=False)
    excluded.to_parquet(excl_path, index=False)
    # Continuity / missingness audit across cohort entities.
    audit = {
        "eligible_entities": int(len(cohort)),
        "excluded_entities": int(len(excluded)),
        "exclusion_reason_counts": (
            excluded["exclusion_reason"].value_counts(dropna=False).astype(int).to_dict()
            if len(excluded)
            else {}
        ),
        "cells": list(cells),
        "total_missing_slots_eligible": int(cohort["missing_slots"].sum()) if len(cohort) else 0,
        "entities_with_request_change": int(cohort["has_request_change"].sum())
        if len(cohort)
        else 0,
        "min_observed_slots": int(cohort["observed_slots"].min()) if len(cohort) else None,
        "eligibility_rules": {
            "min_valid_slots": MIN_VALID_SLOTS,
            "min_span_us": MIN_SPAN_US,
            "outcome_blind": True,
        },
    }
    audit_path = COHORT_ROOT / "continuity_missingness_audit.json"
    audit_path.write_text(canonical_json(audit) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "google2019-replication-cohort-v1",
        "cells": list(cells),
        "eligible_entities": int(len(cohort)),
        "excluded_entities": int(len(excluded)),
        "artifacts": {
            "cohort": {
                "path": _rel(cohort_path),
                "sha256": file_sha256(cohort_path),
            },
            "exclusions": {
                "path": _rel(excl_path),
                "sha256": file_sha256(excl_path),
            },
            "continuity_audit": {
                "path": _rel(audit_path),
                "sha256": file_sha256(audit_path),
            },
        },
        "audit": audit,
        "method_outcomes_computed": False,
        "frozen_at": utc_now(),
    }
    man_path = COHORT_ROOT / "cohort_manifest.json"
    man_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return {**manifest, "manifest_sha256": file_sha256(man_path)}


def write_acquisition_record(doc: dict[str, Any]) -> dict[str, Any]:
    RECORD_JSON.parent.mkdir(parents=True, exist_ok=True)
    RECORD_JSON.write_text(canonical_json(doc) + "\n", encoding="utf-8")
    return {**doc, "record_sha256": file_sha256(RECORD_JSON), "path": str(RECORD_JSON.relative_to(REPO_ROOT))}


def run_streaming_acquisition(*, billing_project: str) -> dict[str, Any]:
    """Full V4B.6 pipeline: preflight → e → (disk gate) → g → cohort."""
    EXECUTION_ROOT.mkdir(parents=True, exist_ok=True)
    preflight = streaming_preflight(billing_project=billing_project)
    (EXECUTION_ROOT / "preflight.json").write_text(
        canonical_json(preflight) + "\n", encoding="utf-8"
    )

    cell_results: dict[str, Any] = {}
    disposition = "GOOGLE_CORPUS_ACQUIRED"
    blocker = None

    cell_results["e"] = acquire_cell(billing_project=billing_project, cell="e")
    g_gate = disk_safe_for_g_after_e()
    (EXECUTION_ROOT / "g_disk_gate.json").write_text(
        canonical_json(g_gate) + "\n", encoding="utf-8"
    )
    if not g_gate["safe"]:
        disposition = "ACQUISITION_PARTIAL"
        blocker = "g_disk_guard_refuse_after_e_measurement"
        cohort = None
    else:
        cell_results["g"] = acquire_cell(billing_project=billing_project, cell="g")
        cohort = freeze_cohort(("e", "g"))

    ledger_bytes = cumulative_executed_bytes()
    record = write_acquisition_record(
        {
            "schema_version": "google2019-v4b6-acquisition-record-v1",
            "gate": "V4B.6",
            "disposition": disposition,
            "blocker": blocker,
            "plan_fingerprint": FROZEN_PLAN_FINGERPRINT,
            "streaming_plan_fingerprint": preflight["streaming_plan_fingerprint"],
            "v4a_protocol_fingerprint": v4a_hashes()["protocol_fingerprint"],
            "chosen_cells": list(CHOSEN_CELLS),
            "cells_acquired": sorted(cell_results.keys()),
            "billing_enabled": False,
            "executed_query_bytes": ledger_bytes,
            "executed_query_gib": round(ledger_bytes / GIB, 6),
            "cap_gib": 900,
            "preflight": {
                "projected_cumulative_bytes": preflight["projected_cumulative_bytes"],
                "fresh_dry_runs": preflight["fresh_dry_runs"],
            },
            "cell_results": {
                k: {
                    "canonical_rows": v["validation"]["canonical_rows"],
                    "entities": v["validation"]["entities"],
                    "eligible_entities": v["validation"]["eligible_entities"],
                    "validation_passed": v["validation"]["passed"],
                    "disk_gib": v["disk_gib"],
                    "query_jobs": [
                        {
                            "template": e["template"],
                            "job_id": e["job_id"],
                            "execution_bytes": e["execution_bytes"],
                            "query_sha256": e["query_sha256"],
                        }
                        for e in v["query_ledger"]
                        if e["cell"] == k
                    ],
                }
                for k, v in cell_results.items()
            },
            "g_disk_gate": g_gate,
            "cohort": (
                {
                    "eligible_entities": cohort["eligible_entities"],
                    "excluded_entities": cohort["excluded_entities"],
                    "manifest_sha256": cohort["manifest_sha256"],
                }
                if cohort
                else None
            ),
            "next_gate": (
                "V4C — Google corpus/protocol validation"
                if disposition == "GOOGLE_CORPUS_ACQUIRED"
                else None
            ),
            "method_outcomes_computed": False,
            "recorded_at": utc_now(),
        }
    )
    # Persist full query ledger copy under managed root.
    full_ledger = []
    for v in cell_results.values():
        full_ledger.extend(v["query_ledger"])
    (EXECUTION_ROOT / "query_ledger.json").write_text(
        canonical_json({"entries": full_ledger, "cumulative_executed_bytes": ledger_bytes})
        + "\n",
        encoding="utf-8",
    )
    return record
