"""Offline tests only; no live cluster or compressed validation is launched."""
from copy import deepcopy
from pathlib import Path
import pytest
from dynapm.core.run_store import write_json
from dynapm.system_validation.neutral_characterization import (pending_opportunity,require_idle,observe_probe,
 component_refresh,summary,qualification,TARGETS,MAX_ACTIVE_SECONDS,MAX_RESIZE_SECONDS)
from dynapm.system_validation.timing_probes import ResizeProbe
from dynapm.system_validation.trial_preparation import measured_bootstrap,MeasuredProfileAdapter
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.tests.test_system_trial_preparation import unit_evidence,START,END
ROOT=Path(__file__).parents[2]


def test_component_benchmark_does_not_refresh_live_policy_or_modify_history():
 d=frozen_spec(ROOT);b=measured_bootstrap(unit_evidence(),START,END,END,d)
 a=MeasuredProfileAdapter('pw_6h',b,d,planned_streaming_slots=576);before=a.snapshot();history=a.history.copy(deep=True)
 for _ in range(3):
  result=component_refresh(a)
  assert result['end_monotonic_ns']>=result['start_monotonic_ns'] and result['thread_cpu_ns']>=0
  assert result['live_runtime_refreshes']==0 and result['role']=='ISOLATED_REFRESH_COMPONENT_NOT_SCHEDULER_EVENT'
 after=a.snapshot();before.pop('snapshot_wall_time_ns');after.pop('snapshot_wall_time_ns')
 assert after==before and a.history.equals(history)


@pytest.mark.parametrize('pending',[{}, {'cpu_millicores':100}])
def test_pending_guard_skips_and_refuses_another_patch(pending):
 assert pending_opportunity(pending)=='SKIPPED_PENDING'
 with pytest.raises(ValueError,match='overlapping'):require_idle(pending)
 assert pending_opportunity(None)=='READY';require_idle(None)


def test_status_and_cgroup_timestamps_are_independent_complete_receipt_bounds():
 p=ResizeProbe('unit',10,100,500,128,True,True);p.acknowledged(11,101)
 actual=dict(requests=dict(cpu='500m',memory='128Mi'))
 sample=dict(cpu_limit_cores=.5,memory_limit_bytes=64*2**20,persistent_workset_bytes=32*2**20,host_receipt_monotonic_ns=20)
 observe_probe(p,15,25,115,actual,sample)
 assert p.first_observed['pod_cpu'][0]==15 and p.first_observed['cgroup_cpu'][0]==20
 assert p.first_observed['pod_memory'][0]==15 and 'cgroup_memory' not in p.first_observed
 sample.update(memory_limit_bytes=128*2**20,host_receipt_monotonic_ns=35)
 observe_probe(p,30,40,130,actual,sample)
 assert p.first_observed['pod_cpu'][0]==15 and p.first_observed['cgroup_memory'][0]==35
 r=p.record(pending_end_monotonic_ns=42,skipped_decisions=1)
 assert r['seconds']['pod_cpu']==5e-9 and r['seconds']['cgroup_memory']==25e-9


def test_bounded_stimuli_cover_all_directions_and_do_not_choose_compression():
 d=frozen_spec(ROOT);fixed=[t for t in TARGETS if t[0] is not None]
 assert TARGETS[0]==(None,None)  # natural PW6 recommendation first
 assert any(a[0]<b[0] for a,b in zip(fixed,fixed[1:])) and any(a[0]>b[0] for a,b in zip(fixed,fixed[1:]))
 assert any(a[1]<b[1] for a,b in zip(fixed,fixed[1:])) and any(a[1]>b[1] for a,b in zip(fixed,fixed[1:]))
 assert any(a==b for a,b in zip(fixed,fixed[1:]))
 assert all(d['consumer']['cpu_millicores_minimum']<=c<=d['consumer']['cpu_millicores_maximum'] and d['consumer']['memory_mib_minimum']<=m<=d['consumer']['memory_mib_maximum'] for c,m in fixed)
 assert MAX_ACTIVE_SECONDS==240 and MAX_RESIZE_SECONDS==60
 assert d['telemetry']['min_samples']==50 and d['telemetry']['min_span_seconds']==270


def test_qualification_tampering_fails_before_any_workload(tmp_path):
 p=tmp_path/'results/shared_bootstrap/qualifications/block0001';p.mkdir(parents=True)
 write_json(p/'qualification.json',{'artifact_sha256':'wrong'})
 with pytest.raises(ValueError,match='qualification_hash'):qualification(tmp_path)


def test_nonempty_trace_descriptor_roundtrips_through_managed_input_validation(tmp_path):
 from dynapm.system_validation.neutral_characterization import prepare_inputs
 from dynapm.data.manifests import check_dataset
 config={'unit':'offline','targets':((100,64),(500,128))}
 root,dataset=prepare_inputs(tmp_path,config)
 assert dataset.trace_names==('stable',) and len(dataset.files)==1
 check_dataset(root,dataset)
 assert prepare_inputs(tmp_path,config)[1].sha256==dataset.sha256
 (root/'stable/input.json').write_text('{}')
 with pytest.raises(ValueError,match='immutable_probe_descriptor'):prepare_inputs(tmp_path,config)


def test_artifact_initialization_has_separate_bounded_timeout(monkeypatch):
 import json
 from dynapm.system_validation import neutral_characterization as module
 class Response:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self):return b'{"initialized":true}'
 def opener(request,timeout):
  assert timeout==60 and request.full_url=='http://127.0.0.1:1234/initialize'
  assert json.loads(request.data)=={'fresh':'unit'}
  return Response()
 monkeypatch.setattr(module,'urlopen',opener)
 assert module.initialize_profile('http://127.0.0.1:1234/initialize',{'fresh':'unit'})=={'initialized':True}


def test_engineering_memory_safe_ladder_is_explicit_and_does_not_change_consumer():
 from dynapm.system_validation.neutral_characterization import ENGINEERING_TARGETS
 d=frozen_spec(ROOT)
 assert d['consumer']['memory_mib_minimum']==64
 assert min(m for c,m in ENGINEERING_TARGETS)==128
 assert any(a[0]>b[0] for a,b in zip(ENGINEERING_TARGETS,ENGINEERING_TARGETS[1:]))
 assert any(a[0]<b[0] for a,b in zip(ENGINEERING_TARGETS,ENGINEERING_TARGETS[1:]))
 assert any(a[1]>b[1] for a,b in zip(ENGINEERING_TARGETS,ENGINEERING_TARGETS[1:]))
 assert any(a[1]<b[1] for a,b in zip(ENGINEERING_TARGETS,ENGINEERING_TARGETS[1:]))
 assert any(a==b for a,b in zip(ENGINEERING_TARGETS,ENGINEERING_TARGETS[1:]))
 assert TARGETS[0]==(None,None)  # original failing production target is not rewritten
