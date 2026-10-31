"""Unit-only host compatibility and neutral timing tests; no live probes."""
from pathlib import Path
import subprocess
import pytest

from dynapm.system_validation.host_certificate import RUNTIME,OBSERVER,require_same_host_runtime
from dynapm.system_validation.timing_probes import ResizeProbe,distribution,request_drain_seconds,collect_local_durations


@pytest.fixture
def pinned(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('init','-b','dynapm')
    for name in RUNTIME:
        p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('UNIT = 1\n')
    clock=repo/'dynapm/system_validation/clock_observations.py'
    clock.write_text('MAX_CLOCK_DELTA_NS=2000000000\nclass ObservationClock:\n    def check_host(self,wall,mono):\n        return wall-mono\n')
    (repo/OBSERVER).write_text('import time\ndef require_endurance():\n    return 1\ndef observe():\n    return time.time()\n')
    git('add','.');git('-c','user.name=UNIT','-c','user.email=unit@example.invalid','commit','-m','unit')
    return repo,git('rev-parse','HEAD')


def test_unrelated_bootstrap_code_does_not_invalidate_host_runtime(pinned):
    repo,commit=pinned
    (repo/'dynapm/system_validation/shared_bootstrap.py').write_text('UNRELATED = 2\n')
    assert require_same_host_runtime(repo,commit)['observation_source_commit']==commit


def test_host_runtime_or_observation_change_invalidates(pinned):
    repo,commit=pinned
    p=repo/RUNTIME[0];p.write_text('UNIT = 2\n')
    with pytest.raises(ValueError,match='runtime_mismatch'):require_same_host_runtime(repo,commit)
    p.write_text('UNIT = 1\n')
    p=repo/OBSERVER;p.write_text(p.read_text().replace('return time.time()','return 2'))
    with pytest.raises(ValueError,match='runtime_mismatch'):require_same_host_runtime(repo,commit)


def test_validation_helper_only_is_outside_acquisition_code(pinned):
    repo,commit=pinned;p=repo/OBSERVER
    p.write_text(p.read_text().replace('return 1','return 99'))
    assert require_same_host_runtime(repo,commit)
    with pytest.raises(ValueError,match='pinned'):require_same_host_runtime(repo,'HEAD')


def test_cpu_memory_ack_and_status_are_separate_first_observed_timings():
    p=ResizeProbe('UNIT',10**9,100*10**9,500,128,True,True)
    p.acknowledged(2*10**9,101*10**9)
    for t,podmem,cgmem in [(3,64,64),(4,128,64),(6,128,128)]:
        p.observe(t*10**9,(99+t)*10**9,pod_cpu_millicores=500,pod_memory_mib=podmem,
            cgroup_cpu_cores=.5,cgroup_memory_bytes=cgmem*2**20)
    r=p.record(pending_end_monotonic_ns=6*10**9,skipped_decisions=1)
    assert r['seconds']=={'api_ack':1,'pod_cpu':2,'cgroup_cpu':2,'pod_memory':3,'cgroup_memory':5}
    assert r['pending_seconds']==5 and r['skipped_decisions']==1
    assert r['application_steady_state'].startswith('NOT_ESTABLISHED')


def test_unchanged_dimension_not_reported_as_zero_latency():
    p=ResizeProbe('UNIT',1,10,500,128,True,False)
    p.observe(2,11,pod_cpu_millicores=500,pod_memory_mib=128,cgroup_cpu_cores=.5,cgroup_memory_bytes=128*2**20)
    r=p.record(timeout=True)
    assert 'cgroup_memory' not in r['seconds'] and r['pending_seconds'] is None and r['timeout']
    with pytest.raises(ValueError,match='nonincreasing'):p.observe(2,11,pod_cpu_millicores=500,pod_memory_mib=128,cgroup_cpu_cores=.5,cgroup_memory_bytes=128*2**20)


def test_local_duration_integrity_and_distribution():
    r=collect_local_durations(telemetry_start_ns=1,body_received_ns=3,decode_finished_ns=4,recommendation_start_ns=5,recommendation_end_ns=9)
    assert r['telemetry_transport_seconds']==2e-9
    assert distribution([1,2,3],missing=1)['median']==2
    assert distribution([],censored=2)['p95'] is None
    with pytest.raises(ValueError):distribution([float('nan')])
    with pytest.raises(ValueError):collect_local_durations(telemetry_start_ns=3,body_received_ns=1,decode_finished_ns=4,recommendation_start_ns=5,recommendation_end_ns=9)


def test_request_drain_is_not_a_steady_state_claim():
    r=request_drain_seconds([{'sent_at':9,'completed_at':11.5,'success':True},
        {'sent_at':11,'completed_at':20,'success':True}],10)
    assert r['drain_seconds']==1.5 and r['pre_enforcement_requests']==1
    assert r['scope']=='old in-flight request drain only'


def test_cluster_reception_does_not_relabel_host_endurance(pinned):
    repo,commit=pinned;p=repo/'dynapm/system_validation/clock_observations.py'
    p.write_text(p.read_text()+'\ndef receive_cluster():\n    return 99\n')
    assert require_same_host_runtime(repo,commit)
    p.write_text(p.read_text().replace('return wall-mono','return wall+mono'))
    with pytest.raises(ValueError,match='runtime_mismatch'):require_same_host_runtime(repo,commit)
