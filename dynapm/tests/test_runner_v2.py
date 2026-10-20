"""Bounded single-VM replay through the production policy factories."""
import pytest

from dynapm.eval.runner_v2 import run_method_on_vm
from dynapm.eval.provisioning import collect_verified_p95_pairs
from dynapm.methods.factories import policy_factory, policy_class
from dynapm.eval.replay import prepare_vm_replay

METHODS = ["static_v2", "periodic_6h_v2", "reactive_v2", "full_rewrite_v2",
           "periodic_predictor_6h_v2", "dynapm_v3_v2"]


@pytest.mark.parametrize("method", METHODS)
def test_evaluation_and_provisioning_share_construction(method, replay_repo, lag_predictor_factory):
    factory = policy_factory(method)
    opts = dict(repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    out = run_method_on_vm("TestTrace", "1", factory, **opts)
    pairs = collect_verified_p95_pairs("TestTrace", "1", factory, **opts)
    assert out["n_eval_points_verified"] == len(pairs) == 1
    assert out["snapshots_dropped_unverified"] == 0
    assert out["n_streaming_steps"] == 408
    assert out["n_refresh_events"] == len(out["refresh_log"])
    assert out["n_periodic_refreshes"] + out["n_drift_refreshes"] <= out["n_refresh_events"]
    if method == "static_v2":
        assert out["total_updates"] == 0
    else:
        assert out["total_updates"] > 0
    assert out["cpu_p95_mae"] == pytest.approx(
        (pairs.snapshot_cpu_p95 - pairs.gt_cpu_p95).abs().mean())
    assert out["mem_p95_mae"] == pytest.approx(
        (pairs.snapshot_mem_p95 - pairs.gt_mem_p95).abs().mean())
    predictors = lag_predictor_factory.instances
    if policy_class(factory).requires_predictors:
        assert len(predictors) == 4  # Two targets, once per independent replay.
        assert all(len(p.fit_index) == 216 for p in predictors)
        assert all(p.fit_index[-1] < pairs.eval_timestamp.iloc[0] for p in predictors)
        assert predictors[0].target != predictors[1].target
    else:
        assert predictors == []  # No predictor construction, fitting, or residual files.


def test_observation_policy_never_constructs_predictors(replay_repo):
    def forbidden(**kwargs):
        raise AssertionError("observation policy requested a predictor")
    for name in METHODS[:4]:
        run_method_on_vm("TestTrace", "1", policy_factory(name),
                         repo_root=replay_repo, predictor_factory=forbidden)


def test_opaque_factory_rejected_before_io():
    with pytest.raises(TypeError, match="policy class"):
        prepare_vm_replay("unused", "unused", lambda *a, **k: None)


def test_all_script_factories_share_contract():
    from dynapm.scripts.task15_full_corpus import FACTORIES as evaluation
    from dynapm.scripts.task17b_provisioning import _factory
    from dynapm.scripts.task18b_corpus_churn_rerun import FACTORIES as events
    for name in METHODS:
        cls = policy_class(policy_factory(name))
        assert policy_class(evaluation[name]) is cls
        assert policy_class(_factory(name)) is cls
        if name in events:
            assert policy_class(events[name]) is cls


@pytest.mark.parametrize("script", ["task15_full_corpus", "task18b_corpus_churn_rerun"])
def test_script_cache_rejects_unversioned_measurements(script, replay_repo, lag_predictor_factory, monkeypatch):
    import importlib
    import json
    from dynapm.eval.replay import CAUSAL_PROTOCOL
    module = importlib.import_module("dynapm.scripts." + script)
    method = "periodic_predictor_6h_v2"
    fresh = run_method_on_vm("TestTrace", "1", policy_factory(method),
                            repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    out_dir = replay_repo / "outputs"
    out_dir.mkdir()
    output = out_dir / f"{method}__TestTrace__1.json"
    old = {k: v for k, v in fresh.items() if k != "causal_protocol"}
    output.write_text(json.dumps(old, default=str))
    if script == "task18b_corpus_churn_rerun":
        assert module.row_from_json(output) is None
    monkeypatch.setattr(module, "_precheck_vm", lambda *args: None)
    calls = []
    def run(*args):
        calls.append(args)
        return fresh
    monkeypatch.setattr(module, "run_method_on_vm", run)
    if script == "task15_full_corpus":
        invoke = lambda: module._run_one(method, "TestTrace", "1", "low", out_dir)
    else:
        monkeypatch.setattr(module, "OUT_JSON", out_dir)
        invoke = lambda: module._run_one(method, "TestTrace", "1")
    invoke()
    assert len(calls) == 1
    assert json.loads(output.read_text())["causal_protocol"] == CAUSAL_PROTOCOL
    if script == "task18b_corpus_churn_rerun":
        assert module.row_from_json(output)["causal_protocol"] == CAUSAL_PROTOCOL
    invoke()
    assert len(calls) == 1  # A matching causal generation can be reused.


@pytest.mark.parametrize("protocol", [None, "causal-policy-v1", "causal-timeline-v2"])
def test_table_protocol_guard(protocol):
    import pandas as pd
    from dynapm.eval.replay import require_causal_protocol, CAUSAL_PROTOCOL
    frame = pd.DataFrame({"value": [1.0]})
    if protocol is not None:
        frame["causal_protocol"] = protocol
    if protocol == CAUSAL_PROTOCOL:
        require_causal_protocol(frame)
    else:
        with pytest.raises(ValueError, match="fresh experimental generation"):
            require_causal_protocol(frame)


@pytest.mark.parametrize("method", ["periodic_predictor_6h_v2", "dynapm_v3_v2"])
def test_small_real_forest_policy_path(method, replay_repo):
    """Join real predictor fit/inference to policy replay on 720 synthetic rows."""
    from functools import partial
    from dynapm.core.predictor import VMPredictor
    factory = partial(policy_factory(method), period_hours=30.0)
    out = run_method_on_vm("TestTrace", "1", factory, repo_root=replay_repo,
        predictor_factory=partial(VMPredictor, n_estimators=3, max_depth=3))
    assert out["n_eval_points_verified"] == 1
    assert out["total_updates"] > 0
    assert out["n_streaming_steps"] == 408


def test_legacy_runner_is_causal_compatibility_import():
    from dynapm.eval.runner import run_method_on_vm as legacy
    assert legacy is run_method_on_vm
