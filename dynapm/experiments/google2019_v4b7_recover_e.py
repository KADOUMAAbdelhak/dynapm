"""V4B.7 — recover cell e usage via Storage Read; never query cell g."""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, utc_now
from dynapm.experiments.google2019_acquisition import (
    GIB,
    cumulative_executed_bytes,
    load_byte_ledger,
    record_executed_bytes,
    require_zero_cost_project,
)
from dynapm.experiments.google2019_acquisition_monitor import (
    HEARTBEAT_SECONDS,
    build_heartbeat,
    disk_snapshot,
    ledger_snapshot,
    write_status,
)
from dynapm.experiments.google2019_execute_acquisition import (
    DRY_RUN_TOLERANCE,
    expected_bytes_map,
)
from dynapm.experiments.google2019_storage_read import (
    StorageReadBlocked,
    download_job_result_storage_read,
    merge_part_parquets,
    temp_table_from_job,
    ttl_remaining_seconds,
    verify_storage_read_zero_spend,
)
from dynapm.experiments.google2019_streaming import (
    DEFAULT_CHUNK_ROWS,
    DEFAULT_MIN_FREE_RESERVE_GIB,
    ChunkedParquetWriter,
    assess_disk_guard,
    read_checkpoint,
    write_checkpoint,
)
from dynapm.experiments.google2019_streaming_execute import (
    StreamingAcquisitionBlocked,
    build_request_index,
    cell_canonical_dir,
    join_usage_batch,
    maximum_bytes_billed_for,
    measure_path_gib,
    query_output_path,
    validate_cell_artifacts,
    write_cell_canonical_from_joined,
)
from dynapm.experiments.google2019_zero_cost_plan import render_plan_query, template_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
EVIDENCE_ROOT = MANAGED_ROOT / "failed_generations" / "v4b6_e_usage_temp_expired"
USAGE_PARTS_DIR = MANAGED_ROOT / "raw" / "e" / "usage_parts"
USAGE_PARQUET = MANAGED_ROOT / "raw" / "e" / "usage.parquet"
JOINED_PATH = MANAGED_ROOT / "staging" / "e" / "joined.parquet"
RECORD_JSON = REPO_ROOT / "configs" / "google2019_v4b7_recovery_record.json"

# Conservative Google-side accounting for this month (user-specified).
EVENTS_BYTES = 73_125_247_840  # 68.103194 GiB
FAILED_E_USAGE_BYTES = 363_453_673_016  # 338.492611 GiB (processed, download incomplete)
CONSERVATIVE_MONTHLY_BEFORE_RETRY = EVENTS_BYTES + FAILED_E_USAGE_BYTES  # ~406.595805 GiB
EXPECTED_E_USAGE = FAILED_E_USAGE_BYTES
PROJECTED_AFTER_RETRY = CONSERVATIVE_MONTHLY_BEFORE_RETRY + EXPECTED_E_USAGE  # ~745.088416 GiB
CAP_BYTES = 900 * GIB
CELL = "e"
USAGE_TEMPLATE = "20_usage_minimal.sql"
MAX_STREAMS_DEFAULT = 32
MAX_STREAMS_BOOST = 64


class RecoveryBlocked(RuntimeError):
    """Safe stop for V4B.7 recovery."""


def preserve_failed_generation_evidence() -> dict[str, Any]:
    """Copy stale checkpoint + error log; do not delete originals until repair."""
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    ckpt = MANAGED_ROOT / "checkpoints" / "e.json"
    evidence = {
        "preserved_at": utc_now(),
        "reason": "v4b6_e_usage_temp_table_expired_mid_download",
        "failed_job_id": "7a69fcea-7074-4e0d-84e4-b915a15b95c3",
        "failed_usage_processed_bytes": FAILED_E_USAGE_BYTES,
        "events_bytes": EVENTS_BYTES,
        "conservative_monthly_before_retry_bytes": CONSERVATIVE_MONTHLY_BEFORE_RETRY,
        "rows_downloaded_approx": 468_000_000,
        "rows_total": 513_023_210,
        "error": "Not found: anonymous temporary result table (TTL ~24h)",
    }
    (EVIDENCE_ROOT / "evidence.json").write_text(
        canonical_json(evidence) + "\n", encoding="utf-8"
    )
    if ckpt.is_file():
        shutil.copy2(ckpt, EVIDENCE_ROOT / "e_checkpoint_before_repair.json")
    err = REPO_ROOT / "logs" / "v4b6_error.txt"
    if err.is_file():
        shutil.copy2(err, EVIDENCE_ROOT / "v4b6_error.txt")
    log = REPO_ROOT / "logs" / "v4b6_cell_e.log"
    if log.is_file():
        # Keep a truncated tail for size; full log stays in logs/.
        text = log.read_text(encoding="utf-8", errors="replace")
        (EVIDENCE_ROOT / "v4b6_cell_e_log_tail.txt").write_text(text[-100_000:])
    return evidence


