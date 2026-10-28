"""V4C metadata/availability audit only. No policies, predictions or cloud calls."""
from __future__ import annotations
from dataclasses import asdict
import argparse
from pathlib import Path
import shutil
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from dynapm.core.provenance import (SourceProvenance, EnvironmentProvenance,
    canonical_json, fingerprint, file_sha256, read_json, utc_now)
from dynapm.core.run_store import write_json
from dynapm.experiments.replication_corpus import frozen_hashes
from dynapm.experiments.google2019_local_canonical import require_corrected_generation, verify_parents

SCHEMA = 'google2019-protocol-validation-v1'
RULE_SCHEMA = 'google2019-outcome-blind-cohort-rule-v1'
PROTOCOL = '4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226'
CANONICAL = '06ec0ce8a599890bc98f5c2adb1bfb01c3858c83b6d0630a1f0a29335b77fdaf'
GENERATION = 'cell-e-unambiguous-v2-85c74588191efa0b'
STEP = 300_000_000
SELECTION_SALT = 'google2019-v4c-cohort-v1'
METHODS = ['static', 'pw_12h', 'pw_6h', 'pw_3h', 'full_rewrite']
SPEC_PATH = 'configs/google2019_cohort_design_spec_v1.json'


def design_spec():
    return dict(schema_version=RULE_SCHEMA, protocol_fingerprint=PROTOCOL,
        required_cells=['e','g'], bootstrap='first floor(0.30 * nominal slots); observations strictly before nominal cut',
        bootstrap_minimum_paired_observations=96, minimum_refresh_paired_slots=200,
        minimum_forward_paired_slots=200, pw_complete_history_slots=96,
        minimum_globally_verifiable_origins=1, minimum_refresh_opportunities=1,
        selection_inputs=['cell','collection_id','instance_index','protocol-validity presence metadata'],
        forbidden_selection_inputs=['utilization magnitude','volatility','policy output','method accuracy'],
        selection_salt=SELECTION_SALT, bounded_entities_per_cell=1000,
        resource_decision='all if projected two-cell outputs and conservative wall time fit; otherwise lowest SHA-256 per cell, capped at 1000; resolve once on e and apply unchanged to g',
        resources=dict(output_budget_gib=16, reserve_gib=20, wall_budget_hours=48,
            workers=4, profile_operation_ms=[0.1,10.0], event_dispatch_ms=[0.01,0.1],
            bytes_per_evaluation_record=256, bytes_per_refresh_event=256,
            storage_safety_factor=1.5, runtime_safety_factor=1.25),
        final_cohort_requires_both_cells_validated=True,
        availability_policy='do not repair start-label visibility silently; block readiness if aggregate end exceeds nominal label',
        initialization='V3 inherited bootstrap estimators: Static whole bootstrap, PW last cadence-length bootstrap window, Full-Rewrite last 24h; runtime 200-slot gate does not apply to initialization')


