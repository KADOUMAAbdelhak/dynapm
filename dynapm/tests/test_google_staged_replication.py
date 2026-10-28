"""Synthetic V4D validation only. Never evaluate the real Google cohorts."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import numpy as np
import pandas as pd
import pytest

from dynapm.core.provenance import (canonical_json,fingerprint,file_sha256,read_json,
    prepare_experiment,CohortManifest,CohortEntity)
from dynapm.core.run_store import RunSession,check_cache,write_json
from dynapm.data.manifests import build_dataset_manifest,check_dataset
from dynapm.data.google2019_clock import (STEP_US as S,observation_frame,
    visible_observations,trailing_observations,forward_truth_observations)
from dynapm.experiments import google_replication as gr
from dynapm.experiments.google_staged_design import (frozen_design,DESIGN_PATH,
    E_BINDING,G_BINDING,E_COHORT_SHA)
from dynapm.experiments.google2019_protocol_validation import select_cohort
from dynapm.experiments.google2019_local_canonical import SCHEMA,NORMALIZATION
from dynapm.experiments.google2019_availability_validation import SCHEMA as AUDIT_SCHEMA

REPO=Path(__file__).resolve().parents[2]

@pytest.fixture(scope='module')
def design():return frozen_design(REPO)


def synthetic(n=720,cell='e',cid=1,idx=0):
    b=np.arange(n,dtype=np.int64)*S
    return pd.DataFrame(dict(cell=cell,collection_id=cid,instance_index=idx,
        timestamp_us=b,source_start_time_us=b,source_end_time_us=b+S,
        cpu_utilization=.7+.4*np.sin(np.arange(n)/29),
        memory_utilization=.8+.3*np.cos(np.arange(n)/73)))


@pytest.fixture(scope='module')
def answer(design):
    return gr.run_google_entity(synthetic(),'e',1,0,gr.google_config('e',design),design)


def test_prospective_frozen_design_and_statistics(design):
    assert design['stages']['A']['exact_entities']==1000
    assert design['stages']['A']['cohort_sha256']==E_COHORT_SHA
    assert design['stages']['B']['required_regardless_of_e_direction']
    assert design['commitments']['no_method_config_statistics_or_cohort_rule_changes_after_e']
    assert design['statistics']['bootstrap_repetitions']==10000
    assert design['statistics']['bootstrap_seed']==20251022
    assert design['statistics']['wilcoxon_zero_method']=='wilcox'
    assert design['statistics']['confidence_level']==.95
    assert len(design['comparison_families'])==3
    assert design['cross_cell_synthesis']['no_opportunistic_pooling']
    assert canonical_json(gr.google_config('g',design))==canonical_json(gr.google_config('g',deepcopy(design)))


@pytest.mark.parametrize('change',['period','methods','statistics','cadence','window','initialization'])
def test_configuration_is_bound_to_execution(design,change):
    c=gr.google_config('e',design)
    if change=='period':c=replace(c,policies=(c.policies[0],replace(c.policies[1],periodic_interval_hours=9),*c.policies[2:]))
    if change=='methods':c=replace(c,policies=c.policies[:-1])
    if change=='statistics':c=replace(c,statistics=replace(c.statistics,bootstrap_seed=7))
    if change=='cadence':c=replace(c,data=replace(c.data,evaluation_cadence_seconds=43200))
    if change=='window':c=replace(c,policies=(c.policies[0],replace(c.policies[1],observation_window_hours=12),*c.policies[2:]))
    if change=='initialization':c=replace(c,policies=(replace(c.policies[0],parameters={'initialization':'wrong'}),*c.policies[1:]))
    with pytest.raises(ValueError,match='config_execution_mismatch'):
        gr.prepare_google_inputs(synthetic(),'e','1:0',c,design)


def test_exact_five_method_matrix_and_factory_periods(answer,design):
    rows=pd.DataFrame(answer['rows']).set_index('method_id')
    assert set(rows.index)=={'static','pw_12h','pw_6h','pw_3h','full_rewrite'}
    for h in (12,6,3):assert rows.loc[f'pw_{h}h','period_hours_executed']==h
    assert rows.loc['pw_3h','n_refresh_events']>rows.loc['pw_6h','n_refresh_events']>rows.loc['pw_12h','n_refresh_events']
    assert gr.google_config('e',design).model.family=='unused-observation-only'


def test_accounting_and_identical_verified_reads(answer):
    rows=pd.DataFrame(answer['rows']);rec=answer['evaluations'];events=answer['events']
    assert rows.n_initialization_events.eq(1).all()
    assert rows.n_field_writes.eq(4*rows.n_refresh_events).all()
    assert rows.query("method_id=='static'").n_refresh_events.eq(0).all()
    assert rows.query("method_id.str.startswith('pw_')",engine='python').eval('n_refresh_events==n_periodic_refreshes').all()
    assert rows.query("method_id=='full_rewrite'").eval('n_refresh_events==n_full_rewrite_refreshes').all()
    assert rows.evaluation_stamp_fingerprint.nunique()==rows.truth_fingerprint.nunique()==1
    reference=None
    for _,g in rec.groupby('method_id'):
        truth=g[['eval_timestamp','truth_cpu_class','truth_memory_class','truth_cpu_p95','truth_memory_p95']].reset_index(drop=True)
        if reference is not None:pd.testing.assert_frame_equal(reference,truth)
        reference=truth
    assert not events.duplicated(['method_id','actual_commit_time']).any()
    assert rec.query("method_id=='pw_12h'").profile_age_hours.gt(0).any()
    assert rec.cpu_p95_abs_err.notna().all()
    assert len(answer['rows'])==5 and answer['diagnostics']['resource_units']=='request_normalized_ratio'


def test_availability_and_exact_288_slots(design):
    raw=synthetic();f=observation_frame(raw);r=350*S
    assert visible_observations(f,r-1).source_end_time_us.le(r-1).all()
    trailing=trailing_observations(f,r);truth=forward_truth_observations(f,r,r+288*S)
    assert len(trailing)==len(truth)==288
    assert trailing.analysis_slot_close_us.tolist()==list(range(r-287*S,r+S,S))
    assert truth.analysis_slot_close_us.tolist()==list(range(r+S,r+289*S,S))
    assert trailing.source_end_time_us.max()<=r
    with pytest.raises(ValueError,match='not_elapsed'):forward_truth_observations(f,r,r+288*S-1)
    # The aggregate which starts at r cannot affect bootstrap or a state read at r.
    other=raw.copy();other.loc[other.source_start_time_us.ge(r),['cpu_utilization','memory_utilization']]=1e9
    pd.testing.assert_frame_equal(trailing,trailing_observations(observation_frame(other),r))
    c=gr.google_config('e',design)
    a,_=gr.prepare_google_inputs(raw,'e','1:0',c,design)
    b,_=gr.prepare_google_inputs(other,'e','1:0',c,design)
    assert a.cpu_thresholds==b.cpu_thresholds and a.mem_thresholds==b.mem_thresholds
    assert a.profile.static.provisioned_cpu_cores is None and a.profile.static.provisioned_ram_gb is None


def test_missing_read_and_commit_before_read(design):
    raw=synthetic();config=gr.google_config('e',design)
    # stream anchor q=217; first hourly read after it q=229 has no sample.
    raw=raw[raw.timestamp_us.ne(228*S)]
    result=gr.run_google_entity(raw,'e',1,0,config,design)
    t=pd.Timestamp(229*S,unit='us')
    rec=result['evaluations']
    assert rec.loc[rec.eval_timestamp.eq(t),'method_id'].nunique()==5
    assert rec.loc[rec.eval_timestamp.eq(t),'last_refresh_actual_commit_time'].lt(t).all()
    t=pd.Timestamp((217+36)*S,unit='us')
    full=rec[rec.eval_timestamp.eq(t)&rec.method_id.eq('full_rewrite')]
    assert len(full)==1 and full.profile_age_seconds.eq(0).all()
    # PW retains its frozen stricter 96-slot gate after the missing sample.
    assert rec[rec.eval_timestamp.eq(t)&rec.method_id.eq('pw_3h')].profile_age_seconds.gt(0).all()


def test_pw96_gate_and_delayed_grid_uses_completed_slots(design):
    raw=synthetic().drop(index=280);config=gr.google_config('e',design)
    result=gr.run_google_entity(raw,'e',1,0,config,design)
    events=result['events'];pw6=events[events.method_id.eq('pw_6h')]
    # q=289 tick lacks 96 complete slots; it resumes q=377, anchored nominal q=361.
    event=pw6.iloc[0]
    assert pd.Timestamp(event.actual_commit_time)==pd.Timestamp(377*S,unit='us')
    assert pd.Timestamp(event.nominal_scheduled_time)==pd.Timestamp(361*S,unit='us')
    assert result['evaluations'].groupby('method_id').size().nunique()==1


@pytest.mark.parametrize('kind',['empty','oversized','duplicate','mixed_cell','unsorted'])
def test_bounded_cohort_enforcement(kind):
    records=[dict(cell='e',collection_id=i,instance_index=0) for i in range(2)]
    if kind=='empty':records=[]
    if kind=='oversized':records=[dict(cell='e',collection_id=i,instance_index=0) for i in range(1001)]
    if kind=='duplicate':records.append(records[0])
    if kind=='mixed_cell':records[0]['cell']='g'
    if kind=='unsorted':records.reverse()
    with pytest.raises(ValueError):gr._cohort_ids({'entities':records},'e')


def test_e_g_selection_independent_no_backfill_and_outcomes_ignored(design):
    rule=design['cohort_selection_rule']
    data=pd.DataFrame([dict(cell=c,collection_id=i,instance_index=0,nominal_protocol_eligible=True) for c,n in [('e',1005),('g',3)] for i in range(n)])
    chosen=select_cohort(data,rule)
    assert chosen.groupby('cell').size().to_dict()=={'e':1000,'g':3}
    other=data.assign(cpu_utilization=1e12,method_result='favorable',volatility=7)
    pd.testing.assert_frame_equal(chosen,select_cohort(other,rule))
    pd.testing.assert_frame_equal(chosen[chosen.cell.eq('g')].reset_index(drop=True),select_cohort(data[data.cell.eq('g')],rule))
    before=canonical_json(gr.google_config('g',design))
    e_outcomes={'direction':'negative','selected':0} # never an argument to Stage-B config
    assert e_outcomes and canonical_json(gr.google_config('g',design))==before


def test_real_g_unavailable_refused_before_any_execution(design):
    assert not (REPO/G_BINDING).exists()
    with pytest.raises(ValueError,match='g_validated_cohort_unavailable'):
        gr.load_stage_inputs(REPO,'g',REPO/'not-an-input.json')


@pytest.fixture
def local_stage(tmp_path,design,monkeypatch):
    """Fully synthetic corrected generation with checked audit/cohort lineage."""
    root=tmp_path/'repo';root.mkdir();(root/'configs').mkdir()
    gen=root/'canonical';(gen/'canonical_usage').mkdir(parents=True)
    synthetic(cell='g').to_parquet(gen/'canonical_usage/part_000.parquet',index=False)
    part=dict(path='canonical_usage/part_000.parquet',sha256=file_sha256(gen/'canonical_usage/part_000.parquet'))
    canonical_sha=fingerprint([part])
    write_json(gen/'manifest.json',dict(schema_version=SCHEMA,normalization_version=NORMALIZATION,status='VERIFIED',
        artifacts=[part],canonical_dataset_sha256=canonical_sha,partitions=1))
    write_json(gen/'SUCCESS',dict(manifest_sha256=file_sha256(gen/'manifest.json')))
    audit=root/'audit';audit.mkdir()
    metadata=pd.DataFrame([dict(cell='g',collection_id=1,instance_index=0,nominal_protocol_eligible=True,
        observations=720,first_timestamp_us=S,last_timestamp_us=720*S,globally_verifiable_origins=18)])
    metadata.to_parquet(audit/'eligibility.parquet',index=False)
    selected=select_cohort(metadata,design['cohort_selection_rule'])
    cohort=dict(cell='g',entities=selected.to_dict('records'),protocol_fingerprint=design['protocol']['protocol_fingerprint'],
        canonical_sha256=canonical_sha,clock_contract_sha256=design['protocol']['clock_contract_sha256'],
        cohort_rule_sha256=design['cohort_selection_rule_sha256'])
    write_json(audit/'cohort.json',cohort)
    artifacts=[dict(path=name,sha256=file_sha256(audit/name)) for name in ['cohort.json','eligibility.parquet']]
    write_json(audit/'manifest.json',dict(schema_version=AUDIT_SCHEMA,artifacts=artifacts,
        canonical_sha256=canonical_sha,protocol_fingerprint=design['protocol']['protocol_fingerprint'],
        summary=dict(disposition='AVAILABILITY_CONTRACT_READY',timing=dict(ambiguous_rows=0),incomplete_bootstrap_rows=0,incomplete_rows_at_stream_anchor=0)))
    write_json(audit/'SUCCESS',dict(manifest_sha256=file_sha256(audit/'manifest.json')))
    binding=dict(schema_version='google2019-stage-input-binding-v1',cell='g',status='AVAILABILITY_CONTRACT_READY',
        protocol_fingerprint=cohort['protocol_fingerprint'],cohort_rule_sha256=cohort['cohort_rule_sha256'],
        canonical_path='canonical',canonical_sha256=canonical_sha,canonical_manifest_sha256=file_sha256(gen/'manifest.json'),
        clock_audit_path='audit',clock_audit_manifest_sha256=file_sha256(audit/'manifest.json'),
        cohort_path='audit/cohort.json',cohort_sha256=file_sha256(audit/'cohort.json'),member_records_sha256=fingerprint(cohort['entities']),
        eligibility_path='audit/eligibility.parquet',eligibility_sha256=file_sha256(audit/'eligibility.parquet'))
    write_json(root/G_BINDING,binding)
    monkeypatch.setattr(gr,'frozen_design',lambda repo:design)
    return root,audit/'cohort.json',gen


def test_synthetic_stage_lineage_and_required_explicit_cohort(local_stage):
    repo,cohort,gen=local_stage
    b=gr.load_stage_inputs(repo,'g',cohort)
    assert len(b['entities'])==1 and b['cell']=='g'
    assert next(gr._entity_frames(b))[1].cell.eq('g').all()
    with pytest.raises(ValueError,match='explicit_frozen_cohort'):gr.load_stage_inputs(repo,'g',repo/'other.json')


def test_superseded_canonical_rejected(local_stage):
    repo,cohort,gen=local_stage;m=read_json(gen/'manifest.json');m['normalization_version']='superseded-v1'
    write_json(gen/'manifest.json',m)
    with pytest.raises(ValueError,match='old_or_unsupported'):gr.load_stage_inputs(repo,'g',cohort)


def test_frozen_cohort_tamper_rejected(local_stage):
    repo,cohort,gen=local_stage;c=read_json(cohort);c['entities']=[];write_json(cohort,c)
    with pytest.raises(ValueError,match='cohort_hash'):gr.load_stage_inputs(repo,'g',cohort)


def test_parquet_shard_inventory_and_mutation(tmp_path):
    d=tmp_path/'canonical_usage';d.mkdir();synthetic(3).to_parquet(d/'part_000.parquet',index=False)
    m=build_dataset_manifest(tmp_path,dataset_id='fixture',source_name='fixture',trace_names=('canonical_usage',),schema_identity='test',selection='parquet-shards-v1')
    assert m.files[0].role=='entity_shard' and m.files[0].entity_id is None
    check_dataset(tmp_path,m)
    (d/'unexpected.txt').write_text('unversioned')
    with pytest.raises(ValueError,match='non-Parquet'):check_dataset(tmp_path,m)


def test_managed_outputs_statistics_and_cache_integrity(local_stage,tmp_path,answer,design):
    repo,cohort_path,gen=local_stage
    b=gr.load_stage_inputs(repo,'g',cohort_path)
    config,dataset,cohort=gr.provenance_inputs(b)
    assert config.preprocessing['frozen_cohort_sha256']==file_sha256(cohort_path)
    assert cohort.entities[0].trace=='g' and cohort.entities[0].entity_id=='1:0'
    (repo/'tracked.txt').write_text('synthetic source only\n');(repo/'.gitignore').write_text('results/\n')
    for args in [('init','-b','dynapm'),('add','.'),('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','synthetic')]:
        subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
    exp,env=prepare_experiment(repo,gen,config,dataset,cohort,{'statistics':20251022})
    # Use the identical production entity evaluator, on synthetic g only.
    out=gr.run_google_entity(synthetic(cell='g'),'g',1,0,gr.google_config('g',design),design)
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=gen,purpose='smoke',required_outputs=gr.output_specs(b['entities'])) as session:
        gr.write_entity_outputs(session,b['entities'][0],out)
        gr.write_analysis(session,out['rows'],design,b['binding'])
        session.complete()
    assert check_cache(session.path,exp,'smoke').reusable
    assert not check_cache(session.path,exp,'claim').reusable
    assert read_json(session.path/'outputs/family_inference.json')['bootstrap_repetitions']==10000
    inference=pd.read_parquet(session.path/'outputs/family_inference.parquet')
    assert len(inference)==30 and inference.n_pairs.eq(1).all()
    changed=replace(exp,config=replace(exp.config,statistics=replace(exp.config.statistics,bootstrap_seed=1)))
    assert not check_cache(session.path,changed,'smoke').reusable
    copied=tmp_path/'tampered-copy';shutil.copytree(session.path,copied)
    with (copied/'outputs/per_entity_results.parquet').open('ab') as f:f.write(b'tamper')
    assert 'output_hash_mismatch' in check_cache(copied,exp,'smoke').reasons
    assert check_cache(session.path,exp,'smoke').reusable


def test_cross_cell_synthesis_predefined_no_pooling():
    base=dict(family=['F1']*4,treatment=['pw_3h']*4,control=['static']*4,endpoint=list('abcd'),
        mean=[1.,-1.,0.,1.],median=[1.,-1.,0.,1.],mean_ci_low=[0.]*4,mean_ci_high=[2.]*4,median_ci_low=[0.]*4,median_ci_high=[2.]*4)
    e=pd.DataFrame(base);g=e.copy();g['mean']=[2.,-2.,0.,-1.]
    result=gr.cross_cell_synthesis(e,g)
    assert not result['pooled_inference']
    assert [x['direction'] for x in result['rows']]==['same_positive','same_negative','same_zero','discordant_or_one_zero']
    with pytest.raises(ValueError,match='missing_cross_cell'):gr.cross_cell_synthesis(e,g.iloc[:-1])


def test_production_managed_execute_on_synthetic_stage_only(local_stage,design):
    repo,cohort_path,gen=local_stage
    # This is a one-entity generated fixture, never a real cell/cohort.
    (repo/'.gitignore').write_text('results/\n')
    for args in [('init','-b','dynapm'),('add','.'),('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','synthetic')]:
        subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
    bound=gr.load_stage_inputs(repo,'g',cohort_path)
    config,dataset,cohort=gr.provenance_inputs(bound)
    exp,_=prepare_experiment(repo,gen,config,dataset,cohort,{'statistics':20251022})
    path=gr.execute(repo,'g',cohort_path)
    assert check_cache(path,exp,'claim').reusable
    assert gr.execute(repo,'g',cohort_path,reuse_run=path)==path
    manifest=read_json(path/'manifest.json')
    assert manifest['purpose']=='claim' and manifest['status']=='SUCCESS'
    assert read_json(path/'outputs/run_diagnostics.json')['method_entity_runs']==5
    assert not subprocess.check_output(['git','-C',str(repo),'status','--short'])


def test_scientific_source_freeze_rejects_change(tmp_path,design):
    from dynapm.experiments.google_staged_design import RUNTIME_FILES
    required=list(RUNTIME_FILES)+[DESIGN_PATH,'configs/google2019_staged_replication_v1.yaml',E_BINDING,
        'configs/google2019_replication_cohort_v2.json','configs/google2019_v4c1_validation_record.json',
        'configs/google_clusterdata_2019_replication_protocol_v1.json',
        'configs/google_clusterdata_2019_replication_protocol_v2.json','configs/google_clusterdata_2019_replication_protocol_v2.yaml']
    for name in required:
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/name,target)
    binding=read_json(REPO/E_BINDING);target=tmp_path/binding['canonical_path']/'manifest.json'
    target.parent.mkdir(parents=True);shutil.copyfile(REPO/binding['canonical_path']/'manifest.json',target)
    assert frozen_design(tmp_path)==design
    with (tmp_path/'dynapm/core/ground_truth.py').open('a') as f:f.write('\n# changed after freeze\n')
    with pytest.raises(ValueError,match='scientific_source_mismatch'):frozen_design(tmp_path)


def test_preflight_cli_defaults_to_no_execution(monkeypatch,design,capsys):
    from dynapm.scripts import task30_google_replication as cli
    monkeypatch.setattr('sys.argv',['task30','--cell','e','--cohort-manifest','explicit.json'])
    monkeypatch.setattr(cli,'load_stage_inputs',lambda *args:dict(entities=[1],design=design))
    def forbidden(*args,**kwargs):raise AssertionError('preflight cannot execute outcomes')
    monkeypatch.setattr(cli,'execute',forbidden)
    cli.main()
    assert 'INPUTS_VERIFIED_NO_OUTCOMES' in capsys.readouterr().out
