"""Offline conformance fixtures; no cluster, application or scientific data acquisition."""
import copy
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

from dynapm.system_validation.bounded_v8 import plan, offers, cells
from dynapm.system_validation.service_primary import (
    primary_config, validate_t0_handoff, storage_requirement, SLOT_BUDGET,
    GENERATOR_BUDGET, RESERVE, campaign)
from dynapm.system_validation.service_checkpoint import Checkpoint, next_slot
from dynapm.system_validation import primary_service_generator as primary
from dynapm.system_validation import service_generator as qualified
from dynapm.core.provenance import canonical_json, fingerprint, file_sha256

DOMAIN=dict(boot_id='linux-boot',time_namespace='time:[1]')
URL='http://application.fixture.svc.cluster.local:8080'


def test_frozen_generator_configuration_all_cells():
    for cell in cells():
        p=plan('primary',sequence=cell['sequence'])
        cfg=primary_config(p,'unit',URL,{'profile':'fixed'},DOMAIN)
        assert [x for _,x in qualified.offers(cfg)]==list(offers(p))
        assert cfg['warmup_seconds']==1800 and cfg['lead_seconds']==10
        assert cfg['maximum_record_bytes']==64*2**20
        assert 'origin_monotonic_ns' not in cfg  # Chosen in the generator domain only.


def t0_fixture():
    cfg=primary_config(plan('primary',sequence=1),'unit',URL,{},DOMAIN)
    start=dict(DOMAIN,origin_monotonic_ns=900_000_000_000_000)
    marker=dict(DOMAIN,run_id='unit',origin_monotonic_ns=start['origin_monotonic_ns'],
                emitted_monotonic_ns=start['origin_monotonic_ns']+1000,snapshot_sha256=cfg['snapshot_sha256'])
    envelope=dict(marker=marker,watch_start_monotonic_ns=start['origin_monotonic_ns']-10**9,
                  watch_end_monotonic_ns=marker['emitted_monotonic_ns']+10_000_000)
    return cfg,start,envelope


def test_t0_event_brackets_but_never_equates_epochs():
    cfg,start,envelope=t0_fixture()
    handoff=validate_t0_handoff(cfg,start,envelope,100,1_100_000_100)
    assert handoff['host_t0_admission_monotonic_ns']==1_100_000_100
    assert handoff['epoch_conversion_used'] is False
    assert start['origin_monotonic_ns']>handoff['host_receipt_monotonic_ns']


@pytest.mark.parametrize('failure',['late_watch','wrong_snapshot','wrong_boot','bad_order','too_wide'])
def test_t0_invalid_program_order_or_identity_fails(failure):
    cfg,start,e=t0_fixture();before,after=100,1_100_000_100
    if failure=='late_watch':e['watch_start_monotonic_ns']=start['origin_monotonic_ns']+1
    if failure=='wrong_snapshot':e['marker']['snapshot_sha256']='other'
    if failure=='wrong_boot':e['marker']['boot_id']='other'
    if failure=='bad_order':e['watch_end_monotonic_ns']=start['origin_monotonic_ns']-1
    if failure=='too_wide':after=before+2*10**9+1
    with pytest.raises(ValueError):validate_t0_handoff(cfg,start,e,before,after)


def test_storage_includes_host_node_and_runtime_growth():
    assert storage_requirement(18)>RESERVE+18*SLOT_BUDGET+GENERATOR_BUDGET
    assert storage_requirement(18)/2**30==26.09375
    with pytest.raises(ValueError):storage_requirement(0)


def test_no_forwarding_in_primary_path_and_no_enforcement_gate_in_generator():
    from dynapm.system_validation import service_primary
    assert 'local_kind(' not in inspect.getsource(service_primary)
    assert "'port-forward'" not in inspect.getsource(service_primary)
    assert 'actuate(' not in inspect.getsource(primary)
    assert 'g.request(' in inspect.getsource(primary)
    assert 'g.offers(' in inspect.getsource(primary)


