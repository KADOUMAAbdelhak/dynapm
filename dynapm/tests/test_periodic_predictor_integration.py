def test_periodic_predictor_v2_runs():
    from dynapm.eval.runner_v2 import run_method_on_vm
    from dynapm.methods.baselines_v2 import PeriodicPredictorPolicyV2

    out = run_method_on_vm(
        "Materna-Trace-1",
        "501",
        lambda p, c, m, **k: PeriodicPredictorPolicyV2(p, c, m, period_hours=6, **k),
    )
    assert out["n_eval_points_verified"] > 10
    assert out["total_updates"] > 0
