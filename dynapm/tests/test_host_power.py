"""Deterministic OS fixtures only; never change real power settings."""
import json
import os
import time
from pathlib import Path

import pytest

from dynapm.core.provenance import read_json,file_sha256
from dynapm.system_validation.host_power import (
    ManagedPowerGuard,PowerGuardError,own_assertions,power_state,MAX_CLOCK_DELTA_NS,
    MAX_HEARTBEAT_GAP_NS,ENDURANCE_SECONDS)
from dynapm.system_validation.host_endurance import require_endurance,observe,OUTPUTS

CONTEXT=dict(run_id='UNIT',source_commit='c'*40,experiment_fingerprint='f'*64)


class Host:
    pid=87654
    def __init__(self):
        self.active=False;self.ac=True;self.lid='No';self.boot=1700000000
        self.missing=False;self.calls=[];self.spawned=[]
    def read(self,args):
        self.calls.append(args)
        if args[-1]=='batt':return "Now drawing from 'AC Power'\n" if self.ac else "Now drawing from 'Battery Power'\n"
        if args[0].endswith('ioreg'):return '"AppleClamshellState" = '+self.lid
        if args[-1]=='kern.boottime':return '{ sec = '+str(self.boot)+', usec = 1 }'
        if args[-1]=='custom':return 'AC Power:\n sleep 0\n displaysleep 0\n'
        if args[-1]=='assertions':
            if self.active and not self.missing:
                return '\n'.join(f'   pid {self.pid}(caffeinate): [0x0] 00:00:01 {t} named: "UNIT"' for t in ('PreventUserIdleSystemSleep','PreventSystemSleep'))
            return '   pid 55(other): PreventSystemSleep\n'
        raise AssertionError(args)
    def spawn(self,args,**kwargs):
        self.spawned.append((args,kwargs));self.active=True;return self
    def poll(self):return None if self.active else 0
    def terminate(self):self.active=False
    def wait(self,timeout):return 0
    def kill(self):self.active=False


def guard(tmp_path,host,**kwargs):
    return ManagedPowerGuard(tmp_path,CONTEXT,read=host.read,spawn=host.spawn,
        platform='darwin',background=False,startup_timeout=0,**kwargs)


def test_owned_assertion_verified_before_body_and_released(tmp_path):
    h=Host()
    with guard(tmp_path,h) as g:
        state=read_json(tmp_path/'outputs/power_guard.json')
        assert state['status']=='ACTIVE' and state['assertion_pid']==h.pid and state['owner_pid']==os.getpid()
        assert len(state['verified_assertions'])==2
        assert h.spawned[0][0]==['/usr/bin/caffeinate','-i','-s','-w',str(os.getpid())]
    state=read_json(tmp_path/'outputs/power_guard.json')
    assert state['release_confirmed'] and state['status']=='RELEASED' and state['ended_at']
    assert not h.active
    assert all(args[:2]!=['/usr/bin/pmset','-a'] for args in h.calls)
    assert state['continuity_log_sha256']==file_sha256(tmp_path/'outputs/host_continuity.jsonl')


def test_release_on_workload_exception(tmp_path):
    h=Host()
    with pytest.raises(RuntimeError,match='UNIT workload'):
        with guard(tmp_path,h):raise RuntimeError('UNIT workload')
    assert not h.active
    assert read_json(tmp_path/'outputs/power_guard.json')['release_confirmed']


@pytest.mark.parametrize('field,value,reason',[('ac',False,'mains_power_lost'),('lid','Yes','lid_closed'),('lid','UNKNOWN','lid_state_unavailable')])
def test_power_lid_fail_preflight_without_spawn(tmp_path,field,value,reason):
    h=Host();setattr(h,field,value)
    with pytest.raises(PowerGuardError,match=reason):
        with guard(tmp_path,h):pytest.fail('workload must not start')
    assert not h.spawned
    assert read_json(tmp_path/'outputs/power_guard.json')['status']=='PREFLIGHT_FAILED'


def test_wrong_pid_or_partial_assertion_not_accepted():
    with pytest.raises(PowerGuardError):own_assertions('pid 1(caffeinate): PreventSystemSleep\npid 2(caffeinate): PreventUserIdleSystemSleep',1)
    with pytest.raises(PowerGuardError):own_assertions('pid 11(caffeinate): PreventSystemSleep PreventUserIdleSystemSleep',1)


def test_missing_owned_assertions_release_child(tmp_path):
    h=Host();h.missing=True
    with pytest.raises(PowerGuardError,match='owned_power_assertion_missing'):
        with guard(tmp_path,h):pytest.fail('no unguarded workload')
    assert not h.active


@pytest.mark.parametrize('delta',[MAX_CLOCK_DELTA_NS+1,358766629583])
def test_sleep_discontinuity_preserved_before_exit(tmp_path,delta):
    h=Host()
    with pytest.raises(PowerGuardError,match='host_sleep_or_clock_discontinuity'):
        with guard(tmp_path,h) as g:
            w,m=g.previous
            g.checkpoint(wall_ns=w+1_000_000_000+delta,mono_ns=m+1_000_000_000)
    failure=read_json(tmp_path/'outputs/host_continuity_failure.json')
    assert failure['context']==CONTEXT
    assert failure['evidence']['wall_minus_monotonic_elapsed_ns']==delta
    assert not h.active


