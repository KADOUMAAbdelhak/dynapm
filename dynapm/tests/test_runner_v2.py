from __future__ import annotations

from dynapm.eval.runner_v2 import run_method_on_vm
from dynapm.methods.baselines_v2 import FullRewritePolicyV2, PeriodicPolicyV2, StaticPolicyV2


def test_static_v2_runs():
    out = run_method_on_vm("Materna-Trace-1", "501", lambda p, c, m, **k: StaticPolicyV2(p, c, m, **k))
    expected = {
        "trace",
        "vm_id",
        "cpu_class_accuracy",
        "memory_class_accuracy",
        "cpu_p95_mae",
        "mem_p95_mae",
        "n_cpu_class_updates",
        "n_memory_class_updates",
        "n_cpu_p95_updates",
        "n_mem_p95_updates",
        "total_updates",
        "n_eval_points_verified",
        "snapshots_dropped_unverified",
        "n_streaming_steps",
        "stream_days",
    }
    assert expected.issubset(set(out.keys()))
    assert out["total_updates"] == 0
    assert out["n_eval_points_verified"] > 10


def test_full_rewrite_v2_runs():
    out = run_method_on_vm("Materna-Trace-1", "501", lambda p, c, m, **k: FullRewritePolicyV2(p, c, m, **k))
    assert out["total_updates"] > 0
    assert out["n_eval_points_verified"] > 10


def test_periodic_v2_runs():
    out = run_method_on_vm(
        "Materna-Trace-1",
        "501",
        lambda p, c, m, **k: PeriodicPolicyV2(p, c, m, period_hours=6, **k),
    )
    expected_refreshes = out["stream_days"] * 4.0
    assert out["total_updates"] > 0
    assert out["total_updates"] <= expected_refreshes * 8.0
