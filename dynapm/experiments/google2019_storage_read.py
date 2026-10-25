"""V4B.7 BigQuery Storage Read download for temporary query result tables.

Zero-spend constraints (must hold before any read session):
- billingEnabled=false
- no permanent destination tables / GCS
- Storage Read only against the query job's anonymous temporary result table
- Google pricing: bytes read from temporary cached query-result tables are free
  and do not count against Storage Read free-tier (see BigQuery pricing docs)

Never loads the full result into RAM; writes chunked zstd Parquet per stream.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

import pyarrow as pa
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, utc_now
from dynapm.experiments.google2019_acquisition import GIB, require_zero_cost_project
from dynapm.experiments.google2019_streaming import (
    DEFAULT_MIN_FREE_RESERVE_GIB,
    assess_disk_guard,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
DEFAULT_MAX_STREAMS = 32
TEMP_RESULT_TTL_SECONDS = 24 * 3600
# Stop if ETA to finish exceeds remaining TTL minus this safety margin.
TTL_SAFETY_SECONDS = 2 * 3600


class StorageReadBlocked(RuntimeError):
    """Refuse Storage Read when zero-spend or temp-table constraints fail."""


@dataclass
class TempTableRef:
    project: str
    dataset_id: str
    table_id: str

    @property
    def resource_name(self) -> str:
        return (
            f"projects/{self.project}/datasets/{self.dataset_id}/tables/{self.table_id}"
        )

    @property
    def is_anonymous_temp(self) -> bool:
        # Cached query results live in anonymous datasets (typically underscore-prefixed).
        return self.dataset_id.startswith("_")


def verify_storage_read_zero_spend(billing_project: str, temp: TempTableRef) -> dict[str, Any]:
    """Hard gates before create_read_session."""
    billing = require_zero_cost_project(billing_project)
    if billing.billing_enabled:
        raise StorageReadBlocked("BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED")
    if not temp.is_anonymous_temp:
        raise StorageReadBlocked(
            "storage_read_refuses_non_anonymous_table_would_risk_paid_read"
        )
    return {
        "billing_enabled": False,
        "zero_spend_guaranteed": True,
        "temporary_anonymous_table": True,
        "table": temp.resource_name,
        "pricing_note": (
            "Storage Read bytes from temporary cached query-result tables are free "
            "per Google BigQuery pricing; permanent-table reads are forbidden here."
        ),
        "verified_at": utc_now(),
    }


def temp_table_from_job(job: Any) -> TempTableRef:
    dest = getattr(job, "destination", None)
    if dest is None:
        raise StorageReadBlocked("query_job_has_no_destination_temp_table")
    return TempTableRef(
        project=str(dest.project),
        dataset_id=str(dest.dataset_id),
        table_id=str(dest.table_id),
    )


def temp_table_age_seconds(job: Any) -> float:
    """Age since job finished (temp TTL clock starts at result materialization)."""
    ended = getattr(job, "ended", None) or getattr(job, "created", None)
    if ended is None:
        return 0.0
    # google.cloud datetime may be aware
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (now - ended).total_seconds())


def ttl_remaining_seconds(job: Any) -> float:
    return max(0.0, TEMP_RESULT_TTL_SECONDS - temp_table_age_seconds(job))


def _page_to_table(page: Any) -> pa.Table:
    """Convert a Storage Read page to Arrow without holding the full stream."""
    try:
        batch = page.to_arrow()
        if isinstance(batch, pa.Table):
            return batch
        return pa.Table.from_batches([batch])
    except Exception:
        # Fallback: row dictionaries (slower, still bounded by page).
        rows = [dict(row) for row in page]
        if not rows:
            return pa.table({})
        return pa.Table.from_pylist(rows)


def _download_one_stream(
    *,
    stream_name: str,
    start_offset: int,
    part_path: Path,
    read_session: Any,
    billing_project: str,
    min_free_reserve_gib: float,
    progress: dict[str, Any],
    progress_lock: threading.Lock,
    checkpoint_cb: Callable[[str, int, int], None] | None,
) -> dict[str, Any]:
    from google.cloud import bigquery_storage_v1  # type: ignore[import-not-found]

    require_zero_cost_project(billing_project)
    client = bigquery_storage_v1.BigQueryReadClient()
    offset = int(start_offset)
    rows_this = 0
    writer: pq.ParquetWriter | None = None
    tmp = part_path.with_suffix(part_path.suffix + ".tmp")
    if part_path.exists() and start_offset == 0:
        # Fresh stream part; refuse clobber of finalized part.
        raise StorageReadBlocked(f"immutable_stream_part_exists:{part_path}")
    try:
        row_stream = client.read_rows(stream_name, offset=offset)
        for page in row_stream.rows(read_session).pages:
            status = assess_disk_guard(0.5, min_free_reserve_gib=min_free_reserve_gib)
            if not status.safe:
                raise StorageReadBlocked(
                    f"disk_guard_during_storage_read_usable_{status.usable_gib}"
                )
            table = _page_to_table(page)
            if table.num_rows == 0:
                continue
            if writer is None:
                writer = pq.ParquetWriter(tmp, table.schema, compression="zstd")
            writer.write_table(table)
            n = int(table.num_rows)
            prev = rows_this
            rows_this += n
            offset += n
            with progress_lock:
                progress["rows_downloaded"] = int(progress.get("rows_downloaded") or 0) + n
                progress["bytes_written"] = int(progress.get("bytes_written") or 0)
            # Throttle checkpoint/status callbacks (~every 250k rows/stream).
            if checkpoint_cb is not None and (
                prev == 0 or (rows_this // 250_000) > (prev // 250_000)
            ):
                checkpoint_cb(stream_name, offset, rows_this)
        if writer is not None:
            writer.close()
            writer = None
            tmp.replace(part_path)
        if checkpoint_cb is not None and rows_this:
            checkpoint_cb(stream_name, offset, rows_this)
        return {
            "stream": stream_name,
            "rows": rows_this,
            "final_offset": offset,
            "path": str(part_path) if part_path.exists() else "",
        }
    except Exception:
        if writer is not None:
            writer.close()
        if tmp.exists():
            tmp.unlink()
        raise


def download_job_result_storage_read(
    job: Any,
    output_dir: Path,
    *,
    billing_project: str,
    max_streams: int = DEFAULT_MAX_STREAMS,
    min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB,
    stream_offsets: dict[str, int] | None = None,
    status_hook: Callable[[dict[str, Any]], None] | None = None,
    expected_rows: int | None = None,
) -> dict[str, Any]:
    """Parallel Arrow Storage Read of a query job's anonymous temp table → Parquet parts."""
    from google.cloud import bigquery_storage_v1  # type: ignore[import-not-found]
    from google.cloud.bigquery_storage_v1 import types  # type: ignore[import-not-found]

    require_zero_cost_project(billing_project)
    temp = temp_table_from_job(job)
    safety = verify_storage_read_zero_spend(billing_project, temp)
    ttl_left = ttl_remaining_seconds(job)
    if ttl_left < 600:
        raise StorageReadBlocked(f"temp_table_ttl_too_low_seconds_{ttl_left:.0f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    offsets = dict(stream_offsets or {})
    started = time.time()
    progress: dict[str, Any] = {
        "rows_downloaded": sum(offsets.values()),
        "started_at": utc_now(),
        "expected_rows": expected_rows,
    }
    progress_lock = threading.Lock()
    checkpoint_lock = threading.Lock()

    require_zero_cost_project(billing_project)
    bqstorage = bigquery_storage_v1.BigQueryReadClient()
    requested = types.ReadSession()
    requested.table = temp.resource_name
    requested.data_format = types.DataFormat.ARROW
    try:
        session = bqstorage.create_read_session(
            parent=f"projects/{billing_project}",
            read_session=requested,
            max_stream_count=int(max_streams),
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "billing" in msg or "payment" in msg or "403" in msg:
            raise StorageReadBlocked(f"storage_read_billing_or_auth_refused:{exc}") from exc
        raise

    streams = list(session.streams)
    if not streams:
        raise StorageReadBlocked("storage_read_session_returned_zero_streams")

    # Estimated total rows from job result if available.
    total_rows = expected_rows
    if total_rows is None:
        try:
            total_rows = int(job.result(timeout=60).total_rows or 0) or None
        except Exception:
            total_rows = None
    progress["expected_rows"] = total_rows
    progress["n_streams"] = len(streams)
    progress["ttl_remaining_seconds"] = ttl_left
    progress["zero_spend"] = safety

    ckpt_path = output_dir / "storage_read_checkpoint.json"

    def _ckpt(stream_name: str, offset: int, rows_this: int) -> None:
        with checkpoint_lock:
            offsets[stream_name] = offset
            payload = {
                "updated_at": utc_now(),
                "job_id": job.job_id,
                "temp_table": temp.resource_name,
                "stream_offsets": dict(offsets),
                "rows_downloaded": progress.get("rows_downloaded"),
                "session_streams": [s.name for s in streams],
            }
            # Unique tmp name per stream to avoid cross-thread replace races.
            tmp = ckpt_path.with_suffix(f".{threading.get_ident()}.tmp")
            tmp.write_text(canonical_json(payload) + "\n", encoding="utf-8")
            tmp.replace(ckpt_path)
        if status_hook is not None:
            elapsed = max(time.time() - started, 1.0)
            rows_done = int(progress.get("rows_downloaded") or 0)
            rate = rows_done / elapsed
            remaining = None
            eta = None
            if total_rows:
                remaining = max(total_rows - rows_done, 0)
                eta = remaining / rate if rate > 0 else None
            try:
                status_hook(
                    {
                        "rows_downloaded": rows_done,
                        "expected_rows": total_rows,
                        "pct": (
                            round(100.0 * rows_done / total_rows, 4)
                            if total_rows
                            else None
                        ),
                        "rows_per_sec": round(rate, 2),
                        "eta_seconds": round(eta, 1) if eta is not None else None,
                        "ttl_remaining_seconds": round(ttl_remaining_seconds(job), 1),
                        "n_streams": len(streams),
                        "stream_checkpoint": stream_name,
                        "stream_offset": offset,
                    }
                )
            except Exception:
                # Progress hooks must never abort the download.
                pass

    # Preflight: if ETA already exceeds TTL safety before starting, refuse.
    # (Updated dynamically via status_hook in the runner.)

    part_metas: list[dict[str, Any]] = []
    # Prefer parallel when multiple streams; fall back path uses same worker fn.
    workers = min(len(streams), max(1, int(max_streams)))

    def _run_one(i: int, stream: Any) -> dict[str, Any]:
        part_path = output_dir / f"part_{i:03d}.parquet"
        start_off = int(offsets.get(stream.name, 0))
        return _download_one_stream(
            stream_name=stream.name,
            start_offset=0 if not part_path.exists() else start_off,
            part_path=part_path,
            read_session=session,
            billing_project=billing_project,
            min_free_reserve_gib=min_free_reserve_gib,
            progress=progress,
            progress_lock=progress_lock,
            checkpoint_cb=_ckpt,
        )

    if workers <= 1 or len(streams) == 1:
        for i, stream in enumerate(streams):
            print(f"[storage_read] stream {i+1}/{len(streams)}", flush=True)
            part_metas.append(_run_one(i, stream))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run_one, i, stream): stream.name
                for i, stream in enumerate(streams)
            }
            for fut in as_completed(futures):
                part_metas.append(fut.result())

    # Atomic manifest of parts.
    total = sum(int(p["rows"]) for p in part_metas)
    manifest = {
        "schema_version": "google2019-storage-read-parts-v1",
        "job_id": job.job_id,
        "temp_table": temp.resource_name,
        "zero_spend": safety,
        "rows": total,
        "expected_rows": total_rows,
        "n_streams": len(streams),
        "parts": [
            {
                "path": (
                    str(Path(p["path"]).relative_to(REPO_ROOT)).replace("\\", "/")
                    if p.get("path") and Path(p["path"]).is_file()
                    and Path(p["path"]).resolve().is_relative_to(REPO_ROOT.resolve())
                    else (Path(p["path"]).name if p.get("path") else None)
                ),
                "rows": p["rows"],
                "sha256": (
                    file_sha256(Path(p["path"]))
                    if p.get("path")
                    and Path(p["path"]).is_file()
                    and Path(p["path"]).stat().st_size > 0
                    else None
                ),
            }
            for p in part_metas
        ],
        "duration_seconds": round(time.time() - started, 3),
        "finished_at": utc_now(),
        "method_outcomes_computed": False,
    }
    man_path = output_dir / "parts_manifest.json"
    man_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest


def merge_part_parquets(parts_dir: Path, output_path: Path) -> dict[str, Any]:
    """Concatenate non-empty part parquets into one file (streaming, bounded memory)."""
    if output_path.exists():
        raise FileExistsError(f"immutable output exists: {output_path}")
    parts = sorted(parts_dir.glob("part_*.parquet"))
    parts = [p for p in parts if p.is_file() and p.stat().st_size > 0]
    if not parts:
        raise StorageReadBlocked("no_nonempty_parquet_parts")
    writer: pq.ParquetWriter | None = None
    rows = 0
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        for part in parts:
            pf = pq.ParquetFile(part)
            for batch in pf.iter_batches(batch_size=100_000):
                table = pa.Table.from_batches([batch])
                if writer is None:
                    writer = pq.ParquetWriter(tmp, table.schema, compression="zstd")
                writer.write_table(table)
                rows += table.num_rows
        if writer is None:
            raise StorageReadBlocked("merge_produced_no_rows")
        writer.close()
        writer = None
        tmp.replace(output_path)
    finally:
        if writer is not None:
            writer.close()
        if tmp.exists() and not output_path.exists():
            tmp.unlink()
    return {"path": str(output_path), "rows": rows, "sha256": file_sha256(output_path)}
