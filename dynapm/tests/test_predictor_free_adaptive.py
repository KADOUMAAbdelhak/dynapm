from dataclasses import replace

import pandas as pd
import pytest

from dynapm.experiments.pilot_design import default_config
from dynapm.experiments.predictor_free_adaptive import (
    ADAPTIVE_MATCHES,
    METHODS,
    run_vm,
    study_config,
    validate_config,
)
from dynapm.scripts.task26_predictor_free_adaptive import analyze


def test_predictor_free_config_is_frozen():
    config = study_config(default_config())
    validate_config(config)
    assert tuple(policy.method_id for policy in config.policies) == METHODS
    with pytest.raises(ValueError):
        validate_config(
            replace(
                config,
                policies=(
                    replace(config.policies[0], periodic_interval_hours=3),
                    *config.policies[1:],
                ),
            )
        )
    with pytest.raises(ValueError):
        validate_config(
            replace(config, policies=(
                *config.policies[:2],
                replace(config.policies[2], adwin_delta=0.01),
                *config.policies[3:],
            ))
        )


def test_full_predictor_free_execution_path_synthetic(replay_repo):
    rows, events, records, schedules, triggers, diagnostic = run_vm(
        (
            replay_repo,
            {"trace": "TestTrace", "vm_id": "1", "volatility_tier": "low"},
            study_config(default_config()),
        )
    )
    frame = pd.DataFrame(rows)
    assert len(frame) == len(METHODS)
    assert set(frame.method_id) == set(METHODS)
    assert diagnostic["predictor_fits"] == diagnostic["prediction_calls"] == 0
    assert diagnostic["equal_reactive_budget"]
    assert diagnostic["equal_adwin_budget"]
    indexed = frame.set_index("method_id")
    for adaptive, matched in ADAPTIVE_MATCHES.items():
        assert indexed.at[adaptive, "n_refresh_events"] == indexed.at[
            matched, "n_refresh_events"
        ]
    evaluations = pd.DataFrame(records)
    assert evaluations.groupby("eval_timestamp").method_id.nunique().eq(5).all()
    assert evaluations.groupby("eval_timestamp").observed_truth_sha256.nunique().eq(1).all()
    assert len(pd.DataFrame(events)) > 0
    schedule_frame = pd.DataFrame(schedules)
    if len(schedule_frame):
        assert set(schedule_frame.adaptive_method_id) <= set(ADAPTIVE_MATCHES)
    trigger_frame = pd.DataFrame(triggers)
    assert set(trigger_frame.method_id) <= set(ADAPTIVE_MATCHES)
    assert {"timestamp", "content_eligible", "disposition"} <= set(trigger_frame)


def test_analysis_pairs_each_adaptive_with_its_control_and_pw(replay_repo):
    rows, *_ = run_vm(
        (
            replay_repo,
            {"trace": "TestTrace", "vm_id": "1", "volatility_tier": "low"},
            study_config(default_config()),
        )
    )
    deltas, effects, tiers = analyze(pd.DataFrame(rows))
    assert len(deltas) == 4
    assert set(deltas.reference_type) == {"matched", "pw"}
    matched = deltas[deltas.reference_type == "matched"]
    assert {
        (row.adaptive_method_id, row.reference_method_id)
        for row in matched.itertuples()
    } == set(ADAPTIVE_MATCHES.items())
    assert len(effects) and len(tiers)
