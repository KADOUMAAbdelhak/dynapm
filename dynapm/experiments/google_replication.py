"""Shared staged Google evaluator. Real execution is opt-in; no acquisition APIs."""
from __future__ import annotations
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from dynapm.core.provenance import (DataConfig,ModelConfig,PolicyConfig,StatisticsConfig,
    ExperimentConfigProvenance,CohortEntity,CohortManifest,SourceProvenance,
    canonical_json,fingerprint,file_sha256,read_json,relative_path,utc_now,prepare_experiment)
from dynapm.core.run_store import RunSession,OutputSpec,check_cache,write_json
from dynapm.core.accounting import ACCOUNTING_METRICS,require_accounting_metrics
from dynapm.core.schema import StaticFields,DynamicFields,ProfileInstance
from dynapm.core.temporal import METRICS
from dynapm.data.google2019_clock import (observation_frame,bootstrap_partition,
    bootstrap_thresholds_at_read,forward_truth_observations,RESOURCES)
from dynapm.data.manifests import build_dataset_manifest
from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.core.ground_truth import derive_ground_truth_at_t
from dynapm.eval.replay import PreparedVM,replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.experiments.confirmatory_execution import factory_for,_periodic_delay_stats
from dynapm.experiments.confirmatory_estimation import (analyze_families,robustness_summaries,
    BOOTSTRAP_B,BOOTSTRAP_SEED,CI_LEVEL)
from dynapm.experiments.google2019_local_canonical import require_corrected_generation
from dynapm.experiments.google2019_availability_validation import validate_clock_audit
from dynapm.experiments.google2019_protocol_validation import select_cohort
from dynapm.experiments.google_staged_design import frozen_design,DESIGN_PATH,E_BINDING,G_BINDING

OUTPUTS={
    'design_binding.json':'prospective-staged-design-and-input-binding',
    'per_entity_results.parquet':'five-method-entity-fidelity-and-accounting',
    'paired_effects.parquet':'paired-entity-treatment-minus-control',
    'family_inference.parquet':'per-cell-f1-f2-f3-frozen-statistics',
    'family_inference.json':'per-cell-estimation-summary',
    'robustness_summary.json':'secondary-input-only-tertile-and-resource-descriptions',
    'cost_accounting_summary.json':'canonical-counters-directly-aggregated',
    'run_diagnostics.json':'coverage-invariants-and-stage-boundaries'}
EVENT_COLUMNS=['cell','vm_id','method_id','actual_commit_time','trigger','nominal_scheduled_time','fields_written','fields_changed']


def _local(repo,rel):
    repo=Path(repo).resolve();p=repo/relative_path(rel)
    for part in [p,*p.parents]:
        if part.is_symlink():raise ValueError('symlink_stage_input')
        if part==repo:break
    if not p.resolve().is_relative_to(repo):raise ValueError('stage_input_outside_repository')
    return p


def _cohort_ids(cohort,cell):
    records=cohort['entities'];keys=[]
    for e in records:
        if e['cell']!=cell:raise ValueError('cohort_cell_mismatch')
        cid,idx=e['collection_id'],e['instance_index']
        if type(cid) is not int or type(idx) is not int or cid<0 or idx<0:raise ValueError('invalid_entity_identity')
        keys.append((cid,idx))
    if not 1<=len(keys)<=1000 or len(set(keys))!=len(keys) or keys!=sorted(keys):
        raise ValueError('cohort_must_be_frozen_unique_sorted_and_bounded')
    return keys


