"""Offline UNIT fixtures only. No cluster or runtime verification is claimed."""
from copy import deepcopy
from pathlib import Path
import pytest
from dynapm.core.provenance import fingerprint,read_json
from dynapm.system_validation.reservation_protocol import (
 Target,reservation_recommendation,reservation_patch,reservation_resources,resources_match,
 enforcement_check,application_window,ActuationLedger,read_protocol,protocol_specification,
 FIXED_MEMORY_LIMIT_MIB,WATCHDOG_NS)
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.consumer import resource_patch
ROOT=Path(__file__).parents[2]


class Clock:
 def __init__(self):self.now=10**9
 def __call__(self):self.now+=1;return self.now,1790000000000000000+self.now
 def advance(self,n):self.now+=n


def fixture(target=Target(80,64)):
 resources=target.resources()
 pod=dict(metadata=dict(uid='UNIT_POD',resourceVersion='3',generation=2),spec=dict(containers=[dict(name='workload',resources=deepcopy(resources))]),status=dict(qosClass='Burstable',observedGeneration=2,
  conditions=[dict(type='Ready',status='True')],containerStatuses=[dict(name='workload',restartCount=0,lastState={},resources=deepcopy(resources),allocatedResources=deepcopy(resources['requests']))]))
 domain=dict(boot_id='UNIT_BOOT',time_namespace='UNIT_NS',hostname='application')
 sample=dict(instance_id='UNIT_APP',clock_schema='system-clock-observation-v2',sample_time_ns=20,cluster_received_at_ns=21,
  source_clock=dict(domain=domain,wall_ns=20,monotonic_ns=1),cluster_clock_domain=domain,cluster_receipt_monotonic_ns=2,
  received_at_ns=5,host_admitted_at_ns=6,host_receipt_monotonic_ns=3,host_admitted_monotonic_ns=4,
  oom_kills=0,cpu_limit_cores=target.cpu_millicores/1000,memory_limit_bytes=1024*2**20,memory_current_bytes=80*2**20)
 return pod,sample


def observation(target=Target(80,64)):
 p,s=fixture(target)
 return enforcement_check(p,s,target,pod_uid='UNIT_POD',app_instance_id='UNIT_APP',accepted_generation=2,accepted_monotonic_ns=0,pod_receipt_monotonic_ns=5,read_monotonic_ns=10)


def test_frozen_contract_is_separate_and_keeps_legacy_physical_semantics():
 d=frozen_spec(ROOT);v=read_protocol(ROOT)
 assert v==protocol_specification(ROOT) and v['selected_memory_semantics']=='B'
 assert v['telemetry']['path']=='U' and not v['telemetry']['compression_enabled']
 assert v['telemetry']['candidate_slot_duration_seconds'] is None
 assert d['consumer']['version']=='p95-fixed-headroom-quantized-v1' and d['telemetry']['min_span_seconds']==270
 assert v['engineering_verification']['live_verified'] is False


@pytest.mark.parametrize('cpu,mem',[(False,64),(80,True),(40,64),(1001,64),(85,64),(80,60),(80,516),(80,65)])
def test_grid_rejects_invalid_or_qos_changing_targets(cpu,mem):
 with pytest.raises(ValueError):Target(cpu,mem)


def test_reservation_target_and_templates_do_not_change_legacy_hard_cap():
 d=frozen_spec(ROOT);before=deepcopy(d);resources=reservation_resources(d)
 app=next(p for p in resources['items'] if p['kind']=='Pod' and p['metadata']['name']=='application')
 assert app['spec']['containers'][0]['resources']==Target(1000,512).resources() and d==before
 for mem in (64,128,256,512):assert Target(80,mem).resources()['limits']['memory']=='1024Mi'
 old=resource_patch(dict(cpu_millicores=80,memory_mib=64))
 assert old['spec']['containers'][0]['resources']['limits']['memory']=='64Mi'
 p,s=fixture();before=deepcopy(p);patch=reservation_patch(Target(80,64),p)
 assert p==before and patch['metadata']=={'uid':'UNIT_POD','resourceVersion':'3'}
 assert patch['spec']['containers'][0]['resources']['requests']['memory']=='64Mi'
 assert reservation_recommendation({'dynamic':{'predicted_cpu_p95_next_24h':6.,'predicted_mem_p95_next_24h':10.}},d)==Target(80,64)


