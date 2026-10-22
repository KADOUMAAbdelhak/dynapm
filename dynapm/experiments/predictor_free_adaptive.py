"""Fixed predictor-free adaptive-trigger study over shared observation content."""
from dataclasses import replace
from functools import partial
import time

import numpy as np
import pandas as pd

from dynapm.core.accounting import require_accounting_metrics
from dynapm.core.provenance import PolicyConfig, canonical_json, fingerprint
from dynapm.core.temporal import (
    PeriodicGrid,
    forecast_targets,
    forward_observations,
    validity_table,
)
from dynapm.eval.replay import CPU_T, MEM_T, prepare_vm_inputs, replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.methods.budget_matched import (
    BUDGET_SCHEDULE_VERSION,
    budget_extra_times,
    periodic_commit_times,
)
from dynapm.methods.observation_timing import (
    ADWINObservationPolicy,
    BudgetMatchedWindowPolicy,
    CONTENT_VERSION,
    ReactiveWindowPolicy,
    WindowPeriodicPolicy,
    paired_content_window,
)

STUDY_VERSION = "predictor-free-adaptive-trigger-v1"
METHODS = (
    "pw_6h",
    "reactive",
    "adwin_observation",
    "budget_matched_reactive",
    "budget_matched_adwin",
)
ADAPTIVE_MATCHES = {
    "reactive": "budget_matched_reactive",
    "adwin_observation": "budget_matched_adwin",
}


def study_config(previous):
    return replace(
        previous,
        policies=tuple(
            PolicyConfig(
                method,
                periodic_interval_hours=6,
                observation_window_hours=24,
                adwin_delta=0.002,
            )
            for method in METHODS
        ),
        analysis={
            "study_version": STUDY_VERSION,
            "content": CONTENT_VERSION,
            "budget_schedule": BUDGET_SCHEDULE_VERSION,
            "cohort_size": 18,
            "eligibility": "200-of-288-paired-finite-observed-slots",
            "reactive_trigger": "existing-6h-class-change-50-of-72-paired-slots",
            "adwin_trigger": "direct-observed-cpu-or-memory-delta-0.002",
            "signal_handling": "periodic-precedence;consume-ineligible-or-coincident",
            "purpose": "pilot-descriptive-only",
            "meaningful_margin": "not-defined-no-retrospective-threshold",
            "decision": "fixed-three-way-architecture-disposition-no-confirmatory-inference",
        },
    )


def validate_config(config):
    if config != study_config(config):
        raise ValueError("exact frozen predictor-free matrix and analysis required")
    from dynapm.experiments.pilot_design import default_config

    old = default_config()
    fixed = (config.data, config.model, config.statistics, config.preprocessing)
    expected = (old.data, old.model, old.statistics, old.preprocessing)
    if canonical_json(fixed) != canonical_json(expected):
        raise ValueError("no data/model/ADWIN/statistical tuning allowed")


def factory_for(policy, extra_times=()):
    common = {"period_hours": policy.periodic_interval_hours}
    if policy.method_id == "pw_6h":
        return partial(WindowPeriodicPolicy, **common)
    if policy.method_id == "reactive":
        return partial(ReactiveWindowPolicy, **common)
    if policy.method_id == "adwin_observation":
        return partial(
            ADWINObservationPolicy, drift_delta=policy.adwin_delta, **common
        )
    if policy.method_id.startswith("budget_matched_"):
        return partial(BudgetMatchedWindowPolicy, extra_times=extra_times, **common)
    raise ValueError("unknown predictor-free timing policy")


def assert_counts(rows, schedules):
    by = {row["method_id"]: row for row in rows}
    assert by["pw_6h"]["n_refresh_events"] == by["pw_6h"]["n_periodic_refreshes"]
    for adaptive, matched in ADAPTIVE_MATCHES.items():
        trigger_counter = (
            "n_reactive_refreshes" if adaptive == "reactive" else "n_drift_refreshes"
        )
        adaptive_row, matched_row = by[adaptive], by[matched]
        assert adaptive_row["n_refresh_events"] == (
            adaptive_row["n_periodic_refreshes"] + adaptive_row[trigger_counter]
        )
        assert matched_row["n_refresh_events"] == (
            matched_row["n_periodic_refreshes"]
            + matched_row["n_budget_extra_refreshes"]
        )
        assert matched_row["n_refresh_events"] == adaptive_row["n_refresh_events"]
        assert matched_row["n_budget_extra_refreshes"] == adaptive_row[trigger_counter]
        assert adaptive_row["total_trigger_signals"] == (
            adaptive_row[trigger_counter]
            + adaptive_row["ineligible_trigger_signals"]
            + adaptive_row["periodic_coincident_trigger_signals"]
        )
    assert len({tuple(value) for value in schedules.values()}) == 1
    for row in rows:
        assert row["n_initialization_events"] == 1
        assert row["n_field_writes"] == 4 * row["n_refresh_events"]
    require_accounting_metrics(pd.DataFrame(rows))


