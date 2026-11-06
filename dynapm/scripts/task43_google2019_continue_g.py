"""Offline continuation of the verified November cell-g disk stop."""
import argparse
from collections import Counter
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_availability_validation import validate_protocol_v2
from dynapm.experiments.google2019_durable_read import sync_directory
from dynapm.experiments.google2019_g_local import Progress, inventory, seal_canonical
from dynapm.experiments.google2019_local_canonical import PARTITIONS, disk_guard, process_partition, validate_local
from dynapm.experiments.google2019_requests import KEYS, PAIR, REQUEST_RULE, prepare_request_history
from dynapm.experiments.google_replication import load_stage_inputs
from dynapm.experiments.google_staged_design import E_BINDING, G_BINDING, frozen_design
from dynapm.scripts.task42_google2019_cell_g import LEDGER, MONTH, ROOT, campaign_lock, finish, raw_paths, read_ledger
from dynapm.system_validation.v8_campaign import publish_record

EVIDENCE = 'results/google2019_v4c2_g_blocked/4494d58a3711'
EVIDENCE_SHA = '861c78e3f8700546e9f3e3087e3adf7e41fd24f02b0504adb22ef11fe1a04289'
MIN_FREE = 40*2**30
EXPECTED_BYTES = 449979620664
ORIGINAL_END = 186
V8_SEAL = 'results/bounded_v8/campaign-v1/snapshots/FROZEN'
V8_SEAL_SHA = '3b9b443d18706589a6c8fb87654d7c89170e891dda9c93b0cac37bef4e49de94'
HISTORY = ('request_history','ambiguous_requests','positive_event_times')
PRODUCTS = ('canonical_usage','rejected_rows','entities','partition_diagnostics',*HISTORY)


def contiguous(indices, start=0):
    numbers = sorted(indices)
    if numbers!=list(range(start,start+len(numbers))):
        raise ValueError('noncontiguous_shard_checkpoints')
    return start+len(numbers)


def verified_partial(repo, root):
    evidence = repo/EVIDENCE
    record = read_json(evidence/'RECORD.json')
    if file_sha256(evidence/'RECORD.json')!=EVIDENCE_SHA:
        raise ValueError('original_blocked_record_changed')
    for item in record['local_evidence']:
        if file_sha256(evidence/item['path'])!=item['sha256']:
            raise ValueError('original_blocked_evidence_changed')
    old = root/'.canonical.partial'
    original = read_json(evidence/'partial-canonical-inventory.json')['artifacts']
    if len(original)!=1444 or inventory(old)!=original:
        raise ValueError('blocked_partial_inventory_changed')
    ids = (int(p.stem) for p in (old/'partition_diagnostics').glob('*.json'))
    if contiguous(ids)!=ORIGINAL_END:
        raise ValueError('historical_shard_count_changed')
    for pid in range(ORIGINAL_END):
        reconcile_shard(old,pid)
    return old,record


def reconcile_shard(root, pid):
    part = f'part_{pid:03d}.parquet'
    counts = read_json(root/'partition_diagnostics'/f'{pid:03d}.json')
    if (counts['partition']!=pid or counts['canonical_rows']+counts['rejected_rows']!=counts['raw_usage_rows']
            or sum(counts['exclusion_reasons'].values())!=counts['rejected_rows']):
        raise ValueError('shard_counts_do_not_reconcile')
    for key in ('canonical_rows','rejected_rows'):
        folder = 'canonical_usage' if key=='canonical_rows' else 'rejected_rows'
        if pq.ParquetFile(root/folder/part).metadata.num_rows!=counts[key]:
            raise ValueError('shard_footer_does_not_reconcile')
    return counts


def verified_shard(path, inputs):
    if path.is_symlink():
        raise ValueError('linked_shard_output')
    record = read_json(path/'SHARD.json')
    files = [x for x in inventory(path) if x['path']!='SHARD.json']
    if record['inputs']!=inputs or record['artifacts']!=files:
        raise ValueError('shard_seal_changed')
    if reconcile_shard(path,inputs['partition'])!=record['counts']:
        raise ValueError('shard_diagnostics_changed')
    return record


def publish_shard(work, inputs, produce):
    """Atomic per-shard publication. Interrupted attempts remain available."""
    pid = inputs['partition']
    destination = work/f'{pid:03d}'
    if destination.exists():
        return verified_shard(destination,inputs)
    disk_guard(work,256*2**20)
    attempts = work/'attempts'
    attempts.mkdir(exist_ok=True)
    previous = sorted(attempts.glob(f'{pid:03d}-*'))
    sealed = [p for p in previous if (p/'SHARD.json').is_file()]
    if len(sealed)>1:
        raise ValueError('multiple_sealed_attempts_for_shard')
    if sealed:
        record = verified_shard(sealed[0],inputs)
        os.rename(sealed[0],destination)
        sync_directory(work)
        sync_directory(attempts)
        return record
    number = 1+len(previous)
    stage = attempts/f'{pid:03d}-{number:03d}'
    stage.mkdir()
    validation = produce(stage)
    record = dict(inputs=inputs,counts=reconcile_shard(stage,pid),validation=validation,
                  artifacts=inventory(stage))
    directories = set()
    for entry in record['artifacts']:
        path = stage/entry['path']
        with path.open('rb') as handle:
            os.fsync(handle.fileno())
        directories.add(path.parent)
    for directory in directories:
        sync_directory(directory)
    publish_record(stage/'SHARD.json',record)
    verified_shard(stage,inputs)
    os.rename(stage,destination)
    sync_directory(work)
    sync_directory(attempts)
    return record


