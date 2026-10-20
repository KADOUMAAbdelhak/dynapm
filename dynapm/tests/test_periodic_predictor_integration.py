"""Periodic-Predictor replay is small, causal, and independent of residual caches."""
from dynapm.eval.runner_v2 import run_method_on_vm
from dynapm.methods.factories import policy_factory


def test_periodic_predictor_v2_runs(replay_repo, lag_predictor_factory, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Periodic-Predictor must not consume a one-step prediction stream")
    monkeypatch.setattr(lag_predictor_factory, "predict_streaming", forbidden)
    out = run_method_on_vm("TestTrace", "1", policy_factory("periodic_predictor_6h_v2"),
                          repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    assert out["n_eval_points_verified"] == 1
    assert out["total_updates"] > 0
    assert all(len(h) >= 96 for p in lag_predictor_factory.instances for h in p.histories)