def test_full_frozen_generator_schedule_with_accelerated_fixture_clock(tmp_path,monkeypatch):
    # Pure fixture clock, explicitly not a physical duration/qualification claim.
    import math
    ticks=[10**15]
    class Event:
        def __init__(self):self.stopped=False
        def set(self):self.stopped=True
        def is_set(self):return self.stopped
        def wait(self,seconds=0):
            ticks[0]+=math.ceil(seconds*10**9)
            return self.stopped
    class Proc:
        def read_text(self):return 'linux-boot'
    actual_path=Path
    monkeypatch.setattr(primary,'Path',lambda p:Proc() if str(p)=='/proc/sys/kernel/random/boot_id' else actual_path(p))
    monkeypatch.setattr(primary,'time',SimpleNamespace(monotonic_ns=lambda:ticks[0],time_ns=lambda:ticks[0]+10**18))
    monkeypatch.setattr(primary,'threading',SimpleNamespace(Event=Event,Lock=__import__('threading').Lock,BoundedSemaphore=__import__('threading').BoundedSemaphore))
    monkeypatch.setattr(primary.os,'readlink',lambda _:DOMAIN['time_namespace'])
    monkeypatch.setattr(primary.os,'fsync',lambda _:None)
    monkeypatch.setattr(primary.signal,'signal',lambda *_:None)
    monkeypatch.setattr(primary.socket,'getaddrinfo',lambda *_a,**_kw:[(None,None,None,None,('10.0.0.1',8080))])
    def request(url,event,phase,origin):
        now=max(ticks[0],origin+event['offset_ns'])
        return dict(schema=qualified.SCHEMA,request_id=event['request_id'],offer=event,intended_phase=phase,
            sent_offset_ns=now-origin,completed_offset_ns=now-origin,completed_monotonic_ns=now,
            completed_wall_ns=now+10**18,scheduled_monotonic_ns=origin+event['offset_ns'],latency_ns=now-origin-event['offset_ns'],
            success=True,outcome='success',http_status=200,failure_layer=None,exception=None,retries=0)
    monkeypatch.setattr(qualified,'request',request)
    cfg=primary_config(plan('primary',sequence=1),'fixture',URL,{},DOMAIN)
    assert primary.run(cfg,tmp_path)==0
    from dynapm.system_validation.service_transport import validate_download
    records,start,done=validate_download(tmp_path,cfg)
    assert len(records)==34200 and done['completed_monotonic_ns']>=start['origin_monotonic_ns']+1800*10**9
    marker=json.loads((tmp_path/'T0.json').read_text())
    assert marker['emitted_monotonic_ns']>=start['origin_monotonic_ns']
    assert sum(r['offer']['offset_ns']<0 for r in records)==21600
    assert sum(r['offer']['offset_ns']>=0 for r in records)==12600


def test_real_campaign_orchestration_stops_seals_restarts_with_fresh_stack(tmp_path,monkeypatch):
    import dynapm.system_validation.service_primary as mod
    spec=dict(executor_commit='fixture',t0_policy='FROZEN_T0_INCLUDES_ENFORCEMENT_TRANSITION',host_amendment_path='one',host_amendment_sha256='one')
    calls=[]
    monkeypatch.setattr(mod,'source_binding',lambda *_:dict(executor_commit='fixture'))
    bundle=dict(snapshots=[dict(scenario=c['scenario'],method=c['method']) for c in cells()])
    def preflight(repo,root,spec,remaining):
        calls.append(('new_host_session',remaining,spec['host_amendment_sha256']))
        return dict(status='PASS',preflight_sha256=str(len(calls))),{},bundle,{}
    monkeypatch.setattr(mod,'preflight',preflight)
    def treatment(repo,run,planned,snapshot,design,environment,identity):
        calls.append(('fresh_cluster',planned['cell']['sequence']))
        run.mkdir(parents=True)
        paths={}
        for name in ('requests','endpoint','continuity'):
            p=run/(name+'.json');p.write_text(canonical_json(dict(fixture=True,name=name)))
            paths[name+'_path']=str(p)
        return dict(status='SEALED_VALID',**paths)
    monkeypatch.setattr(mod,'treatment',treatment)
    root=tmp_path/'campaign'
    state=campaign(tmp_path,root,spec,'DIAGNOSTIC_NON_CLAIM',max_slots=2)
    assert [s['status'] for s in state['slots'][:3]]==['SEALED_VALID','SEALED_VALID','PENDING']
    assert [c[1] for c in calls if c[0]=='fresh_cluster']==[1,2]
    spec=dict(spec,host_amendment_path='new-session',host_amendment_sha256='new-session')
    state=campaign(tmp_path,root,spec,'DIAGNOSTIC_NON_CLAIM',resume=True,max_slots=1)
    assert [c[1] for c in calls if c[0]=='fresh_cluster']==[1,2,3]
    assert calls[-2][2]=='new-session'
    # Stop boundary already reached: no additional preflight or cluster.
    previous=len(calls)
    campaign(tmp_path,root,spec,'DIAGNOSTIC_NON_CLAIM',resume=True,stop_after_slot=3)
    assert len(calls)==previous


