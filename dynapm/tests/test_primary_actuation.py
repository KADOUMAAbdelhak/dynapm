import ast
import copy
import inspect
import json
from pathlib import Path
import pytest
from dynapm.system_validation import primary_actuation as amended
from dynapm.system_validation import bounded_v8_runtime as frozen
from dynapm.system_validation.outcome_taxonomy import control_enforcement as original
from dynapm.system_validation.reservation_protocol import Target


def fixture():
    data=json.loads((Path(__file__).parent/'fixtures/v8_unready_enforced_nonqualifying.json').read_text())
    assert data['scope']=='DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'
    frame=data['frame'];pod=frame['pod'];node=frame['node']
    args=dict(pod_uid=pod['metadata']['uid'],generation=pod['metadata']['generation'],ack_ns=0,
              pod_received_ns=frame['receipt_monotonic_ns'],now_ns=max(node['end_monotonic_ns'],frame['receipt_monotonic_ns'])+1)
    return pod,node,Target(**frame['target']),args


def test_actual_unready_but_physically_enforced_regression():
    pod,node,target,args=fixture()
    legacy=original(pod,node,target,**args)
    assert not legacy['complete'] and not legacy['gates']['pod_ready']
    assert all(v for k,v in legacy['gates'].items() if k!='pod_ready')
    checked=amended.control_enforcement(pod,node,target,**args)
    assert checked['complete'] and checked['application_observations']['pod_ready'] is False
    assert checked['legacy_readiness_gated_complete'] is False
    assert checked['gates']=={k:v for k,v in legacy['gates'].items() if k!='pod_ready'}


@pytest.mark.parametrize('fault',['cpu','memory','spec','status','reservation','generation','binding','resize','freshness'])
def test_no_resource_gate_is_relaxed(fault):
    pod,node,target,args=fixture()
    cs=pod['status']['containerStatuses'][0]
    if fault=='cpu':node['values']['cpu.max']='10000 100000'
    if fault=='memory':node['values']['memory.max']=str(64*2**20)
    if fault=='spec':pod['spec']['containers'][0]['resources']['requests']['cpu']='100m'
    if fault=='status':cs['resources']['requests']['cpu']='100m'
    if fault=='reservation':cs['allocatedResources']['memory']='512Mi'
    if fault=='generation':pod['status']['observedGeneration']=0
    if fault=='binding':node['binding']['container_id']='wrong'
    if fault=='resize':pod['status']['conditions'].append(dict(type='PodResizePending',status='True'))
    if fault=='freshness':args['ack_ns']=node['end_monotonic_ns']+1
    assert amended.control_enforcement(pod,node,target,**args)['complete'] is False


def test_restart_still_requires_stream_reconciliation():
    pod,node,target,args=fixture();pod['status']['containerStatuses'][0]['restartCount']=1
    with pytest.raises(ValueError,match='restart'):amended.control_enforcement(pod,node,target,**args)


def test_physical_patch_and_watchdog_logic_are_identical():
    assert ast.dump(ast.parse(inspect.getsource(amended.actuate)),include_attributes=False)==ast.dump(ast.parse(inspect.getsource(frozen.actuate)),include_attributes=False)
    assert ast.dump(ast.parse(inspect.getsource(amended.confirm)),include_attributes=False)==ast.dump(ast.parse(inspect.getsource(frozen.confirm)),include_attributes=False)
