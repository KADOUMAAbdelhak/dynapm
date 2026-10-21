"""Frozen pilot selection/matrix and input-only telemetry-gap characterization."""
from dataclasses import replace
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

from dynapm.core.provenance import (CohortEntity, CohortManifest, DataConfig, ModelConfig,
    PolicyConfig, StatisticsConfig, ExperimentConfigProvenance, fingerprint)
from dynapm.data.bootstrap import compute_split
from dynapm.methods.budget_matched import BUDGET_SCHEDULE_VERSION

SELECTION_VERSION = "dynapm-v2-pilot-selection-v1"
MATRIX_VERSION = "bounded-refresh-pilot-v1"
TRACES = tuple(f"Materna-Trace-{i}" for i in (1, 2, 3))
TIERS = ("low", "medium", "high")
GAPS = {"exact_5m": lambda d: d == 300, "gt_5m": lambda d: d > 300,
        "gt_10m": lambda d: d > 600, "gt_30m": lambda d: d > 1800,
        "gt_1h": lambda d: d > 3600}


def default_config():
    policies = [PolicyConfig(m) for m in ("static", "reactive", "full_rewrite")]
    policies += [PolicyConfig(f"{kind}_{hours}h", periodic_interval_hours=hours)
                 for kind in ("pw", "pp") for hours in (3, 6, 12)]
    policies += [PolicyConfig("v3", periodic_interval_hours=6, adwin_delta=.002),
                 PolicyConfig("budget_matched", periodic_interval_hours=6,
                              parameters={"schedule_version": BUDGET_SCHEDULE_VERSION,
                                          "budget_source": "paired_v3_drift_count_only"})]
    return ExperimentConfigProvenance(DataConfig("materna"), ModelConfig(), tuple(policies),
        StatisticsConfig(bootstrap_repetitions=0, test_specification={"inference": "none-pilot-descriptive-only"}),
        preprocessing={"selection_version": SELECTION_VERSION, "tiers": "pooled-bootstrap-cpu-std-tertiles-ddof0"},
        analysis={"matrix_version": MATRIX_VERSION, "purpose": "pilot", "cohort_size": 18,
                  "lookback_steps": 288, "gap_decision_rule": "any-retained-history-gap-over-1h-requires-preconfirmation-correction"})


def select_pilot(characterization):
    """Consumes input-only columns; added outcome columns cannot affect selection."""
    rows = characterization.loc[:, ["trace", "vm_id", "volatility", "observation_count",
                                     "first_timestamp", "last_timestamp"]].copy()
    if rows.duplicated(["trace", "vm_id"]).any() or not np.isfinite(rows.volatility).all():
        raise ValueError("invalid eligible selection pool")
    q1, q2 = rows.volatility.quantile([1/3, 2/3])
    rows["volatility_tier"] = np.where(rows.volatility <= q1, "low", np.where(rows.volatility <= q2, "medium", "high"))
    rows["selection_hash"] = [hashlib.sha256(f"{SELECTION_VERSION}|{t}|{v}".encode()).hexdigest()
                               for t, v in zip(rows.trace, rows.vm_id)]
    selected = []
    for trace in TRACES:
        for tier in TIERS:
            cell = rows[(rows.trace == trace) & (rows.volatility_tier == tier)].sort_values(["selection_hash", "vm_id"])
            if len(cell) < 2:
                raise ValueError(f"fewer than 2 eligible VMs: {trace}/{tier}")
            selected.append(cell.iloc[:2])
    out = pd.concat(selected).sort_values(["trace", "volatility_tier", "selection_hash"]).reset_index(drop=True)
    out["inclusion_reason"] = "DEVELOPMENT PILOT COHORT: first two input-only SHA ranks per trace/tier"
    return out, {"q1": float(q1), "q2": float(q2), "pool_sha256": fingerprint(rows.sort_values(["trace", "vm_id"]).to_dict("records"))}


