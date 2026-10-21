"""Periodic and ADWIN refreshes use the production causal dependency contract."""
from functools import partial

import pandas as pd

from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.methods.factories import policy_factory


def _policy(lag_predictor_factory, values, *, period_hours=6):
    idx = pd.date_range("2021-01-01", periods=288 + len(values), freq="5min")
    boot = pd.Series([25.0] * 288, index=idx[:288])
    cpu = pd.concat([boot, pd.Series(values, index=idx[288:])])
    mem = cpu.copy()
    profile = ProfileInstance(
        StaticFields("vm", "TestTrace", 2, 4.0, idx[0], idx[288], len(idx)),
        DynamicFields("idle", "idle", float("nan"), float("nan")), {},
    )
    thresholds = {"p20": 10.0, "p40": 30.0, "p60": 60.0, "p80": 90.0, "p95": 95.0}
    factory = partial(policy_factory("dynapm_v3_v2"), period_hours=period_hours)
    policy = factory(profile, thresholds, thresholds,
        bootstrap_cpu_series=boot, bootstrap_mem_series=boot,
        cpu_predictor=lag_predictor_factory("CPU usage [%]"),
        mem_predictor=lag_predictor_factory("Memory usage [%]"),
        cpu_obs_full=cpu, mem_obs_full=mem)
    return policy, cpu.loc[idx[288]:], mem.loc[idx[288]:]


def test_dynapm_v3_initializes(lag_predictor_factory):
    policy, _, _ = _policy(lag_predictor_factory, [25.0] * 200)
    assert policy.profile.dynamic.cpu_class == "low"
    assert policy.profile.dynamic.memory_class == "low"
    assert policy.profile.dynamic.predicted_cpu_p95_next_24h == 25.0
    assert policy.profile.dynamic.predicted_mem_p95_next_24h == 25.0


def test_dynapm_v3_periodic_only(lag_predictor_factory):
    policy, cpu, mem = _policy(lag_predictor_factory, [25.0] * 180, period_hours=1)
    for ts in cpu.index:
        policy.step(ts, policy._cpu_obs_full.loc[:ts], policy._mem_obs_full.loc[:ts], cpu_prediction=25.0, mem_prediction=25.0)
    assert policy.refresh_log
    assert {r["trigger"] for r in policy.refresh_log} == {"periodic"}
    refreshes = pd.DatetimeIndex(sorted({r["actual_commit_time"] for r in policy.refresh_log}))
    assert (refreshes[1:] - refreshes[:-1] == pd.Timedelta(hours=1)).all()


def test_dynapm_v3_drift_adds_extra_refreshes(lag_predictor_factory):
    policy, cpu, mem = _policy(lag_predictor_factory, [10.0] * 400 + [95.0] * 1100,
                               period_hours=5000)
    for ts in cpu.index:
        policy.step(ts, policy._cpu_obs_full.loc[:ts], policy._mem_obs_full.loc[:ts], cpu_prediction=10.0, mem_prediction=10.0)
    reasons = [r["trigger"] for r in policy.refresh_log]
    assert reasons.count("periodic") == 0  # Bootstrap initialization is not a scheduled tick.
    assert "drift" in reasons
    assert policy.profile.dynamic.predicted_cpu_p95_next_24h == 95.0