def load_stage_inputs(repo,cell,cohort_path):
    """All real runs enter here: no free-form entity list, fallback or backfill."""
    repo=Path(repo).resolve();design=frozen_design(repo)
    if cell not in ('e','g'):raise ValueError('explicit_cell_e_or_g_required')
    stage=design['stages']['A' if cell=='e' else 'B'];bp=_local(repo,stage['binding_path'])
    if not bp.is_file():raise ValueError('g_validated_cohort_unavailable' if cell=='g' else 'e_binding_missing')
    b=read_json(bp)
    if cell=='e' and file_sha256(bp)!=stage['binding_sha256']:raise ValueError('frozen_e_binding_mismatch')
    if b.get('schema_version')!='google2019-stage-input-binding-v1' or b.get('cell')!=cell or b.get('status')!='AVAILABILITY_CONTRACT_READY':raise ValueError('unvalidated_stage_binding')
    if b['protocol_fingerprint']!=design['protocol']['protocol_fingerprint'] or b['cohort_rule_sha256']!=design['cohort_selection_rule_sha256']:raise ValueError('stage_protocol_or_rule_mismatch')
    cp=_local(repo,b['cohort_path'])
    if Path(cohort_path).resolve()!=cp.resolve():raise ValueError('explicit_frozen_cohort_manifest_required')
    if file_sha256(cp)!=b['cohort_sha256']:raise ValueError('cohort_hash_mismatch')
    c=read_json(cp);keys=_cohort_ids(c,cell)
    if c.get('cell')!=cell or c.get('protocol_fingerprint')!=b['protocol_fingerprint'] or c.get('canonical_sha256')!=b['canonical_sha256'] or c.get('clock_contract_sha256')!=design['protocol']['clock_contract_sha256']:raise ValueError('cohort_provenance_mismatch')
    if c.get('cohort_rule_sha256')!=b['cohort_rule_sha256'] or fingerprint(c['entities'])!=b['member_records_sha256']:raise ValueError('cohort_member_identity_mismatch')
    if cell=='e' and (len(keys)!=1000 or b['cohort_sha256']!=stage['cohort_sha256'] or b['member_records_sha256']!=stage['member_records_sha256']):raise ValueError('frozen_e_cohort_changed')
    generation=_local(repo,b['canonical_path']);m=require_corrected_generation(generation)
    if file_sha256(generation/'manifest.json')!=b['canonical_manifest_sha256']:raise ValueError('canonical_manifest_mismatch')
    parts=[a for a in m['artifacts'] if a['path'].startswith('canonical_usage/')]
    if fingerprint(parts)!=b['canonical_sha256'] or m['canonical_dataset_sha256']!=b['canonical_sha256']:raise ValueError('canonical_dataset_mismatch')
    expected=sorted(a['path'] for a in parts)
    if expected!=sorted(p.relative_to(generation).as_posix() for p in (generation/'canonical_usage').iterdir()):raise ValueError('canonical_shard_inventory_mismatch')
    ap=_local(repo,b['clock_audit_path']);audit=validate_clock_audit(ap)
    if file_sha256(ap/'manifest.json')!=b['clock_audit_manifest_sha256'] or audit['canonical_sha256']!=b['canonical_sha256'] or audit['protocol_fingerprint']!=b['protocol_fingerprint']:raise ValueError('clock_audit_binding_mismatch')
    s=audit['summary']
    if s['disposition']!='AVAILABILITY_CONTRACT_READY' or s['timing']['ambiguous_rows'] or s['incomplete_bootstrap_rows'] or s['incomplete_rows_at_stream_anchor']:raise ValueError('clock_contract_not_validated')
    ep=_local(repo,b['eligibility_path'])
    if file_sha256(ep)!=b['eligibility_sha256']:raise ValueError('eligibility_hash_mismatch')
    metadata=pq.read_table(ep).to_pandas()
    if not metadata.cell.eq(cell).all():raise ValueError('eligibility_cell_mismatch')
    chosen=select_cohort(metadata,design['cohort_selection_rule'])
    if chosen.to_dict('records')!=c['entities']:raise ValueError('cohort_not_frozen_independent_hash_selection')
    if len(keys)!=min(1000,int(metadata.nominal_protocol_eligible.sum())):raise ValueError('cohort_backfill_or_truncation')
    selected=metadata.merge(chosen[['cell','collection_id','instance_index']],on=['cell','collection_id','instance_index'],validate='one_to_one')
    return dict(repo=repo,cell=cell,design=design,binding=b,binding_sha256=file_sha256(bp),generation=generation,
        canonical_manifest=m,cohort=c,entities=selected.sort_values(['collection_id','instance_index']).to_dict('records'))