def run_vm(task):
    repo, entity, config = task
    validate_config(config)
    started = time.perf_counter()
    trace, vm = entity["trace"], str(entity["vm_id"])
    inputs = prepare_vm_inputs(
        trace,
        vm,
        repo_root=repo,
        with_predictors=False,
        bootstrap_fraction=config.data.bootstrap_fraction,
        evaluation_period_hours=config.data.evaluation_cadence_seconds / 3600,
        minimum_ground_truth_slots=config.data.minimum_ground_truth_paired_slots,
    )
    if inputs.predictors is not None or inputs.predictions is not None:
        raise ValueError("predictor-free study constructed prediction state")
    threshold_sha = fingerprint(
        {"cpu": inputs.cpu_thresholds, "memory": inputs.mem_thresholds}
    )
    valid = validity_table(inputs.frame)
    observed_valid = valid.window24.reindex(inputs.observations.index).to_numpy()
    eligible = inputs.observations.index[observed_valid]
    periodic = periodic_commit_times(
        inputs.observations.index,
        inputs.info["bootstrap_end"],
        6,
        valid.window24,
    )
    independent_grid = PeriodicGrid(inputs.info["bootstrap_end"], 6)
    expected_periodic_schedule = []
    for timestamp in inputs.observations.index:
        nominal = independent_grid.pop_due(timestamp, bool(valid.window24.loc[timestamp]))
        if nominal is not None:
            expected_periodic_schedule.append((timestamp, nominal))
    rows, events, evaluations, extra_rows, signal_rows = [], [], [], [], []
    schedules, initials = {}, []
    common_index = None
    adaptive_counts = {}

    for policy in config.policies:
        extras = ()
        if policy.method_id.startswith("budget_matched_"):
            source = next(
                adaptive
                for adaptive, matched in ADAPTIVE_MATCHES.items()
                if matched == policy.method_id
            )
            count = adaptive_counts[source]
            extras = budget_extra_times(eligible, periodic, count)
            extra_rows.extend(
                {
                    "trace": trace,
                    "vm_id": vm,
                    "matched_method_id": policy.method_id,
                    "adaptive_method_id": source,
                    "timestamp": timestamp,
                    "k": count,
                    "candidate_count": len(eligible) - len(periodic),
                    "schedule_version": BUDGET_SCHEDULE_VERSION,
                }
                for timestamp in extras
            )

        replay = replay_from_inputs(inputs, factory_for(policy, extras))
        initial = replay.method.profile.dynamic
        initials.append(
            (
                initial.cpu_class,
                initial.memory_class,
                initial.predicted_cpu_p95_next_24h,
                initial.predicted_mem_p95_next_24h,
            )
        )
        hashes = {}
        original_commit = replay.method.accounting.commit

        def checked_commit(t, values, **kwargs):
            window = paired_content_window(
                inputs.frame[CPU_T], inputs.frame[MEM_T], t
            )
            expected = replay.method._forecast_values(window.cpu, window.memory)
            if len(window) < 200 or values != expected:
                raise ValueError("shared content/eligibility mismatch")
            numeric = [
                values["predicted_cpu_p95_next_24h"],
                values["predicted_mem_p95_next_24h"],
            ]
            if not np.isfinite(numeric).all():
                raise ValueError("nonfinite commit")
            hashes[pd.Timestamp(t)] = fingerprint(values)
            return original_commit(t, values, **kwargs)

        replay.method.accounting.commit = checked_commit
        result = evaluate_replay(replay, include_records=True)
        records = result.pop("evaluation_records")
        index = pd.DatetimeIndex(record["eval_timestamp"] for record in records)
        if common_index is None:
            common_index = index
        if not len(index) or not common_index.equals(index):
            raise ValueError("unequal evaluation grid")
        for record in records:
            t = record["eval_timestamp"]
            truth = inputs.ground_truth.loc[t]
            targets = forward_observations(inputs.frame, t)
            evaluations.append(
                {
                    "trace": trace,
                    "vm_id": vm,
                    "tier": entity["volatility_tier"],
                    "method_id": policy.method_id,
                    **record,
                    "thresholds_sha256": threshold_sha,
                    "ground_truth_cpu_class": truth.cpu_class,
                    "ground_truth_memory_class": truth.memory_class,
                    "ground_truth_cpu_p95": truth.p95_cpu_next_24h,
                    "ground_truth_memory_p95": truth.p95_mem_next_24h,
                    "target_grid_sha256": fingerprint(
                        [str(value) for value in forecast_targets(t)]
                    ),
                    "observed_truth_sha256": fingerprint(
                        targets.reset_index().astype(str).to_dict("records")
                    ),
                }
            )
        refresh_events = replay.method.accounting.refresh_events
        schedules[policy.method_id] = [
            (event.actual_commit_time, event.nominal_scheduled_time)
            for event in refresh_events
            if event.trigger.value == "periodic"
        ]
        assert pd.DatetimeIndex(
            event.actual_commit_time for event in refresh_events
        ).is_unique
        events.extend(
            {
                "trace": trace,
                "vm_id": vm,
                "method_id": policy.method_id,
                **event.as_record(),
                "content_sha256": hashes[event.actual_commit_time],
            }
            for event in refresh_events
        )
        signal_rows.extend(
            {
                "trace": trace,
                "vm_id": vm,
                "method_id": policy.method_id,
                **event,
            }
            for event in getattr(replay.method, "trigger_events", [])
        )
        row = {
            key: value
            for key, value in result.items()
            if key not in ("refresh_log", "initialization_log")
        }
        row.update(
            method_id=policy.method_id,
            tier=entity["volatility_tier"],
            policy_config_sha256=fingerprint(policy),
            thresholds_sha256=threshold_sha,
            cpu_p95_bias=float(np.mean([r["cpu_p95_bias"] for r in records])),
            mem_p95_bias=float(np.mean([r["mem_p95_bias"] for r in records])),
            profile_age_mean_hours=float(
                np.mean([r["profile_age_hours"] for r in records])
            ),
            profile_age_p95_hours=float(
                np.quantile([r["profile_age_hours"] for r in records], 0.95)
            ),
            total_trigger_signals=getattr(
                replay.method, "total_trigger_signals", 0
            ),
            cpu_trigger_signals=getattr(replay.method, "cpu_trigger_signals", 0),
            mem_trigger_signals=getattr(replay.method, "mem_trigger_signals", 0),
            ineligible_trigger_signals=getattr(
                replay.method, "ineligible_trigger_signals", 0
            ),
            periodic_coincident_trigger_signals=getattr(
                replay.method, "periodic_coincident_trigger_signals", 0
            ),
        )
        rows.append(row)
        if policy.method_id in ADAPTIVE_MATCHES:
            counter = (
                "n_reactive_refreshes"
                if policy.method_id == "reactive"
                else "n_drift_refreshes"
            )
            adaptive_counts[policy.method_id] = int(row[counter])

    assert len(set(initials)) == 1
    assert_counts(rows, schedules)
    assert schedules["pw_6h"] == expected_periodic_schedule
    assert [actual for actual, _ in expected_periodic_schedule] == list(periodic)
    record_frame = pd.DataFrame(evaluations)
    for _, group in record_frame.groupby("eval_timestamp"):
        assert len(group) == len(METHODS)
        for column in (
            "target_grid_sha256",
            "observed_truth_sha256",
            "ground_truth_cpu_class",
            "ground_truth_memory_class",
            "ground_truth_cpu_p95",
            "ground_truth_memory_p95",
        ):
            assert group[column].nunique() == 1
    pw_records = record_frame[record_frame.method_id == "pw_6h"]
    assert pw_records.profile_age_seconds.gt(0).any(), "periodic age-grid aliasing"
    for _, group in pd.DataFrame(events).groupby("actual_commit_time"):
        assert group.content_sha256.nunique() == 1
    numeric = record_frame[
        ["cpu_p95_abs_err", "mem_p95_abs_err", "cpu_p95_bias", "mem_p95_bias"]
    ].to_numpy()
    assert np.isfinite(numeric).all()
    diagnostics = {
        "trace": trace,
        "vm_id": vm,
        "completed": len(METHODS),
        "common_evaluation_points": len(common_index),
        "content_identical": True,
        "periodic_commits_identical": True,
        "equal_reactive_budget": True,
        "equal_adwin_budget": True,
        "collision_count": 0,
        "causal_numeric_failures": 0,
        "observed_steps": len(inputs.observations),
        "content_ineligible_slots": int(
            (~valid.window24.reindex(inputs.observations.index)).sum()
        ),
        "maximum_gap_seconds": float(
            inputs.frame.index.to_series().diff().dt.total_seconds().max()
        ),
        "predictor_fits": 0,
        "prediction_calls": 0,
        "recursive_forecast_calls": 0,
        "wall_seconds": time.perf_counter() - started,
    }
    print(canonical_json(diagnostics), flush=True)
    return rows, events, evaluations, extra_rows, signal_rows, diagnostics
