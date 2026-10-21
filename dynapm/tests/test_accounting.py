"""Uniform event, write, change, serialization, and analysis accounting."""
from copy import deepcopy
import json

import pandas as pd
import pytest

from dynapm.core.accounting import (ACCOUNTING_SCHEMA, ACCOUNTING_METRICS,
    DYNAMIC_FIELDS, FIELD_CHANGE_METRICS, ProfileCommitter, RefreshEvent, Trigger, require_accounting_metrics)
from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.eval.runner_v2 import run_method_on_vm
from dynapm.eval.metrics import summarize_accounting
from dynapm.methods.factories import policy_factory, policy_class

ANCHOR = pd.Timestamp("2021-01-01 08:00")
METHODS = ["static_v2", "periodic_6h_v2", "reactive_v2", "full_rewrite_v2",
           "periodic_predictor_6h_v2", "dynapm_v3_v2"]


def profile():
    return ProfileInstance(StaticFields("1", "TestTrace", 2, 4.,
        ANCHOR - pd.Timedelta(hours=8), ANCHOR, 500),
        DynamicFields("idle", "idle", float("nan"), float("nan")), {})


def values(cpu_p95=25.):
    return dict(zip(DYNAMIC_FIELDS, ("low", "low", cpu_p95, 25.)))


@pytest.fixture
def make_policy(lag_predictor_factory):
    def make(method, index, predictor_value=25.):
        boot_idx = pd.date_range(end=ANCHOR-pd.Timedelta(minutes=5), periods=288, freq="5min")
        boot = pd.Series(25., index=boot_idx)
        history = pd.concat([boot, pd.Series(25., index=index)])
        deps = dict(bootstrap_cpu_series=boot, bootstrap_mem_series=boot)
        if policy_class(policy_factory(method)).requires_predictors:
            class ConstantHorizon(lag_predictor_factory):
                def predict_causal_horizon(self, history, n_steps=288):
                    result = super().predict_causal_horizon(history, n_steps)
                    return result * 0 + predictor_value
            deps.update(cpu_predictor=ConstantHorizon("CPU usage [%]"),
                mem_predictor=ConstantHorizon("Memory usage [%]"),
                cpu_obs_full=history, mem_obs_full=history.copy())
        policy = policy_factory(method)(profile(),
            {"p20": 10, "p40": 30, "p60": 60, "p80": 90, "p95": 95},
            {"p20": 10, "p40": 30, "p60": 60, "p80": 90, "p95": 95}, **deps)
        policy.test_history = history
        return policy
    return make


def step(policy, t, cpu=25., mem=25.):
    kwargs = dict(cpu_prediction=25., mem_prediction=25.) if policy.requires_residuals else {}
    window = policy.test_history.loc[:t].copy()
    window.iloc[-1] = cpu
    memory = policy.test_history.loc[:t].copy()*0+25.
    memory.iloc[-1] = mem
    policy.step(t, window, memory, **kwargs)


def test_static_initialization_is_separate(make_policy):
    idx = pd.date_range(ANCHOR, periods=20, freq="5min")
    policy = make_policy("static_v2", idx)
    for t in idx:
        step(policy, t)
    m = policy.accounting_metrics()
    assert m["n_initialization_events"] == 1
    assert len(policy.accounting.initialization_events[0].fields_written) == 4
    assert m["n_refresh_events"] == m["n_field_writes"] == m["n_field_value_changes"] == 0
    assert all(m[k] == 0 for k in ACCOUNTING_METRICS if k != "n_initialization_events")


@pytest.mark.parametrize("timeline", ["complete", "missing_tick", "long_gap"])
def test_pw_pp_counts_are_equal_even_with_different_content(make_policy, timeline):
    idx = pd.date_range(ANCHOR, ANCHOR + pd.Timedelta(hours=24), freq="5min")
    if timeline == "missing_tick":
        idx = idx[idx != ANCHOR + pd.Timedelta(hours=6)]
    if timeline == "long_gap":
        idx = pd.DatetimeIndex([ANCHOR, ANCHOR+pd.Timedelta(hours=20), ANCHOR+pd.Timedelta(hours=24)])
    pw = make_policy("periodic_6h_v2", idx)
    pp = make_policy("periodic_predictor_6h_v2", idx, predictor_value=95.)
    for t in idx:
        step(pw, t)
        step(pp, t)
    a, b = pw.accounting_metrics(), pp.accounting_metrics()
    expected = 0 if timeline == "long_gap" else 3 if timeline == "missing_tick" else 4
    for metric in ["n_refresh_events", "n_periodic_refreshes", "periodic_refresh_events_committed"]:
        assert a[metric] == b[metric] == expected
    assert a["n_field_writes"] == b["n_field_writes"] == 4 * expected
    assert a["nominal_periodic_ticks_due"] == b["nominal_periodic_ticks_due"] == 4
    assert a["n_field_value_changes"] == 0
    assert b["n_field_value_changes"] > 0 if expected else b["n_field_value_changes"] == 0
    assert [(e.actual_commit_time, e.nominal_scheduled_time) for e in pw.accounting.refresh_events] == [
        (e.actual_commit_time, e.nominal_scheduled_time) for e in pp.accounting.refresh_events]


