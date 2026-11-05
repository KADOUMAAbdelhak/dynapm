from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import json

import pandas as pd
import pytest

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.core.temporal import METRICS
from dynapm.scripts.task41_bounded_v8 import completed_attempts, next_attempt, seal_attempt
from dynapm.system_validation.bounded_v8 import (FIXTURE, NS, PHASES, cells, compile_snapshots,
    load_contract, logical_history, new_profile, offers, plan, reference_library)
from dynapm.system_validation.bounded_v8_metrics import paired_analysis, request_metrics, resource_endpoints
from dynapm.system_validation.bounded_v8_runtime import actuate, integration_disposition, observe_live, pinned_images
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.reservation_protocol import Target
from dynapm.system_validation.trial_preparation import MeasuredBootstrap
from dynapm.system_validation.v8_campaign import publish_record

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def inputs():
    design = frozen_spec(ROOT)
    library = dict(scope=FIXTURE,contract_sha256=load_contract(ROOT),donors={})
    for name,(rps,mem) in PHASES.items():
        library['donors'][name] = dict(run_id=name, raw_sha256=fingerprint(name), manifest_sha256=fingerprint([name]),
            buckets=[dict(cpu_percent=rps+i/10,memory_percent=100*mem/512,host_receipt_start_ns=i*300*NS)
                     for i in range(6)])
    frame = pd.DataFrame([[5.,6.25]]*288,columns=METRICS,index=pd.date_range(end=pd.Timestamp(0,tz='UTC'),periods=288,freq='5min'))
    bootstrap = MeasuredBootstrap(frame,-86400*NS,0,288,0,fingerprint('fixture'))
    return design,library,bootstrap


def test_exact_matrix_clocks_and_order():
    planned = cells()
    assert len(planned)==18 and len({(x['repetition'],x['scenario'],x['method']) for x in planned})==18
    assert [x['method'] for x in planned] == [
        'static','pw_12h','pw_3h', 'static','pw_3h','pw_12h',
        'pw_3h','pw_12h','static', 'pw_12h','pw_3h','static',
        'pw_3h','static','pw_12h', 'pw_12h','static','pw_3h']
    for x in planned:
        p=plan('primary',sequence=x['sequence'])
        assert p['seed']==2026110500+x['repetition']
        assert p['warmup_seconds']+p['cooldown_seconds']+p['measurement_seconds']==4500
        assert p['warmup_phase']=='high12'
        assert p['segments']==([[0,'high12'],[900,'low2']] if x['scenario']=='periodic' else [[0,'high12']])
    integration=plan('integration')
    assert integration['segments']==[[0,'low4'],[1800,'high12']]
    assert integration['refresh_seconds']==10800 and integration['measurement_seconds']==12600
    for group in range(1,19,3):
        assert list(offers(plan('primary',sequence=group))) == list(offers(plan('primary',sequence=group+2)))
    assert load_contract(ROOT)


def test_replay_causal_tile_reset_and_deterministic_compilation(inputs):
    design,library,bootstrap=inputs
    before=fingerprint(library)
    history=logical_history('periodic',library)
    assert len(history)==81 and history[-1]['logical_end_seconds']==24300
    assert [x['donor_bucket_index'] for x in history[:7]]==[0,1,2,3,4,5,0]
    assert history[42]['donor_phase']=='high12' and history[42]['donor_bucket_index']==0
    assert all(x['available_logical_seconds']==x['logical_end_seconds'] for x in history)
    assert all('received_at_ns' not in x for x in history)
    first,cost=compile_snapshots(library,bootstrap,design)
    second,_=compile_snapshots(library,bootstrap,design)
    assert first==second and fingerprint(library)==before and first['scope']==FIXTURE
    assert len(first['snapshots'])==len(first['structural_targets'])==len(cost)==6
    assert [x['maintenance_counts']['n_refresh_events'] for x in first['snapshots']]==[0,0,2,0,2,9]
    assert {x['status'] for x in first['structural_targets']}=={'STRUCTURAL_EQUAL_TARGET','DISTINCT_TARGET'}
    assert first['histories']['abrupt_regime_shift'][288]['donor_bucket_index']==0
    assert all(len(x['steps']) in (81,324) for x in cost)


def test_native_live_refresh_and_noop_disposition(inputs):
    design,_,bootstrap=inputs
    profile=new_profile('pw_3h',bootstrap,design,0,42)
    refreshed=[]
    for offset in range(300,12601,300):
        q=offset*NS
        event,changed=observe_live(profile,dict(logical_slot_ns=q,available_at_ns=q,
            host_receipt_start_ns=q-300*NS,host_receipt_end_ns=q-NS,cpu_percent=15,memory_percent=18),offset,wall_ns=q)
        if changed:refreshed.append(event['offset_seconds'])
    assert refreshed==[10800]
    assert integration_disposition({'status':'NO_OP'},[],0)=='NO_OP_OBJECTIVE_NOT_DEMONSTRATED'
    assert integration_disposition({'status':'ENFORCED','enforced_monotonic_ns':1},[{'sent_offset_ns':2}],0)=='DEMONSTRATED'


