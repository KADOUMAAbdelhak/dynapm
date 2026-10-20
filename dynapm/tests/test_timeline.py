"""Deterministic scheduling and refresh/read/verify ordering, without training."""
from copy import deepcopy

import pandas as pd
import pytest

from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.core.temporal import PeriodicGrid, HORIZON
from dynapm.eval.replay import prepare_vm_replay, iter_verified_snapshots
from dynapm.methods.factories import policy_factory

METHODS = ["periodic_6h_v2", "periodic_predictor_6h_v2", "dynapm_v3_v2"]
ANCHOR = pd.Timestamp("2021-01-01 08:00")


@pytest.fixture
def make_policy(lag_predictor_factory):
    def make(method, stream_index, constant=False):
        boot_idx = pd.date_range(end=ANCHOR - pd.Timedelta(minutes=5), periods=96, freq="5min")
        boot = pd.Series(25.0, index=boot_idx)
        obs = pd.Series(25.0 if constant else range(len(stream_index)), index=stream_index, dtype=float)
        history = pd.concat([boot, obs])
        profile = ProfileInstance(StaticFields("1", "TestTrace", 2, 4.0,
            boot_idx[0], ANCHOR, len(history)), DynamicFields("idle", "idle", 0.0, 0.0), {})
        th = {"p20": 10, "p40": 30, "p60": 60, "p80": 90, "p95": 95}
        deps = dict(bootstrap_cpu_series=boot, bootstrap_mem_series=boot)
        if method != "periodic_6h_v2":
            deps.update(cpu_predictor=lag_predictor_factory("CPU usage [%]"),
                mem_predictor=lag_predictor_factory("Memory usage [%]"),
                cpu_obs_full=history, mem_obs_full=history.copy())
        return policy_factory(method)(profile, th, th, **deps), obs
    return make


def advance(policy, obs, t):
    kwargs = dict(cpu_prediction=0.0, mem_prediction=0.0) if policy.requires_residuals else {}
    policy.step(t, obs.loc[:t], obs.loc[:t], **kwargs)


@pytest.mark.parametrize("gap,expected", [
    (None, [(6, 6), (12, 12), (18, 18), (24, 24)]),
    ((6, 6), [(6, 6 + 5/60), (12, 12), (18, 18), (24, 24)]),
    ((6 - 5/60, 6 + 15/60), [(6, 6 + 20/60), (12, 12), (18, 18), (24, 24)]),
    ((6 - 5/60, 20 - 5/60), [(18, 20), (24, 24)]),
])
def test_pw_pp_v3_have_identical_nominal_grid_despite_gaps(make_policy, gap, expected):
    idx = pd.date_range(ANCHOR, ANCHOR + pd.Timedelta(hours=24), freq="5min")
    if gap:
        idx = idx[~((idx >= ANCHOR + pd.Timedelta(hours=gap[0])) &
                    (idx <= ANCHOR + pd.Timedelta(hours=gap[1])))]
    schedules = []
    for name in METHODS:
        policy, obs = make_policy(name, idx)
        assert policy.periodic_grid.anchor == ANCHOR
        for t in idx:
            advance(policy, obs, t)
        periodic = [x for x in policy.refresh_log if x["reason"] == "periodic"]
        actual = [(x["nominal_scheduled_time"], x["actual_commit_time"]) for x in periodic]
        expected_times = [(ANCHOR + pd.Timedelta(hours=n), ANCHOR + pd.Timedelta(hours=a)) for n, a in expected]
        assert actual == expected_times
        assert len({x["actual_commit_time"] for x in policy.refresh_log}) == len(policy.refresh_log)
        assert policy.periodic_grid.next_tick == ANCHOR + pd.Timedelta(hours=30)
        schedules.append(actual)
    assert schedules[0] == schedules[1] == schedules[2]


def test_drift_between_ticks_and_coincidence_do_not_move_grid(make_policy):
    idx = pd.date_range(ANCHOR, ANCHOR + pd.Timedelta(hours=12), freq="5min")
    policy, obs = make_policy("dynapm_v3_v2", idx)
    class Trigger:
        fire = False
        calls = 0
        def update(self, residual):
            self.calls += 1
            return self.fire
    cpu = policy._cpu_drift = Trigger()
    mem = policy._mem_drift = Trigger()
    for t in idx:
        cpu.fire = mem.fire = t in [ANCHOR + pd.Timedelta(hours=3), ANCHOR + pd.Timedelta(hours=6)]
        advance(policy, obs, t)
        if t == ANCHOR + pd.Timedelta(hours=3):
            assert policy.periodic_grid.next_tick == ANCHOR + pd.Timedelta(hours=6)
    assert cpu.calls == mem.calls == len(idx)
    assert [(r["actual_commit_time"], r["reason"]) for r in policy.refresh_log] == [
        (ANCHOR + pd.Timedelta(hours=3), "drift"),
        (ANCHOR + pd.Timedelta(hours=6), "periodic"),
        (ANCHOR + pd.Timedelta(hours=12), "periodic"),
    ]
    assert policy.refresh_log[0]["nominal_scheduled_time"] is None


@pytest.mark.parametrize("method", METHODS)
def test_refresh_event_is_recorded_even_when_values_do_not_change(make_policy, method):
    idx = pd.date_range(ANCHOR, ANCHOR + pd.Timedelta(hours=6), freq="5min")
    policy, obs = make_policy(method, idx, constant=True)
    for t in idx:
        advance(policy, obs, t)
    assert len(policy.refresh_log) == 1
    event = policy.refresh_log[0]
    assert event["nominal_scheduled_time"] == event["actual_commit_time"] == idx[-1]
    if method == "periodic_6h_v2":
        assert policy.update_log == []  # Field mutations and refresh events differ.