def test_exact_existing_clock_boundary_not_widened(tmp_path):
    h=Host()
    with guard(tmp_path,h) as g:
        w,m=g.previous
        g.checkpoint(wall_ns=w+1_000_000_000+MAX_CLOCK_DELTA_NS,mono_ns=m+1_000_000_000)
        assert g.max_drift==MAX_CLOCK_DELTA_NS


def test_checkpoint_gap_independent_of_wall_clock(tmp_path):
    h=Host()
    with pytest.raises(PowerGuardError,match='host_continuity_heartbeat_gap'):
        with guard(tmp_path,h) as g:
            w,m=g.previous;gap=MAX_HEARTBEAT_GAP_NS+1
            g.checkpoint(wall_ns=w+gap,mono_ns=m+gap)


@pytest.mark.parametrize('change,reason',[('battery','mains_power_lost'),('assertion','owned_power_assertion_missing'),('boot','host_boot_identity_changed')])
def test_monitor_detects_power_assertion_or_boot_change(tmp_path,change,reason):
    h=Host()
    with pytest.raises(PowerGuardError,match=reason):
        with guard(tmp_path,h) as g:
            if change=='battery':h.ac=False
            if change=='assertion':h.missing=True
            if change=='boot':h.boot+=1
            g.checkpoint(force_power=True)
    assert not h.active


def test_independent_thread_latches_failure(tmp_path,monkeypatch):
    from dynapm.system_validation import host_power as module
    monkeypatch.setattr(module,'CHECK_SECONDS',.01);monkeypatch.setattr(module,'POWER_SECONDS',0)
    h=Host()
    with pytest.raises(PowerGuardError,match='owned_power_assertion_missing'):
        with ManagedPowerGuard(tmp_path,CONTEXT,read=h.read,spawn=h.spawn,platform='darwin',startup_timeout=0) as g:
            h.missing=True
            deadline=time.monotonic()+1
            while g.failure is None and time.monotonic()<deadline:time.sleep(.01)
            assert g.failure is not None
            g.raise_if_failed()


@pytest.mark.parametrize('seconds',[0,300,ENDURANCE_SECONDS-1,21601])
def test_endurance_refuses_short_smoke_as_long_host_evidence(seconds):
    with pytest.raises(ValueError,match='3_to_6_hours'):observe('.',seconds)


def test_long_trials_require_explicit_completed_endurance():
    with pytest.raises(ValueError,match='validated_host_endurance_run_required'):require_endurance('.',None)
    with pytest.raises(ValueError,match='managed_host_endurance_path_required'):require_endurance('.','/tmp/unmanaged')


def test_host_and_application_output_inventories_and_gate_binding():
    from dynapm.system_validation.calibration_runner import output_specs
    paths={o.path for o in output_specs()}
    assert {o.path for o in OUTPUTS if 'endurance_summary' not in o.path}<=paths
    source=(Path(__file__).parents[1]/'system_validation/calibration_runner.py').read_text()
    assert 'if not plumbing_only:require_endurance(repo,host_endurance_run)' in source
    assert 'power.raise_if_failed()' in source and 'clock.check_host(time.time_ns(),time.monotonic_ns())' in source


def test_real_host_unsupported_os_requires_new_adapter(tmp_path):
    with pytest.raises(PowerGuardError,match='platform_adapter'):
        with ManagedPowerGuard(tmp_path,CONTEXT,platform='linux'):pytest.fail('no fake Linux assertion')



def test_monitor_shutdown_failure_cannot_report_success(tmp_path):
    h=Host()
    class Stuck:
        def join(self,timeout):pass
        def is_alive(self):return True
    with pytest.raises(PowerGuardError,match='monitor_shutdown_timeout'):
        with guard(tmp_path,h) as g:g.thread=Stuck()
    assert not h.active and read_json(tmp_path/'outputs/power_guard.json')['release_confirmed']


def test_endurance_cli_installs_graceful_termination_handlers(monkeypatch,capsys):
    import sys,signal
    from dynapm.scripts import task35_host_endurance as cli
    handlers={}
    monkeypatch.setattr(sys,'argv',['host-observe'])
    monkeypatch.setattr(cli.signal,'signal',lambda sig,callback:handlers.setdefault(sig,callback))
    cli.main()
    assert 'NOT STARTED' in capsys.readouterr().out
    with pytest.raises(KeyboardInterrupt,match='termination_requested'):handlers[signal.SIGTERM](signal.SIGTERM,None)



def test_host_observation_config_binds_real_cadence_without_profile_semantics():
    from dynapm.system_validation.host_endurance import observation_config
    from dynapm.system_validation.host_power import CHECK_SECONDS
    c=observation_config('UNIT',{'duration_seconds':10800})
    assert c.data.sampling_cadence_seconds==c.data.evaluation_cadence_seconds==CHECK_SECONDS
    assert c.data.bootstrap_fraction==c.data.forecast_horizon_steps==c.data.feature_history_slots==0
    assert not c.policies and c.preprocessing['duration_seconds']==10800
