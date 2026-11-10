"""Synthetic clocks/OS fixtures only. No physical qualification or live workloads."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dynapm.system_validation import uuid_host_observer as observer
from dynapm.system_validation import v8_host_identity as identity
from dynapm.system_validation.host_power import ENDURANCE_SECONDS, PowerGuardError
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.tests.test_host_power import Host, CONTEXT

FIXTURE = json.loads((Path(__file__).parent/'fixtures/host_boot_calendar_boundary.json').read_text())
UUID = FIXTURE['initial']['boot_uuid']
OTHER = '00000000-0000-0000-0000-000000000001'


class BootHost(Host):
    def __init__(self):
        super().__init__()
        self.uuid = UUID
        self.timeval = FIXTURE['initial']['timeval_raw']
        self.calendar_reads = None

    def read(self, args):
        if args[-1] == 'kern.bootsessionuuid':
            return self.uuid+'\n'
        if args[-1] == 'kern.boottime':
            return next(self.calendar_reads) if self.calendar_reads is not None else self.timeval
        return super().read(args)


def guard(tmp_path, host):
    return identity.UUIDPowerGuard(tmp_path, CONTEXT, read=host.read, spawn=host.spawn,
        platform='darwin', background=False, startup_timeout=0)


def raw_time(ns):
    sec, part = divmod(ns, 10**9)
    return f'{{ sec = {sec}, usec = {part//1000} }}'


def test_recorded_calendar_boundary_is_not_a_reboot(tmp_path):
    host = BootHost()
    with guard(tmp_path, host) as g:
        host.timeval = FIXTURE['before_boundary']['timeval_raw']
        g.checkpoint(force_power=True)
        host.timeval = FIXTURE['after_boundary']['timeval_raw']
        g.checkpoint(force_power=True)
    rows = [json.loads(l) for l in g.log.read_text().splitlines()]
    assert {r['power']['boot_identity_checkpoint']['boot_epoch_seconds'] for r in rows} == {1794336848, 1794336849}
    assert {r['power']['boot_identity_checkpoint']['boot_uuid'] for r in rows} == {UUID}
    assert g.failure is None and g.state['release_confirmed']
    assert g.state['boot_timeval_anchor_ns'] == FIXTURE['initial']['boot_timeval_ns']


def test_boundary_between_two_os_reads_uses_existing_bound(tmp_path):
    host = BootHost()
    with guard(tmp_path, host) as g:
        host.calendar_reads = iter([FIXTURE['before_boundary']['timeval_raw'], FIXTURE['after_boundary']['timeval_raw']])
        snapshot = g._snapshot()
        assert snapshot['boot_identity_checkpoint'] == FIXTURE['after_boundary']
        # The separately sampled coarse value remains diagnostic metadata.
        assert snapshot['boot_epoch_seconds'] == 1794336848
        host.calendar_reads = None


def test_uuid_change_rejects_on_next_checkpoint_without_waiting_for_power_poll(tmp_path):
    host = BootHost()
    with pytest.raises(PowerGuardError, match='host_boot_uuid_mismatch'):
        with guard(tmp_path, host) as g:
            assert g.last_power is not None
            host.uuid = OTHER
            g.checkpoint()  # no force_power; less than 30 seconds since prior power read
    assert g.state['release_confirmed'] and g.failure['invariant'] == 'host_boot_uuid_mismatch'


@pytest.mark.parametrize('delta, passes', [(MAX_CLOCK_DELTA_NS, True), (MAX_CLOCK_DELTA_NS+1000, False)])
def test_same_uuid_calendar_bound_is_exactly_existing_two_seconds(tmp_path, delta, passes):
    host = BootHost()
    def body():
        with guard(tmp_path, host) as g:
            host.timeval = raw_time(FIXTURE['initial']['boot_timeval_ns']+delta)
            g.checkpoint()
    if passes:
        body()
    else:
        with pytest.raises(PowerGuardError, match='material_boot_calendar_discrepancy'):
            body()


@pytest.mark.parametrize('field,value,reason', [
    ('ac',False,'mains_power_lost'), ('lid','Yes','lid_closed'),
    ('missing',True,'owned_power_assertion_missing'),
])
def test_uuid_observer_preserves_strict_power_lid_assertion_gates(tmp_path, field, value, reason):
    host = BootHost()
    with pytest.raises(PowerGuardError, match=reason):
        with guard(tmp_path, host) as g:
            setattr(host, field, value)
            g.checkpoint(force_power=True)
    assert g.state['release_confirmed']


@pytest.mark.parametrize('change', ['wall_jump', 'heartbeat_gap'])
def test_uuid_observer_retains_original_host_clock_and_gap_limits(tmp_path, change):
    host = BootHost()
    expected = 'clock_discontinuity' if change == 'wall_jump' else 'heartbeat_gap'
    with pytest.raises(PowerGuardError, match=expected):
        with guard(tmp_path, host) as g:
            wall, mono = g.previous
            if change == 'wall_jump':
                g.checkpoint(wall_ns=wall+3*10**9, mono_ns=mono)
            else:
                g.checkpoint(wall_ns=wall+31*10**9, mono_ns=mono+31*10**9)
    assert g.state['release_confirmed']


def history():
    anchor = FIXTURE['initial']['boot_timeval_ns']
    summary = dict(schema_version=identity.UUID_ENDURANCE_SCHEMA, boot_uuid=UUID, boot_timeval_anchor_ns=anchor)
    state = dict(boot_uuid_anchor=UUID, boot_timeval_anchor_ns=anchor)
    points = []
    for second in range(0, ENDURANCE_SECONDS+1, 5):
        boot = FIXTURE['initial'] if second < 7400 else FIXTURE['after_boundary']
        points.append(dict(kind='CHECKPOINT', wall_ns=10**18+second*10**9, monotonic_ns=second*10**9,
            power=dict(boot_epoch_seconds=boot['boot_epoch_seconds'],boot_uuid=UUID,
                boot_identity_checkpoint=deepcopy(boot),ac_power=True,lid_open=True,
                external_power_deficit_observed=False,authorized_external_power_deficit=False)))
    return summary, state, points


def test_sealed_history_validation_accepts_variable_calendar_seconds_with_exact_uuid():
    args = history()
    assert len({p['power']['boot_epoch_seconds'] for p in args[2]}) == 2
    result = identity.endurance_boot_metadata(*args)
    assert result['original_uuid_recorded'] and result['boot_uuid'] == UUID
    assert result['boot_timeval_anchor_ns'] == FIXTURE['initial']['boot_timeval_ns']


@pytest.mark.parametrize('broken', ['uuid','raw_hash_identity','missing_uuid','anchor','short_history','gap','clock','lid','failure_row'])
def test_sealed_uuid_history_rejects_corrupted_or_incomplete_evidence(broken):
    summary, state, points = history()
    if broken == 'uuid':
        points[-1]['power']['boot_identity_checkpoint']['uuid_raw'] = OTHER
        points[-1]['power']['boot_identity_checkpoint']['boot_uuid'] = OTHER
        points[-1]['power']['boot_uuid'] = OTHER
    elif broken == 'raw_hash_identity':
        points[-1]['power']['boot_identity_checkpoint']['boot_timeval_ns'] += 1000
    elif broken == 'missing_uuid':
        del points[-1]['power']['boot_identity_checkpoint']
    elif broken == 'anchor':
        del state['boot_timeval_anchor_ns']
    elif broken == 'short_history':
        points.pop()
    elif broken == 'gap':
        del points[1:10]
    elif broken == 'clock':
        points[-1]['wall_ns'] += MAX_CLOCK_DELTA_NS+1
    elif broken == 'lid':
        points[-1]['power']['lid_open'] = False
    else:
        points[-1]['kind'] = 'FAILURE'
    with pytest.raises(ValueError):
        identity.endurance_boot_metadata(summary, state, points)


def test_actual_observer_uses_uuid_guard_and_versioned_provenance():
    assert observer.UUIDPowerGuard is identity.UUIDPowerGuard
    source = inspect.getsource(observer.observe)
    assert 'with UUIDPowerGuard(run.path,context)' in source
    assert 'with ManagedPowerGuard' not in source
    assert 'schema_version=UUID_ENDURANCE_SCHEMA' in source
    assert 'boot_uuid=guard.state' in source
    assert observer.ENDURANCE_SECONDS == 10800


@pytest.mark.parametrize('uuid_value, passes', [(UUID,True),(OTHER,False)])
def test_current_boot_admission_checks_uuid_not_legacy_epoch(tmp_path,monkeypatch,uuid_value,passes):
    run = tmp_path/'results/host_endurance/runs/test'; run.mkdir(parents=True)
    monkeypatch.setattr(observer.SourceProvenance,'capture',lambda _:SimpleNamespace(dirty=False))
    anchor = FIXTURE['initial']['boot_timeval_ns']
    monkeypatch.setattr(observer,'qualification_inputs',lambda *_:(dict(original_uuid_recorded=True,
        boot_uuid=UUID,boot_timeval_anchor_ns=anchor),dict(power_settings='unit')))
    import dynapm.system_validation.host_power as power
    monkeypatch.setattr(power,'power_state',lambda:dict(boot_epoch_seconds=1794336849))
    monkeypatch.setattr(power,'command',lambda _: 'unit')
    current = dict(FIXTURE['after_boundary'],boot_uuid=uuid_value,uuid_raw=uuid_value+'\n')
    monkeypatch.setattr(observer,'read_boot',lambda:current)
    if passes:
        assert observer.require_endurance(tmp_path,run)==run
    else:
        with pytest.raises(ValueError,match='uuid_mismatch'):
            observer.require_endurance(tmp_path,run)


def test_calendar_anchor_does_not_roll_forward(tmp_path):
    host=BootHost()
    anchor=FIXTURE['initial']['boot_timeval_ns']
    with pytest.raises(PowerGuardError,match='material_boot_calendar_discrepancy'):
        with guard(tmp_path,host) as g:
            for shift in (900_000_000,1_800_000_000,2_700_000_000):
                host.timeval=raw_time(anchor+shift)
                g.checkpoint()
    assert g.state['boot_timeval_anchor_ns']==anchor and g.state['release_confirmed']


@pytest.mark.parametrize('uuid_value',['','not-a-uuid'])
def test_unavailable_or_malformed_uuid_fails_checkpoint(tmp_path,uuid_value):
    host=BootHost()
    with pytest.raises(PowerGuardError,match='malformed_boot_uuid'):
        with guard(tmp_path,host) as g:
            host.uuid=uuid_value
            g.checkpoint()
    assert g.state['release_confirmed']


def test_new_observer_dependency_changes_fail_runtime_compatibility(tmp_path):
    import subprocess
    from dynapm.system_validation.host_certificate import RUNTIME,OBSERVER
    repo=tmp_path/'repo';repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('init','-b','dynapm')
    for name in set(RUNTIME)|set(observer.UUID_RUNTIME):
        p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('UNIT=1\n')
    (repo/OBSERVER).write_text('def observe():\n    return 1\n')
    clock=repo/'dynapm/system_validation/clock_observations.py'
    clock.write_text('MAX_CLOCK_DELTA_NS=2000000000\nclass ObservationClock:\n    def check_host(self,wall,mono):\n        return wall-mono\n')
    git('add','.');git('-c','user.name=UNIT','-c','user.email=unit@example.invalid','commit','-m','fixture')
    commit=git('rev-parse','HEAD')
    assert observer.require_same_uuid_runtime(repo,commit)
    path=repo/'dynapm/system_validation/v8_host_identity.py';path.write_text('UNIT=2\n')
    with pytest.raises(ValueError,match='runtime_mismatch'):
        observer.require_same_uuid_runtime(repo,commit)


def test_legacy_frozen_calibration_files_are_unchanged():
    import subprocess
    root=Path(__file__).parents[2]
    for name in ('dynapm/system_validation/host_endurance.py','dynapm/system_validation/host_certificate.py',
                 'configs/system_trials_v8_estimation_v2.json'):
        assert (root/name).read_bytes()==subprocess.check_output(['git','show','67bfd37:'+name],cwd=root)
    from dynapm.system_validation.estimation_design import frozen_spec
    assert frozen_spec(root)['host_execution']['minimum_endurance_seconds']==10800
