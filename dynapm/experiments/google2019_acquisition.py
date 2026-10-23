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
DISPOSITION = "ACQUISITION_BLOCKED"
BLOCKER_CODE = "google_cloud_adc_and_billing_project_unavailable"
CELLS = tuple("abcdefgh")
BOUNDED_CELLS = ("a", "b")
PRICE_USD_PER_TIB = 6.25
TIB = 1024**4
DEFAULT_MAXIMUM_BYTES_BILLED = 10 * 1024**3  # 10 GiB: guard, not an estimate.
MIN_VALID_SLOTS = 2000
MIN_SPAN_US = 7 * 24 * 3600 * 1_000_000
CADENCE_US = 300 * 1_000_000
MANAGED_ROOT = REPO_ROOT / "data" / "google2019"
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


class BudgetExceeded(AcquisitionBlocked):
    """Dry-run bytes exceed the configured maximum_bytes_billed guard."""


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
            "code": BLOCKER_CODE,
            "detail": (
                "The Python google-cloud-bigquery client is available in the project "
                "environment, but Application Default Credentials and an explicit "
                "billing/quota project are not configured. Authenticated dry-runs and "
                "bounded extraction are refused until both are present."
            ),
            "resolution": (
                "Authenticate ADC, set an explicit billed GOOGLE_CLOUD_PROJECT / "
                "--billing-project, then run guarded dry-runs before any extraction."
            ),
            "human_bootstrap_actions": human_bootstrap_actions(),
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
            "dry_run_required_before_every_new_query_class": True,
            "execute_requires_explicit_maximum_bytes_billed": True,
            "default_guard_bytes_not_estimate": DEFAULT_MAXIMUM_BYTES_BILLED,
            "dry_run_records": [],
            "estimated_processed_bytes": None,
            "estimated_cost_usd": None,
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
        raise ValueError("disposition must remain ACQUISITION_BLOCKED without dry-runs")
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
    project = billing_project or _env_billing_project()
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


def _require_access(billing_project: str) -> AccessStatus:
    if not billing_project or not str(billing_project).strip():
        raise AcquisitionBlocked(BLOCKER_CODE)
    status = inspect_access(billing_project=billing_project)
    if not status.dry_run_possible:
        raise AcquisitionBlocked(BLOCKER_CODE)
    return status


def dry_run_query(
    sql: str,
    *,
    billing_project: str,
    maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED,
    query_name: str | None = None,
) -> dict[str, Any]:
    """Authenticated dry-run. Never executes a query."""
    _require_access(billing_project)
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing_project)
    job_config = bigquery.QueryJobConfig(
        dry_run=True,
        use_query_cache=False,
        maximum_bytes_billed=maximum_bytes_billed,
    )
    started = utc_now()
    job = client.query(sql, job_config=job_config, location="US")
    processed = int(job.total_bytes_processed or 0)
    return {
        "query_name": query_name,
        "query_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "processed_bytes": processed,
        "estimated_on_demand_cost_usd_before_free_tier": estimate_on_demand_cost_usd(
            processed
        ),
        "maximum_bytes_billed": maximum_bytes_billed,
        "fits_guard": fits_guard(processed, maximum_bytes_billed),
        "location": "US",
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
    """Dry-run first; execute only when dry-run bytes fit the guard."""
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
    from google.cloud import bigquery  # type: ignore[import-not-found]

    client = bigquery.Client(project=billing_project)
    job_config = bigquery.QueryJobConfig(
        dry_run=False,
        use_query_cache=False,
        maximum_bytes_billed=maximum_bytes_billed,
    )
    started = utc_now()
    job = client.query(sql, job_config=job_config, location="US")
    frame = job.to_dataframe(create_bqstorage_client=False)
    executed_bytes = int(job.total_bytes_processed or 0)
    return {
        **dry,
        "dry_run": False,
        "executed": True,
        "execution_timestamp": started,
        "job_id": job.job_id,
        "execution_bytes": executed_bytes,
        "row_count": int(len(frame)),
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
