"""Read-only raw input hashing and lightweight cohort characterization."""
from pathlib import Path
import csv

import pandas as pd
import numpy as np

from dynapm.core.features import LAGS, MAX_CONTEXT

from dynapm.core.provenance import (DatasetFile, DatasetProvenance, CohortEntity,
    CohortManifest, file_sha256, fingerprint, relative_path, utc_now)
from dynapm.data.loader import SCHEMA_COLUMNS
from dynapm.data.filter import vm_passes_min_timesteps

FILTER_RULE = "minimum-observed-rows-v1"
MATERNA_SCHEMA = fingerprint({"columns": SCHEMA_COLUMNS, "separator": ";",
    "decimal": ",", "timestamp_format": "%d.%m.%Y %H:%M:%S"})


def _input_files(root, traces):
    root = Path(root)
    for trace in sorted(traces):
        directory = root / relative_path(trace)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"missing/nonregular trace directory: {trace}")
        for p in sorted(directory.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_symlink() or not p.is_file():
                raise ValueError("raw manifest accepts regular files only")
            yield trace, p


def build_dataset_manifest(root, *, dataset_id, source_name, trace_names,
                           schema_identity, expected_cadence_seconds=300, selection="all-regular-files-v1"):
    """Root is an execution location and is deliberately absent from the manifest."""
    root = Path(root)
    if selection not in {"all-regular-files-v1", "materna-csv-and-trace-info-v1"}:
        raise ValueError("unsupported input selection rule")
    files, ancillary = [], []
    for trace, p in _input_files(root, trace_names):
        is_vm = p.suffix.lower() == ".csv"
        selected = selection == "all-regular-files-v1" or is_vm or p.name == "00-Trace-Info.txt"
        target = files if selected else ancillary
        target.append(DatasetFile(relative_path(p.relative_to(root)), p.stat().st_size,
            file_sha256(p), trace, p.stem if is_vm else None,
            "raw_entity" if is_vm else "trace_metadata" if selected else "ancillary_not_loaded"))
    if not files or not dataset_id or not schema_identity or expected_cadence_seconds <= 0:
        raise ValueError("nonempty identified dataset and positive cadence required")
    return DatasetProvenance(dataset_id, source_name, tuple(sorted(trace_names)),
        schema_identity, expected_cadence_seconds, tuple(files), utc_now(),
        selection=selection, ancillary_files=tuple(ancillary))


def materna_manifest(root):
    return build_dataset_manifest(root, dataset_id="materna", source_name="GWA-T-13 Materna",
        trace_names=tuple(f"Materna-Trace-{n}" for n in (1, 2, 3)), schema_identity=MATERNA_SCHEMA,
        selection="materna-csv-and-trace-info-v1")


def check_dataset(root, manifest):
    """Rehash inputs and inventory, never trust paths or mtimes as evidence."""
    current = build_dataset_manifest(root, dataset_id=manifest.dataset_id,
        source_name=manifest.source_name, trace_names=manifest.trace_names,
        schema_identity=manifest.schema_identity,
        expected_cadence_seconds=manifest.expected_cadence_seconds, selection=manifest.selection)
    if current.sha256 != manifest.sha256:
        raise ValueError("dataset_mismatch")


def materna_cohort(root, dataset, minimum_observations=2000):
    """Same row-count predicate as filter_corpus, without persisting kept_vms.json.

    Only timestamps are parsed; no features, training, labels or policy evaluation.
    Loader sorting makes min/max equivalent to the first/last loaded timestamps.
    """
    if dataset.schema_identity != MATERNA_SCHEMA or minimum_observations < 1:
        raise ValueError("Materna schema and positive observation threshold required")
    check_dataset(root, dataset)
    entities = []
    for f in dataset.files:
        if f.role != "raw_entity":
            continue
        p = Path(root) / relative_path(f.path)
        with p.open(newline="") as stream:
            header = next(csv.reader(stream, delimiter=";"))
        header = tuple(x.strip().strip('"') for x in header)
        if header != SCHEMA_COLUMNS:
            raise ValueError(f"raw schema mismatch: {f.path}")
        frame = pd.read_csv(p, sep=";", usecols=["Timestamp"], dtype=str)
        ts = pd.to_datetime(frame["Timestamp"], format="%d.%m.%Y %H:%M:%S", errors="raise")
        included = vm_passes_min_timesteps(frame, minimum_observations)
        ordered = np.sort(ts.to_numpy(dtype="datetime64[ns]").astype("int64"))
        def distribution(values):
            if not len(values):
                return None
            return {"min": float(values.min()), "median": float(np.median(values)),
                    "p95": float(np.quantile(values, .95)), "max": float(values.max())}
        steps = np.diff(ordered) / 1e9
        characterization = {"duplicate_timestamps": int((steps == 0).sum()),
            "steps_above_expected_cadence": int((steps > dataset.expected_cadence_seconds).sum()),
            "observed_step_seconds": distribution(steps),
            "lag_elapsed_seconds": {str(k): distribution((ordered[k:] - ordered[:-k]) / 1e9)
                for k in sorted(set((*LAGS, MAX_CONTEXT))) if len(ordered) > k}}

        entities.append(CohortEntity(f.trace, f.entity_id, included,
            None if included else "below_minimum_observations", len(frame),
            ts.min().isoformat() if len(ts) else None, ts.max().isoformat() if len(ts) else None, characterization))
    check_dataset(root, dataset)  # Fail if inputs changed during characterization.
    return CohortManifest(dataset.dataset_id, dataset.sha256, FILTER_RULE,
        {"minimum_observations": minimum_observations, "predicate": "row_count >= minimum_observations"},
        tuple(sorted(entities, key=lambda e: (e.trace, e.entity_id))), utc_now())