def histories(path, pid):
    part = f'part_{pid:03d}.parquet'
    return tuple(pq.read_table(path/n/part).to_pandas() for n in HISTORY)


def create_shard(out, old, pid):
    event = old/'work/events'/f'raw_{pid:03d}.parquet'
    usage = old/'work/usage'/f'raw_{pid:03d}.parquet'
    if pq.ParquetFile(usage).metadata.num_rows>8_000_000:
        raise ValueError('canonical_partition_memory_ceiling')
    part = f'part_{pid:03d}.parquet'
    for n in (*HISTORY,'partition_diagnostics'):
        (out/n).mkdir()
    if event.exists():
        if pq.ParquetFile(event).metadata.num_rows>8_000_000:
            raise ValueError('request_partition_memory_ceiling')
        clean,bad,latest,_ = prepare_request_history(pq.read_table(event).to_pandas())
        for name,frame in zip(HISTORY,(clean,bad,latest),strict=True):
            disk_guard(out,max(256*2**20,int(frame.memory_usage(index=False,deep=True).sum())))
            frame.to_parquet(out/name/part,compression='zstd',index=False)
    else:
        # Shard 186 had sealed-in-inventory request tables before the reserve stop.
        clean,bad,latest = histories(old,pid)
        for name in HISTORY:
            os.link(old/name/part,out/name/part)
    process_partition((usage,out/'request_history'/part,out/'positive_event_times'/part,out,pid),
                      cell='g',consume_input=False)
    return validate_local(out,clean,bad,latest,Progress(),cell='g',partition=part)


def event_totals(paths, expected):
    """Account for invalid and identical raw requests without storing another copy."""
    positive = 0
    rows = 0
    for path in paths:
        for batch in pq.ParquetFile(path).iter_batches(columns=KEYS+PAIR):
            columns = [batch.column(i).to_numpy(zero_copy_only=False) for i in range(len(KEYS+PAIR))]
            good = np.logical_and.reduce([np.isfinite(a) for a in columns])
            positive += int((good & (columns[-2]>0) & (columns[-1]>0)).sum())
            rows += batch.num_rows
    if rows!=expected:
        raise ValueError('raw_event_footer_reconciliation_failed')
    return rows,positive


def assemble(root, old, work, raw, files, source, binding):
    canonical = root/'canonical'
    if canonical.exists():
        return
    # A failed assembly is retained. Links reuse bytes already on this volume.
    attempt = 1+len(list(work.glob('assembly-*')))
    stage = work/f'assembly-{attempt:03d}'
    stage.mkdir()
    for name in PRODUCTS:
        (stage/name).mkdir()
    totals,reasons,validation = Counter(),Counter(),Counter()
    clean_rows = ambiguous_groups = ambiguous_tuples = 0
    flags = None
    for pid in range(PARTITIONS):
        part = f'part_{pid:03d}.parquet'
        location = old if pid<ORIGINAL_END else work/f'{pid:03d}'
        counts = reconcile_shard(location,pid)
        reasons.update(counts.pop('exclusion_reasons'))
        counts.pop('partition')
        totals.update(counts)
        clean,bad,latest = histories(location,pid)
        clean_rows += len(clean)
        ambiguous_groups += len(bad)
        ambiguous_tuples += int(bad.distinct_request_pairs.sum())
        if len(latest)!=len(clean)+len(bad):
            raise ValueError('request_group_counts_do_not_reconcile')
        if pid<ORIGINAL_END:
            result = validate_local(location,clean,bad,latest,Progress(),cell='g',partition=part)
        else:
            result = verified_shard(location,dict(binding,partition=pid))['validation']
        validation.update({k:v for k,v in result.items() if type(v) is int})
        current = {k:v for k,v in result.items() if type(v) is not int}
        if flags is not None and current!=flags:
            raise ValueError('canonical_validation_flags_changed')
        flags = current
        for name in PRODUCTS:
            filename = f'{pid:03d}.json' if name=='partition_diagnostics' else part
            os.link(location/name/filename,stage/name/filename)
    rows,positive = event_totals(files['events'],raw['events']['rows'])
    distinct = clean_rows+ambiguous_tuples
    if distinct>positive or totals['raw_usage_rows']!=raw['usage']['rows']:
        raise ValueError('final_raw_counts_do_not_reconcile')
    request = dict(raw_event_rows=rows,invalid_request_event_rows=rows-positive,positive_event_rows=positive,
        identical_duplicate_copies=positive-distinct,distinct_request_tuples=distinct,ambiguous_groups=ambiguous_groups,
        ambiguous_distinct_request_tuples=ambiguous_tuples,usable_request_history_rows=clean_rows,rule=REQUEST_RULE)
    disk_guard(stage,256*2**20)
    manifest = seal_canonical(stage,'g',raw,source,totals,reasons,request,dict(**flags,**validation))
    publish_record(stage/'PHASE.json',dict(inputs=dict(source=source,raw=fingerprint(raw)),
                                         result=manifest,artifacts=inventory(stage)))
    os.rename(stage,canonical)
    sync_directory(root)
    sync_directory(work)