def test_exact_request_denominator_and_slices():
    p=plan('primary',sequence=1)
    data=[dict(request_id=x['request_id'],offer=x,sent_offset_ns=x['offset_ns'],completed_offset_ns=x['offset_ns']+1,
               success=True,outcome='success') for x in offers(p)]
    data[-1].update(success=False,outcome='request_timeout',completed_offset_ns=1801*NS)
    report=request_metrics(p,data)
    assert report['primary']['offered_requests']==12600
    assert report['transition']['offered_requests']==3600
    assert report['followup']['offered_requests']==9000 and report['followup']['request_timeouts']==1
    assert report['primary']['slo_violation_rate']==1/12600
    with pytest.raises(ValueError):request_metrics(p,data[:-1])


def test_observed_resource_edges_and_efficiency_denominator():
    actual=[dict(host_receipt_monotonic_ns=i*NS,source_clock={'monotonic_ns':i*NS},cpu_seconds=i*.1,
                 memory_working_set_bytes=128*2**20) for i in (1,2,3)]
    result=resource_endpoints(actual,0,[dict(status='ENFORCED',cpu_millicores=100,memory_request_mib=64,
                                           ack_monotonic_ns=NS,enforced_monotonic_ns=2*NS)],0,4)
    assert result['mean_cpu_requested_cores']==pytest.approx(.325)
    assert result['mean_cpu_allocated_cores']==pytest.approx(.55)
    assert result['memory_utilization_efficiency']==pytest.approx(2)


def create_intent(root, name, p, ordinal, replacement=None, snapshot_sha="frozen"):
    run=root/'attempts'/name;run.mkdir(parents=True)
    (root/'issued').mkdir(exist_ok=True)
    record=dict(plan=p,snapshot_sha256=snapshot_sha,replacement=replacement,ordinal=ordinal)
    publish_record(run/'intent.json',record);publish_record(root/'issued'/f'{name}.json',record)
    return run