@pytest.mark.parametrize("period", [0, -6, float("nan")])
def test_grid_rejects_invalid_period(period):
    with pytest.raises(ValueError):
        PeriodicGrid(ANCHOR, period)


def test_grid_rejects_duplicate_or_reversed_observations():
    grid = PeriodicGrid(ANCHOR, 6)
    grid.pop_due(ANCHOR)
    with pytest.raises(ValueError, match="increase strictly"):
        grid.pop_due(ANCHOR)


def test_residual_drift_commit_snapshot_then_delayed_verification(replay_repo, lag_predictor_factory, monkeypatch):
    import dynapm.eval.replay as replay_module
    replay = prepare_vm_replay("TestTrace", "1", policy_factory("dynapm_v3_v2"),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    origin = replay.ground_truth.index[0]  # Also a nominal periodic tick.
    replay.observations = replay.observations.loc[origin:origin + HORIZON]
    order = []
    last_step = [None]
    policy = replay.method
    class Detector:
        def __init__(self, metric):
            self.metric = metric
            self.first = True
        def update(self, residual):
            if self.first:
                col = "CPU usage [%]" if self.metric == "cpu" else "Memory usage [%]"
                assert residual == pytest.approx(replay.observations.at[origin, col] - replay.predictions.at[origin, self.metric])
                order.append(self.metric + " residual/ADWIN")
                self.first = False
                return True  # Both detectors coincide with the periodic trigger.
            return False
    policy._cpu_drift = Detector("cpu")
    policy._mem_drift = Detector("mem")
    record = policy._record_refresh
    def record_commit(*args):
        record(*args)
        if args[0] == origin:
            order.append("commit")
    monkeypatch.setattr(policy, "_record_refresh", record_commit)
    def snapshot(value):
        order.append("snapshot")
        return deepcopy(value)
    monkeypatch.setattr(replay_module, "deepcopy", snapshot)
    step = policy.step
    def record_step(t, **kwargs):
        last_step[0] = t
        step(t=t, **kwargs)
    monkeypatch.setattr(policy, "step", record_step)
    truth = replay.ground_truth
    class GuardedTruth:
        index = truth.index
        @property
        def loc(self):
            assert last_step[0] >= origin + HORIZON
            order.append("attach truth")
            return truth.loc
    replay.ground_truth = GuardedTruth()
    records = list(iter_verified_snapshots(replay))
    assert order[:4] == ["cpu residual/ADWIN", "mem residual/ADWIN", "commit", "snapshot"]
    assert order[-1] == "attach truth"
    assert len(records) == 1 and last_step[0] == origin + HORIZON
    snap = records[0][1]
    assert snap.predicted_cpu_p95_next_24h == replay.observations.at[origin, "CPU usage [%]"]
    assert snap != policy.profile.dynamic  # Later commits did not mutate the copy.
    at_origin = [r for r in policy.refresh_log if r["actual_commit_time"] == origin]
    assert len(at_origin) == 1 and at_origin[0]["reason"] == "periodic"
    for p in [policy._cpu_predictor, policy._mem_predictor]:
        assert p.histories[0].index[-1] == origin


def test_verification_waits_for_next_observation_after_missing_endpoint(replay_repo, lag_predictor_factory):
    replay = prepare_vm_replay("TestTrace", "1", policy_factory("static_v2"),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    origin = replay.ground_truth.index[0]
    end = origin + HORIZON
    replay.observations = replay.observations.drop(end)
    records = list(iter_verified_snapshots(replay))
    assert len(records) == 1  # A later observation permits attachment after elapsed time.
    early = prepare_vm_replay("TestTrace", "1", policy_factory("static_v2"),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    early.observations = early.observations.loc[:end - pd.Timedelta(minutes=5)]
    assert list(iter_verified_snapshots(early)) == []
    assert early.snapshots_dropped_unverified == 1


def test_shared_anchor_survives_feature_warmup(replay_repo, lag_predictor_factory):
    schedules = []
    for name in METHODS:
        replay = prepare_vm_replay("TestTrace", "1", policy_factory(name),
            repo_root=replay_repo, predictor_factory=lag_predictor_factory)
        anchor = replay.method.periodic_grid.anchor
        first_observed = replay.observations.index[0]
        assert first_observed == anchor + pd.Timedelta(hours=8)
        list(iter_verified_snapshots(replay))
        periodic = [r for r in replay.method.refresh_log if r["reason"] == "periodic"]
        assert periodic[0]["nominal_scheduled_time"] == anchor + pd.Timedelta(hours=6)
        assert periodic[0]["actual_commit_time"] == first_observed
        schedules.append([(r["nominal_scheduled_time"], r["actual_commit_time"]) for r in periodic])
    assert schedules[0] == schedules[1] == schedules[2]


def test_replay_ignores_incompatible_cached_labels(replay_repo, lag_predictor_factory, monkeypatch):
    from dynapm.eval.runner_v2 import run_method_on_vm
    old = replay_repo / "dynapm/results/ground_truth/TestTrace__1.parquet"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"incompatible old boundary labels")
    def forbidden(*args, **kwargs):
        raise AssertionError("canonical replay must not load cached labels or residuals")
    monkeypatch.setattr(pd, "read_parquet", forbidden)
    out = run_method_on_vm("TestTrace", "1", policy_factory("static_v2"),
        repo_root=replay_repo, predictor_factory=lag_predictor_factory)
    assert out["n_eval_points_verified"] == 1
    assert out["causal_protocol"] == "causal-timeline-v2"
    assert old.read_bytes() == b"incompatible old boundary labels"
