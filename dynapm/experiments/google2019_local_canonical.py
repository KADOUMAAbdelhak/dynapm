"""V4B.8 local-only canonical generation. No BigQuery/client/query calls.

Raw inputs and legacy canonical files are opened read-only. New files live in a
separate immutable generation. Exact frozen JSON source hashes and tie-breaking
are retained, with vectorized causal joins and entity-contained partitions.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dynapm.core.provenance import SourceProvenance, canonical_json, fingerprint, file_sha256, read_json, utc_now
from dynapm.core.run_store import write_json
from dynapm.experiments.google2019_requests import prepare_request_history, KEYS, PAIR, REQUEST_RULE
from dynapm.experiments.google2019_acquisition import CADENCE_US, MIN_SPAN_US, MIN_VALID_SLOTS

SCHEMA = 'google2019-canonical-generation-v2'
NORMALIZATION = 'google2019-unambiguous-local-canonical-v2'
PARTITIONS = 256
RESERVE = 20 * 2**30
EXPECTED = {'events':('7e70a9bea2763b3ffd4676ca16595726cfbbcf3f07527811b150ba34526c0e2e',2696535),
    'usage':('5f3fa7120ee5587e87cc42be0d6ecb732de8f8e2c0f7cb6f564551263a4e3fe0',513023210)}
USAGE_COLUMNS = ['collection_id','instance_index','collection_type','start_time','end_time','average_cpu','average_memory']


def disk_guard(path, upcoming=0):
    free=shutil.disk_usage(path).free
    if free < RESERVE+upcoming:raise RuntimeError('disk reserve would be breached')
    return free


def source_hashes(frame):
    """Exact canonical-json/fingerprint bytes, optimized for frozen finite schema.

    Fixed JSON keys are lexically sorted. repr(float) matches the stdlib JSON
    encoder for finite numbers; IDs/times retain integer spelling. Tests compare
    every digest with the original generic fingerprint implementation.
    """
    source=json.dumps('google.com:google-cluster-data.clusterdata_2019_e.instance_usage')
    request=json.dumps('google.com:google-cluster-data.clusterdata_2019_e.instance_events')
    cols=['average_cpu','average_memory','collection_id','collection_type','end_time','instance_index','request_cpu','request_event_time','request_memory','start_time']
    def digest(r):
        cpu,mem,cid,ct,end,idx,rc,rt,rm,start=r
        data=(f'{{"average_cpu":{float(cpu)!r},"average_memory":{float(mem)!r},"cell":"e",'
            f'"collection_id":{int(cid)},"collection_type":{int(ct)},"end_time":{int(end)},'
            f'"instance_index":{int(idx)},"request_cpu":{float(rc)!r},"request_event_time":{int(rt)},'
            f'"request_memory":{float(rm)!r},"request_source_table":{request},'
            f'"start_time":{int(start)},"usage_source_table":{source}}}')
        return hashlib.sha256(data.encode()).hexdigest()
    return [digest(r) for r in frame[cols].itertuples(index=False,name=None)]


def join_partition(raw, history, latest):
    raw=raw.sort_values('start_time',kind='mergesort').copy()
    hist=history.rename(columns={'time':'request_event_time'}).sort_values('request_event_time',kind='mergesort')
    old=latest.rename(columns={'time':'latest_positive_event_time'}).sort_values('latest_positive_event_time',kind='mergesort')
    by=['collection_id','instance_index']
    joined=pd.merge_asof(raw,hist,left_on='start_time',right_on='request_event_time',by=by,direction='backward')
    joined=pd.merge_asof(joined,old,left_on='start_time',right_on='latest_positive_event_time',by=by,direction='backward')
    joined['requires_ambiguity_fallback']=joined.latest_ambiguous.eq(True)
    joined['used_earlier_request']=joined.requires_ambiguity_fallback & joined.request_event_time.notna()
    return joined


def canonical_partition(raw, history, latest):
    f=join_partition(raw,history,latest)
    reasons=pd.Series('',index=f.index,dtype=object)
    numeric=['collection_id','instance_index','collection_type','start_time','end_time','average_cpu','average_memory']
    reasons.loc[~np.isfinite(f[numeric].to_numpy(float)).all(axis=1)]='corrupt_or_nonfinite_source_data'
    reasons.loc[reasons.eq('') & f.request_event_time.isna()]='missing_unambiguous_positive_request'
    checks=[('non_alloc_collection_type',f.collection_type.ne(1)),
        ('negative_resource_usage',f.average_cpu.lt(0)|f.average_memory.lt(0)),
        ('missing_positive_resource_request',f.request_cpu.le(0)|f.request_memory.le(0)),
        ('request_event_after_usage_window',f.request_event_time.gt(f.start_time)),
        ('protocol_invalid_window_duration',f.end_time.le(f.start_time)|(f.end_time-f.start_time).gt(CADENCE_US))]
    for reason,bad in checks:reasons.loc[reasons.eq('') & bad]=reason
    rejected=f.loc[reasons.ne('')].copy();rejected['exclusion_reason']=reasons[reasons.ne('')]
    valid=f.loc[reasons.eq('')].copy();valid['request_event_time']=valid.request_event_time.astype('int64')
    valid['timestamp_us']=(valid.start_time//CADENCE_US)*CADENCE_US
    valid['source_row_sha256']=source_hashes(valid)
    keys=['collection_id','instance_index','timestamp_us']
    valid=valid.sort_values(keys+['end_time','source_row_sha256'],ascending=[True,True,True,False,True],kind='mergesort')
    duplicate=valid.duplicated(keys,keep='first');dups=valid.loc[duplicate].copy();dups['exclusion_reason']='duplicate_nominal_bucket'
    rejected=pd.concat([rejected,dups],ignore_index=True);valid=valid.loc[~duplicate].copy()
    valid['cpu_utilization']=valid.average_cpu/valid.request_cpu;valid['memory_utilization']=valid.average_memory/valid.request_memory
    if not np.isfinite(valid[['cpu_utilization','memory_utilization']].to_numpy(float)).all():raise ValueError('nonfinite normalized data')
    valid['cell']='e';valid['usage_source_table']='google.com:google-cluster-data.clusterdata_2019_e.instance_usage'
    valid['request_source_table']='google.com:google-cluster-data.clusterdata_2019_e.instance_events'
    valid=valid.rename(columns={'average_cpu':'average_cpu_ncu','average_memory':'average_memory_normalized_ram',
        'request_cpu':'request_cpu_ncu','request_memory':'request_memory_normalized_ram','request_event_time':'request_event_time_us',
        'start_time':'source_start_time_us','end_time':'source_end_time_us'})
    cols=['cell','collection_id','instance_index','timestamp_us','cpu_utilization','memory_utilization',
        'average_cpu_ncu','average_memory_normalized_ram','request_cpu_ncu','request_memory_normalized_ram',
        'request_event_time_us','usage_source_table','request_source_table','source_row_sha256',
        'source_start_time_us','source_end_time_us','requires_ambiguity_fallback','used_earlier_request']
    canonical=valid[cols].reset_index(drop=True)
    entities=[]
    for (cid,idx),g in canonical.groupby(['collection_id','instance_index'],sort=True):
        ts=g.timestamp_us.to_numpy();n=len(ts);span=int(ts[-1]-ts[0]);expected=1+span//CADENCE_US
        reason='insufficient_bootstrap_history' if n<MIN_VALID_SLOTS else ('insufficient_continuous_span_for_24h_windows' if span<MIN_SPAN_US else None)
        states=len(g[['request_cpu_ncu','request_memory_normalized_ram']].drop_duplicates())
        entities.append(dict(cell='e',collection_id=int(cid),instance_index=int(idx),first_timestamp_us=int(ts[0]),
            last_timestamp_us=int(ts[-1]),observed_slots=n,expected_slots=expected,missing_slots=expected-n,
            maximum_gap_us=int(np.diff(ts).max()) if n>1 else 0,request_states=states,has_request_change=states>1,
            eligible=reason is None,exclusion_reason=reason))
    counts={str(k):int(v) for k,v in rejected.exclusion_reason.value_counts().items()}
    diagnostics=dict(raw_usage_rows=len(raw),canonical_rows=len(canonical),rejected_rows=len(rejected),exclusion_reasons=counts,
        requires_ambiguity_fallback_raw=int(f.requires_ambiguity_fallback.sum()),successful_fallback_raw=int(f.used_earlier_request.sum()),
        no_earlier_valid_request_raw=int((f.requires_ambiguity_fallback & ~f.used_earlier_request).sum()),
        fallback_canonical_rows=int(canonical.used_earlier_request.sum()),
        above_one_cpu=int(canonical.cpu_utilization.gt(1).sum()),above_one_memory=int(canonical.memory_utilization.gt(1).sum()))
    return canonical,pd.DataFrame(entities),rejected,diagnostics


def partition_usage(usage, work, count, status):
    work.mkdir();writers={};buffers={};sizes={};seen=0
    try:
        for batch in pq.ParquetFile(usage).iter_batches(batch_size=1000000,columns=USAGE_COLUMNS):
            frame=batch.to_pandas();ids=(frame.collection_id.to_numpy()*1000003+frame.instance_index.to_numpy())%count
            for pid,group in frame.groupby(ids,sort=False):
                pid=int(pid);table=pa.Table.from_pandas(group,preserve_index=False)
                buffers.setdefault(pid,[]).append(table);sizes[pid]=sizes.get(pid,0)+len(group)
                if sizes[pid]>=100000:
                    disk_guard(work,256*2**20)
                    if pid not in writers:writers[pid]=pq.ParquetWriter(work/f'raw_{pid:03d}.parquet',table.schema,compression='zstd')
                    writers[pid].write_table(pa.concat_tables(buffers[pid]),row_group_size=100000);buffers[pid]=[];sizes[pid]=0
            seen+=len(frame);status.update(stage='partition_raw_usage',rows_processed=seen,expected_rows=pq.ParquetFile(usage).metadata.num_rows)
        for pid,tables in buffers.items():
            if not tables:continue
            t=pa.concat_tables(tables)
            if pid not in writers:writers[pid]=pq.ParquetWriter(work/f'raw_{pid:03d}.parquet',t.schema,compression='zstd')
            writers[pid].write_table(t,row_group_size=100000)
    finally:
        for writer in writers.values():writer.close()
    return seen


def process_partition(task):
    raw_path,history_path,latest_path,out,pid=task;out=Path(out);disk_guard(out,256*2**20)
    raw=pq.read_table(raw_path).to_pandas()
    hist=pq.read_table(history_path).to_pandas();latest=pq.read_table(latest_path).to_pandas()
    mask=((hist.collection_id.to_numpy()*1000003+hist.instance_index.to_numpy())%PARTITIONS)==pid
    history=hist.loc[mask].copy()
    mask=((latest.collection_id.to_numpy()*1000003+latest.instance_index.to_numpy())%PARTITIONS)==pid
    recent=latest.loc[mask].copy()
    canonical,entities,rejected,counts=canonical_partition(raw,history,recent)
    for kind,frame in [('canonical_usage',canonical),('entities',entities),('rejected_rows',rejected)]:
        folder=out/kind;folder.mkdir(exist_ok=True)
        frame.to_parquet(folder/f'part_{pid:03d}.parquet',compression='zstd',row_group_size=100000,index=False)
    counts['partition']=pid
    write_json(out/'partition_diagnostics'/f'{pid:03d}.json',counts)
    Path(raw_path).unlink()  # only scratch created by this generation
    return counts


class Progress:
    def __init__(self,repo,out):
        self.repo=repo;self.out=out;self.started=time.time();self.state={};self.stop=threading.Event();self.lock=threading.Lock()
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def update(self,**values):
        with self.lock:
            if values.get("stage") and values["stage"]!=self.state.get("stage"):self.state["stage_started"]=time.time()
            self.state.update(values)
    def emit(self):
        with self.lock:body=dict(self.state)
        elapsed=max(time.time()-self.started,1);stage_elapsed=max(time.time()-body.pop('stage_started',self.started),1);n=body.get('rows_processed',0);expected=body.get('expected_rows',0);rate=n/stage_elapsed
        body.update(gate='V4B.8',updated_at=utc_now(),elapsed_seconds=elapsed,throughput_rows_per_second=rate,
            percent=100*n/expected if expected else None,eta_seconds=(expected-n)/rate if expected and rate else None,
            free_disk_gib=shutil.disk_usage(self.repo).free/2**30,error=body.get('error'),zero_query_bytes=0,raw_acquisition='VERIFIED',
            old_canonical='SUPERSEDED_INVALID_FOR_SCIENTIFIC_REPLICATION',
            corrected_canonical='VERIFIED' if body.get('stage')=='VERIFIED' else ('FAILED' if body.get('stage')=='FAILED' else 'PENDING'))
        write_json(self.out/'status.json',body)
        write_json(self.repo/'data/google2019/monitor/status.json',body)
        with (self.out/'progress.jsonl').open('a') as f:f.write(canonical_json(body)+'\n')
        print(canonical_json(body),flush=True)
    def loop(self):
        while not self.stop.wait(60):self.emit()
    def close(self):self.stop.set();self.thread.join();self.emit()


def require_corrected_generation(path):
    path=Path(path);m=read_json(path/'manifest.json')
    if m.get('schema_version')!=SCHEMA or m.get('normalization_version')!=NORMALIZATION:
        raise ValueError('old_or_unsupported_canonical_generation')
    if m.get('status')!='VERIFIED' or not (path/'SUCCESS').exists():raise ValueError('incomplete_canonical_generation')
    if read_json(path/'SUCCESS').get('manifest_sha256')!=file_sha256(path/'manifest.json'):raise ValueError('canonical_manifest_hash_mismatch')
    for entry in m['artifacts']:
        p=path/entry['path']
        if p.is_symlink() or not p.is_file() or file_sha256(p)!=entry['sha256']:raise ValueError('canonical_artifact_hash_mismatch')
    return m


def validate_local(out, history, ambiguous, latest, status):
    """Independent NumPy ASOF + full ratios/cadence/eligibility audit."""
    bad_index=pd.MultiIndex.from_frame(ambiguous[KEYS])
    assert not pd.MultiIndex.from_frame(history[KEYS]).isin(bad_index).any()
    assert not history.duplicated(KEYS).any()
    lookup={key:(g.time.to_numpy(),g.request_cpu.to_numpy(),g.request_memory.to_numpy())
            for key,g in history.groupby(['collection_id','instance_index'],sort=False)}
    previous={key:(g.time.to_numpy(),g.latest_ambiguous.to_numpy())
              for key,g in latest.groupby(['collection_id','instance_index'],sort=False)}
    manifest_entities=pq.read_table(out/'entity_manifest.parquet').to_pandas().set_index(['collection_id','instance_index'])
    checked=ambiguous_hits=sampled=0;maxerr=0.;cpu_above=mem_above=fallbacks=0;entities_checked=set()
    for file in sorted((out/'canonical_usage').glob('*.parquet')):
        f=pq.read_table(file).to_pandas();keys=['collection_id','instance_index','timestamp_us']
        if f.empty:continue
        assert not f.duplicated(keys).any()
        assert f[keys].equals(f.sort_values(keys,kind='mergesort')[keys])
        assert (f.timestamp_us%CADENCE_US).eq(0).all()
        assert ((f.source_start_time_us//CADENCE_US)*CADENCE_US).eq(f.timestamp_us).all()
        assert f.source_end_time_us.gt(f.source_start_time_us).all()
        assert (f.source_end_time_us-f.source_start_time_us).le(CADENCE_US).all()
        assert f.request_event_time_us.le(f.source_start_time_us).all()
        assert f.request_cpu_ncu.gt(0).all() and f.request_memory_normalized_ram.gt(0).all()
        values=f[['cpu_utilization','memory_utilization']].to_numpy(float)
        assert np.isfinite(values).all()
        expected=np.column_stack([f.average_cpu_ncu/f.request_cpu_ncu,f.average_memory_normalized_ram/f.request_memory_normalized_ram])
        assert np.array_equal(values,expected)
        hits=pd.MultiIndex.from_frame(f[['collection_id','instance_index','request_event_time_us']].rename(columns={'request_event_time_us':'time'})).isin(bad_index)
        ambiguous_hits+=int(hits.sum());assert not hits.any()
        for key,indices in f.groupby(['collection_id','instance_index'],sort=False).indices.items():
            g=f.iloc[indices];times,cpus,mems=lookup[key];positions=np.searchsorted(times,g.source_start_time_us.to_numpy(),side='right')-1
            assert (positions>=0).all()
            assert np.array_equal(times[positions],g.request_event_time_us.to_numpy())
            assert np.array_equal(cpus[positions],g.request_cpu_ncu.to_numpy())
            assert np.array_equal(mems[positions],g.request_memory_normalized_ram.to_numpy())
            lt,la=previous[key];old=np.searchsorted(lt,g.source_start_time_us.to_numpy(),side='right')-1
            assert np.array_equal(la[old],g.requires_ambiguity_fallback.to_numpy())
            assert g.used_earlier_request.equals(g.requires_ambiguity_fallback)
            entity=manifest_entities.loc[key];n=len(g);first=int(g.timestamp_us.iloc[0]);last=int(g.timestamp_us.iloc[-1]);gap=int(g.timestamp_us.diff().max()) if n>1 else 0
            assert key not in entities_checked;entities_checked.add(key)
            assert entity.observed_slots==n and entity.first_timestamp_us==first and entity.last_timestamp_us==last
            assert entity.missing_slots==1+(last-first)//CADENCE_US-n and entity.maximum_gap_us==gap
            assert bool(entity.eligible)==(n>=MIN_VALID_SLOTS and last-first>=MIN_SPAN_US)
            assert entity.request_states==len(g[['request_cpu_ncu','request_memory_normalized_ram']].drop_duplicates())
        # Independently encode edge/normalization source hashes via generic JSON.
        samples=pd.concat([f.head(10),f.tail(10),f[f.used_earlier_request].head(10),f[f.cpu_utilization.gt(1)|f.memory_utilization.gt(1)].head(10)]).drop_duplicates(keys)
        for row in samples.to_dict('records'):
            value=dict(cell='e',collection_id=int(row['collection_id']),instance_index=int(row['instance_index']),collection_type=1,
                start_time=int(row['source_start_time_us']),end_time=int(row['source_end_time_us']),
                average_cpu=float(row['average_cpu_ncu']),average_memory=float(row['average_memory_normalized_ram']),
                request_cpu=float(row['request_cpu_ncu']),request_memory=float(row['request_memory_normalized_ram']),
                request_event_time=int(row['request_event_time_us']),usage_source_table=row['usage_source_table'],request_source_table=row['request_source_table'])
            assert fingerprint(value)==row['source_row_sha256'];sampled+=1
        cpu_above+=int(f.cpu_utilization.gt(1).sum());mem_above+=int(f.memory_utilization.gt(1).sum());fallbacks+=int(f.used_earlier_request.sum())
        checked+=len(f);status.update(stage='exhaustive_validation',rows_processed=checked)
    assert len(entities_checked)==len(manifest_entities)
    return dict(passed=True,canonical_rows_verified=checked,entities_verified=len(entities_checked),
        ambiguous_groups_excluded=len(ambiguous),ambiguous_requests_selected=ambiguous_hits,
        every_row_latest_request_verified=True,every_row_normalization_exact=True,source_hash_edge_samples=sampled,
        above_one_cpu=cpu_above,above_one_memory=mem_above,fallback_canonical_rows=fallbacks,
        eligibility_definition=dict(minimum_observed_slots=MIN_VALID_SLOTS,minimum_span_us=MIN_SPAN_US),
        method_outcomes_computed=False)


def verify_parents(repo):
    parents={}
    for kind,(expected,rows) in EXPECTED.items():
        p=repo/f'data/google2019/raw/e/{kind}.parquet'
        sha=file_sha256(p);actual=pq.ParquetFile(p).metadata.num_rows
        if sha!=expected or actual!=rows:raise ValueError(f'raw {kind} identity mismatch')
        parents[kind]=dict(path=p.relative_to(repo).as_posix(),sha256=sha,rows=rows,size_bytes=p.stat().st_size)
    legacy=repo/'data/google2019/canonical/e';m=read_json(legacy/'manifest.json')
    old={p.relative_to(repo).as_posix():file_sha256(p) for p in legacy.iterdir() if p.is_file()}
    for entry in m['artifacts'].values():
        if old[entry['path']]!=entry['sha256']:raise ValueError('legacy canonical hash mismatch')
    lineage={}
    for name in ['data/google2019/raw/e/usage_parts/parts_manifest.json',
                 'data/google2019/raw/e/usage_parts/storage_read_checkpoint.json',
                 'configs/google2019_v4b7_recovery_record.json','data/google2019/checkpoints/e.json',
                 'data/google2019/v4_byte_ledger.json']:
        lineage[name]=dict(sha256=file_sha256(repo/name),record=read_json(repo/name))
    parts=lineage['data/google2019/raw/e/usage_parts/parts_manifest.json']['record']
    if parts['rows']!=EXPECTED['usage'][1] or parts['expected_rows']!=parts['rows']:raise ValueError('download lineage mismatch')
    for entry in parts['parts']:
        if file_sha256(repo/entry['path'])!=entry['sha256']:raise ValueError('download part hash mismatch')
    return parents,old,lineage


def regenerate(repo,workers=4):
    repo=Path(repo).resolve();source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean committed producer required')
    parents,legacy_hashes,lineage=verify_parents(repo)
    old_manifest=read_json(repo/'data/google2019/canonical/e/manifest.json')
    required=pq.ParquetFile(repo/parents['usage']['path']).metadata.serialized_size
    old_size=(repo/'data/google2019/canonical/e/canonical_usage.parquet').stat().st_size
    peak=int(old_size*1.25+parents['usage']['size_bytes']*1.5+2*2**30)
    free=disk_guard(repo,peak)
    identity=dict(schema_version=SCHEMA,normalization_version=NORMALIZATION,producer_commit=source.commit,
        parent_raw_sha256={k:v['sha256'] for k,v in parents.items()},partitions=PARTITIONS,
        request_rule=REQUEST_RULE,cadence_us=CADENCE_US,minimum_span_us=MIN_SPAN_US,minimum_valid_slots=MIN_VALID_SLOTS,
        source_hash='frozen-canonical-json-sha256-v1')
    generation_id='cell-e-unambiguous-v2-'+fingerprint(identity)[:16]
    out=repo/'data/google2019/canonical/generations'/generation_id
    if out.exists():raise FileExistsError('immutable generation already exists: '+str(out))
    out.mkdir(parents=True);(out/'partition_diagnostics').mkdir()
    status=Progress(repo,out);status.update(stage='prepare_request_history',rows_processed=0,expected_rows=EXPECTED['usage'][1],generation_id=generation_id)
    status.emit();start=time.time()
    try:
        clean,ambiguous,latest,request_audit=prepare_request_history(pq.read_table(repo/parents['events']['path']).to_pandas())
        if request_audit['ambiguous_groups']!=26002:raise ValueError('conflict-group audit changed')
        clean.to_parquet(out/'request_history.parquet',compression='zstd',index=False)
        ambiguous.to_parquet(out/'ambiguous_requests.parquet',compression='zstd',index=False)
        latest.to_parquet(out/'positive_event_times.parquet',compression='zstd',index=False)
        write_json(out/'request_history_audit.json',request_audit)
        n=partition_usage(repo/parents['usage']['path'],out/'work',PARTITIONS,status)
        if n!=EXPECTED['usage'][1]:raise ValueError('partitioning lost raw rows')
        tasks=[(p,out/'request_history.parquet',out/'positive_event_times.parquet',out,int(p.stem.split('_')[1])) for p in sorted((out/'work').glob('raw_*.parquet'))]
        status.update(stage='canonicalize',rows_processed=0);counts=[];processed=0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(process_partition,t) for t in tasks]
            try:
                for future in as_completed(futures):
                    result=future.result();counts.append(result);processed+=result['raw_usage_rows'];status.update(rows_processed=processed)
            except BaseException:
                for future in futures:future.cancel()
                raise
        (out/'work').rmdir()
        entities=pd.concat([pq.read_table(p).to_pandas() for p in sorted((out/'entities').glob('*.parquet'))],ignore_index=True)
        entities=entities.sort_values(['cell','collection_id','instance_index'],kind='mergesort').reset_index(drop=True)
        if entities.duplicated(['cell','collection_id','instance_index']).any():raise ValueError('entity partition split')
        entities.to_parquet(out/'entity_manifest.parquet',compression='zstd',index=False)
        eligible=entities.loc[entities.eligible,['cell','collection_id','instance_index']].to_dict('records')
        write_json(out/'eligible_cohort.json',dict(schema_version='google2019-acquisition-cohort-v2',generation_id=generation_id,
            role='acquisition-eligible; V4C protocol validation not yet frozen',rule=dict(minimum_observed_slots=MIN_VALID_SLOTS,minimum_span_us=MIN_SPAN_US),entities=eligible))
        sums={k:sum(int(c[k]) for c in counts) for k in ['raw_usage_rows','canonical_rows','rejected_rows',
            'requires_ambiguity_fallback_raw','successful_fallback_raw','no_earlier_valid_request_raw',
            'fallback_canonical_rows','above_one_cpu','above_one_memory']}
        reasons={}
        for c in counts:
            for k,v in c['exclusion_reasons'].items():reasons[k]=reasons.get(k,0)+v
        assert sums['raw_usage_rows']==sums['canonical_rows']+sums['rejected_rows']==EXPECTED['usage'][1]
        assert sums['rejected_rows']==sum(reasons.values())
        status.update(stage='exhaustive_validation',rows_processed=0,expected_rows=sums['canonical_rows'])
        validation=validate_local(out,clean,ambiguous,latest,status)
        assert validation['canonical_rows_verified']==sums['canonical_rows']
        for k,new in [('above_one_cpu','above_one_cpu'),('above_one_memory','above_one_memory'),('fallback_canonical_rows','fallback_canonical_rows')]:assert sums[k]==validation[new]
        status.update(stage='verify_unchanged_parents',rows_processed=0,expected_rows=0)
        again,old_again,lineage_again=verify_parents(repo)
        if again!=parents or old_again!=legacy_hashes or lineage_again!=lineage:raise ValueError('parent data/provenance changed')
        if SourceProvenance.capture(repo).commit!=source.commit or SourceProvenance.capture(repo).dirty:raise ValueError('producer source changed during regeneration')
        write_json(out/'validation.json',validation)
        diagnostics=dict(**sums,exclusion_reasons=reasons,request_history=request_audit,entities=len(entities),eligible_entities=len(eligible),
            request_change_entities=int(entities.has_request_change.sum()),entities_with_gaps=int(entities.missing_slots.gt(0).sum()),
            missing_slots=int(entities.missing_slots.sum()),maximum_gap_us=int(entities.maximum_gap_us.max()),
            minimum_timestamp_us=int(entities.first_timestamp_us.min()),maximum_timestamp_us=int(entities.last_timestamp_us.max()))
        write_json(out/'diagnostics.json',diagnostics)
        artifacts=[]
        for p in sorted(out.rglob('*')):
            if not p.is_file() or p.suffix not in ('.parquet','.json') or p.name=='status.json':continue
            entry=dict(path=p.relative_to(out).as_posix(),size_bytes=p.stat().st_size,sha256=file_sha256(p))
            if p.suffix=='.parquet':entry['rows']=pq.ParquetFile(p).metadata.num_rows
            artifacts.append(entry)
        canonical_parts=[a for a in artifacts if a['path'].startswith('canonical_usage/')]
        manifest=dict(**identity,generation_id=generation_id,status='VERIFIED',source=asdict(source),raw_parents=parents,
            download_lineage=lineage,legacy_generation=dict(path='data/google2019/canonical/e',status='SUPERSEDED_INVALID_FOR_REPLICATION',sha256_inventory=legacy_hashes),
            environment=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__),
            output_row_count=sums['canonical_rows'],entity_count=len(entities),acquisition_eligible_entities=len(eligible),
            canonical_dataset_sha256=fingerprint(canonical_parts),entity_manifest_sha256=file_sha256(out/'entity_manifest.parquet'),
            cohort_sha256=file_sha256(out/'eligible_cohort.json'),artifacts=artifacts,diagnostics=diagnostics,validation=validation,
            query_bytes_this_generation=0,cloud_calls=0,billing='untouched; no cloud client constructed',
            replication_outcomes_computed=False,replication_cohort_frozen=False,next_gate='V4C — Google corpus/cohort protocol validation',
            disk_preflight=dict(available_bytes=free,required_peak_bytes=peak,reserve_bytes=RESERVE),
            created_at=utc_now(),wall_seconds=time.time()-start)
        write_json(out/'manifest.json',manifest)
        write_json(out/'SUCCESS',dict(manifest_sha256=file_sha256(out/'manifest.json'),generation_id=generation_id))
        require_corrected_generation(out)
        registry=dict(schema_version='google2019-canonical-registry-v1',cell='e',raw_acquisition='VERIFIED',
            old_generation=dict(path='data/google2019/canonical/e',status='SUPERSEDED_INVALID_FOR_SCIENTIFIC_REPLICATION',hashes=legacy_hashes),
            active_generation=dict(path=out.relative_to(repo).as_posix(),generation_id=generation_id,status='VERIFIED',manifest_sha256=file_sha256(out/'manifest.json')),
            next_gate=manifest['next_gate'],query_bytes_this_generation=0)
        write_json(repo/'data/google2019/canonical/registry.json',registry)
        status.update(stage='VERIFIED',rows_processed=sums['canonical_rows'],expected_rows=sums['canonical_rows'],generation_id=generation_id)
        record=dict(schema_version='google2019-v4b8-correction-record-v1',gate='V4B.8',status='VERIFIED',
            generation_id=generation_id,path=out.relative_to(repo).as_posix(),producer_commit=source.commit,
            manifest_sha256=file_sha256(out/'manifest.json'),canonical_dataset_sha256=manifest['canonical_dataset_sha256'],
            entity_manifest_sha256=manifest['entity_manifest_sha256'],cohort_sha256=manifest['cohort_sha256'],
            raw_parents=parents,old_counts=dict(rows=old_manifest['row_count'],entities=old_manifest['entity_count'],eligible=old_manifest['eligible_entity_count']),
            diagnostics=diagnostics,validation=validation,query_bytes_this_generation=0,billing='untouched',next_gate=manifest['next_gate'])
        write_json(repo/'configs/google2019_v4b8_correction_record.json',record)
        print(canonical_json(record),flush=True)
        return record
    except BaseException as exc:
        status.update(stage='FAILED',error=f'{type(exc).__name__}: {exc}')
        write_json(out/'FAILED',dict(error_type=type(exc).__name__,message=str(exc),recorded_at=utc_now()))
        raise
    finally:status.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--workers',type=int,choices=(1,2,4),default=4)
    a=p.parse_args();regenerate(a.repo,a.workers)

if __name__=='__main__':main()
