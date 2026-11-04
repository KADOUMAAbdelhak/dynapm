import pytest
from dynapm.system_validation.outcome_taxonomy import classify,observation_window,OutcomeLedger
from dynapm.system_validation.reservation_protocol import Target
@pytest.mark.parametrize('kind',['request_timeout','http_error','application_error','slo_violation','throughput_degradation','queue_buildup'])
def test_application_harm_is_retained_outcome(kind):assert not classify(kind)['invalidates_run']
@pytest.mark.parametrize('kind',['generator_failure','lost_control_telemetry','controller_crash','enforcement_unverifiable','missing_provenance','host_continuity_failure','corrupt_measurement_stream'])
def test_measurement_failures_invalidate(kind):assert classify(kind)['invalidates_run']
def test_diagnostic_failure_requires_independent_evidence():assert 'condition' in classify('application_diagnostic_timeout')
def test_fresh_failed_attempts_complete_observation_without_claiming_health():
 l=OutcomeLedger(lambda:(7_000_000_000,7_000_000_000));l.intend('low',Target(100,64));l.no_op({'complete':True,'gates':{'all':True}})
 l.active['enforced_ns']=0
 records=[dict(request_id=i,sent_monotonic_ns=i*250_000_000,completed_monotonic_ns=i*250_000_000+100_000_000,success=i!=3,work_verified=i!=3) for i in range(24)]
 w=observation_window(records,[],0,7_000_000_000)
 assert w['observation_complete'] and w['application_failures']==1 and not w['healthy'] and not w['server_drain_proven']
 assert l.finish_window(w) and l.active is None and not l.terminal
 assert l.events[-1]['event']=='POST_ENFORCEMENT_MEASUREMENT_COMPLETE'
 assert l.events[-1]['application_failures']==1
def test_missing_registry_does_not_complete():assert not observation_window([],None,0,7_000_000_000)['observation_complete']
def test_unknown_event_cannot_be_silently_accepted():
 with pytest.raises(ValueError):classify('unknown')

def node_fixture():
 from dynapm.tests.test_reservation_protocol import fixture
 p,_=fixture(Target(100,64));p['spec']['nodeName']='UNIT_NODE';p['status']['containerStatuses'][0]['containerID']='containerd://UNIT_CONTAINER'
 n=dict(start_monotonic_ns=3,end_monotonic_ns=4,values={'cpu.max':'10000 100000','memory.max':str(1024*2**20)},binding={'node':'UNIT_NODE','container_id':'UNIT_CONTAINER'})
 return p,n

def test_independent_enforcement_has_no_application_diagnostic_dependency():
 from dynapm.system_validation.outcome_taxonomy import control_enforcement
 p,n=node_fixture();v=control_enforcement(p,n,Target(100,64),pod_uid='UNIT_POD',generation=2,ack_ns=2,pod_received_ns=3,now_ns=5)
 assert v['complete'] and all(v['gates'].values())

@pytest.mark.parametrize('change',['wrong_container','wrong_quota','wrong_limit','stale_read','unallocated','pending'])
def test_independent_enforcement_fails_closed(change):
 from dynapm.system_validation.outcome_taxonomy import control_enforcement
 p,n=node_fixture()
 if change=='wrong_container':n['binding']['container_id']='OTHER'
 if change=='wrong_quota':n['values']['cpu.max']='20000 100000'
 if change=='wrong_limit':n['values']['memory.max']=str(64*2**20)
 if change=='stale_read':n['start_monotonic_ns']=1
 if change=='unallocated':p['status']['containerStatuses'][0]['allocatedResources']={}
 if change=='pending':p['status']['conditions'].append({'type':'PodResizeInProgress','status':'True'})
 assert not control_enforcement(p,n,Target(100,64),pod_uid='UNIT_POD',generation=2,ack_ns=2,pod_received_ns=3,now_ns=5)['complete']