def test_long_gap_counts_due_ticks_without_fabricating_commits(make_policy):
    idx = pd.DatetimeIndex([ANCHOR, ANCHOR+pd.Timedelta(hours=20)])
    p = make_policy("periodic_predictor_6h_v2", idx)
    for t in idx:
        step(p, t)
    m = p.accounting_metrics()
    assert m["nominal_periodic_ticks_due"] == 3
    assert m["periodic_refresh_events_committed"] == m["n_refresh_events"] == 0
    assert p.periodic_grid.pending_tick == ANCHOR+pd.Timedelta(hours=18)
    assert p.periodic_grid.next_tick == ANCHOR+pd.Timedelta(hours=24)


@pytest.mark.parametrize("drift_hours", [[], [3], [6], [3, 6]])
def test_v3_trigger_decomposition_and_precedence(make_policy, drift_hours):
    idx = pd.date_range(ANCHOR, ANCHOR+pd.Timedelta(hours=12), freq="5min")
    p = make_policy("dynapm_v3_v2", idx)
    class Detector:
        fire = False
        calls = 0
        def update(self, value):
            self.calls += 1
            return self.fire
    cpu = p._cpu_drift = Detector()
    mem = p._mem_drift = Detector()
    for t in idx:
        cpu.fire = mem.fire = t in [ANCHOR+pd.Timedelta(hours=h) for h in drift_hours]
        step(p, t)
    m = p.accounting_metrics()
    assert m["n_periodic_refreshes"] == 2
    assert m["n_drift_refreshes"] == int(3 in drift_hours)
    assert m["n_refresh_events"] == m["n_periodic_refreshes"] + m["n_drift_refreshes"]
    assert m["n_field_writes"] == 4 * m["n_refresh_events"]
    assert m["n_field_value_changes"] == 0  # Identical content still commits.
    assert cpu.calls == mem.calls == len(idx)
    at_six = [e for e in p.accounting.refresh_events if e.actual_commit_time == ANCHOR+pd.Timedelta(hours=6)]
    assert len(at_six) == 1 and at_six[0].trigger == Trigger.PERIODIC


def test_reactive_counts_triggered_commits_not_field_rows(make_policy):
    idx = pd.date_range(ANCHOR, periods=5, freq="6h")
    p = make_policy("reactive_v2", idx)
    step(p, idx[0])
    step(p, idx[1], cpu=27.)  # Different p95 but same class: no trigger.
    assert p.accounting_metrics()["n_refresh_events"] == 0
    p.test_history = pd.Series(71., index=pd.date_range(ANCHOR-pd.Timedelta(days=1), idx[-1], freq="5min"))
    step(p, idx[2], cpu=71.)
    step(p, idx[3], cpu=75.)  # Again same class: no trigger or write.
    p.test_history.loc[idx[3]:idx[4]] = 5.
    step(p, idx[4], cpu=5.)
    m = p.accounting_metrics()
    assert m["n_refresh_events"] == m["n_reactive_refreshes"] == 2
    assert m["n_field_writes"] == 8 and m["n_field_value_changes"] == 4


def test_full_rewrite_counts_every_observation_even_unchanged(make_policy):
    idx = pd.date_range(ANCHOR, periods=10, freq="5min")
    p = make_policy("full_rewrite_v2", idx)
    for t in idx:
        step(p, t)
    m = p.accounting_metrics()
    assert m["n_initialization_events"] == 1
    assert m["n_full_rewrite_refreshes"] == m["n_refresh_events"] == len(idx)
    assert m["n_field_writes"] == 4 * len(idx) and m["n_field_value_changes"] == 0
    assert set(p.profile.last_updated.values()) == {idx[-1]}