def test_interrupted_resume_two_global_replacements_and_tamper(tmp_path):
    p=plan('primary',sequence=1)
    run=create_intent(tmp_path,'001',p,1)
    with pytest.raises(ValueError,match='unresolved_attempt'):completed_attempts(tmp_path)
    fail=dict(status='HARNESS_FAILED',metrics=None,measurement_seconds=100)
    seal_attempt(run,fail)
    with pytest.raises(ValueError,match='explicit_exogenous'):next_attempt(completed_attempts(tmp_path),p,'frozen',None)
    for i in (2,3):
        approval=dict(authorization_id=f'review-{i}',evidence='fixture',exogenous=True,failed_terminal_sha256=file_sha256(run/'terminal.json'))
        assert next_attempt(completed_attempts(tmp_path),p,'frozen',approval)==approval
        run=create_intent(tmp_path,f'{i:03d}',p,i,approval);seal_attempt(run,fail)
    with pytest.raises(ValueError,match='explicit_exogenous'):next_attempt(completed_attempts(tmp_path),p,'frozen',approval)
    (run/'intent.json').chmod(0o644);(run/'intent.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):completed_attempts(tmp_path)


def test_resume_does_not_rerun_completed_or_substitute_snapshot(tmp_path):
    p=plan('primary',sequence=1);run=create_intent(tmp_path,'001',p,1)
    seal_attempt(run,dict(status='COMPLETE',metrics={},measurement_seconds=1800))
    attempts=completed_attempts(tmp_path)
    with pytest.raises(ValueError,match='next_frozen'):next_attempt(attempts,p,'frozen',None)
    assert next_attempt(attempts,plan('primary',sequence=2),'frozen',None) is None
    with pytest.raises(ValueError,match='substitution'):next_attempt(attempts,plan('primary',sequence=2),'changed',None)


def test_analysis_uses_three_pairs_and_marks_missing(inputs):
    design,library,bootstrap=inputs;snapshots,_=compile_snapshots(library,bootstrap,design)
    attempts=[dict(sequence=i,status='COMPLETE',metrics={'primary':{'slo_violation_rate':i/20}}) for i in range(1,19)]
    r=paired_analysis(attempts,snapshots)
    assert len(r['rows'])==18 and len(r['contrasts'])==6
    assert all(len(x['estimates']['slo_violation_rate']['differences'])==3 for x in r['contrasts'])
    r=paired_analysis(attempts[1:],snapshots)
    assert any(x['estimates']['slo_violation_rate']['status']=='NOT_ESTIMABLE' for x in r['contrasts'])
    assert any(x['target_status']=='STRUCTURAL_EQUAL_TARGET' and not x['identifies_target_effect'] for x in r['contrasts'])


def test_reference_loader_rejects_fixture_scope(tmp_path,inputs):
    design,_,_=inputs
    publish_record(tmp_path/'intent.json',{'fixture':True})
    publish_record(tmp_path/'manifest.json',dict(plan=plan('reference',phase='low2'),scope=FIXTURE,origin_wall_ns=0))
    seal_attempt(tmp_path,dict(status='COMPLETE',measurement_origin_wall_ns=0))
    with pytest.raises(ValueError,match='unqualified_reference_run'):
        reference_library([tmp_path],design,load_contract(ROOT))


def test_complete_offline_manifest_sequence(tmp_path,inputs):
    design,library,bootstrap=inputs
    snapshots,_=compile_snapshots(library,bootstrap,design)
    digest=fingerprint(snapshots)
    for c in cells():
        p=plan('primary',sequence=c['sequence'])
        prior=completed_attempts(tmp_path)
        assert next_attempt(prior,p,digest,None) is None
        run=create_intent(tmp_path,f"{c['sequence']:03d}",p,c['sequence'],snapshot_sha=digest)
        # Fixture manifests cannot enter the measured reference/library gates.
        publish_record(run/'manifest.json',dict(scope=FIXTURE, plan=p, snapshot_sha256=digest,
                                              runtime_identity=f"fixture-{c['sequence']}"))
        seal_attempt(run,dict(status='COMPLETE',measurement_seconds=1800,
                              metrics={'primary':{'slo_violation_rate':c['sequence']/20}}))
    attempts=completed_attempts(tmp_path)
    assert len(attempts)==18
    integration=create_intent(tmp_path,'019',plan('integration'),19)
    publish_record(integration/'manifest.json',dict(scope=FIXTURE,plan=plan('integration')))
    seal_attempt(integration,dict(status='COMPLETE',measurement_seconds=12600,
        metrics={},integration='NO_OP_OBJECTIVE_NOT_DEMONSTRATED'))
    with pytest.raises(ValueError,match='single_reference_or_integration'):
        next_attempt(completed_attempts(tmp_path),plan('integration'),None,None)


def test_snapshot_digest_and_file_tamper_fail_before_donor_read(tmp_path,inputs):
    from dynapm.scripts.task41_bounded_v8 import read_bundle
    design,_,_=inputs
    path=tmp_path/'snapshots';path.mkdir()
    for name in ['library.json','snapshots.json','maintenance.json']:
        publish_record(path/name,{})
    publish_record(path/'FROZEN',{p.name:file_sha256(p) for p in path.iterdir()})
    expected=file_sha256(path/'FROZEN')
    with pytest.raises(ValueError,match='reviewed_snapshot_digest'):
        read_bundle(tmp_path,'wrong',design,'fixture',[])
    (path/'snapshots.json').chmod(0o644);(path/'snapshots.json').write_text('{"tampered":true}')
    with pytest.raises(ValueError,match='snapshot_bundle_tampered'):
        read_bundle(tmp_path,expected,design,'fixture',[])


def test_fake_kube_actuation_checks_allocated_spec_and_cgroup():
    import copy
    import io
    import json
    import time
    from dynapm.tests.test_outcome_taxonomy import node_fixture
    p,n=node_fixture()
    target=Target(200,128)
    kube=Mock()
    kube.pod.side_effect=lambda:copy.deepcopy(p)
    def patch(args,**kwargs):
        assert args[:5]==['patch','pod','application','--subresource=resize','--type=strategic']
        body=json.loads(args[6]);assert body['metadata']['uid']==p['metadata']['uid']
        r=body['spec']['containers'][0]['resources'];assert r==target.resources()
        p['spec']['containers'][0]['resources']=r
        p['metadata']['generation']+=1;p['status']['observedGeneration']=p['metadata']['generation']
        p['status']['containerStatuses'][0].update(resources=r,allocatedResources=r['requests'])
        return json.dumps(p)
    kube.call.side_effect=patch
    observer=Mock()
    def observe():
        now=time.monotonic_ns()
        return dict(n,start_monotonic_ns=now,end_monotonic_ns=now,
            values=dict(n['values'],**{'cpu.max':'20000 100000','memory.min':'0','memory.low':'0','memory.swap.current':'0'}))
    observer.enforcement.side_effect=observe
    guard=Mock();events=[]
    r=actuate(kube,observer,p['metadata']['uid'],target,io.StringIO(),events.append,guard)
    assert r['status']=='ENFORCED' and r['actuation_latency_seconds'] is not None
    r=actuate(kube,observer,p['metadata']['uid'],target,io.StringIO(),events.append,guard)
    assert r['status']=='NO_OP' and r['actuation_latency_seconds'] is None and kube.call.call_count==1



def test_pinned_cached_images_use_node_digest_and_parent_image_ids():
    node = 'kindest/node:v1.35.8@sha256:manifest'
    images = ['app:local','prom:local',node]
    parent = {'app:local':'sha256:app','prom:local':'sha256:prom'}
    node_details = {'Id':'sha256:node','RepoDigests':['docker.io/kindest/node@sha256:manifest']}
    def inspect(args, *, timeout):
        name = args[-1]
        return json.dumps([node_details if name==node else {'Id':parent[name]}])
    commands = Mock()
    commands.run.side_effect = inspect
    assert pinned_images(commands,images,parent) == dict(parent, **{node:'sha256:node'})
    node_details['RepoDigests'] = ['kindest/node@sha256:changed']
    with pytest.raises(ValueError,match='pinned_kind_node_digest_missing'):
        pinned_images(commands,images,parent)
