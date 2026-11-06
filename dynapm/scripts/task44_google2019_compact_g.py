"""Offline cell-g compaction and continuation with append-only retirement evidence."""
import argparse
import json
from importlib.metadata import version
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pandas as pd
import pyarrow.parquet as pq

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_availability_validation import audit_partition, validate_protocol_v2
from dynapm.experiments.google2019_durable_read import sync_directory
from dynapm.experiments.google2019_local_canonical import PARTITIONS, RESERVE, disk_guard
from dynapm.experiments.google2019_rejection_audit import rejection_record, validate_record
from dynapm.experiments.google_replication import load_stage_inputs
from dynapm.experiments.google_staged_design import E_BINDING, G_BINDING, frozen_design
from dynapm.scripts import task43_google2019_continue_g as resume
from dynapm.system_validation.v8_campaign import publish_record

GIB = 2**30
MARGIN = 512*2**20  # row-group write admission plus final small manifests
SAMPLES = {0,185}


def allocated(path):
    return path.stat().st_blocks*512 if path.is_file() else 0


def capacity(old, first, free):
    """Forecast from actual historical accepted/audit output and remaining footers."""
    prior_rows = 0
    output = 0
    for pid in range(resume.ORIGINAL_END):
        counts = read_json(old/'partition_diagnostics'/f'{pid:03d}.json')
        prior_rows += counts['raw_usage_rows']
        for name in resume.PRODUCTS:
            if name!='rejected_rows':
                filename = f'{pid:03d}.json' if name=='partition_diagnostics' else f'part_{pid:03d}.parquet'
                output += allocated(old/name/filename)
    spent = peak = gross = scratch = 0
    for pid in range(first,PARTITIONS):
        usage = old/'work/usage'/f'raw_{pid:03d}.parquet'
        events = old/'work/events'/f'raw_{pid:03d}.parquet'
        rows = pq.ParquetFile(usage).metadata.num_rows
        estimate = math.ceil(rows*output/prior_rows*1.10)
        release = allocated(usage)+allocated(events)
        gross += estimate
        scratch += release
        peak = max(peak,spent+estimate)
        spent += estimate-release
    required = RESERVE+max(0,peak,spent)+MARGIN
    return dict(free_bytes=free,required_free_bytes=required,estimated_output_bytes=gross,
                scratch_release_bytes=scratch,available=free>=required,estimate_safety_factor=1.10)


def sample_proof(log):
    entries = [line[6:] for line in Path(log).read_text().splitlines() if line.startswith('PROOF ')]
    if len(entries)!=1:
        raise ValueError('completed_raw_replay_proof_required')
    rows = json.loads(entries[0])
    if len(rows)!=len(SAMPLES) or {r['partition'] for r in rows}!=SAMPLES:
        raise ValueError('raw_replay_sample_scope_changed')
    return {r['partition']:r for r in rows}


def historical_audits(old, work, proof, binding):
    audits = work/'historical-audits'
    audits.mkdir(exist_ok=True)
    for pid in range(resume.ORIGINAL_END):
        part = f'part_{pid:03d}.parquet'
        path = audits/f'{pid:03d}.json'
        accepted = old/'canonical_usage'/part
        rejected = old/'rejected_rows'/part
        counts = read_json(old/'partition_diagnostics'/f'{pid:03d}.json')
        if path.exists():
            value = validate_record(path,accepted,counts,pid)
            if value['binding']!=binding:
                raise ValueError('historical_compaction_binding_changed')
        else:
            disk_guard(work,32*2**20)
            value = rejection_record(accepted,pq.read_table(rejected),partition=pid,counts=counts,
                conflicts=pq.ParquetFile(old/'ambiguous_requests'/part).metadata.num_rows,
                entities=pq.ParquetFile(old/'entities'/part).metadata.num_rows,
                binding=binding,prior=file_sha256(rejected))
            publish_record(path,value)
            validate_record(path,accepted,counts,pid)
        if pid in proof:
            replay = proof[pid]
            for key in ('accepted_sha256','logical_rejected_sha256','interval_counts','conflict_groups'):
                if replay[key]!=value[key]:
                    raise ValueError('sealed_raw_replay_disagrees_with_compact_record')
            if replay['rejected_parquet_sha256']!=value['prior_parquet_sha256']:
                raise ValueError('raw_replay_original_rejection_hash_changed')
    return audits