def metadata_for_entity(cell, cid, idx, timestamps, cpu, mem, source_end, acquired, acquisition_reason=None):
    """Presence-only temporal eligibility; values used ONLY for bootstrap thresholds.

    Split follows the explicit V4A nominal-time rule, not Materna's observed-row
    split. No streaming aggregate/profile/ground-truth value is calculated.
    """
    ts=np.asarray(timestamps,dtype=np.int64);cpu=np.asarray(cpu,float);mem=np.asarray(mem,float)
    ends=np.asarray(source_end,dtype=np.int64)
    if not len(ts) or np.any(np.diff(ts)<=0) or np.any(ts%STEP):
        raise ValueError('protocol_invalid_timeline_or_schema')
    slots=(ts-ts[0])//STEP;total=int(slots[-1])+1;cut_slots=total*3//10
    cut=int(ts[0])+cut_slots*STEP
    paired=np.isfinite(cpu)&np.isfinite(mem)
    dense=np.zeros(total,dtype=np.int64);dense[slots]=paired
    prefix=np.r_[0,np.cumsum(dense)]
    grid=np.arange(total)
    trailing=prefix[grid+1]-prefix[np.maximum(0,grid-287)]
    history=prefix[grid+1]-prefix[np.maximum(0,grid-95)]
    forward=prefix[np.minimum(total,grid+289)]-prefix[np.minimum(total,grid+1)]
    boot=(ts<cut)&paired;stream=(ts>=cut)&paired;stream_slots=slots[stream]
    anchor=int(stream_slots[0]) if len(stream_slots) else total
    hourly=np.arange(anchor,max(anchor,total-288),12,dtype=int)
    verified=hourly[forward[hourly]>=200]
    window=trailing[stream_slots]>=200
    pw=window&(history[stream_slots]==96)
    previous=prefix[slots]-prefix[np.maximum(0,slots-96)]
    candidate_boot=(ts<cut)&(slots>=96)&paired
    threshold={}
    for resource,values in [('cpu',cpu),('memory',mem)]:
        for q in (20,40,60,80,95):
            threshold[f'{resource}_threshold_p{q}']=float(np.percentile(values[boot],q)) if boot.any() else None
    reasons=[]
    if not acquired:reasons.append(acquisition_reason or 'insufficient_continuous_span_for_24h_windows')
    if int(boot.sum())<96:reasons.append('insufficient_bootstrap_history')
    if not window.any() or not pw.any():reasons.append('insufficient_exact_grid_feature_or_window_validity')
    if not len(verified):reasons.append('insufficient_globally_verifiable_evaluation_origins')
    gaps=np.diff(ts)
    row=dict(cell=cell,collection_id=int(cid),instance_index=int(idx),acquisition_eligible=bool(acquired),
        first_timestamp_us=int(ts[0]),last_timestamp_us=int(ts[-1]),span_seconds=int((ts[-1]-ts[0])//1_000_000),
        observations=len(ts),nominal_slots=total,paired_finite_slots=int(paired.sum()),
        cpu_nonfinite=int((~np.isfinite(cpu)).sum()),memory_nonfinite=int((~np.isfinite(mem)).sum()),
        missing_slots=int(total-paired.sum()),gap_intervals=int((gaps>STEP).sum()),maximum_gap_seconds=int(gaps.max()//1_000_000) if len(gaps) else 0,
        bootstrap_cut_us=cut,bootstrap_nominal_slots=cut_slots,bootstrap_observations=int(boot.sum()),
        bootstrap_coverage=float(boot.sum()/cut_slots) if cut_slots else 0.,
        bootstrap_valid_exact_history_rows=int((candidate_boot&(previous==96)).sum()),
        streaming_observations=int(stream.sum()),stream_anchor_us=int(ts[0]+anchor*STEP) if len(stream_slots) else None,
        window24_refresh_opportunities=int(window.sum()),pw_refresh_opportunities=int(pw.sum()),
        nominal_hourly_origins=len(hourly),globally_verifiable_origins=len(verified),
        evaluation_origins_without_observation=int((dense[verified]==0).sum()),
        evaluation_retained_fraction=float(len(verified)/len(hourly)) if len(hourly) else 0.,
        nominal_protocol_eligible=not reasons,protocol_exclusion_reasons='|'.join(dict.fromkeys(reasons)),
        rows_available_after_nominal_time=int((ends>ts).sum()),
        max_availability_delay_seconds=float(np.maximum(ends-ts,0).max()/1_000_000),
        bootstrap_rows_ending_after_cut=int((boot&(ends>cut)).sum()),
        bootstrap_rows_ending_after_stream_anchor=int((boot&(ends>int(ts[0]+anchor*STEP))).sum()),
        # This is a global protocol issue, not an outcome-driven entity exclusion.
        availability_contract_blocked=bool((ends>ts).any()),**threshold)
    last_boot=int(slots[boot][-1]) if boot.any() else -1
    for h in (3,6,12,24):
        row[f'initial_window_{h}h_slots']=int(((slots>last_boot-h*12)&(slots<=last_boot)&boot).sum())
    for h in (3,6,12):
        row[f'p{h}_nominal_ticks']=int((total-1-anchor)//(h*12)) if anchor<total else 0
    return row


def selection_hash(cell,cid,idx):
    import hashlib
    return hashlib.sha256(f'{SELECTION_SALT}|{cell}|{int(cid)}|{int(idx)}'.encode()).hexdigest()


def select_cohort(table,rule):
    """Never receives outcomes: project only explicitly allowed identity/validity columns."""
    cols=['cell','collection_id','instance_index','nominal_protocol_eligible']
    f=table[cols].copy();f=f[f.nominal_protocol_eligible].drop(columns='nominal_protocol_eligible')
    if f.duplicated(['cell','collection_id','instance_index']).any():raise ValueError('duplicate entity')
    f['selection_hash']=[selection_hash(*x) for x in f.itertuples(index=False,name=None)]
    f=f.sort_values(['cell','selection_hash','collection_id','instance_index'],kind='mergesort')
    if rule['mode']=='lowest_sha256_per_cell':f=f.groupby('cell',sort=True).head(rule['maximum_entities_per_cell'])
    elif rule['mode']!='all_protocol_eligible':raise ValueError('unsupported cohort rule')
    return f.sort_values(['cell','collection_id','instance_index']).reset_index(drop=True)


def cost_estimate(table,cells=1):
    """Analytical planning assumptions, NOT policy timing or measured overhead."""
    n=len(table)*cells;evals=int(table.globally_verifiable_origins.sum())*cells
    full=int(table.window24_refresh_opportunities.sum())*cells
    periodic=int(table[[f'p{h}_nominal_ticks' for h in (3,6,12)]].sum().sum())*cells
    events=full+periodic;records=5*evals;dispatch=5*int(table.streaming_observations.sum())*cells
    ops=events+evals+5*n
    spec=design_spec()['resources']
    disk=spec['storage_safety_factor']*(events+records)*256/2**30+1
    hours=[spec['runtime_safety_factor']*(ops*x/1000+dispatch*y/1000)/3600 for x,y in zip(spec['profile_operation_ms'],spec['event_dispatch_ms'])]
    return dict(entities=n,method_entity_runs=5*n,verified_origins=evals,
        evaluation_records=records,refresh_event_upper_bound=events,profile_or_truth_operations=ops,
        dispatch_upper_bound=dispatch,output_reservation_gib=disk,serial_core_hours=hours,
        wall_hours_at_four_workers=[h/4 for h in hours],
        assumptions='unmeasured analytical range; two-cell extrapolation assumes g has e-like lengths/counts; new g metadata must replace this estimate before V5')


def freeze_selection_rule(table):
    estimate=cost_estimate(table,cells=2);s=design_spec()['resources']
    all_ok=estimate['output_reservation_gib']<=s['output_budget_gib'] and estimate['wall_hours_at_four_workers'][1]<=s['wall_budget_hours']
    return dict(schema_version=RULE_SCHEMA,mode='all_protocol_eligible' if all_ok else 'lowest_sha256_per_cell',
        maximum_entities_per_cell=None if all_ok else 1000,selection_salt=SELECTION_SALT,
        required_cells=['e','g'],resolved_from='cell-e metadata-only resource feasibility; apply unchanged to g',
        rule_input='nominal protocol eligibility; no utilization magnitude, volatility or outcome',
        provisional_until_availability_contract_validated=True)


def require_replication_ready(records):
    if set(records)!=set(['e','g']):raise ValueError('cell_g_acquisition_and_validation_required')
    if any(r['disposition']!='PROTOCOL_READY' for r in records.values()):raise ValueError('protocol_requires_correction')
    if len({r['cohort_rule_sha256'] for r in records.values()})!=1:raise ValueError('cohort_rule_mismatch')


def validate_audit(path):
    path=Path(path);m=read_json(path/'manifest.json')
    if m['schema_version']!=SCHEMA or not (path/'SUCCESS').is_file():raise ValueError('incomplete_or_unsupported_audit')
    if read_json(path/'SUCCESS')['manifest_sha256']!=file_sha256(path/'manifest.json'):raise ValueError('audit_manifest_hash_mismatch')
    for a in m['artifacts']:
        p=path/a['path']
        if not p.is_file() or p.is_symlink() or file_sha256(p)!=a['sha256']:raise ValueError('audit_output_hash_mismatch')
    return m


def run(repo):
    repo=Path(repo).resolve();source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean committed source required')
    frozen=frozen_hashes()
    if frozen['protocol_fingerprint']!=PROTOCOL:raise ValueError('frozen_protocol_mismatch')
    spec=read_json(repo/SPEC_PATH)
    if canonical_json(spec)!=canonical_json(design_spec()):raise ValueError('cohort_design_spec_mismatch')
    generation=repo/'data/google2019/canonical/generations'/GENERATION
    m=require_corrected_generation(generation)
    if m['canonical_dataset_sha256']!=CANONICAL:raise ValueError('corrected_canonical_identity_mismatch')
    try:require_corrected_generation(repo/'data/google2019/canonical/e')
    except ValueError as exc:
        if str(exc)!='old_or_unsupported_canonical_generation':raise
    else:raise ValueError('legacy_generation_accepted')
    parents=verify_parents(repo)
    if shutil.disk_usage(repo).free<22*2**30:raise ValueError('metadata_audit_disk_reserve')
    identity=dict(schema_version=SCHEMA,source_commit=source.commit,protocol=PROTOCOL,canonical=CANONICAL,spec_sha256=fingerprint(spec))
    out=repo/'data/google2019/protocol_validation'/('v4c-e-'+fingerprint(identity)[:16])
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'partitions').mkdir()
    start=time.monotonic();rows=[];processed=0
    entities=pq.read_table(generation/'entity_manifest.parquet').to_pandas().set_index(['collection_id','instance_index'])
    files=sorted((generation/'canonical_usage').glob('*.parquet'))
    try:
        for num,p in enumerate(files,1):
            frame=pq.read_table(p,columns=['collection_id','instance_index','timestamp_us','cpu_utilization','memory_utilization','source_end_time_us']).to_pandas()
            part=[]
            for (cid,idx),g in frame.groupby(['collection_id','instance_index'],sort=False):
                e=entities.loc[(cid,idx)]
                part.append(metadata_for_entity('e',cid,idx,g.timestamp_us,g.cpu_utilization,g.memory_utilization,
                    g.source_end_time_us,e.eligible,e.exclusion_reason if isinstance(e.exclusion_reason,str) else None))
            pd.DataFrame(part).to_parquet(out/'partitions'/p.name,index=False,compression='zstd')
            rows.extend(part);processed+=len(frame)
            elapsed=time.monotonic()-start
            status=dict(stage='metadata_only',parts_completed=num,total_parts=len(files),canonical_rows=processed,
                percent=100*num/len(files),entities=len(rows),elapsed_seconds=elapsed,
                rows_per_second=processed/max(elapsed,1),eta_seconds=elapsed*(len(files)-num)/num,
                free_disk_gib=shutil.disk_usage(repo).free/2**30,query_bytes=0,method_outcomes=False,error=None)
            write_json(out/'status.json',status)
            print(canonical_json(status),flush=True)
        table=pd.DataFrame(rows).sort_values(['cell','collection_id','instance_index']).reset_index(drop=True)
        assert len(table)==m['entity_count'] and int(table.observations.sum())==m['output_row_count']
        assert int(table.acquisition_eligible.sum())==62451
        table.to_parquet(out/'entity_eligibility.parquet',compression='zstd',index=False)
        eligible=table[table.nominal_protocol_eligible]
        rule=freeze_selection_rule(eligible);selected=select_cohort(table,rule)
        chosen=table.merge(selected[['cell','collection_id','instance_index']],on=['cell','collection_id','instance_index'],validate='one_to_one')
        cohort=dict(schema_version='google2019-provisional-cohort-v1',cell='e',role='PROVISIONAL; no replication authorization',
            canonical_sha256=CANONICAL,protocol_fingerprint=PROTOCOL,cohort_rule_sha256=fingerprint(rule),
            final_two_cell_cohort_frozen=False,entities=selected.to_dict('records'))
        write_json(out/'cohort_rule.json',rule);write_json(out/'provisional_e_cohort.json',cohort)
        counts=table.protocol_exclusion_reasons.str.split('|').explode();counts=counts[counts.ne('')].value_counts()
        acquired=table[table.acquisition_eligible]
        global_block=bool(table.availability_contract_blocked.any())
        summary=dict(disposition='PROTOCOL_REQUIRES_CORRECTION' if global_block else 'PROTOCOL_READY',
            canonical_entities=len(table),acquisition_eligible=len(acquired),nominal_protocol_eligible=len(eligible),
            acquisition_candidates_excluded=len(acquired)-len(eligible),provisional_selected=len(selected),
            reason_counts_all_entities={k:int(v) for k,v in counts.items()},
            reason_counts_acquisition_candidates={k:int(v) for k,v in acquired.protocol_exclusion_reasons.str.split('|').explode().loc[lambda s:s.ne('')].value_counts().items()},
            counts_acquisition_candidates={c:int(acquired[c].sum()) for c in ['observations','bootstrap_observations','bootstrap_valid_exact_history_rows','window24_refresh_opportunities','pw_refresh_opportunities','nominal_hourly_origins','globally_verifiable_origins','evaluation_origins_without_observation','missing_slots','gap_intervals','cpu_nonfinite','memory_nonfinite']},
            rows_with_end_after_nominal=int(table.rows_available_after_nominal_time.sum()),
            entities_with_availability_conflict=int(table.availability_contract_blocked.sum()),
            max_availability_delay_seconds=float(table.max_availability_delay_seconds.max()),
            bootstrap_rows_ending_after_cut=int(table.bootstrap_rows_ending_after_cut.sum()),
            bootstrap_rows_ending_after_stream_anchor=int(table.bootstrap_rows_ending_after_stream_anchor.sum()),
            bootstrap_thresholds_finite_for_all_nominal_eligible=bool(np.isfinite(eligible.filter(regex='_threshold_').to_numpy(float)).all()),
            cohort_sha256=fingerprint(cohort),cohort_rule_sha256=fingerprint(rule),
            all_eligible_e_cost=cost_estimate(eligible),all_two_cell_extrapolation=cost_estimate(eligible,cells=2),
            selected_e_cost=cost_estimate(chosen),selected_two_cell_extrapolation=cost_estimate(chosen,cells=2),
            v5_blockers=['cell_g_not_acquired_or_validated','final_two_cell_cohort_unfrozen']+(['usage_window_start_label_precedes_aggregate_availability'] if global_block else []),
            query_bytes=0,billing='untouched',method_outcomes_computed=False,
            eligibility_scope='nominal-time/presence feasibility only; global availability contract prevents scientific readiness',
            wall_seconds=time.monotonic()-start)
        write_json(out/'summary.json',summary)
        if parents!=verify_parents(repo):raise ValueError('parent_or_ledger_changed')
        require_corrected_generation(generation)
        if frozen!=frozen_hashes():raise ValueError('frozen_protocol_changed')
        if SourceProvenance.capture(repo).dirty or SourceProvenance.capture(repo).commit!=source.commit:raise ValueError('source_changed')
        artifacts=[dict(path=p.relative_to(out).as_posix(),size_bytes=p.stat().st_size,sha256=file_sha256(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='status.json']
        manifest=dict(**identity,status='COMPLETED',purpose='metadata_protocol_validation',disposition=summary['disposition'],source=asdict(source),environment=asdict(EnvironmentProvenance.capture()),
            canonical_generation_manifest_sha256=file_sha256(generation/'manifest.json'),frozen_protocol_files=frozen,
            parent_identity_sha256=fingerprint(parents),artifacts=artifacts,summary=summary,created_at=utc_now(),replication_authorized=False)
        write_json(out/'manifest.json',manifest);write_json(out/'SUCCESS',dict(manifest_sha256=file_sha256(out/'manifest.json'),role='audit integrity completion, NOT protocol readiness'))
        validate_audit(out)
        record=dict(schema_version=SCHEMA,path=out.relative_to(repo).as_posix(),producer_commit=source.commit,
            manifest_sha256=file_sha256(out/'manifest.json'),summary=summary,cohort_rule=rule,
            eligibility_parquet_sha256=file_sha256(out/'entity_eligibility.parquet'),provisional_cohort_file_sha256=file_sha256(out/'provisional_e_cohort.json'),
            final_cohort_frozen=False,replication_authorized=False)
        write_json(repo/'configs/google2019_v4c_validation_record.json',record)
        print(canonical_json(record),flush=True)
        return record
    except BaseException as exc:
        write_json(out/'FAILED',dict(error_type=type(exc).__name__,error=str(exc),created_at=utc_now()))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--write-design-spec',action='store_true')
    args=p.parse_args()
    if args.write_design_spec:write_json(args.repo/SPEC_PATH,design_spec())
    else:run(args.repo)

if __name__=='__main__':main()