def google_config(cell,design):
    if cell not in ('e','g'):raise ValueError('explicit_cell_required')
    policies=[]
    for method in design['methods']:
        hours=float(method.split('_')[1][:-1]) if method.startswith('pw_') else None
        policies.append(PolicyConfig(method,periodic_interval_hours=hours,observation_window_hours=24 if method!='static' else None,
            parameters=dict(initialization='whole_bootstrap' if method=='static' else 'cadence_bootstrap' if hours else 'trailing24h_bootstrap',pw_history_slots=96 if hours else 0)))
    return ExperimentConfigProvenance(DataConfig(f'google_clusterdata_2019_{cell}'),
        ModelConfig(family='unused-observation-only'),tuple(policies),
        StatisticsConfig(bootstrap_repetitions=10000,bootstrap_seed=20251022,confidence_level=.95,
            test_specification=design['statistics']),
        preprocessing=dict(staged_design_fingerprint=fingerprint(design),stage='A' if cell=='e' else 'B',cell=cell,
            google_protocol_fingerprint=design['protocol']['protocol_fingerprint'],clock_contract_sha256=design['protocol']['clock_contract_sha256'],
            bootstrap_split='nominal-closing-time-30pct',resource_units='request_normalized_ratio',
            cohort_selection_rule_sha256=design['cohort_selection_rule_sha256']),
        analysis=dict(comparison_families=design['comparison_families'],cross_cell_synthesis=design['cross_cell_synthesis'],
            robustness=design['robustness'],practical_significance='NOT_DEFINED_AT_PROFILE_LEVEL'))


def validate_config(config,cell,design):
    if canonical_json(config)!=canonical_json(google_config(cell,design)):raise ValueError('config_execution_mismatch')
    if (BOOTSTRAP_B,BOOTSTRAP_SEED,CI_LEVEL)!=(config.statistics.bootstrap_repetitions,config.statistics.bootstrap_seed,config.statistics.confidence_level):raise ValueError('statistics_execution_mismatch')


