"""V4B Google ClusterData 2019 acquisition and canonical preprocessing.

This module is outcome-blind: it handles schema/request alignment, continuity,
normalization, deterministic extraction identities, and provenance. It never
constructs or evaluates Static/PW/Full-Rewrite policies.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.experiments.confirmatory_design import emit_yaml
from dynapm.experiments.replication_corpus import frozen_hashes as v4a_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]
QUERY_ROOT = REPO_ROOT / "queries" / "google2019"
CONFIG_JSON = REPO_ROOT / "configs" / "google2019_acquisition_v1.json"
CONFIG_YAML = REPO_ROOT / "configs" / "google2019_acquisition_v1.yaml"

SCHEMA_VERSION = "google2019-acquisition-v1"
DISPOSITION = "ZERO_COST_BOUNDED_SUBSET_REQUIRED"
BLOCKER_CODE = "google_cloud_adc_and_billing_project_unavailable"
BILLING_ENABLED_BLOCKER = "BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED"
ZERO_COST_SCAN_BLOCKER = "frozen_queries_exceed_zero_cost_guards_unpartitioned_full_scans"
CELLS = tuple("abcdefgh")
BOUNDED_CELLS = ("a", "b")
PRICE_USD_PER_TIB = 6.25
GIB = 1024**3
TIB = 1024**4
DEFAULT_MAXIMUM_BYTES_BILLED = 10 * GIB  # 10 GiB: guard, not an estimate.
# Hard zero-cost headroom for V4 executed bytes this month (below 1 TiB free tier).
ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES = 900 * GIB
MIN_VALID_SLOTS = 2000
MIN_SPAN_US = 7 * 24 * 3600 * 1_000_000
CADENCE_US = 300 * 1_000_000
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
LEDGER_PATH = MANAGED_ROOT / "v4_byte_ledger.json"
BOUNDED_EXTRACT_QUERY = "03_bounded_validation_extract.sql"
FULL_CELL_DRY_RUN_CELL = "a"  # representative cell for template dry-runs only

QUERY_FILES = (
    "01_schema_probe.sql",
    "02_bounded_population.sql",
    "03_bounded_validation_extract.sql",
    "04_full_cell_population.sql",
    "05_full_cell_extract.sql",
)

RAW_REQUIRED_COLUMNS = (
    "cell",
    "collection_id",
    "instance_index",
    "collection_type",
    "start_time",
    "end_time",
    "average_cpu",
    "average_memory",
    "request_cpu",
    "request_memory",
    "request_event_time",
    "usage_source_table",
    "request_source_table",
)

CANONICAL_COLUMNS = (
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


class AcquisitionBlocked(RuntimeError):
    """Safe stop caused by missing access/budget prerequisites."""


@dataclass(frozen=True)
class AccessStatus:
    bigquery_cli: bool
    gcloud_cli: bool
    python_bigquery_client: bool
    application_default_credentials: bool
    billing_project: str | None
    dry_run_possible: bool
    blocker_code: str | None
    missing: tuple[str, ...]


@dataclass(frozen=True)
class BillingState:
    project_id: str
    billing_enabled: bool
    billing_account_name: str
    zero_spend_guaranteed: bool
    blocker_code: str | None
    source: str


class BudgetExceeded(AcquisitionBlocked):
    """Dry-run bytes exceed the configured maximum_bytes_billed guard."""


class BillingEnabledBlocked(AcquisitionBlocked):
    """Project has billing enabled; zero cloud spend cannot be guaranteed."""


def query_hashes(root: Path = QUERY_ROOT) -> dict[str, str]:
    return {name: file_sha256(root / name) for name in QUERY_FILES}


def human_bootstrap_actions() -> list[str]:
    """Exact operator actions required before any authenticated dry-run."""
    return [
        "Install Google Cloud SDK once (provides gcloud for ADC login): "
        "brew install --cask google-cloud-sdk",
        "Create or select a billed GCP project with the BigQuery API enabled "
        "(Console → project create / billing linked; enable BigQuery API). "
        "Do not invent a project ID.",
        "Authenticate Application Default Credentials: "
        "gcloud auth application-default login",
        "Bind the ADC quota/billing project (replace YOUR_BILLING_PROJECT): "
        "gcloud auth application-default set-quota-project YOUR_BILLING_PROJECT",
        "Export the billing/quota project for this shell: "
        "export GOOGLE_CLOUD_PROJECT=YOUR_BILLING_PROJECT",
        "Ensure the Python client is installed in the project venv: "
        ".venv/bin/pip install -r requirements-google2019.txt",
        "Verify access (no query execution): "
        ".venv/bin/python -m dynapm.scripts.task28_google2019_acquisition "
        "--access-check --billing-project YOUR_BILLING_PROJECT",
        "Dry-run frozen query classes 01–05: "
        ".venv/bin/python -m dynapm.scripts.task28_google2019_acquisition "
        "--dry-run-all --billing-project YOUR_BILLING_PROJECT",
        "If 01–03 fit the guard, execute only the frozen bounded extract: "
        ".venv/bin/python -m dynapm.scripts.task28_google2019_acquisition "
        "--execute-bounded --billing-project YOUR_BILLING_PROJECT",
    ]


def acquisition_document() -> dict[str, Any]:
    """Frozen V4B acquisition rules and current access disposition."""
    v4a = v4a_hashes()
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "V4B",
        "v4a_protocol_fingerprint": v4a["protocol_fingerprint"],
        "disposition": DISPOSITION,
        "blocker": {
            "code": ZERO_COST_SCAN_BLOCKER,
            "detail": (
                "Zero-spend project (billingEnabled=false) obtained real dry-run bytes, "
                "but frozen queries 02/03 scan ~913.92 GiB and 04/05 (cell a) scan "
                "~471.86 GiB because instance_usage/instance_events are unpartitioned. "
                "All exceed the immutable 10 GiB maximum_bytes_billed guard; 02/03 also "
                "exceed the 900 GiB cumulative free-tier headroom. No query was executed."
            ),
            "resolution": (
                "Redesign scan/engineering for a deterministic outcome-blind subset that "
                "preserves ALLOC_SET entity/continuity/request rules while reducing "
                "processed bytes under the 10 GiB guard—without raising guards or "
                "enabling billing."
            ),
            "human_bootstrap_actions": [],
        },
        "official_source": {
            "project": "google.com:google-cluster-data",
            "datasets": [f"clusterdata_2019_{cell}" for cell in CELLS],
            "tables": ["instance_usage", "instance_events"],
            "location": "US",
            "license": "CC-BY-4.0",
            "schema_url": (
                "https://github.com/google/cluster-data/blob/master/"
                "clusterdata_trace_format_v3.proto"
            ),
        },
        "budget_guard": {
            "pricing_reference_url": "https://cloud.google.com/bigquery/pricing",
            "on_demand_usd_per_tib_at_freeze": PRICE_USD_PER_TIB,
            "first_tib_month_note": "Official pricing lists first 1 TiB/month/account free; do not assume remaining allowance.",
            "zero_cloud_spend_required": True,
            "require_billing_enabled_false": True,
            "billing_enabled_blocker": BILLING_ENABLED_BLOCKER,
            "dry_run_required_before_every_new_query_class": True,
            "execute_requires_explicit_maximum_bytes_billed": True,
            "default_guard_bytes_not_estimate": DEFAULT_MAXIMUM_BYTES_BILLED,
            "cumulative_execution_cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
            "cumulative_execution_cap_gib": 900,
            "prior_monthly_usage_assumed_unknown": True,
            "dry_run_records": [
                {
                    "query": "01_schema_probe.sql",
                    "processed_bytes": None,
                    "decision": "REFUSE",
                    "reason": "INFORMATION_SCHEMA Forbidden on public project",
                },
                {
                    "query": "02_bounded_population.sql",
                    "processed_bytes": 981313230072,
                    "decision": "REFUSE",
                    "reason": "exceeds 10 GiB guard and 900 GiB cumulative headroom",
                },
                {
                    "query": "03_bounded_validation_extract.sql",
                    "processed_bytes": 981313230072,
                    "decision": "REFUSE",
                    "reason": "exceeds 10 GiB guard and 900 GiB cumulative headroom",
                },
                {
                    "query": "04_full_cell_population.sql",
                    "rendered_cell": "a",
                    "processed_bytes": 506658530736,
                    "decision": "REFUSE",
                    "reason": "exceeds 10 GiB guard",
                },
                {
                    "query": "05_full_cell_extract.sql",
                    "rendered_cell": "a",
                    "processed_bytes": 506658530736,
                    "decision": "REFUSE",
                    "reason": "exceeds 10 GiB guard",
                },
            ],
            "estimated_processed_bytes": 981313230072,
            "estimated_cost_usd": None,
            "projected_full_acquisition_query_bytes_cell_a": 506658530736,
            "projected_full_acquisition_query_bytes_eight_cells_if_similar": (
                8 * 506658530736
            ),
            "bounded_extract_executed": False,
            "zero_cost_project_id_note": (
                "quota project resolved at runtime; never commit secrets"
            ),
            "time_predicates_may_not_prune_unpartitioned_tables": True,
            "bounded_time_filter_not_a_cost_guarantee": (
                "instance_usage/instance_events are not documented as partitioned on "
                "start_time. A [7d,15d) predicate may still scan a full cell table; "
                "dry-run bytes, not the SQL filter, determine cost."
            ),
        },
        "population": {
            "eligible_cells": list(CELLS),
            "bounded_validation_cells": list(BOUNDED_CELLS),
            "collection_type": 1,
            "collection_semantics": "ALLOC_SET instances only",
            "reason": "avoid task/alloc parent-child double counting",
            "entity_key": ["cell", "collection_id", "instance_index"],
            "minimum_valid_aligned_slots": MIN_VALID_SLOTS,
            "minimum_span_us": MIN_SPAN_US,
            "minimum_span_days": 7,
            "bounded_interval_us": [7 * 86400 * 1_000_000, 15 * 86400 * 1_000_000],
            "bounded_selection": (
                "up to two FARM_FINGERPRINT-ranked entities per "
                "(cell, has_request_change, has_missing_slot) metadata stratum"
            ),
            "forbidden_selection_inputs": [
                "Static/PW/Full-Rewrite outputs",
                "profile fidelity",
                "Materna effects",
            ],
        },
        "normalization": {
            "usage_cpu": "instance_usage.average_usage.cpus (NCU)",
            "usage_memory": "instance_usage.average_usage.memory (normalized RAM)",
            "request_cpu": "instance_events.resource_request.cpus (NCU)",
            "request_memory": "instance_events.resource_request.memory (normalized RAM)",
            "cpu_formula": "average_usage.cpus / latest_positive_request.cpus",
            "memory_formula": "average_usage.memory / latest_positive_request.memory",
            "request_alignment": (
                "latest unambiguous positive request event with event.time <= usage.start_time"
            ),
            "zero_missing_request": "row invalid; never divide or carry backward from future",
            "changing_request": "re-align each usage window causally",
            "utilization_above_one": "preserve; never clip",
        },
        "cadence_and_missingness": {
            "nominal_cadence_seconds": 300,
            "bucket_rule": "floor(start_time / 300s) * 300s",
            "short_lifetime_edge_windows": "retain if duration is positive and <=300s",
            "duplicate_rule": (
                "within entity+bucket choose greatest end_time, then smallest source-row SHA-256"
            ),
            "ambiguous_same_time_requests": "exclude event timestamp unless request pair is unique",
            "missing_slots": "leave absent; never interpolate, forward-fill, or upsample",
            "finite_nonnegative_usage_required": True,
            "positive_requests_required": True,
        },
        "eligibility": {
            "bootstrap_fraction": 0.30,
            "profile_window": "(t-24h,t]",
            "profile_min_paired_slots": 200,
            "truth_window": "(t,t+24h]",
            "truth_min_paired_slots": 200,
            "hourly_evaluation": True,
            "minimum_total_observations_guidance": MIN_VALID_SLOTS,
            "performance_based_exclusion": False,
        },
        "queries": {
            "root": "queries/google2019",
            "sha256": query_hashes(),
        },
        "canonical_output": {
            "format": "parquet",
            "columns": list(CANONICAL_COLUMNS),
            "timestamp_semantics": "trace-relative microseconds at nominal bucket start",
            "scientific_identity_paths": "repository-relative only",
            "immutable_write": True,
        },
        "execution_guards": {
            "method_outcomes_computed": False,
            "full_dataset_downloaded": False,
            "bounded_extract_executed": False,
            "large_export_authorized": False,
        },
    }


def validate_acquisition_document(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = doc if doc is not None else acquisition_document()
    if doc["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported acquisition schema")
    if doc["v4a_protocol_fingerprint"] != (
        "4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226"
    ):
        raise ValueError("V4A protocol fingerprint mismatch")
    if doc["disposition"] != DISPOSITION:
        raise ValueError(f"disposition must match module freeze ({DISPOSITION})")
    if doc["budget_guard"].get("zero_cloud_spend_required") is not True:
        raise ValueError("zero cloud spend remains required")
    if doc["execution_guards"].get("bounded_extract_executed"):
        raise ValueError("bounded extract must remain unexecuted under current guards")
    if doc["population"]["eligible_cells"] != list(CELLS):
        raise ValueError("eligible cells must be a..h")
    if doc["population"]["collection_type"] != 1:
        raise ValueError("canonical population must be ALLOC_SET")
    if doc["normalization"]["utilization_above_one"] != "preserve; never clip":
        raise ValueError("utilization >1 must not be clipped")
    if doc["queries"]["sha256"] != query_hashes():
        raise ValueError("query hash mismatch")
    guards = doc["execution_guards"]
    if guards["method_outcomes_computed"] or guards["full_dataset_downloaded"]:
        raise ValueError("V4B blocked record cannot claim outcomes/download")
    return {
        "config_fingerprint": fingerprint(doc),
        "disposition": doc["disposition"],
        "blocker_code": doc["blocker"]["code"],
    }


def write_config_files(root: Path = REPO_ROOT) -> dict[str, str]:
    doc = acquisition_document()
    json_path = root / "configs" / "google2019_acquisition_v1.json"
    yaml_path = root / "configs" / "google2019_acquisition_v1.yaml"
    json_path.write_text(canonical_json(doc) + "\n", encoding="utf-8")
    yaml_path.write_text(
        "# V4B acquisition/preprocessing freeze; JSON is authoritative\n"
        + emit_yaml(doc),
        encoding="utf-8",
    )
    info = validate_acquisition_document(doc)
    return {
        **info,
        "config_json_sha256": file_sha256(json_path),
        "config_yaml_sha256": file_sha256(yaml_path),
    }


def frozen_hashes() -> dict[str, Any]:
    doc = read_json(CONFIG_JSON)
    info = validate_acquisition_document(doc)
    return {
        **info,
        "config_json_sha256": file_sha256(CONFIG_JSON),
        "config_yaml_sha256": file_sha256(CONFIG_YAML),
        "query_sha256": query_hashes(),
    }


def render_cell_query(name: str, cell: str) -> str:
    if name not in {"04_full_cell_population.sql", "05_full_cell_extract.sql"}:
        raise ValueError("not a cell-template query")
    if cell not in CELLS:
        raise ValueError("cell must be one of a..h")
    text = (QUERY_ROOT / name).read_text(encoding="utf-8")
    rendered = text.replace("{{CELL}}", cell)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("unresolved query template")
    return rendered


def estimate_on_demand_cost_usd(processed_bytes: int) -> float:
    if processed_bytes < 0:
        raise ValueError("processed bytes cannot be negative")
    return float(processed_bytes / TIB * PRICE_USD_PER_TIB)


def fits_guard(processed_bytes: int, maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED) -> bool:
    return int(processed_bytes) <= int(maximum_bytes_billed)


def _has_adc() -> bool:
    import os

    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and Path(env_path).is_file():
        return True
    adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    return adc_path.is_file()


def _env_billing_project() -> str | None:
    import os

    return os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")


def _adc_quota_project() -> str | None:
    """Read quota_project_id from ADC JSON without exposing secrets."""
    import os

    candidates: list[Path] = []
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(
        Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        quota = data.get("quota_project_id")
        if isinstance(quota, str) and quota.strip():
            return quota.strip()
    return None


def resolve_quota_project(explicit: str | None = None) -> str | None:
    return explicit or _env_billing_project() or _adc_quota_project()


def _billing_state_from_payload(
    project_id: str, payload: dict[str, Any], *, source: str
) -> BillingState:
    enabled = bool(payload.get("billingEnabled", False))
    account = str(payload.get("billingAccountName") or "")
    if enabled:
        return BillingState(
            project_id=project_id,
            billing_enabled=True,
            billing_account_name=account,
            zero_spend_guaranteed=False,
            blocker_code=BILLING_ENABLED_BLOCKER,
            source=source,
        )
    return BillingState(
        project_id=project_id,
        billing_enabled=False,
        billing_account_name=account,
        zero_spend_guaranteed=True,
        blocker_code=None,
        source=source,
    )


def _inspect_billing_via_http(project_id: str) -> BillingState | None:
    try:
        import google.auth  # type: ignore[import-not-found]
        import google.auth.transport.requests  # type: ignore[import-not-found]
    except ImportError:
        return None
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = google.auth.transport.requests.AuthorizedSession(credentials)
    url = (
        "https://cloudbilling.googleapis.com/v1/projects/"
        f"{project_id}/billingInfo"
    )
    response = session.get(url, timeout=60)
    if response.status_code != 200:
        return None
    return _billing_state_from_payload(
        project_id, response.json(), source="cloudbilling.googleapis.com"
    )


def _inspect_billing_via_gcloud(project_id: str) -> BillingState | None:
    import shutil
    import subprocess

    if shutil.which("gcloud") is None:
        return None
    completed = subprocess.run(
        [
            "gcloud",
            "billing",
            "projects",
            "describe",
            project_id,
            "--format=json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return _billing_state_from_payload(
        project_id, payload, source="gcloud billing projects describe"
    )


def inspect_billing_state(project_id: str) -> BillingState:
    """Verify Cloud Billing billingEnabled. Refuses when billing is on."""
    if not project_id or not str(project_id).strip():
        raise AcquisitionBlocked(BLOCKER_CODE)
    state = _inspect_billing_via_http(project_id) or _inspect_billing_via_gcloud(
        project_id
    )
    if state is None:
        raise AcquisitionBlocked("billing_info_unavailable")
    return state


def require_zero_cost_project(project_id: str) -> BillingState:
    state = inspect_billing_state(project_id)
    if state.billing_enabled or not state.zero_spend_guaranteed:
        raise BillingEnabledBlocked(BILLING_ENABLED_BLOCKER)
    return state


def load_byte_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": "google2019-v4-byte-ledger-v1",
            "executed_entries": [],
            "cumulative_executed_bytes": 0,
            "prior_monthly_usage_verified": False,
            "cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
        }
    return read_json(path)


def cumulative_executed_bytes(path: Path = LEDGER_PATH) -> int:
    return int(load_byte_ledger(path).get("cumulative_executed_bytes") or 0)


def projected_cumulative_bytes(
    additional_bytes: int, path: Path = LEDGER_PATH
) -> int:
    return cumulative_executed_bytes(path) + int(additional_bytes)


def fits_zero_cost_headroom(
    additional_bytes: int,
    *,
    path: Path = LEDGER_PATH,
    cap_bytes: int = ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
) -> bool:
    return projected_cumulative_bytes(additional_bytes, path) <= int(cap_bytes)


def record_executed_bytes(
    *,
    query_name: str,
    executed_bytes: int,
    job_id: str | None,
    path: Path = LEDGER_PATH,
) -> dict[str, Any]:
    """Append an executed-query entry to the local V4 acquisition byte ledger."""
    ledger = load_byte_ledger(path)
    entry = {
        "query_name": query_name,
        "executed_bytes": int(executed_bytes),
        "job_id": job_id,
        "recorded_at": utc_now(),
    }
    entries = list(ledger.get("executed_entries") or [])
    entries.append(entry)
    cumulative = int(sum(int(item["executed_bytes"]) for item in entries))
    if cumulative > ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES:
        raise BudgetExceeded(
            f"ledger cumulative {cumulative} exceeds zero-cost cap "
            f"{ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES}"
        )
    payload = {
        "schema_version": "google2019-v4-byte-ledger-v1",
        "executed_entries": entries,
        "cumulative_executed_bytes": cumulative,
        "prior_monthly_usage_verified": False,
        "cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
        "updated_at": utc_now(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload


def inspect_access(billing_project: str | None = None) -> AccessStatus:
    """Inspect access without printing account names or credential contents."""
    import importlib.util
    import shutil

    has_client = False
    try:
        spec = importlib.util.find_spec("google.cloud.bigquery")
        has_client = spec is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        has_client = False
    has_adc = _has_adc()
    project = resolve_quota_project(billing_project)
    missing: list[str] = []
    if not has_client:
        missing.append("python_bigquery_client")
    if not has_adc:
        missing.append("application_default_credentials")
    if not project:
        missing.append("billing_project")
    possible = not missing
    return AccessStatus(
        bigquery_cli=shutil.which("bq") is not None,
        gcloud_cli=shutil.which("gcloud") is not None,
        python_bigquery_client=has_client,
        application_default_credentials=has_adc,
        billing_project=project,
        dry_run_possible=possible,
        blocker_code=None if possible else BLOCKER_CODE,
        missing=tuple(missing),
    )


def load_query_sql(name: str, *, cell: str | None = None) -> str:
    """Load a frozen query; render {{CELL}} only for full-cell templates."""
    if name not in QUERY_FILES:
        raise ValueError(f"unknown query file: {name}")
    if name.startswith(("04_", "05_")):
        if cell is None:
            raise ValueError("--cell is required for cell-template queries")
        return render_cell_query(name, cell)
    return (QUERY_ROOT / name).read_text(encoding="utf-8")


def _require_access(billing_project: str) -> tuple[AccessStatus, BillingState]:
    project = resolve_quota_project(billing_project)
    if not project:
        raise AcquisitionBlocked(BLOCKER_CODE)
    status = inspect_access(billing_project=project)
    if not status.dry_run_possible:
        raise AcquisitionBlocked(BLOCKER_CODE)
    billing = require_zero_cost_project(project)
    return status, billing


def dry_run_query(
    sql: str,
    *,
    billing_project: str,
    maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED,
    query_name: str | None = None,
) -> dict[str, Any]:
    """Authenticated dry-run. Never executes a query. Requires billingEnabled=false."""
    _, billing = _require_access(billing_project)
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    job_config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=maximum_bytes_billed,
    )
    started = utc_now()
    try:
        job = client.query(sql, job_config=job_config, location="US")
        processed = int(job.total_bytes_processed or 0)
        error = None
    except Exception as exc:  # noqa: BLE001 — record dry-run refusal, do not execute
        from google.api_core import exceptions as gexc  # type: ignore[import-not-found]

        if not isinstance(
            exc,
            (
                gexc.GoogleAPICallError,
                gexc.RetryError,
            ),
        ):
            raise
        processed = None
        error = {
            "type": type(exc).__name__,
            "message": str(exc).split("\n", 1)[0][:500],
        }
    if processed is None:
        decision = "REFUSE"
        fits = False
        headroom = False
        projected = cumulative_executed_bytes()
    else:
        fits = fits_guard(processed, maximum_bytes_billed)
        headroom = fits_zero_cost_headroom(processed)
        projected = projected_cumulative_bytes(processed)
        decision = "EXECUTE_CANDIDATE" if fits and headroom else "REFUSE"
    return {
        "query_name": query_name,
        "query_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "query_file_sha256": (
            query_hashes().get(query_name) if query_name in QUERY_FILES else None
        ),
        "processed_bytes": processed,
        "estimated_on_demand_cost_usd_before_free_tier": (
            None
            if processed is None
            else estimate_on_demand_cost_usd(processed)
        ),
        "maximum_bytes_billed": maximum_bytes_billed,
        "fits_guard": fits,
        "fits_zero_cost_headroom": headroom,
        "projected_cumulative_executed_bytes": projected,
        "cumulative_executed_bytes_before": cumulative_executed_bytes(),
        "zero_cost_cap_bytes": ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES,
        "decision": decision,
        "error": error,
        "location": "US",
        "quota_project": billing.project_id,
        "billing_enabled": billing.billing_enabled,
        "zero_spend_guaranteed": billing.zero_spend_guaranteed,
        "billing_project_configured": True,
        "dry_run": True,
        "executed": False,
        "timestamp": started,
        "time_filter_not_cost_guarantee": True,
    }


def execute_query_guarded(
    sql: str,
    *,
    billing_project: str,
    maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED,
    query_name: str | None = None,
) -> dict[str, Any]:
    """Dry-run first; execute only under zero-cost billing + byte guards."""
    # Re-check billing immediately before any execution path.
    require_zero_cost_project(resolve_quota_project(billing_project) or billing_project)
    dry = dry_run_query(
        sql,
        billing_project=billing_project,
        maximum_bytes_billed=maximum_bytes_billed,
        query_name=query_name,
    )
    if not dry["fits_guard"]:
        raise BudgetExceeded(
            f"dry-run {dry['processed_bytes']} bytes exceeds guard "
            f"{maximum_bytes_billed}"
        )
    if not dry["fits_zero_cost_headroom"]:
        raise BudgetExceeded(
            f"projected cumulative {dry['projected_cumulative_executed_bytes']} "
            f"exceeds zero-cost cap {ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES}"
        )
    # Final billing check immediately before the paid-capable API call.
    billing = require_zero_cost_project(dry["quota_project"])
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing.project_id)
    job_config = bigquery.QueryJobConfig(
        dry_run=False,
        use_query_cache=False,
        maximum_bytes_billed=maximum_bytes_billed,
    )
    started = utc_now()
    job = client.query(sql, job_config=job_config, location="US")
    frame = job.to_dataframe(create_bqstorage_client=False)
    executed_bytes = int(job.total_bytes_processed or 0)
    ledger = record_executed_bytes(
        query_name=query_name or "anonymous.sql",
        executed_bytes=executed_bytes,
        job_id=job.job_id,
    )
    return {
        **dry,
        "dry_run": False,
        "executed": True,
        "decision": "EXECUTED",
        "execution_timestamp": started,
        "job_id": job.job_id,
        "execution_bytes": executed_bytes,
        "row_count": int(len(frame)),
        "cumulative_executed_bytes_after": ledger["cumulative_executed_bytes"],
        "billing_enabled_at_execution": billing.billing_enabled,
        "dataframe": frame,
    }


def dry_run_all_query_classes(
    *,
    billing_project: str,
    maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED,
    full_cell: str = FULL_CELL_DRY_RUN_CELL,
) -> list[dict[str, Any]]:
    """Dry-run frozen query classes 01–05. Templates use one representative cell."""
    if full_cell not in CELLS:
        raise ValueError("full_cell must be one of a..h")
    require_zero_cost_project(resolve_quota_project(billing_project) or billing_project)
    records: list[dict[str, Any]] = []
    for name in QUERY_FILES:
        cell = full_cell if name.startswith(("04_", "05_")) else None
        sql = load_query_sql(name, cell=cell)
        record = dry_run_query(
            sql,
            billing_project=billing_project,
            maximum_bytes_billed=maximum_bytes_billed,
            query_name=name,
        )
        if cell is not None:
            record = {**record, "rendered_cell": cell}
        records.append(record)
    return records


def write_query_provenance(
    records: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
    kind: str = "dry_run",
) -> dict[str, Any]:
    """Persist dry-run/execution provenance under the gitignored managed root."""
    root = Path(output_dir) if output_dir is not None else MANAGED_ROOT / "provenance"
    root.mkdir(parents=True, exist_ok=True)
    serializable = []
    for record in records:
        item = {k: v for k, v in record.items() if k != "dataframe"}
        serializable.append(item)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "v4a_protocol_fingerprint": v4a_hashes()["protocol_fingerprint"],
        "preprocessing_config_fingerprint": frozen_hashes()["config_fingerprint"],
        "query_file_sha256": query_hashes(),
        "records": serializable,
        "method_outcomes_computed": False,
        "written_at": utc_now(),
    }
    path = root / f"{kind}_provenance.json"
    if path.exists():
        raise FileExistsError(f"immutable provenance already exists: {path}")
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return {**payload, "path": "data/google2019/provenance/" + path.name, "sha256": file_sha256(path)}


def execute_bounded_validation_extract(
    *,
    billing_project: str,
    maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute only the frozen bounded extract after a passing dry-run."""
    sql = load_query_sql(BOUNDED_EXTRACT_QUERY)
    result = execute_query_guarded(
        sql,
        billing_project=billing_project,
        maximum_bytes_billed=maximum_bytes_billed,
        query_name=BOUNDED_EXTRACT_QUERY,
    )
    frame = result.pop("dataframe")
    out = Path(output_dir) if output_dir is not None else (
        MANAGED_ROOT / "bounded_validation"
    )
    write_query_provenance(
        [{k: v for k, v in result.items()}],
        output_dir=out / "provenance",
        kind="bounded_execution",
    )
    manifest = write_canonical_artifacts(
        frame,
        out / "canonical",
        query_name=BOUNDED_EXTRACT_QUERY,
        extraction_timestamp=result["execution_timestamp"],
        job_provenance=result,
    )
    return {
        "execution": result,
        "manifest": manifest,
        "output_root": "data/google2019/bounded_validation",
    }