def test_memory_reservation_is_not_a_hard_cap_or_page_reclamation_claim():
 p,s=fixture();r=observation()
 assert s['memory_current_bytes']>64*2**20 and r['complete']
 assert r['gates']['fixed_memory_cap_enforced'] and r['gates']['reservation_accounted']
 assert 'NOT reclaimed' in r['memory_request_meaning']
 s['memory_limit_bytes']=64*2**20
 assert not enforcement_check(p,s,Target(80,64),pod_uid='UNIT_POD',app_instance_id='UNIT_APP',accepted_generation=2,accepted_monotonic_ns=0,pod_receipt_monotonic_ns=5,read_monotonic_ns=10)['complete']


@pytest.mark.parametrize('fault',['allocated','status','spec','qos','generation','cpu','resize','ready'])
def test_ack_or_partial_convergence_never_establishes_enforcement(fault):
 p,s=fixture()
 if fault=='allocated':p['status']['containerStatuses'][0]['allocatedResources']['memory']='512Mi'
 if fault=='status':p['status']['containerStatuses'][0]['resources']['requests']['memory']='512Mi'
 if fault=='spec':p['spec']['containers'][0]['resources']['requests']['memory']='512Mi'
 if fault=='qos':p['status']['qosClass']='Guaranteed'
 if fault=='generation':p['status']['observedGeneration']=1
 if fault=='cpu':s['cpu_limit_cores']=1.
 if fault=='resize':p['status']['conditions'].append(dict(type='PodResizeInProgress',status='True'))
 if fault=='ready':p['status']['conditions']=[]
 assert not enforcement_check(p,s,Target(80,64),pod_uid='UNIT_POD',app_instance_id='UNIT_APP',accepted_generation=2,accepted_monotonic_ns=0,pod_receipt_monotonic_ns=5,read_monotonic_ns=10)['complete']


@pytest.mark.parametrize('fault',['uid','instance','restart','oom','future','age','admission','domain'])
def test_identity_and_original_clock_rules_remain_fail_closed(fault):
 p,s=fixture()
 if fault=='uid':p['metadata']['uid']='OTHER'
 if fault=='instance':s['instance_id']='OTHER'
 if fault=='restart':p['status']['containerStatuses'][0]['restartCount']=1
 if fault=='oom':s['oom_kills']=1
 if fault=='future':s['sample_time_ns']=22
 if fault=='age':s['cluster_received_at_ns']=3*10**9
 if fault=='admission':s['host_admitted_monotonic_ns']=2
 if fault=='domain':s['source_clock']['domain']={'boot_id':'OTHER'}
 with pytest.raises(ValueError):enforcement_check(p,s,Target(80,64),pod_uid='UNIT_POD',app_instance_id='UNIT_APP',accepted_generation=2,accepted_monotonic_ns=0,pod_receipt_monotonic_ns=5,read_monotonic_ns=10)


def test_pending_supersession_never_overwrites_accepted_patch():
 clock=Clock();ledger=ActuationLedger(clock);p,_=fixture()
 first=Target(80,64);latest=Target(500,256)
 assert ledger.intend('first',first)==first
 ledger.patch(p);ledger.acknowledged(2)
 assert ledger.intend('stale',Target(250,128)) is None
 assert ledger.intend('latest',latest) is None
 ledger.deferred({'UNIT':'actual kubelet error would be retained here'})
 assert ledger.active['target']==first
 with pytest.raises(ValueError):ledger.patch(p)
 with pytest.raises(ValueError):ledger.next_queued()
 assert ledger.observe(observation())
 with pytest.raises(ValueError):ledger.next_queued()
 assert ledger.finish_window(dict(ready=True,statistically_settled=None))
 assert ledger.next_queued()==latest
 assert ledger.patch(p)['spec']['containers'][0]['resources']==latest.resources()
 events=ledger.events
 assert any(e['event']=='SUPERSEDED_BEFORE_SUBMISSION' and e['decision_id']=='stale' for e in events)
 assert sum(e['event']=='SKIPPED_OPPORTUNITY' for e in events)==2
 assert not any(e['event']=='ACCEPTED' and e['decision_id']=='stale' for e in events)
 assert all(e.get('statistically_settled') is not True for e in events)