def test_claim_cannot_start_without_qualification(tmp_path):
    with pytest.raises(ValueError,match='qualification'):
        campaign(tmp_path,tmp_path/'claim',{},'AMENDED_V8_PRIMARY')


def test_other_experiments_rejected_without_persisting_unrelated_arguments():
    from dynapm.system_validation.service_primary import experiment_processes
    rows="1 0 init\n10 1 shell dynapm.scripts.task48_v8_service_primary\n11 10 python -m dynapm.scripts.task48_v8_service_primary\n12 11 ps\n20 1 python -m dynapm.scripts.task42_google2019_cell_g\n21 1 editor personal-file\n"
    assert experiment_processes(rows,11)==[20]


def test_image_alias_resolution_preserves_frozen_objects_and_exact_ids():
    from dynapm.system_validation.service_primary import resolve_runtime_images
    design=dict(kubernetes=dict(application_image='app:frozen',prometheus_local_image='prom:frozen',node_image='kindest/node@sha256:node'))
    environment=dict(image_ids={'app:frozen':'sha256:app','prom:frozen':'sha256:prom'})
    original=copy.deepcopy((design,environment))
    runtime,resolved,aliases=resolve_runtime_images(design,environment)
    assert (design,environment)==original
    assert runtime['kubernetes']['application_image']=='docker.io/library/app:frozen'
    assert resolved['image_ids']['docker.io/library/app:frozen']=='sha256:app'
    assert aliases['app:frozen']['expected_image_id']=='sha256:app'
    assert runtime['kubernetes']['node_image']==design['kubernetes']['node_image']
    environment['image_ids']['docker.io/library/app:frozen']='sha256:wrong'
    with pytest.raises(ValueError,match='conflict'):resolve_runtime_images(design,environment)


def test_battery_mechanics_record_can_never_authorize_claims(tmp_path):
    from dynapm.system_validation.service_primary import BATTERY_SCOPE
    fake=dict(status='PASS',executor_commit='fixture',storage_certified=True,full_lifecycle_verified=True,
              claim_qualification_eligible=False,scope=BATTERY_SCOPE,schema='v8-primary-service-qualification-v1',
              qualification_mode='BATTERY_NON_QUALIFYING')
    with pytest.raises(ValueError,match='qualification'):
        campaign(tmp_path,tmp_path/'claim',dict(executor_commit='fixture'),'AMENDED_V8_PRIMARY',qualification=fake)
    with pytest.raises(ValueError,match='power_scope'):
        campaign(tmp_path,tmp_path/'claim',dict(power_mode='BATTERY_DIAGNOSTIC_ONLY'),'AMENDED_V8_PRIMARY',qualification=fake)


def test_strict_and_battery_power_guard_factories_are_separate(tmp_path):
    from dynapm.system_validation.service_primary import power_guard_for_scope,BATTERY_SCOPE
    from dynapm.system_validation.v8_host_identity import UUIDPowerGuard
    from dynapm.system_validation.battery_diagnostic_guard import BatteryDiagnosticGuard
    assert isinstance(power_guard_for_scope(tmp_path,{},'AMENDED_V8_PRIMARY'),UUIDPowerGuard)
    assert isinstance(power_guard_for_scope(tmp_path,{},'DIAGNOSTIC_NON_CLAIM'),UUIDPowerGuard)
    assert isinstance(power_guard_for_scope(tmp_path,{},BATTERY_SCOPE),BatteryDiagnosticGuard)
    with pytest.raises(ValueError):power_guard_for_scope(tmp_path,{},'implicit')