def _row_sha(row: pd.Series) -> str:
    value = {
        key: None if pd.isna(row[key]) else row[key]
        for key in RAW_REQUIRED_COLUMNS
    }
    return fingerprint(value)


def canonicalize_extract(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Normalize an extracted source table without any method outcome computation."""
    missing = set(RAW_REQUIRED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"missing source columns: {sorted(missing)}")
    frame = raw.loc[:, RAW_REQUIRED_COLUMNS].copy()
    frame["source_row_sha256"] = frame.apply(_row_sha, axis=1)
    numeric = (
        "collection_id",
        "instance_index",
        "collection_type",
        "start_time",
        "end_time",
        "average_cpu",
        "average_memory",
        "request_cpu",
        "request_memory",
        "request_event_time",
    )
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    reasons = pd.Series("", index=frame.index, dtype=object)
    invalid_numeric = ~np.isfinite(frame[list(numeric)].to_numpy(dtype=float)).all(axis=1)
    reasons.loc[invalid_numeric] = "corrupt_or_nonfinite_source_data"
    wrong_type = frame["collection_type"].ne(1)
    reasons.loc[reasons.eq("") & wrong_type] = "non_alloc_collection_type"
    bad_usage = frame["average_cpu"].lt(0) | frame["average_memory"].lt(0)
    reasons.loc[reasons.eq("") & bad_usage] = "negative_resource_usage"
    bad_request = frame["request_cpu"].le(0) | frame["request_memory"].le(0)
    reasons.loc[reasons.eq("") & bad_request] = "missing_positive_resource_request"
    future_request = frame["request_event_time"].gt(frame["start_time"])
    reasons.loc[reasons.eq("") & future_request] = "request_event_after_usage_window"
    bad_window = frame["end_time"].le(frame["start_time"]) | (
        frame["end_time"] - frame["start_time"]
    ).gt(CADENCE_US)
    reasons.loc[reasons.eq("") & bad_window] = "protocol_invalid_window_duration"

    rejected = frame.loc[reasons.ne("")].copy()
    rejected["exclusion_reason"] = reasons.loc[reasons.ne("")]
    valid = frame.loc[reasons.eq("")].copy()
    valid["timestamp_us"] = (valid["start_time"] // CADENCE_US) * CADENCE_US
    valid = valid.sort_values(
        [
            "cell",
            "collection_id",
            "instance_index",
            "timestamp_us",
            "end_time",
            "source_row_sha256",
        ],
        ascending=[True, True, True, True, False, True],
        kind="mergesort",
    )
    duplicate_mask = valid.duplicated(
        ["cell", "collection_id", "instance_index", "timestamp_us"], keep="first"
    )
    duplicates = valid.loc[duplicate_mask].copy()
    duplicates["exclusion_reason"] = "duplicate_nominal_bucket"
    rejected = pd.concat([rejected, duplicates], ignore_index=True)
    valid = valid.loc[~duplicate_mask].copy()

    # Preserve >1 values: over-request usage is a valid observed state.
    valid["cpu_utilization"] = valid["average_cpu"] / valid["request_cpu"]
    valid["memory_utilization"] = valid["average_memory"] / valid["request_memory"]
    valid = valid.rename(
        columns={
            "average_cpu": "average_cpu_ncu",
            "average_memory": "average_memory_normalized_ram",
            "request_cpu": "request_cpu_ncu",
            "request_memory": "request_memory_normalized_ram",
            "request_event_time": "request_event_time_us",
        }
    )
    canonical = valid.loc[:, CANONICAL_COLUMNS].sort_values(
        ["cell", "collection_id", "instance_index", "timestamp_us"],
        kind="mergesort",
    )
    if not np.isfinite(
        canonical[["cpu_utilization", "memory_utilization"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("canonical utilization must be finite")
    entities = []
    for key, group in canonical.groupby(
        ["cell", "collection_id", "instance_index"], sort=True
    ):
        observed = int(group["timestamp_us"].nunique())
        first = int(group["timestamp_us"].min())
        last = int(group["timestamp_us"].max())
        expected = 1 + (last - first) // CADENCE_US
        request_states = int(
            group[["request_cpu_ncu", "request_memory_normalized_ram"]]
            .drop_duplicates()
            .shape[0]
        )
        if observed < MIN_VALID_SLOTS:
            exclusion = "insufficient_bootstrap_history"
        elif last - first < MIN_SPAN_US:
            exclusion = "insufficient_continuous_span_for_24h_windows"
        else:
            exclusion = None
        entities.append(
            {
                "cell": key[0],
                "collection_id": int(key[1]),
                "instance_index": int(key[2]),
                "first_timestamp_us": first,
                "last_timestamp_us": last,
                "observed_slots": observed,
                "expected_slots": int(expected),
                "missing_slots": int(expected - observed),
                "request_states": request_states,
                "has_request_change": request_states > 1,
                "eligible": exclusion is None,
                "exclusion_reason": exclusion,
            }
        )
    entity_manifest = pd.DataFrame(entities)
    diagnostics = {
        "input_rows": int(len(raw)),
        "canonical_rows": int(len(canonical)),
        "rejected_rows": int(len(rejected)),
        "duplicate_rows": int(len(duplicates)),
        "entities": int(len(entity_manifest)),
        "eligible_entities": (
            int(entity_manifest["eligible"].sum()) if len(entity_manifest) else 0
        ),
        "cells": sorted(canonical["cell"].astype(str).unique().tolist()),
        "utilization_above_one_cpu_rows": int((canonical["cpu_utilization"] > 1).sum()),
        "utilization_above_one_memory_rows": int(
            (canonical["memory_utilization"] > 1).sum()
        ),
        "method_outcomes_computed": False,
    }
    return canonical.reset_index(drop=True), entity_manifest, {
        "diagnostics": diagnostics,
        "rejected": rejected,
    }


def write_canonical_artifacts(
    raw: pd.DataFrame,
    output_dir: Path,
    *,
    query_name: str,
    extraction_timestamp: str | None = None,
    job_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write immutable canonical Parquet + manifests. Refuses overwrite."""
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    canonical, entities, details = canonicalize_extract(raw)
    canonical_path = output_dir / "canonical_usage.parquet"
    entities_path = output_dir / "entity_manifest.parquet"
    rejected_path = output_dir / "rejected_rows.parquet"
    canonical.to_parquet(canonical_path, index=False)
    entities.to_parquet(entities_path, index=False)
    details["rejected"].to_parquet(rejected_path, index=False)
    query_path = QUERY_ROOT / query_name
    continuity = {
        "entities_with_missing_slots": int(
            (entities["missing_slots"] > 0).sum() if len(entities) else 0
        ),
        "entities_with_request_change": int(
            entities["has_request_change"].sum() if len(entities) else 0
        ),
        "total_missing_slots": int(
            entities["missing_slots"].sum() if len(entities) else 0
        ),
        "min_timestamp_us": (
            int(canonical["timestamp_us"].min()) if len(canonical) else None
        ),
        "max_timestamp_us": (
            int(canonical["timestamp_us"].max()) if len(canonical) else None
        ),
        "duration_us": (
            int(canonical["timestamp_us"].max() - canonical["timestamp_us"].min())
            if len(canonical)
            else None
        ),
        "cadence_us": CADENCE_US,
    }
    job_meta = None
    if job_provenance is not None:
        job_meta = {
            key: job_provenance[key]
            for key in (
                "query_name",
                "query_sha256",
                "processed_bytes",
                "execution_bytes",
                "job_id",
                "maximum_bytes_billed",
                "fits_guard",
                "execution_timestamp",
                "estimated_on_demand_cost_usd_before_free_tier",
            )
            if key in job_provenance
        }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "preprocessing_config_fingerprint": frozen_hashes()["config_fingerprint"],
        "v4a_protocol_fingerprint": v4a_hashes()["protocol_fingerprint"],
        "query": {
            "path": f"queries/google2019/{query_name}",
            "sha256": file_sha256(query_path),
        },
        "job_provenance": job_meta,
        "source_tables": sorted(
            set(canonical["usage_source_table"].astype(str))
            | set(canonical["request_source_table"].astype(str))
        ),
        "extraction_timestamp": extraction_timestamp or utc_now(),
        "row_count": int(len(canonical)),
        "entity_count": int(len(entities)),
        "eligible_entity_count": (
            int(entities["eligible"].sum()) if len(entities) else 0
        ),
        "cell_count": int(canonical["cell"].nunique()) if len(canonical) else 0,
        "cells": sorted(canonical["cell"].astype(str).unique().tolist()),
        "continuity": continuity,
        "files": {
            path.name: {
                "sha256": file_sha256(path),
                "rows": int(
                    len(
                        canonical
                        if path == canonical_path
                        else entities
                        if path == entities_path
                        else details["rejected"]
                    )
                ),
            }
            for path in (canonical_path, entities_path, rejected_path)
        },
        "diagnostics": details["diagnostics"],
        "method_outcomes_computed": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return {**manifest, "manifest_sha256": file_sha256(manifest_path)}
