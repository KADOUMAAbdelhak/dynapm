"""V4C.1 interval/availability metadata only; no policy or cloud execution."""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import argparse,time,shutil
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from dynapm.core.provenance import (read_json,canonical_json,fingerprint,file_sha256,
    SourceProvenance,EnvironmentProvenance,utc_now)
from dynapm.core.run_store import write_json
from dynapm.experiments.confirmatory_design import emit_yaml
from dynapm.experiments.google2019_local_canonical import require_corrected_generation
from dynapm.experiments.google2019_protocol_validation import (metadata_for_entity,select_cohort,
    cost_estimate,PROTOCOL as PARENT_PROTOCOL,CANONICAL,GENERATION,STEP)
from dynapm.data.google2019_clock import CLOCK_VERSION,clock_contract

SCHEMA='google2019-availability-validation-v1'
PROTOCOL_SCHEMA='google-clusterdata-2019-replication-protocol-v2'
PROTOCOL_JSON='configs/google_clusterdata_2019_replication_protocol_v2.json'
PROTOCOL_YAML='configs/google_clusterdata_2019_replication_protocol_v2.yaml'
PARENT_JSON='configs/google_clusterdata_2019_replication_protocol_v1.json'


def protocol_v2(repo):
    parent=read_json(Path(repo)/PARENT_JSON)
    if fingerprint(parent)!=PARENT_PROTOCOL:raise ValueError('parent_protocol_changed')
    result=dict(parent)
    result.update(schema_version=PROTOCOL_SCHEMA,gate='V4C.1',
        disposition='AVAILABILITY_CONTRACT_DEFINED; requires per-cell timing validation',
        parent_protocol_fingerprint=PARENT_PROTOCOL,clock_contract=clock_contract(),
        v5_requires=['both_e_and_g_acquired_and_clock_validated','final_two_cell_cohort_frozen'],
        canonical_start_labels_unchanged=True)
    return result


def validate_protocol_v2(repo):
    p=Path(repo);d=read_json(p/PROTOCOL_JSON);expected=protocol_v2(p)
    if canonical_json(d)!=canonical_json(expected):raise ValueError('clock_protocol_config_mismatch')
    if (p/PROTOCOL_YAML).read_text()!='# V4C.1 availability extension; V4A v1 is preserved.\n'+emit_yaml(d):
        raise ValueError('clock_protocol_yaml_mismatch')
    return dict(protocol_fingerprint=fingerprint(d),clock_contract_sha256=fingerprint(d['clock_contract']),
        config_json_sha256=file_sha256(p/PROTOCOL_JSON),config_yaml_sha256=file_sha256(p/PROTOCOL_YAML))


def timing_counts(f):
    b=f.timestamp_us.to_numpy(np.int64);s=f.source_start_time_us.to_numpy(np.int64);e=f.source_end_time_us.to_numpy(np.int64)
    same=(f.collection_id.to_numpy()[1:]==f.collection_id.to_numpy()[:-1])&(f.instance_index.to_numpy()[1:]==f.instance_index.to_numpy()[:-1])
    duration=e-s;adjacent_gaps=(s[1:]-e[:-1])[same]
    nominal_gaps=np.diff(b)[same]
    invalid=(b%STEP!=0)|(s<b)|(s>=b+STEP)|(e<=s)|(e>b+STEP)
    duplicate=f.duplicated(['collection_id','instance_index','timestamp_us'],keep=False).to_numpy()
    overlaps=np.zeros(len(f),bool);indices=np.flatnonzero(same & (s[1:]<e[:-1]))
    overlaps[indices]=True;overlaps[indices+1]=True
    ambiguous=invalid|duplicate|overlaps
    counts=dict(rows=len(f),exact_300s=int((duration==STEP).sum()),partial_lt_300s=int(((duration>0)&(duration<STEP)).sum()),
        invalid_durations=int(((duration<=0)|(duration>STEP)).sum()),start_off_grid=int((s%STEP!=0).sum()),end_off_grid=int((e%STEP!=0).sum()),
        noncontained_rows=int(invalid.sum()),canonical_duplicate_rows=int(duplicate.sum()),
        overlapping_interval_pairs=int((adjacent_gaps<0).sum()),positive_interval_gaps=int((adjacent_gaps>0).sum()),
        contiguous_interval_pairs=int((adjacent_gaps==0).sum()),
        positive_gaps_with_consecutive_nominal_slots=int(((adjacent_gaps>0)&(nominal_gaps==STEP)).sum()),
        missing_nominal_slot_gaps=int((nominal_gaps>STEP).sum()),ambiguous_rows=int(ambiguous.sum()),
        ambiguous_entities=len(f.loc[ambiguous,['collection_id','instance_index']].drop_duplicates()),
        maximum_interval_gap_us=int(adjacent_gaps.max()) if len(adjacent_gaps) else 0,
        duration_sum_us=int(duration.sum()),availability_delay_sum_us=int((e-b).sum()),
        admission_hold_sum_us=int((b+STEP-e).sum()),early_end_admission_holds=int((e<b+STEP).sum()))
    distributions={}
    for key,value in [('duration_us',duration),('label_to_availability_us',e-b),('availability_to_admission_us',b+STEP-e)]:
        values,n=np.unique(value,return_counts=True);distributions[key]={int(k):int(v) for k,v in zip(values,n)}
    return counts,distributions


