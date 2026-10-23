"""V4B.5 disk-efficient streaming acquisition helpers.

Corrects local storage estimation (never equates BigQuery bytes-processed to
on-disk size), defines per-cell streaming order, disk reserves, chunk writers,
and resume checkpoints. Does not execute BigQuery scans by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.experiments.google2019_acquisition import GIB
from dynapm.experiments.google2019_zero_cost_plan import CHOSEN_CELLS
from dynapm.experiments.replication_corpus import frozen_hashes as v4a_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
CHECKPOINT_ROOT = MANAGED_ROOT / "checkpoints"
STREAM_PLAN_JSON = REPO_ROOT / "configs" / "google2019_streaming_plan_v1.json"
STREAM_PLAN_YAML = REPO_ROOT / "configs" / "google2019_streaming_plan_v1.yaml"
STORAGE_ESTIMATE_JSON = REPO_ROOT / "configs" / "google2019_v4b5_storage_estimate.json"

SCHEMA_VERSION = "google2019-streaming-plan-v1"
DISPOSITION = "READY_FOR_STREAMING_ACQUISITION"
V4B3_PLAN_FINGERPRINT = (
    "f9f4bb846adfe9a303eb3d63f2efba84f7aa233ae4b990eb0b292cb30d76cfba"
)
DEFAULT_MIN_FREE_RESERVE_GIB = 20.0
DEFAULT_CHUNK_ROWS = 100_000

# Canonical audit fields required to recompute utilization offline.
CANONICAL_AUDIT_COLUMNS = (
    "cell",
    "collection_id",
    "instance_index",
    "timestamp_us",
    "cpu_utilization",
    "memory_utilization",
    "average_cpu_ncu",
    "average_memory_normalized_ram",
    "request_cpu_ncu",
    "request_memory_normalized_ram",
    "request_event_time_us",
    "usage_source_table",
    "request_source_table",
    "source_row_sha256",
)


class StreamingPlanError(RuntimeError):
    """Invalid or unsafe streaming-plan state."""


@dataclass(frozen=True)
class DiskGuardStatus:
    free_bytes: int
    free_gib: float
    reserve_bytes: int
    reserve_gib: float
    usable_bytes: int
    usable_gib: float
    required_peak_bytes: int
    required_peak_gib: float
    safe: bool


def load_streaming_plan() -> dict[str, Any]:
    return read_json(STREAM_PLAN_JSON)


def load_storage_estimate() -> dict[str, Any]:
    return read_json(STORAGE_ESTIMATE_JSON)


def validate_streaming_plan(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = doc if doc is not None else load_streaming_plan()
    if doc["schema_version"] != SCHEMA_VERSION:
        raise StreamingPlanError("unsupported streaming plan schema")
    if doc["disposition"] != DISPOSITION:
        raise StreamingPlanError("unexpected streaming disposition")
    if doc["v4a_protocol_fingerprint"] != v4a_hashes()["protocol_fingerprint"]:
        raise StreamingPlanError("V4A protocol fingerprint mismatch")
    if doc["v4b3_plan_fingerprint"] != V4B3_PLAN_FINGERPRINT:
        raise StreamingPlanError("V4B.3 plan fingerprint mismatch")
    if doc["cells"] != list(CHOSEN_CELLS):
        raise StreamingPlanError("cells must remain e,g")
    if doc["executed_bytes_this_task"] != 0:
        raise StreamingPlanError("V4B.5 must not consume query bytes")
    if doc["storage_estimation"]["rejects_bytes_processed_as_local_size"] is not True:
        raise StreamingPlanError("must reject bytes-processed-as-local-size")
    if doc["architecture"]["no_gcs_export"] is not True:
        raise StreamingPlanError("GCS export forbidden")
    if doc["architecture"]["no_bq_destination_tables"] is not True:
        raise StreamingPlanError("BQ destination tables forbidden")
    if doc["method_outcomes_computed"] is not False:
        raise StreamingPlanError("method outcomes forbidden")
    if set(doc["retained_audit_fields_in_canonical"]) != set(CANONICAL_AUDIT_COLUMNS):
        raise StreamingPlanError("canonical audit field set drift")
    est = load_storage_estimate()
    if est["summary"]["old_required_gib_eg_with_1_2x"] <= 100:
        raise StreamingPlanError("storage estimate missing corrected contrast")
    return {
        "plan_fingerprint": fingerprint(doc),
        "disposition": doc["disposition"],
        "blocker": doc.get("blocker"),
        "plan_json_sha256": file_sha256(STREAM_PLAN_JSON),
        "plan_yaml_sha256": file_sha256(STREAM_PLAN_YAML),
        "storage_estimate_sha256": file_sha256(STORAGE_ESTIMATE_JSON),
        "peak_during_g_with_e_canonical_point_gib": est["summary"][
            "peak_during_g_with_e_canonical_point_gib"
        ],
        "peak_during_g_with_e_canonical_conservative_gib": est["summary"][
            "peak_during_g_with_e_canonical_conservative_gib"
        ],
        "usable_disk_gib": est["summary"]["usable_disk_gib"],
    }


def assess_disk_guard(
    required_peak_gib: float,
    *,
    path: Path | None = None,
    min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB,
) -> DiskGuardStatus:
    root = path or REPO_ROOT
    free = int(shutil.disk_usage(root).free)
    reserve = int(min_free_reserve_gib * GIB)
    usable = max(free - reserve, 0)
    required = int(math_ceil_bytes(required_peak_gib))
    return DiskGuardStatus(
        free_bytes=free,
        free_gib=round(free / GIB, 6),
        reserve_bytes=reserve,
        reserve_gib=float(min_free_reserve_gib),
        usable_bytes=usable,
        usable_gib=round(usable / GIB, 6),
        required_peak_bytes=required,
        required_peak_gib=round(required / GIB, 6),
        safe=usable >= required,
    )


def math_ceil_bytes(gib: float) -> int:
    return int(math.ceil(float(gib) * GIB))


def checkpoint_path(cell: str) -> Path:
    return CHECKPOINT_ROOT / f"{cell}.json"


def read_checkpoint(cell: str) -> dict[str, Any] | None:
    path = checkpoint_path(cell)
    if not path.is_file():
        return None
    return read_json(path)


def write_checkpoint(cell: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = checkpoint_path(cell)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        **payload,
        "cell": cell,
        "updated_at": utc_now(),
        "schema_version": "google2019-streaming-checkpoint-v1",
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(canonical_json(body) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body


class ChunkedParquetWriter:
    """Flush Arrow batches to a Parquet file in row chunks; finalize atomically."""

    def __init__(
        self,
        final_path: Path,
        *,
        compression: str = "zstd",
        chunk_rows: int = DEFAULT_CHUNK_ROWS,
        min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB,
    ):
        self.final_path = Path(final_path)
        self.temp_path = self.final_path.with_suffix(self.final_path.suffix + ".tmp")
        self.compression = compression
        self.chunk_rows = int(chunk_rows)
        self.min_free_reserve_gib = float(min_free_reserve_gib)
        self._writer: pq.ParquetWriter | None = None
        self._buffer: list[dict[str, Any]] = []
        self.rows_written = 0
        if self.final_path.exists():
            raise FileExistsError(f"immutable output exists: {self.final_path}")
        self.final_path.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_disk(self, upcoming_rows: int) -> None:
        # Conservative: assume <= 512 bytes/row scratch before compression.
        need_gib = max(0.05, upcoming_rows * 512 / GIB)
        status = assess_disk_guard(
            need_gib, min_free_reserve_gib=self.min_free_reserve_gib
        )
        if not status.safe:
            raise StreamingPlanError(
                f"disk_guard_refuse_free_usable_{status.usable_gib}_need_{need_gib}"
            )

    def write_rows(self, rows: Iterable[dict[str, Any]]) -> None:
        for row in rows:
            self._buffer.append(row)
            if len(self._buffer) >= self.chunk_rows:
                self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._ensure_disk(len(self._buffer))
        table = pa.Table.from_pylist(self._buffer)
        if self._writer is None:
            self._writer = pq.ParquetWriter(
                self.temp_path, table.schema, compression=self.compression
            )
        self._writer.write_table(table)
        self.rows_written += len(self._buffer)
        self._buffer = []

    def finalize(self) -> dict[str, Any]:
        self.flush()
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if not self.temp_path.exists():
            # Empty stream: write empty table with no rows only if schema unknown — refuse.
            raise StreamingPlanError("no_rows_written")
        self.temp_path.replace(self.final_path)
        try:
            rel = str(self.final_path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            rel = self.final_path.name
        return {
            "path": rel,
            "sha256": file_sha256(self.final_path),
            "rows": self.rows_written,
        }

    def cleanup_temp(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self.temp_path.exists():
            self.temp_path.unlink()


def peak_requirement_for_stage(stage: str, estimate: dict[str, Any] | None = None) -> float:
    """Return planning peak GiB for a named streaming stage (point estimate)."""
    estimate = estimate if estimate is not None else load_storage_estimate()
    summary = estimate["summary"]
    if stage == "cell_e":
        return float(summary["peak_e_point_gib"])
    if stage == "cell_g_with_e_canonical":
        return float(summary["peak_during_g_with_e_canonical_point_gib"])
    if stage == "both_canonical_retained":
        return float(summary["both_canonical_retained_point_gib"])
    raise StreamingPlanError(f"unknown stage: {stage}")


def streaming_preflight_disk(stage: str = "cell_e") -> dict[str, Any]:
    plan = load_streaming_plan()
    reserve = float(plan["disk_guards"]["min_free_reserve_gib"])
    required = peak_requirement_for_stage(stage)
    status = assess_disk_guard(required, min_free_reserve_gib=reserve)
    return {
        "stage": stage,
        "required_peak_gib": required,
        "disk": asdict(status),
        "authorized": status.safe,
        "disposition": plan["disposition"],
        "blocker": plan.get("blocker"),
    }
