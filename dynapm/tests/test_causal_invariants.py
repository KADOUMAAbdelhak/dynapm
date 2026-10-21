"""Causal regression tests use tiny forests and deterministic synthetic traces."""
import inspect

import numpy as np
import pandas as pd
import pytest

from dynapm.core.features import MAX_CONTEXT, build_features
from dynapm.core.predictor import VMPredictor, _causal_feature_row, forecast_at_origin
from dynapm.data.bootstrap import compute_split
from dynapm.eval.replay import prepare_vm_replay, iter_verified_snapshots
from dynapm.methods.factories import policy_factory
from dynapm.methods.baselines_v2 import PeriodicPredictorPolicyV2
from dynapm.methods.dynapm_v3 import DynAPMPolicyV3

CPU = "CPU usage [%]"
MEM = "Memory usage [%]"


@pytest.fixture
def small_predictors(synthetic_frame):
    boot, _, _ = compute_split(synthetic_frame)
    predictors = [VMPredictor(target=t, n_estimators=3, max_depth=3) for t in (CPU, MEM)]
    for p in predictors:
        p.fit(boot)
    return predictors


@pytest.mark.parametrize("target", [CPU, MEM])
def test_contemporaneous_target_does_not_change_features_or_prediction(target, synthetic_frame, small_predictors):
    origin = synthetic_frame.index[350]
    changed = synthetic_frame.copy()
    changed.loc[origin:, target] += 1e8
    before = build_features(synthetic_frame, target)
    after = build_features(changed, target)
    pd.testing.assert_frame_equal(before.loc[:origin], after.loc[:origin])
    predictor = small_predictors[(CPU, MEM).index(target)]
    a = predictor.predict_streaming(synthetic_frame)
    b = predictor.predict_streaming(changed)
    assert a.at[origin, "y_pred"] == b.at[origin, "y_pred"]
    assert b.at[origin, "residual"] - a.at[origin, "residual"] == pytest.approx(1e8)


@pytest.mark.parametrize("target", [CPU, MEM])
def test_recursive_forecast_future_invariance_and_horizon(target, synthetic_frame, small_predictors):
    t = synthetic_frame.index[350]
    changed = synthetic_frame.copy()
    changed.loc[changed.index > t, [CPU, MEM]] += 1e8
    predictor = small_predictors[(CPU, MEM).index(target)]
    before = forecast_at_origin(predictor, synthetic_frame[target], t)
    after = forecast_at_origin(predictor, changed[target], t)
    pd.testing.assert_series_equal(before, after, check_exact=True)
    assert len(before) == 288
    assert before.index[0] == t + pd.Timedelta(minutes=5)
    assert before.index[-1] == t + pd.Timedelta(hours=24)


def test_recursive_feature_row_matches_batch_features(synthetic_frame):
    """Training, one-step, and recursive inference use the same ordered features."""
    for target in (CPU, MEM):
        origin = synthetic_frame.index[350]
        batch = build_features(synthetic_frame, target).loc[origin].to_numpy()
        values = synthetic_frame.loc[:origin, target].to_numpy().copy()
        values[-1] = 1e12  # The target slot must be ignored.
        np.testing.assert_allclose(_causal_feature_row(values, origin), batch, rtol=1e-12, atol=1e-10)


def test_recursive_steps_append_predictions_not_actuals(synthetic_frame, small_predictors):
    p = small_predictors[0]
    history = synthetic_frame[CPU].iloc[:351]
    forecast = p.predict_causal_horizon(history, n_steps=3)
    values = history.to_numpy().copy()
    for t, expected in forecast.items():
        values = np.append(values, -1e12)  # Ignored target slot.
        yhat = p.model.predict(_causal_feature_row(values, t).reshape(1, -1))[0]
        assert yhat == expected
        values[-1] = yhat


@pytest.mark.parametrize("target,other", [(CPU, MEM), (MEM, CPU)])
def test_cpu_memory_models_and_features_are_independent(target, other, synthetic_frame, small_predictors):
    changed = synthetic_frame.copy()
    changed[other] += 1e8
    pd.testing.assert_frame_equal(build_features(synthetic_frame, target), build_features(changed, target))
    p = small_predictors[(CPU, MEM).index(target)]
    pd.testing.assert_frame_equal(p.predict_streaming(synthetic_frame), p.predict_streaming(changed))
    assert small_predictors[0].model is not small_predictors[1].model
    assert small_predictors[0].target != small_predictors[1].target


@pytest.mark.parametrize("method", ["periodic_predictor_6h_v2", "dynapm_v3_v2"])
def test_refresh_snapshot_ignores_future_observations(method, replay_repo, lag_predictor_factory):
    opts = dict(repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    first = prepare_vm_replay("TestTrace", "1", policy_factory(method), **opts)
    second = prepare_vm_replay("TestTrace", "1", policy_factory(method), **opts)
    t = first.observations.index[0] + pd.Timedelta(hours=6)
    for name in ["_cpu_obs_full", "_mem_obs_full"]:
        history = getattr(second.method, name).copy()
        history.loc[history.index > t] += 1e8
        setattr(second.method, name, history)
    obs = first.history.loc[:t]
    residual = dict(cpu_prediction=30.0, mem_prediction=50.0) if first.method.requires_residuals else {}
    for replay in [first, second]:
        replay.method.step(t, obs[CPU], obs[MEM], **residual)
        for p in [replay.method._cpu_predictor, replay.method._mem_predictor]:
            assert p.histories[-1].index.max() <= t
            assert len(p.histories[-1]) >= MAX_CONTEXT
    assert first.method.profile.dynamic == second.method.profile.dynamic
    assert first.method.refresh_log == second.method.refresh_log


def test_v3_residual_is_current_observation_minus_current_one_step_prediction(replay_repo, lag_predictor_factory):
    replay = prepare_vm_replay("TestTrace", "1", policy_factory("dynapm_v3_v2"),
                               repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    class Recorder:
        def __init__(self):
            self.values = []
        def update(self, value):
            self.values.append(value)
            return False
    cpu = replay.method._cpu_drift = Recorder()
    mem = replay.method._mem_drift = Recorder()
    list(iter_verified_snapshots(replay))
    np.testing.assert_allclose(cpu.values, replay.observations[CPU] - replay.predictions.cpu)
    np.testing.assert_allclose(mem.values, replay.observations[MEM] - replay.predictions.mem)


@pytest.mark.parametrize("cls", [PeriodicPredictorPolicyV2, DynAPMPolicyV3])
def test_no_full_prediction_stream_constructor(cls):
    params = inspect.signature(cls).parameters
    assert {"cpu_predictor", "mem_predictor", "cpu_obs_full", "mem_obs_full"} <= set(params)
    assert "cpu_pred_full" not in params and "mem_pred_full" not in params
    assert not any(p.kind == p.VAR_KEYWORD for p in params.values())


def test_short_history_returns_empty_forecast(synthetic_frame, small_predictors):
    with pytest.raises(ValueError, match="exact-grid history"):
        small_predictors[0].predict_causal_horizon(synthetic_frame[CPU].iloc[:20])


def test_features_reject_time_reversal(synthetic_frame):
    with pytest.raises(ValueError, match="increasing"):
        build_features(synthetic_frame.iloc[::-1], CPU)