def reconcile_ledger_failed_scan() -> dict[str, Any]:
    """Record Google-side failed e-usage scan if not already present."""
    ledger = load_byte_ledger()
    names = {e.get("query_name") for e in ledger.get("executed_entries") or []}
    if "e:20_usage_minimal.sql#failed_temp_expired_v4b6" in names:
        return ledger
    return record_executed_bytes(
        query_name="e:20_usage_minimal.sql#failed_temp_expired_v4b6",
        executed_bytes=FAILED_E_USAGE_BYTES,
        job_id="7a69fcea-7074-4e0d-84e4-b915a15b95c3",
    )


def repair_checkpoint_for_requery() -> dict[str, Any]:
    """Clear stale usage_running job binding after evidence preserved; allow one requery."""
    cp = read_checkpoint(CELL) or {"queries": {}, "query_ledger": []}
    failed = dict(cp.get("queries", {}).get(f"{CELL}:{USAGE_TEMPLATE}") or {})
    cp["failed_usage_generation"] = {
        **failed,
        "failure": "temp_table_expired_mid_download",
        "processed_bytes_google_side": FAILED_E_USAGE_BYTES,
        "preserved_evidence": str(EVIDENCE_ROOT.relative_to(REPO_ROOT)),
    }
    queries = dict(cp.get("queries") or {})
    queries.pop(f"{CELL}:{USAGE_TEMPLATE}", None)
    cp["queries"] = queries
    cp["stage"] = "events_done"
    cp["v4b7_allow_one_usage_requery"] = True
    cp["v4b7_usage_requery_consumed"] = False
    return write_checkpoint(CELL, cp)


def preflight_retry(*, billing_project: str) -> dict[str, Any]:
    require_zero_cost_project(billing_project)
    billing = require_zero_cost_project(billing_project)
    if billing.billing_enabled:
        raise RecoveryBlocked("BILLING_ENABLED")
    expected = expected_bytes_map()[(CELL, USAGE_TEMPLATE)]
    if expected != EXPECTED_E_USAGE:
        raise RecoveryBlocked(f"expected_bytes_drift:{expected}_vs_{EXPECTED_E_USAGE}")
    sql = render_plan_query(USAGE_TEMPLATE, CELL)
    query_sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    billed_cap = maximum_bytes_billed_for(expected)
    dry = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False, maximum_bytes_billed=billed_cap
        ),
        location="US",
    )
    dry_bytes = int(dry.total_bytes_processed or 0)
    rel = abs(dry_bytes - expected) / expected
    if rel > DRY_RUN_TOLERANCE:
        raise RecoveryBlocked(f"dry_run_mismatch:{dry_bytes}_vs_{expected}")

    # Projected Google-side after retry (conservative).
    if PROJECTED_AFTER_RETRY > CAP_BYTES:
        raise RecoveryBlocked("projected_after_retry_exceeds_900gib")
    # Local ledger after reconcile should already include failed scan.
    ledger = cumulative_executed_bytes()
    if ledger + dry_bytes > CAP_BYTES:
        raise RecoveryBlocked("local_ledger_plus_retry_exceeds_900gib")

    disk = assess_disk_guard(12.0, min_free_reserve_gib=DEFAULT_MIN_FREE_RESERVE_GIB)
    if not disk.safe:
        raise RecoveryBlocked("disk_guard_failed_preflight")

    events = query_output_path(CELL, "21_events_minimal.sql")
    if not events.is_file():
        raise RecoveryBlocked("events_parquet_missing")

    return {
        "billing_enabled": False,
        "dry_run_bytes": dry_bytes,
        "expected_bytes": expected,
        "query_sha256": query_sha,
        "template_sha256": template_hashes()[USAGE_TEMPLATE],
        "projected_google_side_after_retry_bytes": PROJECTED_AFTER_RETRY,
        "projected_google_side_after_retry_gib": round(PROJECTED_AFTER_RETRY / GIB, 6),
        "local_ledger_bytes": ledger,
        "cap_bytes": CAP_BYTES,
        "disk": {
            "free_gib": disk.free_gib,
            "usable_gib": disk.usable_gib,
            "safe": disk.safe,
        },
        "cell_g_authorized": False,
        "verified_at": utc_now(),
    }


