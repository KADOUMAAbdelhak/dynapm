"""Synthetic unit fixtures ONLY; simulated acquisition clocks are not measurements."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import shutil

import pandas as pd
import pytest

from dynapm.tests.test_provenance import inputs
from dynapm.tests.test_system_trial_preparation import unit_evidence,START,END,STEP
from dynapm.core.provenance import ExperimentManifest,read_json,file_sha256,EnvironmentProvenance
from dynapm.core.run_store import RunSession,OutputSpec,write_json
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.shared_bootstrap import (
    create_artifact as production_create_artifact,load_artifact,freeze_blocks,TreatmentRegistry,StartupEvidence,_parent_metadata)
from dynapm.system_validation.trial_preparation import measured_bootstrap

ROOT=Path(__file__).parents[2]

def create_artifact(*args,**kwargs):
    return production_create_artifact(*args,allow_unit_fixture=True,**kwargs)



@pytest.fixture
def acquisition(tmp_path,inputs,monkeypatch):
    """A managed metadata fixture with explicitly simulated 24h wall clocks."""
    repo,raw,base,env=inputs;d=frozen_spec(ROOT)
    env=EnvironmentProvenance.capture(execution_compatibility_keys=tuple(d['hardware']['compatibility_keys']))
    records=unit_evidence()
    for entry in records:
        for sample in entry['samples']:
            sample.update(cpu_limit_cores=1.,memory_limit_bytes=512*2**20)
    for e in records[:144]:
        for s in e['samples']:s['memory_working_set_bytes']=100*2**20
    b=measured_bootstrap(records,START,END,END,d)
    config=replace(base.config,analysis={'unit_test_fixture':True},preprocessing={'mode':'MEASURED_BOOTSTRAP_ONLY_V1','execution_environment':{'image_ids':{'workload':'UNIT_TEST_IMAGE_ONLY'}}})
    exp=replace(base,config=config,scientific_environment=env.scientific)
    import dynapm.core.run_store as store
    n=[0]
    def unit_clock():
        n[0]+=1
        return pd.Timestamp(START-900*10**9 if n[0]<=2 else END+10**9,tz='UTC').isoformat()
    monkeypatch.setattr(store,'utc_now',unit_clock)
    names=['plan','bootstrap_summary','diagnostics','power_guard','host_continuity_summary']
    specs=[OutputSpec('outputs/'+x+'.json','UNIT simulated metadata') for x in names]+[
        OutputSpec('outputs/bootstrap_samples.jsonl','UNIT synthetic samples, not real acquisition')]
    with RunSession(tmp_path/'acquisition',exp,env,repo=repo,dataset_root=raw,purpose='pilot',required_outputs=specs) as run:
        with (run.path/'outputs/bootstrap_samples.jsonl').open('w') as f:
            from dynapm.core.provenance import canonical_json
            for e in records:f.write(canonical_json(e)+'\n')
        write_json(run.path/'outputs/plan.json',dict(design=d,bootstrap_start_seconds=START//10**9,
            measurement_start_seconds=END//10**9,measurement_end_seconds=END//10**9,
            bootstrap_only=True,bootstrap_source_pod_uid='UNIT_SOURCE_POD'))
        write_json(run.path/'outputs/bootstrap_summary.json',dict(real_duration_seconds=86400,
            accepted_slots=288,missing_slots=0,evidence_sha256=b.evidence_sha256,source_pod_uid='UNIT_SOURCE_POD'))
        write_json(run.path/'outputs/diagnostics.json',dict(synthetic_bootstrap_used=False,real_bootstrap_complete=True))
        write_json(run.path/'outputs/power_guard.json',dict(status='RELEASED',release_confirmed=True,failure=None,
            schema_version='managed-macos-power-v1',context={'run_id':run.manifest.run_id}))
        write_json(run.path/'outputs/host_continuity_summary.json',dict(failure=None,
            schema_version='managed-macos-power-v1',maximum_absolute_drift_ns=0,maximum_checkpoint_gap_ns=5*10**9))
        run.complete()
    return run.path,d,tmp_path


def test_bootstrap_only_parent_materializes_deterministically_and_relocates(acquisition):
    parent,d,tmp=acquisition
    a=create_artifact(parent,tmp/'a',d);b=create_artifact(parent,tmp/'b',d)
    assert a.name==b.name
    assert create_artifact(parent,tmp/'a',d)==a
    m,boot=load_artifact(a,a.name,d)
    assert boot.accepted_slots==288 and m['source_pod_uid']=='UNIT_SOURCE_POD'
    assert not any('profile_final' in p.name or 'requests' in p.name for p in a.iterdir())
    assert read_json(a/'parent_plan.json')['measurement_end_seconds']==END//10**9
    moved=tmp/'moved';shutil.copytree(a,moved)
    assert load_artifact(moved,a.name,d)[0]==m


@pytest.mark.parametrize('name',['raw_samples.jsonl','parent_manifest.json','COMPLETE'])
def test_artifact_tampering_rejected(acquisition,name):
    parent,d,tmp=acquisition;a=create_artifact(parent,tmp/'a',d)
    with (a/name).open('a') as f:f.write(' ')
    with pytest.raises(ValueError):load_artifact(a,a.name,d)


def test_parent_tampering_not_upgraded_to_new_artifact(acquisition):
    parent,d,tmp=acquisition
    with (parent/'outputs/bootstrap_samples.jsonl').open('a') as f:f.write(' ')
    with pytest.raises(ValueError,match='parent_integrity'):create_artifact(parent,tmp/'a',d)


def test_synthetic_incomplete_short_and_unavailable_provenance_rejected(acquisition):
    parent,d,tmp=acquisition;m=read_json(parent/'manifest.json');summary=read_json(parent/'outputs/bootstrap_summary.json')
    plan=read_json(parent/'outputs/plan.json');diag=read_json(parent/'outputs/diagnostics.json')
    with pytest.raises(ValueError,match='real_bootstrap'):_parent_metadata(m,summary,plan,{**diag,'synthetic_bootstrap_used':True})
    with pytest.raises(ValueError,match='completed_clean'):_parent_metadata({**m,'status':'INCOMPLETE'},summary,plan,diag)
    with pytest.raises(ValueError,match='cover_real'):_parent_metadata({**m,'started_at':m['ended_at']},summary,plan,diag)
    with pytest.raises(ValueError,match='pod_identity'):_parent_metadata(m,{**summary,'source_pod_uid':'OTHER'},plan,diag)


def startup(i):
    return StartupEvidence(*[f'UNIT_NEW_{i}_{k}' for k in ('trial','pod','app','profile','controller','collector')],
        initial_runtime_refreshes=0,initial_observations=0,initial_resource_changes=0,pending_resize=False)


def test_all_five_share_history_but_keep_factory_semantics_and_isolation(acquisition):
    parent,d,tmp=acquisition;a=create_artifact(parent,tmp/'a',d)
    design=freeze_blocks([(a,a.name)],d,common_stable_prehistory=True,purpose='smoke')
    registry=TreatmentRegistry(design);origin=END+STEP
    adapters={method:registry.initialize(0,method,a,d,origin,startup(i),read_wall_ns=origin)
        for i,method in enumerate(design['methods'])}
    for adapter in adapters.values():
        assert adapter.policy.accounting_metrics()['n_initialization_events']==1
        assert adapter.policy.accounting_metrics()['n_refresh_events']==0
        assert adapter.shared_bootstrap['artifact_sha256']==a.name
    assert adapters['static'].policy.profile.dynamic.predicted_mem_p95_next_24h>adapters['pw_3h'].policy.profile.dynamic.predicted_mem_p95_next_24h
    assert adapters['static'].history.equals(adapters['pw_6h'].history)
    original=adapters['pw_6h'].history.iloc[0,0]
    adapters['static'].history.iloc[0,0]=999
    assert adapters['pw_6h'].history.iloc[0,0]==original
    assert file_sha256(a/'raw_samples.jsonl')==file_sha256(parent/'outputs/bootstrap_samples.jsonl')
    with pytest.raises(ValueError,match='duplicate'):registry.initialize(0,'static',a,d,origin,startup(99),read_wall_ns=origin)


def test_fresh_startup_and_no_future_artifact_injection(acquisition):
    parent,d,tmp=acquisition;a=create_artifact(parent,tmp/'a',d)
    block=freeze_blocks([(a,a.name)],d,common_stable_prehistory=True,purpose='smoke');r=TreatmentRegistry(block);q=END+STEP
    with pytest.raises(ValueError,match='fresh_treatment'):r.initialize(0,'static',a,d,q,replace(startup(0),initial_runtime_refreshes=1),read_wall_ns=q)
    with pytest.raises(ValueError,match='unavailable'):r.initialize(0,'static',a,d,END,startup(0),read_wall_ns=END)
    r.initialize(0,'static',a,d,q,startup(0),read_wall_ns=q)
    with pytest.raises(ValueError,match='identity_reuse'):r.initialize(0,'pw_6h',a,d,q,startup(0),read_wall_ns=q)
    with pytest.raises(ValueError,match='acquisition_instance'):r.initialize(0,'pw_6h',a,d,q,replace(startup(1),pod_uid='UNIT_SOURCE_POD'),read_wall_ns=q)


def test_independent_blocks_cannot_reuse_acquisition(acquisition):
    parent,d,tmp=acquisition;a=create_artifact(parent,tmp/'a',d)
    with pytest.raises(ValueError,match='independent'):freeze_blocks([(a,a.name),(a,a.name)],d,common_stable_prehistory=True,purpose='smoke')
    with pytest.raises(ValueError,match='explicit_common'):freeze_blocks([(a,a.name)],d,common_stable_prehistory=False)


def test_incomplete_or_symlinked_artifact_rejected(acquisition):
    parent,d,tmp=acquisition;a=create_artifact(parent,tmp/'a',d)
    (a/'COMPLETE').unlink()
    with pytest.raises(ValueError):load_artifact(a,a.name,d)
    linked=tmp/'link';linked.symlink_to(parent,target_is_directory=True)
    with pytest.raises(ValueError,match='symlinks'):create_artifact(linked,tmp/'b',d)


def test_unit_artifacts_cannot_be_promoted_to_scientific_inputs(acquisition):
    parent,d,tmp=acquisition
    with pytest.raises(ValueError,match="unit_fixture_not_scientific"):production_create_artifact(parent,tmp/"real",d)
    a=create_artifact(parent,tmp/"unit",d)
    assert load_artifact(a,a.name,d)[0]["data_kind"]=="UNIT_TEST_ONLY"
    with pytest.raises(ValueError,match="unit_artifact_forbidden"):freeze_blocks([(a,a.name)],d,common_stable_prehistory=True)
