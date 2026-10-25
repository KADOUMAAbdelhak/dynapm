"""V4B.7 acquisition heartbeat monitor (30-minute cadence)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from dynapm.core.provenance import canonical_json, utc_now
from dynapm.experiments.google2019_acquisition import GIB, cumulative_executed_bytes, load_byte_ledger
from dynapm.experiments.google2019_streaming import assess_disk_guard, DEFAULT_MIN_FREE_RESERVE_GIB

REPO_ROOT = Path(__file__).resolve().parents[2]
MONITOR_ROOT = REPO_ROOT / "data" / "google2019" / "monitor"
STATUS_JSON = MONITOR_ROOT / "status.json"
MONITOR_LOG = MONITOR_ROOT / "monitor.log"
HEARTBEAT_SECONDS = 30 * 60
_STATUS_LOCK = threading.Lock()


def write_status(payload: dict[str, Any], *, append_log: bool = False) -> dict[str, Any]:
    """Atomically update status.json. Never raises into callers (download-critical)."""
    MONITOR_ROOT.mkdir(parents=True, exist_ok=True)
    body = {**payload, "updated_at": utc_now()}
    try:
        with _STATUS_LOCK:
            tmp = STATUS_JSON.with_name(f"status.{threading.get_ident()}.{time.time_ns()}.tmp")
            tmp.write_text(canonical_json(body) + "\n", encoding="utf-8")
            os_replace = __import__("os").replace
            os_replace(str(tmp), str(STATUS_JSON))
            if append_log:
                with MONITOR_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(canonical_json(body) + "\n")
    except Exception as exc:  # noqa: BLE001 — monitoring must not abort acquisition
        try:
            with MONITOR_LOG.open("a", encoding="utf-8") as fh:
                fh.write(canonical_json({"monitor_write_error": str(exc), "at": utc_now()}) + "\n")
        except Exception:
            pass
    return body


def read_status() -> dict[str, Any] | None:
    if not STATUS_JSON.is_file():
        return None
    return json.loads(STATUS_JSON.read_text(encoding="utf-8"))


def disk_snapshot(min_free_reserve_gib: float = DEFAULT_MIN_FREE_RESERVE_GIB) -> dict[str, Any]:
    # required_peak 0 → report usable headroom only
    st = assess_disk_guard(0.0, min_free_reserve_gib=min_free_reserve_gib)
    return {
        "free_gib": st.free_gib,
        "usable_gib": st.usable_gib,
        "reserve_gib": st.reserve_gib,
        "safe_for_reserve": st.free_gib >= st.reserve_gib,
    }


def ledger_snapshot() -> dict[str, Any]:
    ledger = load_byte_ledger()
    cum = int(ledger.get("cumulative_executed_bytes") or 0)
    return {
        "cumulative_executed_bytes": cum,
        "cumulative_executed_gib": round(cum / GIB, 6),
        "entries": [
            {
                "query_name": e.get("query_name"),
                "executed_bytes": e.get("executed_bytes"),
                "job_id": e.get("job_id"),
            }
            for e in ledger.get("executed_entries") or []
        ],
    }


def build_heartbeat(
    *,
    phase: str,
    rows_downloaded: int | None = None,
    expected_rows: int | None = None,
    rows_per_sec: float | None = None,
    eta_seconds: float | None = None,
    ttl_remaining_seconds: float | None = None,
    job_id: str | None = None,
    job_status: str | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pct = None
    if rows_downloaded is not None and expected_rows:
        pct = round(100.0 * rows_downloaded / expected_rows, 4)
    threat = None
    if (
        eta_seconds is not None
        and ttl_remaining_seconds is not None
        and rows_downloaded is not None
        and rows_downloaded >= 5_000_000
        and eta_seconds > ttl_remaining_seconds - 1800
    ):
        threat = "eta_threatens_temp_table_expiry"
    disk = disk_snapshot()
    if not disk["safe_for_reserve"]:
        threat = threat or "disk_reserve_violation"
    payload = {
        "schema_version": "google2019-acquisition-monitor-v1",
        "gate": "V4B.7",
        "phase": phase,
        "heartbeat": True,
        "rows_downloaded": rows_downloaded,
        "expected_rows": expected_rows,
        "pct_complete": pct,
        "rows_per_sec": rows_per_sec,
        "eta_seconds": eta_seconds,
        "ttl_remaining_seconds": ttl_remaining_seconds,
        "job_id": job_id,
        "job_status": job_status,
        "disk": disk,
        "ledger": ledger_snapshot(),
        "threat": threat,
        "error": error,
        "method_outcomes_computed": False,
        "cell_g_queried": False,
    }
    if extra:
        payload["extra"] = extra
    return write_status(payload, append_log=True)


def sleep_until_next_heartbeat(last_beat: float, interval: float = HEARTBEAT_SECONDS) -> float:
    """Sleep remaining time until next heartbeat; return new beat timestamp."""
    now = time.time()
    wait = max(0.0, interval - (now - last_beat))
    if wait > 0:
        time.sleep(wait)
    return time.time()