def duplicate_interval_counts(canonical,rejected):
    d=rejected[rejected.exclusion_reason.eq('duplicate_nominal_bucket')].copy()
    if d.empty:return dict(rejected_duplicate_nominal_rows=0,exact_interval_surplus_rows=0,exact_duplicate_interval_groups=0)
    keys=['collection_id','instance_index','start_time','end_time']
    groups=d.groupby(keys,sort=False).size().rename('n').reset_index()
    groups['timestamp_us']=(groups.start_time//STEP)*STEP
    joined=groups.merge(canonical[['collection_id','instance_index','timestamp_us','source_start_time_us','source_end_time_us']],
        on=['collection_id','instance_index','timestamp_us'],validate='many_to_one')
    if len(joined)!=len(groups):raise ValueError('duplicate_bucket_winner_missing')
    winner=(joined.start_time==joined.source_start_time_us)&(joined.end_time==joined.source_end_time_us)
    new_intervals=len(groups)-int(winner.sum())
    return dict(rejected_duplicate_nominal_rows=len(d),exact_interval_surplus_rows=len(d)-new_intervals,
        exact_duplicate_interval_groups=int((joined.n+winner.astype(int)>=2).sum()))


def distribution_summary(counter):
    values=np.array(sorted(counter),dtype=np.int64);weights=np.array([counter[int(x)] for x in values],dtype=np.int64)
    cumulative=np.cumsum(weights);n=int(weights.sum())
    def q(p):
        x=(n-1)*p;lo=int(np.floor(x));hi=int(np.ceil(x))
        a=float(values[np.searchsorted(cumulative,lo+1)]);b=float(values[np.searchsorted(cumulative,hi+1)])
        return (a+(b-a)*(x-lo))/1e6
    return dict(min_seconds=float(values.min()/1e6),max_seconds=float(values.max()/1e6),
        mean_seconds=float(np.sum(values.astype(float)*weights)/n/1e6),p50_seconds=q(.5),p95_seconds=q(.95),p99_seconds=q(.99))


def validate_clock_audit(path):
    path=Path(path);m=read_json(path/'manifest.json')
    if m.get('schema_version')!=SCHEMA or not (path/'SUCCESS').is_file():raise ValueError('incomplete_clock_audit')
    if read_json(path/'SUCCESS')['manifest_sha256']!=file_sha256(path/'manifest.json'):raise ValueError('clock_manifest_hash_mismatch')
    for a in m['artifacts']:
        p=path/a['path']
        if p.is_symlink() or not p.is_file() or file_sha256(p)!=a['sha256']:raise ValueError('clock_output_hash_mismatch')
    return m


def run(repo):
    repo=Path(repo).resolve();source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean_committed_clock_audit_required')
    protocol=validate_protocol_v2(repo)
    generation=repo/'data/google2019/canonical/generations'/GENERATION
    m=require_corrected_generation(generation);parent_manifest_sha=file_sha256(generation/'manifest.json')
    parts=[a for a in m['artifacts'] if a['path'].startswith('canonical_usage/')]
    if fingerprint(parts)!=CANONICAL:raise ValueError('canonical_identity_mismatch')
    prior=read_json(repo/'configs/google2019_v4c_validation_record.json')
    authority=read_json(repo/'configs/google2019_replication_cohort_v1.json');rule=authority['selection_rule']
    old_cohort_path=repo/authority['e']['manifest_path']
    if file_sha256(old_cohort_path)!=authority['e']['manifest_file_sha256']:raise ValueError('old_cohort_identity_mismatch')
    old_cohort=read_json(old_cohort_path)
    old_table_path=repo/prior['path']/'entity_eligibility.parquet'
    if file_sha256(old_table_path)!=prior['eligibility_parquet_sha256']:raise ValueError('old_metadata_identity_mismatch')
    old_table=pq.read_table(old_table_path).to_pandas()
    if shutil.disk_usage(repo).free<22*2**30:raise ValueError('clock_audit_disk_reserve')
    identity=dict(schema_version=SCHEMA,producer_commit=source.commit,canonical_sha256=CANONICAL,
        protocol_fingerprint=protocol['protocol_fingerprint'],clock_contract_sha256=protocol['clock_contract_sha256'],
        selection_rule_sha256=fingerprint(rule),prior_audit_manifest_sha256=prior['manifest_sha256'])
    out=repo/'data/google2019/protocol_validation'/('v4c1-e-'+fingerprint(identity)[:16])
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True);(out/'partitions').mkdir();start=time.monotonic()
    all_rows=[];total=Counter();hist={k:Counter() for k in ['duration_us','label_to_availability_us','availability_to_admission_us']}
    entities=pq.read_table(generation/'entity_manifest.parquet').to_pandas().set_index(['collection_id','instance_index'])
    files=sorted((generation/'canonical_usage').glob('*.parquet'))
    max_gap=0
    try:
        for number,p in enumerate(files,1):
            f=pq.read_table(p,columns=['collection_id','instance_index','timestamp_us','source_start_time_us','source_end_time_us','cpu_utilization','memory_utilization']).to_pandas()
            stats,dist=timing_counts(f);max_gap=max(max_gap,stats.pop('maximum_interval_gap_us'));total.update(stats)
            for key,values in dist.items():hist[key].update(values)
            rejected=pq.read_table(generation/'rejected_rows'/p.name,columns=['collection_id','instance_index','start_time','end_time','exclusion_reason']).to_pandas()
            total.update(duplicate_interval_counts(f,rejected))
            rows=[]
            for (cid,idx),g in f.groupby(['collection_id','instance_index'],sort=False):
                e=entities.loc[(cid,idx)]
                rows.append(metadata_for_entity('e',cid,idx,g.timestamp_us+STEP,g.cpu_utilization,g.memory_utilization,
                    g.source_end_time_us,e.eligible,e.exclusion_reason if isinstance(e.exclusion_reason,str) else None))
            pd.DataFrame(rows).to_parquet(out/'partitions'/p.name,index=False,compression='zstd');all_rows.extend(rows)
            elapsed=time.monotonic()-start
            status=dict(stage='intervals_and_availability_metadata',parts_completed=number,total_parts=len(files),
                rows=total['rows'],entities=len(all_rows),percent=100*number/len(files),elapsed_seconds=elapsed,
                rows_per_second=total['rows']/max(elapsed,1),eta_seconds=elapsed*(len(files)-number)/number,
                free_disk_gib=shutil.disk_usage(repo).free/2**30,error=None,query_bytes=0,policy_outcomes=False)
            write_json(out/'status.json',status);print(canonical_json(status),flush=True)
        table=pd.DataFrame(all_rows).sort_values(['cell','collection_id','instance_index']).reset_index(drop=True)
        if total['rows']!=m['output_row_count'] or len(table)!=m['entity_count']:raise ValueError('clock_row_entity_reconciliation')
        table.to_parquet(out/'entity_eligibility.parquet',compression='zstd',index=False)
        selected=select_cohort(table,rule);new_ids=set(selected[['cell','collection_id','instance_index']].itertuples(index=False,name=None))
        old_ids={(e['cell'],e['collection_id'],e['instance_index']) for e in old_cohort['entities']}
        cohort=dict(schema_version='google2019-availability-cohort-v2',role='PROVISIONAL e only; final two-cell freeze absent',cell='e',
            canonical_sha256=CANONICAL,protocol_fingerprint=protocol['protocol_fingerprint'],clock_contract_sha256=protocol['clock_contract_sha256'],
            cohort_rule_sha256=fingerprint(rule),entities=selected.to_dict('records'),final_two_cell_cohort_frozen=False)
        write_json(out/'provisional_e_cohort.json',cohort)
        old_eligible=set(old_table.loc[old_table.nominal_protocol_eligible,['collection_id','instance_index']].itertuples(index=False,name=None))
        eligible=set(table.loc[table.nominal_protocol_eligible,['collection_id','instance_index']].itertuples(index=False,name=None))
        interval_ok=not(total['ambiguous_rows'] or total['overlapping_interval_pairs'] or total['canonical_duplicate_rows'])
        metadata_ok=not table.availability_contract_blocked.any() and not table.bootstrap_rows_ending_after_cut.any() and not table.bootstrap_rows_ending_after_stream_anchor.any()
        acquired=table[table.acquisition_eligible];reason=acquired.protocol_exclusion_reasons.str.split('|').explode();reason=reason[reason.ne('')]
        comparison_columns=['observations','bootstrap_observations','bootstrap_valid_exact_history_rows','window24_refresh_opportunities','pw_refresh_opportunities','nominal_hourly_origins','globally_verifiable_origins','p3_nominal_ticks','p6_nominal_ticks','p12_nominal_ticks']
        old=old_table.set_index(['collection_id','instance_index']);new=table.set_index(['collection_id','instance_index'])
        count_invariance={c:bool(np.array_equal(old[c].to_numpy(),new[c].to_numpy())) for c in comparison_columns}
        threshold_cols=[c for c in table.columns if '_threshold_' in c]
        thresholds_same=bool(np.allclose(old[threshold_cols].to_numpy(float),new[threshold_cols].to_numpy(float),equal_nan=True,rtol=0,atol=0))
        table_ready=interval_ok and metadata_ok and bool(eligible)
        summary=dict(disposition='AVAILABILITY_CONTRACT_READY' if table_ready else 'AVAILABILITY_CONTRACT_BLOCKED',
            timing=dict(total,maximum_interval_gap_us=max_gap),distribution_summaries={k:distribution_summary(v) for k,v in hist.items()},
            canonical_entities=len(table),acquisition_candidates=int(acquired.shape[0]),eligible_before=len(old_eligible),eligible_after=len(eligible),
            eligible_removed=len(old_eligible-eligible),eligible_added=len(eligible-old_eligible),
            exclusion_reasons={k:int(v) for k,v in reason.value_counts().items()},unique_exclusions=int((~acquired.nominal_protocol_eligible).sum()),
            cohort_size=len(selected),cohort_sha256=fingerprint(cohort),cohort_identity_rows_sha256=fingerprint(selected.to_dict('records')),
            cohort_removed=len(old_ids-new_ids),cohort_added=len(new_ids-old_ids),membership_changed=old_ids!=new_ids,
            count_invariance=count_invariance,bootstrap_thresholds_identical=thresholds_same,
            counts_acquisition_candidates={c:int(acquired[c].sum()) for c in comparison_columns[1:]+['evaluation_origins_without_observation']},
            incomplete_bootstrap_rows=int(table.bootstrap_rows_ending_after_cut.sum()),
            incomplete_rows_at_stream_anchor=int(table.bootstrap_rows_ending_after_stream_anchor.sum()),
            eligibility_scope='availability-aware completed closing slots, no policy executions',
            source_label_to_analysis_shift_us=STEP,nominal_slot_counts_unchanged=True,
            final_two_cell_cohort_frozen=False,cell_g_acquired_or_validated=False,replication_authorized=False,
            query_bytes=0,billing='untouched',policy_outcomes_computed=False,wall_seconds=time.monotonic()-start)
        write_json(out/'summary.json',summary)
        write_json(out/'timing_histograms.json',{k:{str(x):v for x,v in sorted(c.items())} for k,c in hist.items()})
        require_corrected_generation(generation)
        if file_sha256(generation/'manifest.json')!=parent_manifest_sha:raise ValueError('canonical_parent_changed')
        if validate_protocol_v2(repo)!=protocol:raise ValueError('clock_protocol_changed')
        current=SourceProvenance.capture(repo)
        if current.dirty or current.commit!=source.commit:raise ValueError('clock_audit_source_changed')
        artifacts=[dict(path=p.relative_to(out).as_posix(),size_bytes=p.stat().st_size,sha256=file_sha256(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='status.json']
        manifest=dict(**identity,source=asdict(source),environment=asdict(EnvironmentProvenance.capture()),
            purpose='measurement_availability_protocol_validation',status='COMPLETED',protocol_files=protocol,
            canonical_parent_manifest_sha256=parent_manifest_sha,summary=summary,artifacts=artifacts,
            created_at=utc_now(),replication_authorized=False)
        write_json(out/'manifest.json',manifest);write_json(out/'SUCCESS',dict(manifest_sha256=file_sha256(out/'manifest.json')))
        validate_clock_audit(out)
        record=dict(schema_version=SCHEMA,path=out.relative_to(repo).as_posix(),producer_commit=source.commit,
            manifest_sha256=file_sha256(out/'manifest.json'),protocol=protocol,summary=summary,
            eligibility_manifest_sha256=file_sha256(out/'entity_eligibility.parquet'),cohort_file_sha256=file_sha256(out/'provisional_e_cohort.json'),
            selection_rule=rule,final_two_cell_cohort_frozen=False,replication_authorized=False)
        write_json(repo/'configs/google2019_v4c1_validation_record.json',record)
        print(canonical_json(record),flush=True)
        return record
    except BaseException as exc:
        write_json(out/'FAILED',dict(error_type=type(exc).__name__,error=str(exc),created_at=utc_now()));raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--write-protocol',action='store_true')
    a=p.parse_args()
    if a.write_protocol:
        d=protocol_v2(a.repo);write_json(a.repo/PROTOCOL_JSON,d)
        (a.repo/PROTOCOL_YAML).write_text('# V4C.1 availability extension; V4A v1 is preserved.\n'+emit_yaml(read_json(a.repo/PROTOCOL_JSON)))
    else:run(a.repo)

if __name__=='__main__':main()