def availability_equivalence(old, audits, work):
    """Compare the unchanged availability path against the compact path on both replays."""
    for pid in sorted(SAMPLES):
        part = f'part_{pid:03d}.parquet'
        path = old/'canonical_usage'/part
        entities = pq.read_table(old/'entities'/part).to_pandas().set_index(['collection_id','instance_index'])
        expected = audit_partition('g',old,path,entities)
        with tempfile.TemporaryDirectory(dir=work) as tmp:
            root = Path(tmp)
            for name,source in [('canonical_usage',path),
                                ('partition_diagnostics',old/'partition_diagnostics'/f'{pid:03d}.json'),
                                ('rejection_audit',audits/f'{pid:03d}.json')]:
                (root/name).mkdir()
                os.link(source,root/name/source.name)
            actual = audit_partition('g',root,root/'canonical_usage'/part,entities)
            pd.testing.assert_frame_equal(pd.DataFrame(expected[0]),pd.DataFrame(actual[0]))
            if expected[1:]!=actual[1:]:
                raise ValueError('compact_availability_stats_changed')


def replacement_path(work, relative):
    parts = Path(relative).parts
    if len(parts)==2 and parts[0]=='rejected_rows':
        pid = int(Path(parts[-1]).stem.split('_')[1])
        if 0<=pid<resume.ORIGINAL_END and relative==f'rejected_rows/part_{pid:03d}.parquet':
            return work/'historical-audits'/f'{pid:03d}.json'
    elif len(parts)==3 and parts[:2] in (('work','events'),('work','usage')):
        pid = int(Path(parts[-1]).stem.split('_')[1])
        if resume.ORIGINAL_END<=pid<PARTITIONS and parts[-1]==f'raw_{pid:03d}.parquet':
            return work/'shards'/f'{pid:03d}'/'SHARD.json'
    raise ValueError('retirement_path_not_authorized')


def retire(old, work, entry, binding):
    """Journal the exact replacement before removing a proven regenerable file."""
    relative = entry['path']
    replacement = replacement_path(work,relative)
    source = old/relative
    records = work/'deletion-ledger'
    records.mkdir(exist_ok=True)
    path = records/(fingerprint(relative)+'.json')
    common = dict(original=entry,replacement=replacement.relative_to(work).as_posix(),
                  replacement_sha256=file_sha256(replacement),regeneration=binding)
    if not path.exists():
        if not source.is_file() or file_sha256(source)!=entry['sha256']:
            raise ValueError('unverified_original_at_retirement')
        disk_guard(work,8*2**20)
        publish_record(path,dict(common,allocated_bytes=allocated(source)))
    saved = read_json(path)
    if {k:v for k,v in saved.items() if k!='allocated_bytes'}!=common:
        raise ValueError('retirement_ledger_binding_changed')
    if source.exists():
        if file_sha256(source)!=entry['sha256']:
            raise ValueError('retired_original_changed')
        source.unlink()
        sync_directory(source.parent)
    return saved


def retired_paths(old, work, original, binding):
    removed = set()
    for p in (work/'deletion-ledger').glob('*.json'):
        saved = read_json(p)
        relative = saved['original']['path']
        replacement = replacement_path(work,relative)
        if (p.stem!=fingerprint(relative) or saved['original']!=original[relative]
                or saved['regeneration']!=binding
                or saved['replacement']!=replacement.relative_to(work).as_posix()
                or file_sha256(replacement)!=saved['replacement_sha256']):
            raise ValueError('retirement_evidence_mismatch')
        if not (old/relative).exists():
            removed.add(relative)
    return removed


def git(repo, *args):
    return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()