def run(repo, execute=False):
    root = repo/ROOT
    free = shutil.disk_usage(root).free
    if execute and free<MIN_FREE:
        raise ValueError(f'continuation_requires_40_GiB_free: {free/2**30:.3f}')
    run = read_json(root/'run.json')
    ledger = repo/LEDGER
    value = read_ledger(repo,MONTH,ledger,run['run_id'])
    if len(value['executed_entries'])!=2 or value['cumulative_executed_bytes']!=EXPECTED_BYTES:
        raise ValueError('sealed_november_accounting_required')
    old,record = verified_partial(repo,root)
    v8_ref = subprocess.check_output(['git','rev-parse','refs/heads/v8b-reference-freeze'],
                                     cwd=repo,text=True).strip()
    if (record['run_id']!=run['run_id'] or file_sha256(ledger)!=record['ledger_sha256']
            or file_sha256(repo/V8_SEAL)!=V8_SEAL_SHA or v8_ref!='39082cf6ffdfe1884194f4160131fa82c58676f1'):
        raise ValueError('protected_binding_changed')
    raw,files = {},{}
    for name in ('events','usage'):
        path = root/f'{name}-download.json'
        if file_sha256(path)!=record['raw_receipts'][name]:
            raise ValueError('sealed_raw_receipt_changed')
        raw[name] = read_json(path)
        if raw[name]['entry'] not in value['executed_entries']:
            raise ValueError('sealed_raw_job_mismatch')
        if execute:
            files[name] = raw_paths(root/name,raw[name])
    e = read_json(repo/E_BINDING)
    if file_sha256(repo/e['cohort_path'])!=e['cohort_sha256']:
        raise ValueError('frozen_e_cohort_changed')
    if not execute:
        return dict(status='LOCAL_CONTINUATION_PREFLIGHT',free_gib=free/2**30,minimum_free_gib=40,
                    storage_pass=free>=MIN_FREE,verified_historical_shards=ORIGINAL_END,processed_bytes=EXPECTED_BYTES)
    source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    status = subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).splitlines()
    final = root/'staged-inventory.json'
    completed_binding = (status==[f'?? {G_BINDING}'] and final.exists()
                         and read_json(repo/G_BINDING)==read_json(final)['g']['binding'])
    if (subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!='dynapm'
            or status and not completed_binding):
        raise ValueError('clean_dynapm_required')
    protocol,design = validate_protocol_v2(repo),frozen_design(repo)
    with campaign_lock(root):
        load_stage_inputs(repo,'e',repo/e['cohort_path'])
        if shutil.disk_usage(root).free<MIN_FREE:
            raise ValueError('continuation_requires_40_GiB_free_before_first_write')
        work = root/'offline-continuation'
        work.mkdir(exist_ok=True)
        binding = dict(source=source,run_id=run['run_id'],blocked_record=EVIDENCE_SHA,
                       raw_sha256=record['raw_receipts'],ledger_sha256=record['ledger_sha256'])
        intent = work/'intent.json'
        if not intent.exists():
            publish_record(intent,binding)
        if read_json(intent)!=binding:
            raise ValueError('continuation_input_binding_changed')
        next_shard = contiguous((int(p.name) for p in work.iterdir() if p.name.isdecimal()),ORIGINAL_END)
        if next_shard>PARTITIONS:
            raise ValueError('extra_canonical_shards')
        for pid in range(ORIGINAL_END,next_shard):
            verified_shard(work/f'{pid:03d}',dict(binding,partition=pid))
        for pid in range(next_shard,PARTITIONS):
            publish_shard(work,dict(binding,partition=pid),lambda out:create_shard(out,old,pid))
            print(f'Verified and sealed shard {pid:03d}',flush=True)
        assemble(root,old,work,raw,files,source,binding)
        disk_guard(root,256*2**20)
        g,dest = finish(repo,root,source,raw,files,protocol,design)
        verified_partial(repo,root)
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()!=source:
            raise ValueError('continuation_source_changed')
        if file_sha256(ledger)!=record['ledger_sha256']:
            raise ValueError('november_ledger_changed')
        if not (repo/G_BINDING).exists():
            publish_record(repo/G_BINDING,g)
        if read_json(repo/G_BINDING)!=g:
            raise ValueError('g_binding_changed')
        load_stage_inputs(repo,'g',repo/g['cohort_path'])
        return dict(status='CELL_G_READY',inventory_sha256=file_sha256(dest))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-local',action='store_true')
    args = parser.parse_args()
    print(canonical_json(run(Path(__file__).resolve().parents[2],args.execute_local)))


if __name__=='__main__':
    main()