def pilot_cohort_manifest(dataset, selected, tier_metadata, minimum_observations=2000):
    guard_cohort(selected)
    entities = tuple(CohortEntity(r.trace, str(r.vm_id), True, None, int(r.observation_count),
        r.first_timestamp, r.last_timestamp) for r in selected.sort_values(["trace", "vm_id"]).itertuples())
    return CohortManifest(dataset.dataset_id, dataset.sha256, SELECTION_VERSION,
        {"minimum_observations": minimum_observations, "development_pilot": True,
         "tier_metadata": tier_metadata, "selection_records": selected.to_dict("records"),
         "future_primary_confirmation": "retained VMs excluding these 18"}, entities,
        "deterministic-selection-no-wallclock")


def guard_cohort(selected):
    if len(selected) > 50 or len(selected) != 18 or selected.duplicated(["trace", "vm_id"]).any():
        raise ValueError("bounded pilot requires exactly 18 unique explicit VMs; maximum 50")
    counts = selected.groupby(["trace", "volatility_tier"]).size()
    if set(counts.index) != {(t, v) for t in TRACES for v in TIERS} or not counts.eq(2).all():
        raise ValueError("pilot must contain 2 VMs per trace/tier cell")


def gap_records(index, trace, vm_id, n_boot):
    index = pd.DatetimeIndex(index)
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("input timestamps must be unique and ordered")
    rows = []
    for phase, times in (("all", index), ("bootstrap", index[:n_boot]), ("streaming", index[n_boot:])):
        d = np.diff(times.as_unit("ns").asi8)/1e9
        row = {"trace": trace, "vm_id": str(vm_id), "phase": phase,
               "n_intervals": len(d), "max_gap_seconds": float(d.max()) if len(d) else 0.0}
        for key, predicate in GAPS.items():
            row[key] = int(predicate(d).sum())
        rows.append(row)
    return rows


def characterize_inputs(raw_root, dataset, config):
    """Read only timestamp/CPU columns; gaps depend on timestamps alone."""
    rows, gaps = [], []
    for entry in dataset.files:
        if entry.role != "raw_entity":
            continue
        frame = pd.read_csv(Path(raw_root)/entry.path, sep=";", usecols=["Timestamp", "CPU usage [%]"], dtype=str)
        if len(frame) < config.data.minimum_observations:
            continue
        frame.index = pd.to_datetime(frame.pop("Timestamp"), format="%d.%m.%Y %H:%M:%S", errors="raise")
        frame = frame.sort_index()
        frame["CPU usage [%]"] = pd.to_numeric(frame["CPU usage [%]"].str.replace(",", ".", regex=False), errors="raise")
        boot, _, info = compute_split(frame, config.data.bootstrap_fraction)
        rows.append({"trace": entry.trace, "vm_id": entry.entity_id,
            "volatility": float(boot["CPU usage [%]"].std(ddof=0)), "observation_count": len(frame),
            "first_timestamp": frame.index[0].isoformat(), "last_timestamp": frame.index[-1].isoformat()})
        gaps.extend(gap_records(frame.index, entry.trace, entry.entity_id, len(boot)))
    return pd.DataFrame(rows), pd.DataFrame(gaps)


def summarize_gaps(gaps):
    result = {}
    for phase, frame in gaps.groupby("phase"):
        n = int(frame.n_intervals.sum())
        result[phase] = {"total_intervals": n, "max_gap_seconds": float(frame.max_gap_seconds.max()),
            "n_vms": len(frame), **{key: {"intervals": int(frame[key].sum()),
                "fraction": float(frame[key].sum()/n) if n else 0.,
                "n_vms": int((frame[key] > 0).sum())} for key in GAPS}}
    needs_correction = result["all"]["gt_1h"]["n_vms"] > 0
    return {"phases": result, "decision": "REQUIRES PRE-V3 CORRECTION" if needs_correction else "ACCEPTABLE FOR V3",
        "decision_rule": "Observed-row history silently spans >1h telemetry gaps; fix explicit gap handling before confirmation, not causal leakage.",
        "phase_boundary": "all includes split-crossing interval; separate phases exclude it"}