def submit_one_usage_query(*, billing_project: str, checkpoint: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Submit exactly one new e-usage query. Refuses if requery already consumed."""
    if not checkpoint.get("v4b7_allow_one_usage_requery"):
        raise RecoveryBlocked("requery_not_authorized")
    if checkpoint.get("v4b7_usage_requery_consumed"):
        raise RecoveryBlocked("requery_already_consumed_no_auto_resubmit")
    # Never bind to the expired failed job.
    prior_id = (checkpoint.get("failed_usage_generation") or {}).get("job_id")
    require_zero_cost_project(billing_project)
    from google.cloud import bigquery  # type: ignore[import-not-found]

    billing = require_zero_cost_project(billing_project)
    client = bigquery.Client(project=billing.project_id)
    expected = EXPECTED_E_USAGE
    sql = render_plan_query(USAGE_TEMPLATE, CELL)
    billed_cap = maximum_bytes_billed_for(expected)
    dry = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False, maximum_bytes_billed=billed_cap
        ),
        location="US",
    )
    dry_bytes = int(dry.total_bytes_processed or 0)
    require_zero_cost_project(billing_project)
    started = utc_now()
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            dry_run=False, use_query_cache=False, maximum_bytes_billed=billed_cap
        ),
        location="US",
    )
    # Mark consumed immediately so a crash cannot auto-submit another.
    checkpoint = write_checkpoint(
        CELL,
        {
            **checkpoint,
            "v4b7_usage_requery_consumed": True,
            "stage": "usage_query_submitted",
            "queries": {
                **checkpoint.get("queries", {}),
                f"{CELL}:{USAGE_TEMPLATE}": {
                    "job_id": job.job_id,
                    "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                    "expected_bytes": expected,
                    "maximum_bytes_billed": billed_cap,
                    "v4b7_retry": True,
                    "supersedes_job_id": prior_id,
                },
            },
        },
    )
    return job, {
        "job_id": job.job_id,
        "dry_run_bytes": dry_bytes,
        "started_at": started,
        "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "expected_bytes": expected,
        "maximum_bytes_billed": billed_cap,
    }


def join_usage_parquet_to_canonical_staging(
    usage_path: Path,
    *,
    events_path: Path,
    joined_path: Path,
) -> dict[str, Any]:
    index = build_request_index(events_path)
    if joined_path.exists():
        raise FileExistsError(joined_path)
    writer = ChunkedParquetWriter(
        joined_path, chunk_rows=DEFAULT_CHUNK_ROWS, min_free_reserve_gib=DEFAULT_MIN_FREE_RESERVE_GIB
    )
    missing = 0
    raw = 0
    try:
        pf = pq.ParquetFile(usage_path)
        for batch in pf.iter_batches(batch_size=DEFAULT_CHUNK_ROWS):
            frame = batch.to_pandas()
            rows = frame.to_dict(orient="records")
            raw += len(rows)
            joined, counts = join_usage_batch(rows, cell=CELL, index=index)
            missing += counts["missing_request"]
            if joined:
                writer.write_rows(joined)
        meta = writer.finalize()
    except Exception:
        writer.cleanup_temp()
        raise
    return {**meta, "raw_usage_rows": raw, "missing_request": missing}


def _storage_read_and_canonicalize(
    *,
    billing_project: str,
    job: Any,
    meta: dict[str, Any],
    executed: int,
    max_streams: int,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    try:
        total_rows = int(job.result(timeout=120).total_rows or 0)
    except Exception:
        total_rows = 513_023_210

    temp = temp_table_from_job(job)
    zero = verify_storage_read_zero_spend(billing_project, temp)
    ttl = ttl_remaining_seconds(job)
    build_heartbeat(
        phase="storage_read_start",
        job_id=job.job_id,
        job_status="DONE",
        expected_rows=total_rows,
        rows_downloaded=0,
        ttl_remaining_seconds=ttl,
        extra={"zero_spend": zero, "max_streams": max_streams},
    )

    streams = max_streams
    last_beat = time.time()
    last_rows = 0
    last_t = time.time()
    progress_threat: dict[str, bool] = {"hit": False}

    def hook(snap: dict[str, Any]) -> None:
        nonlocal last_beat, last_rows, last_t, streams
        now = time.time()
        rows = int(snap.get("rows_downloaded") or 0)
        dt = max(now - last_t, 1e-6)
        inst_rate = (rows - last_rows) / dt if rows >= last_rows else snap.get("rows_per_sec")
        last_rows = rows
        last_t = now
        ttl_left = snap.get("ttl_remaining_seconds")
        eta = snap.get("eta_seconds")
        threat = None
        rate = float(snap.get("rows_per_sec") or inst_rate or 0.0)
        if (
            eta is not None
            and ttl_left is not None
            and rows >= 5_000_000
            and rate > 0
            and float(eta) > float(ttl_left) - 1800
        ):
            threat = "eta_threatens_temp_table_expiry"
            progress_threat["hit"] = True
        write_status(
            {
                "phase": "storage_read",
                "rows_downloaded": rows,
                "expected_rows": snap.get("expected_rows"),
                "pct_complete": snap.get("pct"),
                "rows_per_sec": rate,
                "eta_seconds": eta,
                "ttl_remaining_seconds": ttl_left,
                "job_id": job.job_id,
                "job_status": "DONE",
                "disk": disk_snapshot(),
                "ledger": ledger_snapshot(),
                "threat": threat,
                "n_streams": snap.get("n_streams"),
                "cell_g_queried": False,
            }
        )
        if now - last_beat >= HEARTBEAT_SECONDS or threat:
            last_beat = now
            build_heartbeat(
                phase="storage_read",
                rows_downloaded=rows,
                expected_rows=snap.get("expected_rows"),
                rows_per_sec=rate,
                eta_seconds=eta,
                ttl_remaining_seconds=ttl_left,
                job_id=job.job_id,
                job_status="DONE",
                extra={
                    "threat": threat,
                    "n_streams": snap.get("n_streams"),
                    "streams_requested": streams,
                },
            )

    if USAGE_PARTS_DIR.exists():
        shutil.rmtree(USAGE_PARTS_DIR)
    try:
        parts_manifest = download_job_result_storage_read(
            job,
            USAGE_PARTS_DIR,
            billing_project=billing_project,
            max_streams=streams,
            expected_rows=total_rows,
            status_hook=hook,
        )
    except StorageReadBlocked:
        build_heartbeat(
            phase="storage_read_blocked",
            job_id=job.job_id,
            error="storage_read_blocked",
        )
        raise
    if progress_threat["hit"]:
        raise StorageReadBlocked("eta_threatens_expiry_stop_before_blind_requery")

    if USAGE_PARQUET.exists():
        USAGE_PARQUET.unlink()
    merge_meta = merge_part_parquets(USAGE_PARTS_DIR, USAGE_PARQUET)
    build_heartbeat(
        phase="usage_downloaded",
        rows_downloaded=merge_meta["rows"],
        expected_rows=total_rows,
        job_id=job.job_id,
        job_status="DONE",
        ttl_remaining_seconds=ttl_remaining_seconds(job),
        extra={"usage_sha256": merge_meta["sha256"], "parts": parts_manifest["rows"]},
    )

    # Local join + canonicalize.
    events_path = query_output_path(CELL, "21_events_minimal.sql")
    if JOINED_PATH.exists():
        JOINED_PATH.unlink()
    join_meta = join_usage_parquet_to_canonical_staging(
        USAGE_PARQUET, events_path=events_path, joined_path=JOINED_PATH
    )
    build_heartbeat(phase="joined", extra={"joined_rows": join_meta.get("rows")})

    if cell_canonical_dir(CELL).exists():
        raise RecoveryBlocked("canonical_e_already_exists")
    canon = write_cell_canonical_from_joined(JOINED_PATH, CELL)
    if JOINED_PATH.exists():
        JOINED_PATH.unlink()
    validation = validate_cell_artifacts(CELL)
    if not validation["passed"]:
        raise RecoveryBlocked(f"validation_failed:{validation['findings']}")

    write_checkpoint(
        CELL,
        {
            **(read_checkpoint(CELL) or {}),
            "stage": "validated",
            "validation": validation,
            "canonical_manifest": canon,
            "v4b7_usage_download": {
                "job_id": job.job_id,
                "execution_bytes": executed,
                "rows": merge_meta["rows"],
                "sha256": merge_meta["sha256"],
                "parts_rows": parts_manifest["rows"],
                "duration_seconds": parts_manifest.get("duration_seconds"),
            },
        },
    )

    google_side = CONSERVATIVE_MONTHLY_BEFORE_RETRY + executed
    record = {
        "schema_version": "google2019-v4b7-recovery-record-v1",
        "gate": "V4B.7",
        "disposition": "CELL_E_ACQUIRED",
        "blocker": None,
        "billing_enabled": False,
        "cell_g_queried": False,
        "method_outcomes_computed": False,
        "failed_generation": evidence,
        "retry_query": {
            "job_id": job.job_id,
            "execution_bytes": executed,
            "execution_gib": round(executed / GIB, 6),
            "dry_run_bytes": meta["dry_run_bytes"],
            "query_sha256": meta["query_sha256"],
            "rows": merge_meta["rows"],
            "download_duration_seconds": parts_manifest.get("duration_seconds"),
            "rows_per_sec": (
                round(merge_meta["rows"] / parts_manifest["duration_seconds"], 2)
                if parts_manifest.get("duration_seconds")
                else None
            ),
            "storage_read_streams": parts_manifest.get("n_streams"),
        },
        "google_side_processed_bytes": {
            "events": EVENTS_BYTES,
            "failed_e_usage_v4b6": FAILED_E_USAGE_BYTES,
            "retry_e_usage_v4b7": executed,
            "cumulative": google_side,
            "cumulative_gib": round(google_side / GIB, 6),
            "cap_gib": 900,
            "remaining_cap_gib": round((CAP_BYTES - google_side) / GIB, 6),
        },
        "local_ledger_bytes": cumulative_executed_bytes(),
        "local_ledger_gib": round(cumulative_executed_bytes() / GIB, 6),
        "canonical": {
            "rows": canon.get("row_count"),
            "entities": canon.get("entity_count"),
            "eligible_entities": canon.get("eligible_entity_count"),
            "artifacts": canon.get("artifacts"),
        },
        "validation": validation,
        "disk_gib": {
            "events": round(measure_path_gib(events_path), 6),
            "usage": round(measure_path_gib(USAGE_PARQUET), 6),
            "canonical": round(measure_path_gib(cell_canonical_dir(CELL)), 6),
        },
        "next_gate_note": "Cell g deferred this month; remaining cap insufficient for full g pair after retry.",
        "recorded_at": utc_now(),
    }
    RECORD_JSON.write_text(canonical_json(record) + "\n", encoding="utf-8")
    build_heartbeat(
        phase="complete",
        rows_downloaded=merge_meta["rows"],
        expected_rows=total_rows,
        job_id=job.job_id,
        job_status="DONE",
        extra={"disposition": "CELL_E_ACQUIRED", "record_sha256": file_sha256(RECORD_JSON)},
    )
    return record


def resume_existing_usage_job(
    *,
    billing_project: str,
    max_streams: int = MAX_STREAMS_BOOST,
) -> dict[str, Any]:
    """Resume Storage Read from the already-submitted V4B.7 job. Never submits a query."""
    require_zero_cost_project(billing_project)
    cp = read_checkpoint(CELL) or {}
    q = (cp.get("queries") or {}).get(f"{CELL}:{USAGE_TEMPLATE}")
    if not q or not q.get("job_id"):
        raise RecoveryBlocked("no_existing_usage_job_to_resume")
    if not cp.get("v4b7_usage_requery_consumed"):
        raise RecoveryBlocked("expected_requery_already_consumed_for_resume")
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=require_zero_cost_project(billing_project).project_id)
    job = client.get_job(q["job_id"], location="US")
    if job.state != "DONE" or job.error_result:
        raise RecoveryBlocked(f"existing_job_not_resumable:{job.state}:{job.error_result}")
    ttl = ttl_remaining_seconds(job)
    if ttl < 3600:
        raise RecoveryBlocked(f"temp_ttl_too_low_for_resume_{ttl:.0f}")
    evidence = {
        "reason": "resume_storage_read_after_false_eta_stop",
        "failed_v4b6_job_id": "7a69fcea-7074-4e0d-84e4-b915a15b95c3",
        "v4b7_job_id": job.job_id,
    }
    meta = {
        "job_id": job.job_id,
        "dry_run_bytes": EXPECTED_E_USAGE,
        "query_sha256": q.get("query_sha256"),
        "started_at": utc_now(),
        "resumed": True,
    }
    executed = int(job.total_bytes_processed or 0)
    # Do not re-record ledger bytes for this job.
    return _storage_read_and_canonicalize(
        billing_project=billing_project,
        job=job,
        meta=meta,
        executed=executed,
        max_streams=max_streams,
        evidence=evidence,
    )


def run_v4b7_recover_e(*, billing_project: str, max_streams: int = MAX_STREAMS_DEFAULT) -> dict[str, Any]:
    """Full recovery: evidence → ledger → repair → preflight → one query → storage read → canonicalize."""
    require_zero_cost_project(billing_project)
    cp = read_checkpoint(CELL) or {}
    # If the single allowed requery was already submitted, only resume download.
    q = (cp.get("queries") or {}).get(f"{CELL}:{USAGE_TEMPLATE}")
    if cp.get("v4b7_usage_requery_consumed") and q and q.get("job_id"):
        return resume_existing_usage_job(
            billing_project=billing_project, max_streams=max(max_streams, MAX_STREAMS_BOOST)
        )

    evidence = preserve_failed_generation_evidence()
    ledger_after_fail = reconcile_ledger_failed_scan()
    build_heartbeat(
        phase="preflight",
        extra={
            "evidence": evidence["reason"],
            "ledger_gib": ledger_after_fail["cumulative_executed_bytes"] / GIB,
        },
    )
    cp = repair_checkpoint_for_requery()
    pf = preflight_retry(billing_project=billing_project)
    write_status({"phase": "preflight_ok", "preflight": pf, "updated_at": utc_now()})

    job, meta = submit_one_usage_query(billing_project=billing_project, checkpoint=cp)
    build_heartbeat(phase="usage_query_running", job_id=meta["job_id"], job_status="RUNNING")
    last_beat = time.time()
    while True:
        job.reload()
        if job.state == "DONE":
            break
        if time.time() - last_beat >= HEARTBEAT_SECONDS:
            last_beat = time.time()
            build_heartbeat(
                phase="usage_query_running",
                job_id=job.job_id,
                job_status=job.state,
            )
        time.sleep(15)
    if job.error_result:
        raise RecoveryBlocked(f"usage_query_failed:{job.error_result}")

    executed = int(job.total_bytes_processed or 0)
    record_executed_bytes(
        query_name=f"{CELL}:{USAGE_TEMPLATE}#v4b7_retry",
        executed_bytes=executed,
        job_id=job.job_id,
    )
    return _storage_read_and_canonicalize(
        billing_project=billing_project,
        job=job,
        meta=meta,
        executed=executed,
        max_streams=max_streams,
        evidence=evidence,
    )