@pytest.mark.parametrize('phase,expected',[('dispatch','CONTROLLER_DISPATCH_FAILURE'),('ack','ACK_UNKNOWN_RIGHT_CENSORED'),('accepted','ACTUATION_UNRESOLVED_RIGHT_CENSORED'),('deferred','ACTUATION_UNRESOLVED_RIGHT_CENSORED'),('window','APPLICATION_WINDOW_RIGHT_CENSORED')])
def test_timeout_is_terminal_censored_never_a_finite_enforcement_latency(phase,expected):
 c=Clock();l=ActuationLedger(c);p,_=fixture();l.intend('a',Target(80,64))
 if phase!='dispatch':l.patch(p)
 if phase in ('accepted','deferred','window'):l.acknowledged(2)
 if phase=='deferred':l.deferred({'reason':'Deferred'})
 if phase=='window':l.observe(observation())
 l.intend('queued',Target(500,256));c.advance(WATCHDOG_NS)
 assert l.watchdog() and l.terminal and l.active is not None
 row=next(e for e in l.events if e['event']==expected);assert row['latency_seconds'] is None
 assert any(e['event']=='CANCELLED_UNSUBMITTED_ON_TERMINAL_FAILURE' for e in l.events)
 with pytest.raises(ValueError):l.intend('after',Target(80,64))
 assert not l.watchdog()
 if phase!='window':assert not any(e['event']=='PHYSICALLY_ENFORCED' for e in l.events)


def test_noop_keeps_ack_and_latency_distinct_from_a_patch():
 l=ActuationLedger(Clock());l.intend('a',Target(80,64));l.no_op(observation())
 assert not any(e['event']=='PATCH_SUBMITTED' for e in l.events)
 assert any(e['event']=='ACCEPTED_NO_CHANGE' and e['latency_seconds'] is None for e in l.events)
 with pytest.raises(ValueError):l.no_op(observation())


def requests(n=20,success=True):
 return [dict(request_id=i,sent_monotonic_ns=100+i*300000000,completed_monotonic_ns=200+i*300000000,success=success,work_verified=True) for i in range(n)]


def test_settling_requires_explicit_drain_registry_physical_window_and_progress():
 rr=requests()
 assert application_window(rr,None,100,6*10**9)['ready'] is False
 assert application_window(rr,[],100,6*10**9)['ready'] is True
 assert application_window(rr,[999],100,6*10**9)['ready'] is False
 assert application_window(rr[:19],[],100,6*10**9)['ready'] is False
 r=application_window(requests(20,False),[],100,6*10**9)
 assert not r['ready'] and r['application_failures']==20 and r['statistically_settled'] is None
 assert not application_window(rr,[],100,2*10**9)['ready']
 with pytest.raises(ValueError):application_window(rr+rr,[],100,6*10**9)


def test_bad_or_reused_event_clocks_and_ids_are_not_hidden():
 c=Clock();l=ActuationLedger(c);l.intend('a',Target(80,64))
 with pytest.raises(ValueError):l.intend('a',Target(80,64))
 p,_=fixture();l.patch(p);c.now=0
 with pytest.raises(ValueError):l.acknowledged(2)
 assert l.terminal


def test_terminal_ack_and_late_observations_cannot_relabel_failure():
 c=Clock();l=ActuationLedger(c);p,_=fixture();l.intend('a',Target(80,64));l.patch(p)
 l.fail('ACK_UNKNOWN_RIGHT_CENSORED',{'UNIT':'timeout'})
 with pytest.raises(ValueError):l.acknowledged(2)
 with pytest.raises(ValueError):l.observe(observation())
 assert not any(e['event']=='PHYSICALLY_ENFORCED' for e in l.events)


def test_stale_pre_ack_observations_do_not_complete_new_actuation():
 p,s=fixture()
 r=enforcement_check(p,s,Target(80,64),pod_uid='UNIT_POD',app_instance_id='UNIT_APP',accepted_generation=2,accepted_monotonic_ns=6,pod_receipt_monotonic_ns=5,read_monotonic_ns=10)
 assert not r['complete'] and not r['gates']['fresh_observation']