def run(repo, proof_log, execute):
    root = repo/resume.ROOT
    old = root/'.canonical.partial'
    work = root/'offline-compact-continuation'
    staged = root/'staged-inventory.json'
    source = git(repo,'rev-parse','HEAD')
    status = git(repo,'status','--porcelain')
    generated = (status==f'?? {G_BINDING}' and staged.exists()
                 and read_json(repo/G_BINDING)==read_json(staged)['g']['binding'])
    if git(repo,'branch','--show-current')!='dynapm' or status and not generated:
        raise ValueError('clean_dynapm_required')
    protocol,design = validate_protocol_v2(repo),frozen_design(repo)
    evidence = repo/resume.EVIDENCE
    record = read_json(evidence/'RECORD.json')
    original = {a['path']:a for a in read_json(evidence/'partial-canonical-inventory.json')['artifacts']}
    ledger = repo/resume.LEDGER
    if file_sha256(evidence/'RECORD.json')!=resume.EVIDENCE_SHA or file_sha256(ledger)!=record['ledger_sha256']:
        raise ValueError('historical_record_or_ledger_changed')
    nov = resume.read_ledger(repo,resume.MONTH,ledger,record['run_id'])
    if (len(nov['executed_entries'])!=2 or nov['cumulative_executed_bytes']!=resume.EXPECTED_BYTES
            or file_sha256(repo/resume.V8_SEAL)!=resume.V8_SEAL_SHA
            or git(repo,'rev-parse','refs/heads/v8b-reference-freeze')!='39082cf6ffdfe1884194f4160131fa82c58676f1'):
        raise ValueError('protected_execution_binding_changed')
    raw = {}
    for name in ('events','usage'):
        p = root/f'{name}-download.json'
        if file_sha256(p)!=record['raw_receipts'][name]:
            raise ValueError('sealed_raw_receipt_changed')
        raw[name] = read_json(p)
        if raw[name]['entry'] not in nov['executed_entries']:
            raise ValueError('sealed_raw_job_binding_changed')
    if not execute:
        reclaimed = sum(allocated(p) for p in (old/'rejected_rows').glob('*.parquet'))
        free = shutil.disk_usage(root).free
        return dict(status='OFFLINE_COMPACTION_PLAN',current_free_bytes=free,historical_rejection_bytes=reclaimed,
                    projected_after_compaction=capacity(old,resume.ORIGINAL_END,free+reclaimed))
    with resume.campaign_lock(root):
        disk_guard(root,128*2**20)
        work.mkdir(exist_ok=True)
        proof_file = work/'raw-replay-proof.json'
        if not proof_file.exists():
            if proof_log is None:
                raise ValueError('sealed_raw_replay_log_required')
            proof = sample_proof(proof_log)
            replay_log = work/'raw-replay.log'
            if not replay_log.exists():
                with replay_log.open('xb') as handle:
                    handle.write(proof_log.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                replay_log.chmod(0o444)
            if file_sha256(replay_log)!=file_sha256(proof_log):
                raise ValueError('sealed_replay_log_changed')
            publish_record(proof_file,dict(samples=list(proof.values()),log_sha256=file_sha256(replay_log),
                                          receipts=record['raw_receipts']))
        proof_record = read_json(proof_file)
        proof = {x['partition']:x for x in proof_record['samples']}
        if (set(proof)!=SAMPLES or proof_record['receipts']!=record['raw_receipts']
                or file_sha256(work/'raw-replay.log')!=proof_record['log_sha256']):
            raise ValueError('compact_replay_provenance_changed')
        binding = dict(source_commit=source,prior_generation_source=read_json(evidence/'audit.json')['source_commit'],
            raw_receipts=record['raw_receipts'],blocked_record=resume.EVIDENCE_SHA,
            protocol=protocol,design_sha256=fingerprint(design),replay_sha256=file_sha256(proof_file),
            derivation_sha256={p:file_sha256(repo/p) for p in (
                'dynapm/experiments/google2019_local_canonical.py',
                'dynapm/experiments/google2019_requests.py',
                'dynapm/experiments/google2019_rejection_audit.py')},
            runtime={p:version(p) for p in ('pandas','numpy','pyarrow')},
            partitions=PARTITIONS,partition_rule='(collection_id*1000003+instance_index)%256',
            logical_digest='typed_ordered_arrow_ipc_batches_65536_with_null_validity')
        intent = work/'intent.json'
        if not intent.exists():
            publish_record(intent,binding)
        if read_json(intent)!=binding:
            raise ValueError('compact_continuation_binding_changed')
        audits = work/'historical-audits'
        removed = retired_paths(old,work,original,binding)
        resume.verified_partial(repo,root,removed=removed,compact=audits)
        files = {k:resume.raw_paths(root/k,v) for k,v in raw.items()}
        e = read_json(repo/E_BINDING)
        load_stage_inputs(repo,'e',repo/e['cohort_path'])
        audits = historical_audits(old,work,proof,binding)
        equivalence = work/'EQUIVALENCE.json'
        if not equivalence.exists():
            availability_equivalence(old,audits,work)
            publish_record(equivalence,dict(binding=binding,historical_audits=resume.inventory(audits),
                                            samples=sorted(SAMPLES),same_availability_metadata=True))
        if read_json(equivalence)!=dict(binding=binding,historical_audits=resume.inventory(audits),
                                         samples=sorted(SAMPLES),same_availability_metadata=True):
            raise ValueError('compact_equivalence_seal_changed')
        for pid in range(resume.ORIGINAL_END):
            relative = f'rejected_rows/part_{pid:03d}.parquet'
            if read_json(audits/f'{pid:03d}.json')['prior_parquet_sha256']!=original[relative]['sha256']:
                raise ValueError('historical_rejection_replacement_mismatch')
            retire(old,work,original[relative],binding)
        print('Sealed and retired 186 historical rejection payloads',flush=True)
        shards = work/'shards'
        shards.mkdir(exist_ok=True)
        next_shard = resume.contiguous((int(p.name) for p in shards.iterdir() if p.name.isdecimal()),resume.ORIGINAL_END)
        if next_shard>PARTITIONS:
            raise ValueError('extra_compact_shards')
        for pid in range(resume.ORIGINAL_END,next_shard):
            resume.verified_shard(shards/f'{pid:03d}',dict(binding,partition=pid))
            retire_scratch(old,work,original,pid,binding)
        forecast = capacity(old,next_shard,shutil.disk_usage(root).free)
        print(canonical_json(dict(phase='compact_capacity',**forecast)),flush=True)
        if not forecast['available']:
            raise ValueError('insufficient_capacity_after_verified_compaction')
        for pid in range(next_shard,PARTITIONS):
            resume.publish_shard(shards,dict(binding,partition=pid),
                                 lambda p:resume.create_shard(p,old,pid,compact_binding=binding))
            retire_scratch(old,work,original,pid,binding)
            print(f'Verified and sealed compact shard {pid:03d}',flush=True)
        removed = retired_paths(old,work,original,binding)
        resume.verified_partial(repo,root,removed=removed,compact=audits)
        resume.assemble(root,old,shards,raw,files,source,binding,compact=audits)
        disk_guard(root,256*2**20)
        g,destination = resume.finish(repo,root,source,raw,files,protocol,design)
        if (git(repo,'rev-parse','HEAD')!=source or file_sha256(ledger)!=record['ledger_sha256']
                or any(file_sha256(root/f'{k}-download.json')!=sha for k,sha in record['raw_receipts'].items())):
            raise ValueError('final_protected_binding_changed')
        if not (repo/G_BINDING).exists():
            publish_record(repo/G_BINDING,g)
        if read_json(repo/G_BINDING)!=g:
            raise ValueError('stage_g_binding_changed')
        load_stage_inputs(repo,'g',repo/g['cohort_path'])
        return dict(status='CELL_G_READY',inventory_sha256=file_sha256(destination),retired_files=len(removed))


def retire_scratch(old, work, original, pid, binding):
    for name in ('events','usage'):
        relative = f'work/{name}/raw_{pid:03d}.parquet'
        if relative in original:
            retire(old,work,original[relative],binding)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-local',action='store_true')
    parser.add_argument('--proof-log',type=Path)
    args = parser.parse_args()
    print(canonical_json(run(Path(__file__).resolve().parents[2],args.proof_log,args.execute_local)))


if __name__=='__main__':
    main()