def test_one_commit_four_writes_one_change_and_duplicate_is_atomic():
    p = profile()
    writer = ProfileCommitter(p, [Trigger.PERIODIC])
    writer.initialize(ANCHOR, values())
    t = ANCHOR+pd.Timedelta(hours=6)
    writer.commit(t, values(cpu_p95=26.), trigger=Trigger.PERIODIC, nominal_scheduled_time=t)
    m = writer.counters(nominal_ticks_due=1)
    assert (m["n_refresh_events"], m["n_field_writes"], m["n_field_value_changes"]) == (1, 4, 1)
    assert writer.refresh_events[0].fields_changed == ("predicted_cpu_p95_next_24h",)
    before = deepcopy(p)
    with pytest.raises(ValueError, match="at most one"):
        writer.commit(t, values(cpu_p95=99.), trigger=Trigger.PERIODIC, nominal_scheduled_time=t)
    assert p == before and len(writer.refresh_events) == 1
    with pytest.raises(ValueError, match="only once"):
        writer.initialize(t, values())


def test_nan_to_nan_write_is_not_a_value_change():
    p = profile()
    writer = ProfileCommitter(p, [Trigger.FULL_REWRITE])
    v = values(float("nan"))
    writer.initialize(ANCHOR, v)
    writer.commit(ANCHOR+pd.Timedelta(minutes=5), v, trigger=Trigger.FULL_REWRITE)
    assert writer.counters()["n_field_writes"] == 4
    assert writer.counters()["n_field_value_changes"] == 0


@pytest.mark.parametrize("trigger,nominal", [("invalid", None), ("periodic", None), ("drift", ANCHOR)])
def test_event_rejects_ambiguous_triggers(trigger, nominal):
    with pytest.raises(ValueError):
        RefreshEvent(ANCHOR, trigger, nominal, DYNAMIC_FIELDS, ())


@pytest.mark.parametrize("method", METHODS)
def test_serialized_result_has_canonical_accounting(method, replay_repo, lag_predictor_factory):
    out = run_method_on_vm("TestTrace", "1", policy_factory(method),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    restored = json.loads(json.dumps(out))  # No timestamp-specific encoder required.
    assert restored["accounting_schema"] == ACCOUNTING_SCHEMA
    assert "total_updates" not in restored and "update_log" not in restored
    assert restored["n_initialization_events"] == len(restored["initialization_log"]) == 1
    assert restored["n_refresh_events"] == len(restored["refresh_log"])
    assert restored["n_field_writes"] == 4 * restored["n_refresh_events"]
    assert sum(restored[k] for k in FIELD_CHANGE_METRICS) == restored["n_field_value_changes"]
    assert all(isinstance(restored[k], int) for k in ACCOUNTING_METRICS)
    if method == "full_rewrite_v2":
        assert restored["n_full_rewrite_refreshes"] == restored["n_streaming_steps"]
    counts_only = {k: v for k, v in restored.items() if k not in ["refresh_log", "initialization_log"]}
    frame = pd.DataFrame([{**counts_only, "method": method}])
    require_accounting_metrics(frame)
    stats = summarize_accounting(frame).iloc[0]
    for k in ACCOUNTING_METRICS:
        assert stats["mean_"+k] == restored[k]


def test_tables_read_counters_without_logs_or_overrides(replay_repo, lag_predictor_factory, monkeypatch):
    from dynapm.scripts import task18_paper_packaging as tables
    rows = []
    for method in METHODS:
        out = run_method_on_vm("TestTrace", "1", policy_factory(method),
            repo_root=replay_repo, predictor_factory=lag_predictor_factory)
        rows.append({k: v for k, v in dict(out, method=method, run_status="ok").items()
                     if k not in ["refresh_log", "initialization_log"]})
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(tables, "method_metrics_table", lambda *args: pd.DataFrame(columns=["method", "mean_cpu_under_rate"]))
    table = tables.build_table1(frame, pd.DataFrame()).set_index("method")
    for row in rows:
        for k in ACCOUNTING_METRICS:
            assert table.at[row["method"], "mean_"+k] == row[k]


def test_legacy_counts_and_inconsistent_decomposition_are_rejected(replay_repo, lag_predictor_factory):
    out = run_method_on_vm("TestTrace", "1", policy_factory("static_v2"),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    with pytest.raises(ValueError, match="schema"):
        require_accounting_metrics(pd.DataFrame([{"total_updates": 100}]))
    broken = dict(out, method="static_v2", n_refresh_events=1, n_field_writes=4,
                  n_periodic_refreshes=1, periodic_refresh_events_committed=1,
                  nominal_periodic_ticks_due=1)
    with pytest.raises(ValueError, match="decomposition"):
        require_accounting_metrics(pd.DataFrame([broken]))
