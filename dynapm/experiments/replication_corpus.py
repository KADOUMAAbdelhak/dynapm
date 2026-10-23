"""V4A independent corpus selection: frozen Google ClusterData 2019 protocol-fit.

No dataset download or outcome evaluation. Validates machine-readable replication
protocol against the frozen V3 estimation study framing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.experiments.confirmatory_design import (
    COMPARISON_FAMILIES,
    PRIMARY_FIDELITY_ENDPOINTS,
    PRIMARY_METHODS,
    emit_yaml,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_JSON = REPO_ROOT / "configs" / "google_clusterdata_2019_replication_protocol_v1.json"
CONFIG_YAML = REPO_ROOT / "configs" / "google_clusterdata_2019_replication_protocol_v1.yaml"

SCHEMA_VERSION = "google-clusterdata-2019-replication-protocol-v1"
GATE = "V4A"
DISPOSITION = "CORPUS READY FOR ACQUISITION"
PREFERRED_CORPUS = "google_clusterdata_2019"

# Inherited unchanged from V3 / V2.5A (scientific framing).
INHERITED_UNCHANGED = {
    "methods": list(PRIMARY_METHODS),
    "comparison_families": {
        name: [{"treatment": a, "control": b} for a, b in pairs]
        for name, pairs in COMPARISON_FAMILIES.items()
    },
    "primary_fidelity_endpoints": list(PRIMARY_FIDELITY_ENDPOINTS),
    "primary_cost_endpoint": "n_refresh_events",
    "study_framing": "estimation_first",
    "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
    "temporal_protocol_label": "causal-timeline-v3",
    "evaluation_grid_label": "phase-balanced-hourly-v1",
    "accounting_label": "refresh-accounting-v1",
    "observation_window": "(t-24h,t], >=200/288 paired finite resource slots where refresh eligibility applies",
    "forward_truth_window": "(t,t+24h]",
    "bootstrap_fraction": 0.30,
    "statistics": {
        "bootstrap_repetitions": 10000,
        "bootstrap_seed": 20251022,
        "paired_test": "wilcoxon",
        "zero_method": "wilcox",
        "multiplicity": "holm_within_family",
    },
    "withdrawn_claims": ["C1_forecasting_superiority", "C2_adaptive_refresh_superiority"],
}


def protocol_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": GATE,
        "disposition": DISPOSITION,
        "preferred_corpus_id": PREFERRED_CORPUS,
        "preferred_corpus_name": "Google ClusterData 2019 (Borg / clusterdata-2019)",
        "v3_design_fingerprint_reference": (
            "62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296"
        ),
        "materna_confirmatory_redesign": False,
        "second_corpus_outcome_access": False,
        "ranking_policy": "protocol_fit_and_reproducibility_not_expected_effects",
        "official_sources": [
            {
                "id": "google_clusterdata_2019_readme",
                "url": "https://github.com/google/cluster-data/blob/master/ClusterData2019.md",
                "role": "access_scale_license_overview",
            },
            {
                "id": "google_clusterdata_trace_format_v3",
                "url": "https://github.com/google/cluster-data/blob/master/clusterdata_trace_format_v3.proto",
                "role": "instance_usage_resource_schema",
            },
            {
                "id": "google_clusterdata_license",
                "url": "https://github.com/google/cluster-data#license",
                "role": "cc_by_4_0",
            },
            {
                "id": "google_cluster_usage_traces_v3_doc",
                "url": "https://drive.google.com/file/d/10r6cnJ5cJ89fPWCgj7j4LtLBqYN9RiI9/view",
                "role": "authoritative_trace_documentation",
            },
        ],
        "ranked_candidates": [
            {
                "rank": 1,
                "corpus_id": "google_clusterdata_2019",
                "name": "Google ClusterData 2019",
                "verdict": "preferred",
            },
            {
                "rank": 2,
                "corpus_id": "alibaba_cluster_trace_2018",
                "name": "Alibaba Cluster Trace 2018",
                "verdict": "optional_backup_short_duration",
            },
            {
                "rank": 3,
                "corpus_id": "alibaba_maas_2026_instance_week_5min",
                "name": "Alibaba 2026 MaaS instance_week_5min",
                "verdict": "not_preferred_for_v3_protocol",
            },
        ],
        "inherited_from_v3_unchanged": INHERITED_UNCHANGED,
        "adaptation": {
            "canonical_entity": {
                "key": ["cell", "collection_id", "instance_index"],
                "preferred_population": "long_lived_alloc_or_job_instances",
                "note": (
                    "Prefer alloc instances / long-lived collections; do not double-count "
                    "parent and child usage. Cell is one of the eight May 2019 Borg cells."
                ),
            },
            "resource_fields": {
                "cpu_series": "instance_usage.average_usage.cpus",
                "memory_series": "instance_usage.average_usage.memory",
                "optional_cpu_tail": "tail_cpu_usage_distribution",
                "forbidden_as_primary_memory": "random_sample_usage (CPU-only)",
            },
            "units_and_normalization": {
                "raw_units": {
                    "cpu": "normalized_compute_units_NCU",
                    "memory": "normalized_RAM",
                },
                "profile_utilization_definition": (
                    "request_normalized_utilization = average_usage / request "
                    "when request>0 for that resource; else exclude sample as missing"
                ),
                "materna_percent_equivalence": False,
                "scientific_meaning_transfer": (
                    "Profiles remain trailing-window mean/p95 and class gates on a "
                    "paired two-resource utilization series evaluated hourly against "
                    "forward (t,t+24h] truth. Units are request-normalized Borg usage, "
                    "not Materna provisioned-capacity percentages. RQs about maintenance, "
                    "cadence, rewrite cost, and robustness are unchanged; cross-corpus "
                    "claims must state the unit adaptation."
                ),
            },
            "nominal_cadence": {
                "target_seconds": 300,
                "source": "instance_usage windows typically 300s; may be shorter at lifetime edges",
                "binning_rule": (
                    "Map each usage record to nominal five-minute grid by floor(start_time) "
                    "to 300s buckets in trace-relative microseconds; never upsample or "
                    "invent missing buckets"
                ),
            },
            "duplicate_missing_handling": {
                "duplicates": "dedupe by (entity, bucket_start); keep deterministic max end_time then first row",
                "missing_buckets": "leave absent; never interpolate",
                "nonfinite": "treat as missing",
                "missing_request": "resource sample ineligible for utilization",
            },
            "minimum_history": {
                "minimum_paired_finite_slots_for_refresh": 200,
                "slots_per_24h": 288,
                "feature_history_slots": 96,
                "minimum_total_observations_guidance": 2000,
            },
            "bootstrap_split": {
                "fraction": 0.30,
                "rule": "first 30% of entity timeline by nominal time, causal thresholds only from bootstrap",
            },
            "profile_eligibility": {
                "trailing_window": "(t-24h,t]",
                "min_paired_finite_slots": 200,
                "both_resources_required": True,
            },
            "evaluation_eligibility": {
                "grid": "phase-balanced-hourly-v1",
                "forward_window": "(t,t+24h]",
                "min_forward_paired_slots": 200,
            },
            "cohort_eligibility_exclusions": {
                "include_only_protocol_validity_codes": [
                    "insufficient_bootstrap_history",
                    "insufficient_exact_grid_feature_or_window_validity",
                    "insufficient_globally_verifiable_evaluation_origins",
                    "corrupt_or_nonfinite_source_data",
                    "protocol_invalid_timeline_or_schema",
                    "missing_positive_resource_request",
                    "insufficient_continuous_span_for_24h_windows",
                ],
                "forbidden_exclusion_basis": [
                    "method_performance",
                    "favorable_or_unfavorable_effect_size",
                    "materna_outcome_similarity",
                ],
            },
            "corpus_specific_changes_not_changing_rqs": [
                {
                    "change": "entity is Borg collection_id+instance_index instead of Materna VM",
                    "why_rq_unchanged": "RQs concern profile maintenance/cadence/cost, not VM branding",
                },
                {
                    "change": "utilization is request-normalized NCU/RAM instead of provisioned %",
                    "why_rq_unchanged": (
                        "Still a paired two-resource utilization series with identical "
                        "window/truth/accounting semantics; unit difference is declared"
                    ),
                },
                {
                    "change": "multi-cell export may be one cell first for cost control",
                    "why_rq_unchanged": "Cell choice is a corpus stratum, not a method change",
                },
            ],
        },
        "v4b_acquisition_gates": [
            "authorize_bigquery_project_and_export_budget",
            "outcome_blind_continuity_and_request_coverage_SQL",
            "pin_table_snapshot_time_and_export_hashes",
            "freeze_selected_cell_set_before_filtering_entities",
            "no_materna_outcome_use_in_filters",
        ],
        "execution_guards": {
            "download_full_dataset_in_v4a": False,
            "run_dynapm_pw_outcomes_in_v4a": False,
            "rank_by_expected_favorable_effects": False,
        },
    }


def validate_protocol(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = doc if doc is not None else protocol_document()
    if doc["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported replication protocol schema")
    if doc["disposition"] != DISPOSITION:
        raise ValueError("disposition mismatch")
    if doc["preferred_corpus_id"] != PREFERRED_CORPUS:
        raise ValueError("preferred corpus mismatch")
    if doc["materna_confirmatory_redesign"] is not False:
        raise ValueError("must not redesign Materna confirmation")
    if doc["second_corpus_outcome_access"] is not False:
        raise ValueError("must not access second-corpus outcomes in V4A")
    inherited = doc["inherited_from_v3_unchanged"]
    if inherited["methods"] != list(PRIMARY_METHODS):
        raise ValueError("methods must match V3 primary matrix")
    if inherited["study_framing"] != "estimation_first":
        raise ValueError("study framing must remain estimation_first")
    if inherited["statistics"]["bootstrap_repetitions"] != 10000:
        raise ValueError("bootstrap repetitions mismatch")
    if inherited["statistics"]["bootstrap_seed"] != 20251022:
        raise ValueError("bootstrap seed mismatch")
    adapt = doc["adaptation"]
    if adapt["nominal_cadence"]["target_seconds"] != 300:
        raise ValueError("nominal cadence must remain five minutes")
    if adapt["units_and_normalization"]["materna_percent_equivalence"] is not False:
        raise ValueError("must not claim Materna percent equivalence")
    return {
        "protocol_fingerprint": fingerprint(doc),
        "disposition": doc["disposition"],
        "preferred_corpus_id": doc["preferred_corpus_id"],
    }


def write_protocol_files(root: Path = REPO_ROOT) -> dict[str, str]:
    doc = protocol_document()
    json_path = root / "configs" / "google_clusterdata_2019_replication_protocol_v1.json"
    yaml_path = root / "configs" / "google_clusterdata_2019_replication_protocol_v1.yaml"
    json_path.write_text(canonical_json(doc) + "\n", encoding="utf-8")
    yaml_path.write_text(
        "# Frozen by V4A — authoritative twin is "
        "google_clusterdata_2019_replication_protocol_v1.json\n"
        + emit_yaml(doc),
        encoding="utf-8",
    )
    info = validate_protocol(doc)
    return {
        "protocol_fingerprint": info["protocol_fingerprint"],
        "config_json_sha256": file_sha256(json_path),
        "config_yaml_sha256": file_sha256(yaml_path),
        "disposition": info["disposition"],
        "preferred_corpus_id": info["preferred_corpus_id"],
    }


def frozen_hashes() -> dict[str, Any]:
    if not CONFIG_JSON.is_file():
        raise FileNotFoundError(CONFIG_JSON)
    doc = read_json(CONFIG_JSON)
    info = validate_protocol(doc)
    return {
        "protocol_fingerprint": info["protocol_fingerprint"],
        "config_json_sha256": file_sha256(CONFIG_JSON),
        "config_yaml_sha256": file_sha256(CONFIG_YAML),
        "disposition": info["disposition"],
        "preferred_corpus_id": info["preferred_corpus_id"],
        "gate": GATE,
    }