def test_nonqualifying_session_cannot_admit_strict_slot(tmp_path):
    from dynapm.system_validation.service_primary import BATTERY_SCOPE
    identity=dict(scope=BATTERY_SCOPE,executor_commit='fixture')
    root=tmp_path/'battery';root.mkdir()
    cp=Checkpoint(root,identity)
    session=dict(status='NON_QUALIFYING_DIAGNOSTIC_ADMISSION',preflight_sha256='nq',claim_qualification_eligible=False)
    cp.begin(cells()[0],'nq-only',session)
    strict_root=tmp_path/'strict';strict_root.mkdir()
    strict=Checkpoint(strict_root,dict(scope='DIAGNOSTIC_NON_CLAIM',executor_commit='fixture'))
    with pytest.raises(ValueError,match='preflight'):strict.begin(cells()[0],'strict',session)


@pytest.mark.parametrize('limit',[dict(max_slots=18),dict(stop_after_slot=18)])
def test_final_analysis_runs_even_at_explicit_last_stop(tmp_path,monkeypatch,limit):
    import dynapm.system_validation.service_primary as mod
    import dynapm.system_validation.bounded_v8_metrics as stats
    spec=dict(executor_commit='SYNTHETIC_FIXTURE',t0_policy='FROZEN_T0_INCLUDES_ENFORCEMENT_TRANSITION')
    monkeypatch.setattr(mod,'source_binding',lambda *_:dict(executor_commit='SYNTHETIC_FIXTURE'))
    snapshots=dict(snapshots=[dict(scenario=c['scenario'],method=c['method']) for c in cells()])
    monkeypatch.setattr(mod,'preflight',lambda *_:(dict(status='PASS',preflight_sha256='SYNTHETIC'),{},snapshots,{}))
    def treatment(repo,run,planned,*_):
        run.mkdir(parents=True)
        paths={}
        for name in ('requests','endpoint','continuity'):
            path=run/(name+'.json');path.write_text(canonical_json(dict(fixture=True)))
            paths[name+'_path']=str(path)
        return dict(status='SEALED_VALID',fixture=True,metrics=dict(primary={}),**paths)
    monkeypatch.setattr(mod,'treatment',treatment)
    snapshot_dir=tmp_path/'results/bounded_v8/campaign-v1/snapshots';snapshot_dir.mkdir(parents=True)
    for name in ('library.json','snapshots.json','maintenance.json'):
        (snapshot_dir/name).write_text(canonical_json(dict(fixture=True)))
    (snapshot_dir/'FROZEN').write_text(canonical_json({n:file_sha256(snapshot_dir/n) for n in ('library.json','snapshots.json','maintenance.json')}))
    monkeypatch.setattr(mod,'SNAPSHOTS',file_sha256(snapshot_dir/'FROZEN'))
    calls=[]
    def analysis(terminals,bundle):
        calls.append(terminals)
        assert [t['sequence'] for t in terminals]==list(range(1,19))
        return dict(fixture=True,physical_outcomes=False,count=len(terminals))
    monkeypatch.setattr(stats,'paired_analysis',analysis)
    qualification=dict(status='PASS',schema='v8-primary-service-qualification-v1',scope='DIAGNOSTIC_NON_CLAIM',
        qualification_mode='STRICT_AC_PRIMARY_LIFECYCLE',claim_qualification_eligible=True,full_lifecycle_verified=True,
        executor_commit='SYNTHETIC_FIXTURE',storage_certified=True)
    root=tmp_path/'campaign'
    state=campaign(tmp_path,root,spec,'AMENDED_V8_PRIMARY',qualification=qualification,**limit)
    assert len(calls)==1 and all(s['status']=='SEALED_VALID' for s in state['slots'])
    path=root/'paired-analysis.json';before=path.read_bytes()
    mod.finish_claim_analysis(tmp_path,root,state)
    assert path.read_bytes()==before
    path.write_text('{}')
    with pytest.raises(ValueError,match='analysis_tampered'):mod.finish_claim_analysis(tmp_path,root,state)
    state=copy.deepcopy(state);state['identity']['scope']='DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'
    with pytest.raises(ValueError,match='nonclaim_analysis'):mod.finish_claim_analysis(tmp_path,root,state)