def prepare_google_inputs(canonical,cell,entity_id,config,design):
    validate_config(config,cell,design)
    if canonical.empty or not canonical.cell.eq(cell).all():raise ValueError('canonical_entity_cell_mismatch')
    f=observation_frame(canonical);boot,stream,info=bootstrap_partition(f)
    thresholds=bootstrap_thresholds_at_read(f,info['stream_anchor_us'])
    aliases=dict(zip(RESOURCES,METRICS))
    data=f[list(RESOURCES)].rename(columns=aliases);data.attrs['resource_units']='request_normalized_ratio'
    boot_data=data.loc[boot.index];stream_data=data.loc[stream.index]
    cpu_th,mem_th=(thresholds[k] for k in RESOURCES)
    anchor=pd.Timestamp(info['stream_anchor_us'],unit='us')
    profile=ProfileInstance(StaticFields(str(entity_id),cell,None,None,boot_data.index[0],anchor,len(data)),
        DynamicFields('idle','idle',float('nan'),float('nan')),{k:anchor for k in ('cpu_class','memory_class','predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h')})
    clocks,_=compute_data_aware_evaluation_timestamps(data,stream_data.index,
        period_hours=config.data.evaluation_cadence_seconds//3600,min_observations_in_window=config.data.minimum_ground_truth_paired_slots)
    truth=[]
    for t in clocks:
        # Explicitly validate availability and full maturity before deriving any label.
        origin=int(t.value//1000);window=forward_truth_observations(f,origin,origin+288*300_000_000)
        if len(window)<config.data.minimum_ground_truth_paired_slots:raise ValueError('truth_density_mismatch')
        truth.append(dict(eval_timestamp=t,**derive_ground_truth_at_t(data,t,cpu_thresholds=cpu_th,mem_thresholds=mem_th,
            min_observations_in_window=config.data.minimum_ground_truth_paired_slots)))
    if not truth:raise ValueError('frozen_entity_has_no_verified_origins')
    gt=pd.DataFrame(truth).set_index('eval_timestamp')
    observed=stream_data.loc[np.isfinite(stream_data.to_numpy(float)).all(axis=1)]
    days=(stream_data.index[-1]-stream_data.index[0]).total_seconds()/86400
    prepared=PreparedVM(data,boot_data,stream_data,info,profile,cpu_th,mem_th,None,observed,None,gt,days)
    return prepared,float(boot_data[METRICS[0]].std(ddof=0))


def run_google_entity(canonical,cell,cid,idx,config,design):
    """Same production path for both cells and synthetic fixtures. No acquisition."""
    entity_id=f'{int(cid)}:{int(idx)}';start=time.perf_counter()
    if not canonical.collection_id.eq(cid).all() or not canonical.instance_index.eq(idx).all():raise ValueError('mixed_entity_input')
    inputs,volatility=prepare_google_inputs(canonical,cell,entity_id,config,design)
    rows=[];records=[];events=[];stamps=[];truth_id=fingerprint(inputs.ground_truth.reset_index().assign(eval_timestamp=lambda f:f.eval_timestamp.astype('int64')).to_dict('records'))
    for policy in config.policies:
        factory=factory_for(policy.method_id)
        actual_period=getattr(factory,'keywords',{}).get('period_hours')
        if actual_period!=policy.periodic_interval_hours:raise ValueError('factory_period_config_mismatch')
        replay=replay_from_inputs(inputs,factory);result=evaluate_replay(replay,include_records=True)
        rec=pd.DataFrame(result['evaluation_records']);stamp=fingerprint(rec.eval_timestamp.astype("int64").tolist());stamps.append(stamp)
        if len(rec)!=len(inputs.ground_truth):raise ValueError('verified_evaluation_coverage_mismatch')
        # One shared truth table and thresholds, independent of maintenance decisions.
        gt=inputs.ground_truth.rename(columns={'cpu_class':'truth_cpu_class','memory_class':'truth_memory_class',
            'p95_cpu_next_24h':'truth_cpu_p95','p95_mem_next_24h':'truth_memory_p95'}).reset_index()
        rec=rec.merge(gt,on='eval_timestamp',validate='one_to_one')
        rec=rec.assign(cell=cell,trace=cell,vm_id=entity_id,method_id=policy.method_id,resource_units='request_normalized_ratio')
        if not np.isfinite(rec[['profile_cpu_p95','profile_memory_p95','truth_cpu_p95','truth_memory_p95','cpu_p95_abs_err','mem_p95_abs_err']].to_numpy(float)).all():raise ValueError('nonfinite_profile_or_error')
        refresh=result['n_refresh_events'];kind='n_periodic_refreshes' if policy.method_id.startswith('pw_') else 'n_full_rewrite_refreshes' if policy.method_id=='full_rewrite' else None
        if result['n_initialization_events']!=1 or (refresh!=(result[kind] if kind else 0)) or result['n_field_writes']!=4*refresh:raise ValueError('accounting_decomposition_failure')
        if result['n_drift_refreshes'] or result['n_reactive_refreshes'] or result['n_budget_extra_refreshes']:raise ValueError('nonfrozen_trigger')
        times=[e['actual_commit_time'] for e in result['refresh_log']]
        if len(times)!=len(set(times)) or len(times)!=refresh:raise ValueError('duplicate_or_missing_refresh_event')
        row=dict(cell=cell,trace=cell,vm_id=entity_id,collection_id=int(cid),instance_index=int(idx),method_id=policy.method_id,
            run_status='ok',resource_units='request_normalized_ratio',causal_protocol=result['causal_protocol'],accounting_schema=result['accounting_schema'],
            **{k:result[k] for k in ('cpu_class_accuracy','memory_class_accuracy','cpu_p95_mae','mem_p95_mae',*ACCOUNTING_METRICS)},
            cpu_p95_bias=float(rec.cpu_p95_bias.mean()),mem_p95_bias=float(rec.mem_p95_bias.mean()),
            n_eval_points_verified=len(rec),stream_days=inputs.stream_days,n_streaming_steps=len(inputs.observations),
            age_mean_hours=float(rec.profile_age_hours.mean()),age_median_hours=float(rec.profile_age_hours.median()),
            age_p95_hours=float(rec.profile_age_hours.quantile(.95)),age_max_hours=float(rec.profile_age_hours.max()),
            age_zero_pct=float(rec.profile_age_seconds.eq(0).mean()*100),
            **_periodic_delay_stats(result['refresh_log']),volatility=volatility,
            evaluation_stamp_fingerprint=stamp,truth_fingerprint=truth_id,period_hours_executed=actual_period)
        rows.append(row);records.append(rec)
        events.extend(dict(cell=cell,vm_id=entity_id,method_id=policy.method_id,**e) for e in result['refresh_log'])
    if len(set(stamps))!=1:raise ValueError('methods_have_different_verified_origins')
    require_accounting_metrics(pd.DataFrame(rows))
    return dict(rows=rows,evaluations=pd.concat(records,ignore_index=True),events=pd.DataFrame(events,columns=EVENT_COLUMNS),
        diagnostics=dict(cell=cell,vm_id=entity_id,verified_origins=len(inputs.ground_truth),truth_fingerprint=truth_id,
            cpu_thresholds=inputs.cpu_thresholds,memory_thresholds=inputs.mem_thresholds,
            wall_seconds=time.perf_counter()-start,status='COMPLETED',resource_units='request_normalized_ratio'))


def assign_input_tertiles(frame):
    # Five repeated method rows carry exactly the same bootstrap-only value.
    values=frame[['cell','vm_id','volatility']].drop_duplicates()
    if values.duplicated(['cell','vm_id']).any():raise ValueError('inconsistent_bootstrap_volatility')
    q1,q2=values.volatility.quantile([1/3,2/3])
    values['volatility_tier']=np.where(values.volatility<=q1,'low',np.where(values.volatility<=q2,'medium','high'))
    return frame.merge(values[['cell','vm_id','volatility_tier']],on=['cell','vm_id'],validate='many_to_one'),dict(q1=float(q1),q2=float(q2))


def cross_cell_synthesis(e,g):
    """Post-stage reporting only; never called to configure/select Stage B."""
    keys=['family','treatment','control','endpoint'];cols=keys+['mean','median','mean_ci_low','mean_ci_high','median_ci_low','median_ci_high']
    if e.duplicated(keys).any() or g.duplicated(keys).any():raise ValueError('duplicate_cross_cell_contrast')
    joined=e[cols].merge(g[cols],on=keys,suffixes=('_e','_g'),validate='one_to_one',how='outer',indicator=True)
    if not joined['_merge'].eq('both').all():raise ValueError('missing_cross_cell_contrast')
    out=[]
    for row in joined.drop(columns='_merge').to_dict('records'):
        a,b=np.sign(row['mean_e']),np.sign(row['mean_g'])
        label='same_positive' if a==b==1 else 'same_negative' if a==b==-1 else 'same_zero' if a==b==0 else 'discordant_or_one_zero'
        out.append(dict(**row,direction=label,g_minus_e_mean=row['mean_g']-row['mean_e'],g_minus_e_median=row['median_g']-row['median_e']))
    return dict(rule='predefined descriptive direction/heterogeneity only',pooled_inference=False,rows=out)


def output_specs(entities):
    specs=[OutputSpec('outputs/'+name,role) for name,role in OUTPUTS.items()]
    for e in entities:
        tag=f"{e['cell']}__{int(e['collection_id'])}_{int(e['instance_index'])}"
        specs.extend([OutputSpec(f'outputs/entities/{tag}/evaluation_records.parquet','verified-snapshots-with-common-truth'),
            OutputSpec(f'outputs/entities/{tag}/refresh_events.parquet','canonical-runtime-events-audit'),
            OutputSpec(f'logs/{tag}.json','entity-execution-or-failure-diagnostics')])
    return specs


def write_entity_outputs(run,entity,answer):
    tag=f"{entity['cell']}__{int(entity['collection_id'])}_{int(entity['instance_index'])}"
    root=run.path/'outputs/entities'/tag;root.mkdir(parents=True)
    answer['evaluations'].to_parquet(root/'evaluation_records.parquet',compression='zstd',index=False)
    answer['events'].to_parquet(root/'refresh_events.parquet',compression='zstd',index=False)
    write_json(run.path/f'logs/{tag}.json',answer['diagnostics'])


def write_analysis(run,rows,design,binding):
    frame=pd.DataFrame(rows).sort_values(['cell','vm_id','method_id']).reset_index(drop=True)
    if frame.duplicated(['cell','vm_id','method_id']).any():raise ValueError('duplicate_entity_method_result')
    if not frame.groupby(['cell','vm_id']).size().eq(5).all() or not frame.groupby(['cell','vm_id']).evaluation_stamp_fingerprint.nunique().eq(1).all():raise ValueError('matrix_or_read_coverage_failure')
    if set(frame.cell)!=set([binding['cell']]) or set(frame.method_id)!=set(design['methods']):raise ValueError('analysis_requires_one_cell_and_exact_frozen_methods')
    frame,cutoffs=assign_input_tertiles(frame);require_accounting_metrics(frame)
    paired,inference,summary=analyze_families(frame)
    out=run.path/'outputs'
    write_json(out/'design_binding.json',dict(design_fingerprint=fingerprint(design),design=design,input_binding=binding))
    frame.to_parquet(out/'per_entity_results.parquet',index=False,compression='zstd')
    paired.to_parquet(out/'paired_effects.parquet',index=False,compression='zstd')
    inference.to_parquet(out/'family_inference.parquet',index=False,compression='zstd')
    write_json(out/'family_inference.json',summary)
    write_json(out/'robustness_summary.json',dict(**robustness_summaries(frame,paired),bootstrap_cpu_std_tertiles=cutoffs,
        scope='descriptive within-cell; no selection or additional confirmatory tests'))
    counters=['n_refresh_events','n_periodic_refreshes','n_full_rewrite_refreshes','n_field_writes','n_field_value_changes']
    write_json(out/'cost_accounting_summary.json',{str(method):{f'mean_{k}':float(g[k].mean()) for k in counters} for method,g in frame.groupby('method_id')})
    write_json(out/'run_diagnostics.json',dict(cell=binding['cell'],entities=int(frame.vm_id.nunique()),method_entity_runs=len(frame),
        methods=design['methods'],verified_sets_equal=True,accounting_invariants=True,resource_units='request_normalized_ratio',
        protocol_fingerprint=design['protocol']['protocol_fingerprint'],no_cross_cell_pooling=True,
        practical_significance='NOT_DEFINED_AT_PROFILE_LEVEL',query_bytes=0,acquisition_performed=False))
    return frame


def provenance_inputs(bound):
    cell=bound['cell'];config=google_config(cell,bound['design']);validate_config(config,cell,bound['design'])
    dataset=build_dataset_manifest(bound['generation'],dataset_id=config.data.dataset_id,source_name=f'Google 2019 canonical cell {cell}',
        trace_names=('canonical_usage',),schema_identity=fingerprint(dict(canonical_sha256=bound['binding']['canonical_sha256'],
            canonical_manifest_sha256=bound['binding']['canonical_manifest_sha256'],clock=bound['design']['protocol'])),selection='parquet-shards-v1')
    config=ExperimentConfigProvenance(config.data,config.model,config.policies,config.statistics,
        {**config.preprocessing,'input_binding_sha256':bound['binding_sha256'],'frozen_cohort_sha256':bound['binding']['cohort_sha256']},config.analysis)
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'google-staged-frozen-identity-cohort-v1',
        dict(cell=cell,selection_rule_sha256=bound['design']['cohort_selection_rule_sha256'],frozen_cohort_sha256=bound['binding']['cohort_sha256']),
        tuple(CohortEntity(cell,f"{e['collection_id']}:{e['instance_index']}",True,None,int(e['observations']),
            pd.Timestamp(int(e['first_timestamp_us']),unit='us').isoformat(),pd.Timestamp(int(e['last_timestamp_us']),unit='us').isoformat())
            for e in sorted(bound['entities'],key=lambda e:f"{e['collection_id']}:{e['instance_index']}")),utc_now())
    return config,dataset,cohort


def _entity_frames(bound):
    entities=bound['entities'];m=bound['canonical_manifest'];n=int(m['partitions'])
    grouped={}
    for e in entities:grouped.setdefault((int(e['collection_id'])*1000003+int(e['instance_index']))%n,[]).append(e)
    for pid,batch in sorted(grouped.items()):
        p=bound['generation']/f'canonical_usage/part_{pid:03d}.parquet'
        f=pq.read_table(p,columns=['cell','collection_id','instance_index','timestamp_us','source_start_time_us','source_end_time_us','cpu_utilization','memory_utilization']).to_pandas()
        for entity in batch:
            g=f[f.collection_id.eq(entity['collection_id'])&f.instance_index.eq(entity['instance_index'])].copy()
            if len(g)!=entity['observations']:raise ValueError('frozen_entity_observation_count_mismatch')
            yield entity,g


def execute(repo,cell,cohort_path,*,workers=1,reuse_run=None):
    repo=Path(repo).resolve()
    if SourceProvenance.capture(repo).dirty:raise ValueError('clean_committed_claim_source_required')
    if not 1<=workers<=4:raise ValueError('workers_must_be_1_to_4')
    bound=load_stage_inputs(repo,cell,cohort_path);config,dataset,cohort=provenance_inputs(bound)
    exp,env=prepare_experiment(repo,bound['generation'],config,dataset,cohort,{'statistics':20251022})
    if reuse_run:
        decision=check_cache(reuse_run,exp,'claim')
        if not decision.reusable:raise ValueError('cache_rejected:'+','.join(decision.reasons))
        return Path(reuse_run)
    base=google_config(cell,bound['design'])
    # Added input binding hashes are provenance only; computation uses the same
    # frozen base settings. Assert the exact semantic portion before dispatch.
    if config.data!=base.data or config.policies!=base.policies or config.statistics!=base.statistics:raise ValueError('bound_config_execution_mismatch')
    with RunSession(repo/'results',exp,env,repo=repo,dataset_root=bound['generation'],purpose='claim',required_outputs=output_specs(bound['entities'])) as run:
        rows=[];completed=0
        pool=ProcessPoolExecutor(max_workers=workers) if workers>1 else None
        try:
            # At most workers bounded entity tasks; never an all-corpus queue.
            pending=[]
            def collect(entity,answer):
                nonlocal completed
                if answer['diagnostics']['verified_origins']!=int(entity['globally_verifiable_origins']):raise ValueError('frozen_metadata_read_count_mismatch')
                write_entity_outputs(run,entity,answer);rows.extend(answer['rows']);completed+=1
                print(canonical_json(dict(cell=cell,completed_entities=completed,total_entities=len(bound['entities']),run_id=run.manifest.run_id)),flush=True)
            for entity,canonical in _entity_frames(bound):
                args=(canonical,cell,int(entity['collection_id']),int(entity['instance_index']),base,bound['design'])
                if pool:
                    pending.append((entity,pool.submit(run_google_entity,*args)))
                    if len(pending)>=workers:
                        e,f=pending.pop(0);collect(e,f.result())
                else:collect(entity,run_google_entity(*args))
            for entity,future in pending:collect(entity,future.result())
        finally:
            if pool:pool.shutdown(wait=True,cancel_futures=True)
        if len(rows)!=5*len(bound['entities']) or completed!=len(bound['entities']):raise ValueError('incomplete_frozen_matrix')
        write_analysis(run,rows,bound['design'],bound['binding'])
        # Recheck ignored cohort/audit/parent manifests as well as shard hashes.
        again=load_stage_inputs(repo,cell,cohort_path)
        if canonical_json(again['binding'])!=canonical_json(bound['binding']):raise ValueError('stage_inputs_changed_during_run')
        run.complete()
        return run.path
