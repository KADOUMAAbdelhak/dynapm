"""V4C.2A single-use, month-scoped cell-g acquisition. Default is offline preflight."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.core.run_store import write_json
from dynapm.experiments.google2019_acquisition import (
    ZERO_COST_CUMULATIVE_EXECUTION_CAP_BYTES as CAP, require_zero_cost_project, resolve_quota_project)
from dynapm.experiments.google2019_availability_validation import validate_clock_audit, validate_protocol_v2
from dynapm.experiments.google2019_durable_read import completed_download, download_result, sync_directory
from dynapm.experiments.google2019_execute_acquisition import DRY_RUN_TOLERANCE, FROZEN_PLAN_FINGERPRINT, expected_bytes_map
from dynapm.experiments.google2019_g_local import availability, canonicalize, freeze_cohort, inventory
from dynapm.experiments.google2019_local_canonical import disk_guard
from dynapm.experiments.google2019_streaming import validate_streaming_plan
from dynapm.experiments.google2019_streaming_execute import disk_safe_for_g_after_e, maximum_bytes_billed_for
from dynapm.experiments.google2019_zero_cost_plan import load_plan, render_plan_query, template_hashes
from dynapm.experiments.google_replication import load_stage_inputs
from dynapm.experiments.google_staged_design import E_BINDING, G_BINDING, frozen_design
from dynapm.scripts.task41_bounded_v8 import CAMPAIGN as V8_CAMPAIGN, completed_attempts
from dynapm.system_validation.v8_campaign import publish_record

MONTH = '2026-11'
LEDGER = f'data/google2019/v4_byte_ledger_{MONTH}.json'
OCTOBER = 'data/google2019/v4_byte_ledger.json'
OCTOBER_SHA = '4a2c68fdd3220a96bccc75b98652d52d5d25eaabb6df982bcc067f978d95652d'
ZERO_LEDGER_SHA = 'd80fa106e1ae548e6c908f15048bd559bb115c2c6fcd17759d8cbacd30c00364'
ROOT = f'data/google2019/execution/v4c2-g-{MONTH}'
TEMPLATES = {'events':'21_events_minimal.sql','usage':'20_usage_minimal.sql'}


def read_ledger(repo, month, path, run_id=None):
    if month!=MONTH or path!=repo/LEDGER or path.resolve()!=path:
        raise ValueError('explicit_november_ledger_required')
    if file_sha256(repo/OCTOBER)!=OCTOBER_SHA:
        raise ValueError('october_ledger_changed')
    value = read_json(path)
    if value['month_utc']!=MONTH or value['cap_bytes']!=CAP:
        raise ValueError('ledger_month_or_cap_mismatch')
    entries = value['executed_entries']
    if (len({x['job_id'] for x in entries})!=len(entries)
            or len({x['query_name'] for x in entries})!=len(entries)
            or any(x['query_name'] not in {f'g:{v}' for v in TEMPLATES.values()} for x in entries)):
        raise ValueError('duplicate_or_foreign_ledger_job')
    if entries and (run_id is None or any(x['run_id']!=run_id for x in entries)):
        raise ValueError('ledger_belongs_to_another_run')
    if not entries and file_sha256(path)!=ZERO_LEDGER_SHA:
        raise ValueError('initial_november_ledger_mismatch')
    total = sum(x['executed_bytes'] for x in entries)
    if any(type(x['executed_bytes']) is not int or x['executed_bytes']<0 for x in entries):
        raise ValueError('invalid_ledger_execution_bytes')
    if total!=value['cumulative_executed_bytes'] or total>CAP:
        raise ValueError('monthly_ledger_reconciliation_failed')
    return value


def account(repo, path, run_id, entry):
    ledger = read_ledger(repo,MONTH,path,run_id)
    entries = ledger['executed_entries']
    previous = next((e for e in entries if e['job_id']==entry['job_id']),None)
    if previous is not None:
        if previous!=entry:
            raise ValueError('recorded_job_metadata_changed')
        return
    if entry['run_id']!=run_id or any(e['query_name']==entry['query_name'] for e in entries):
        raise ValueError('duplicate_logical_scan')
    total = ledger['cumulative_executed_bytes']+entry['executed_bytes']
    if total>CAP:
        raise ValueError('monthly_execution_cap_exceeded')
    write_json(path,dict(ledger,executed_entries=[*entries,entry],cumulative_executed_bytes=total,
                         acquisition_status='IN_PROGRESS'))
    sync_directory(Path(path).parent)


def frozen_queries():
    plan = load_plan()
    if fingerprint(plan)!=FROZEN_PLAN_FINGERPRINT or template_hashes()!=plan['templates']:
        raise ValueError('frozen_sql_or_plan_changed')
    queries = {}
    for kind,template in TEMPLATES.items():
        expected = expected_bytes_map(plan)['g',template]
        sql = render_plan_query(template,'g')
        queries[kind] = dict(expected_bytes=expected,maximum_bytes_billed=maximum_bytes_billed_for(expected),
            query_sha256=hashlib.sha256(sql.encode()).hexdigest())
    return queries


def dry_run(client, project, kind, spec, billing):
    from google.cloud import bigquery
    billing(project)
    result = client.query(render_plan_query(TEMPLATES[kind],'g'),location='US',timeout=30,
        job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,
                                         maximum_bytes_billed=spec['maximum_bytes_billed']))
    got = int(result.total_bytes_processed or 0)
    if (got<=0 or got>spec['maximum_bytes_billed']
            or abs(got-spec['expected_bytes'])/spec['expected_bytes']>DRY_RUN_TOLERANCE):
        raise ValueError(f'g_{kind}_dry_run_changed')
    return got


def open_query(root, client, project, kind, spec, run_id, ledger_bytes, billing, dry=dry_run):
    """Journal the stable job ID before submit. Uncertain prior submissions never retry."""
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery
    path = root/f'{kind}-query.json'
    job_id = f'dynapm_v4c2_g_{kind}_{run_id[:24]}'
    binding = dict(kind=kind,job_id=job_id,project=project,location='US',spec=spec,month=MONTH)
    sql = render_plan_query(TEMPLATES[kind],'g')
    billing(project)
    if path.exists():
        journal = read_json(path)
        if journal['binding']!=binding:
            raise ValueError('query_intent_binding_changed')
        try:
            job = client.get_job(job_id,location='US',timeout=30)
        except NotFound as exc:
            raise ValueError('prior_submission_uncertain_no_rescan') from exc
    else:
        dry_bytes = dry(client,project,kind,spec,billing)
        if ledger_bytes+spec['maximum_bytes_billed']>CAP:
            raise ValueError('monthly_cap_reservation_exceeded')
        journal = dict(binding=binding,dry_run_bytes=dry_bytes,created_at=utc_now())
        publish_record(path,journal)
        billing(project)
        job = client.query(sql,job_id=job_id,location='US',timeout=30,retry=None,job_retry=None,
            job_config=bigquery.QueryJobConfig(dry_run=False,use_query_cache=False,
                                             maximum_bytes_billed=spec['maximum_bytes_billed']))
    if (job.job_id!=job_id or job.project!=project or job.location!='US'
            or job.query!=sql or job.maximum_bytes_billed!=spec['maximum_bytes_billed']
            or job.use_query_cache is not False):
        raise ValueError('server_job_configuration_changed')
    return job,journal


def raw_paths(folder, manifest):
    """Reconcile every stream, file, committed offset, footer and manifest row count."""
    if completed_download(folder)!={k:v for k,v in manifest.items() if k!='entry'}:
        raise ValueError('download_rows_do_not_reconcile')
    return [folder/c['path'] for c in manifest['chunks']]


def acquire(repo, root, project, client, run_id, spec, kind, credentials):
    receipt = root/f'{kind}-download.json'
    ledger_path = repo/LEDGER
    ledger = read_ledger(repo,MONTH,ledger_path,run_id)
    if not receipt.exists():
        disk_guard(root,256*2**20)
        if datetime.now(timezone.utc).strftime('%Y-%m')!=MONTH:
            raise ValueError('execution_month_mismatch')
        job,journal = open_query(root,client,project,kind,spec,run_id,ledger['cumulative_executed_bytes'],
                                 require_zero_cost_project)
        while job.state!='DONE':
            time.sleep(3)
            job.reload(timeout=30)
        processed,billed = job.total_bytes_processed,job.total_bytes_billed
        if processed is None or billed is None:
            raise ValueError('query_bytes_unreconciled_no_rescan')
        entry = dict(run_id=run_id,job_id=job.job_id,query_name=f'g:{TEMPLATES[kind]}',
                     executed_bytes=int(processed),billed_bytes=int(billed),
                     dry_run_bytes=journal['dry_run_bytes'],query_sha256=spec['query_sha256'])
        account(repo,ledger_path,run_id,entry)
        if (job.error_result or processed<=0 or billed>spec['maximum_bytes_billed']
                or processed>spec['maximum_bytes_billed'] or job.cache_hit is not False or job.destination is None):
            raise ValueError('query_terminal_invalid_no_rescan')
        raw = completed_download(root/kind)
        if raw is None:
            table = client.get_table(job.destination,timeout=30)
            raw = download_result(job,table,root/kind,project,credentials=credentials)
        if raw['result']['job_id']!=job.job_id:
            raise ValueError('storage_read_result_job_changed')
        publish_record(receipt,dict(entry=entry,**raw))
    raw = read_json(receipt)
    if raw['entry'] not in read_ledger(repo,MONTH,ledger_path,run_id)['executed_entries']:
        raise ValueError('download_ledger_binding_changed')
    journal = read_json(root/f'{kind}-query.json')
    if (raw['entry']['run_id']!=run_id or raw['entry']['query_sha256']!=spec['query_sha256']
            or raw['entry']['job_id']!=raw['result']['job_id']
            or raw['entry']['job_id']!=journal['binding']['job_id']
            or journal['binding']['spec']!=spec or journal['binding']['project']!=project):
        raise ValueError('download_query_binding_changed')
    return raw,raw_paths(root/kind,raw)


def phase(root, name, inputs, produce):
    """Publish completed local phases atomically. Retry only owned, unsealed scratch."""
    dest = root/name
    stage = root/f'.{name}.partial'
    if not dest.exists():
        if stage.exists():
            if stage.is_symlink():
                raise ValueError('linked_phase_scratch')
            # A previously sealed stage can be promoted after interruption.
            if not (stage/'PHASE.json').is_file():
                shutil.rmtree(stage)
        if not stage.exists():
            stage.mkdir()
            result = produce(stage)
            publish_record(stage/'PHASE.json',dict(inputs=inputs,result=result,artifacts=inventory(stage)))
        verify_phase(stage,inputs)
        os.rename(stage,dest)
        sync_directory(root)
    return verify_phase(dest,inputs)


def verify_phase(dest, inputs):
    if dest.is_symlink():
        raise ValueError('linked_phase_output')
    record = read_json(dest/'PHASE.json')
    actual = [a for a in inventory(dest) if a['path']!='PHASE.json']
    if record['inputs']!=inputs or record['artifacts']!=actual:
        raise ValueError('sealed_phase_mismatch')
    return record['result']


def finish(repo, root, source, raw, files, protocol, design):
    def digest(name):
        return file_sha256(root/name/'PHASE.json')

    canonical = phase(root,'canonical',dict(source=source,raw=fingerprint(raw)),
                      lambda p:canonicalize(p,'g',raw,files,source))
    phase(root,'availability',dict(canonical=digest('canonical'),protocol=protocol),
          lambda p:availability(p,'g',root/'canonical',protocol))
    clock = root/'availability'
    validate_clock_audit(clock)
    eligibility = clock/'entity_eligibility.parquet'
    rule = design['cohort_selection_rule']
    cohort = phase(root,'cohort',dict(availability=digest('availability'),rule=fingerprint(rule)),
        lambda p:freeze_cohort(p,'g',canonical['canonical_dataset_sha256'],eligibility,protocol,rule))
    rel = lambda p:p.relative_to(repo).as_posix()
    cp = root/'cohort/g_cohort.json'
    binding = dict(schema_version='google2019-stage-input-binding-v1',cell='g',
        status='AVAILABILITY_CONTRACT_READY',protocol_fingerprint=protocol['protocol_fingerprint'],
        cohort_rule_sha256=fingerprint(rule),canonical_path=rel(root/'canonical'),
        canonical_sha256=canonical['canonical_dataset_sha256'],
        canonical_manifest_sha256=file_sha256(root/'canonical/manifest.json'),
        clock_audit_path=rel(clock),clock_audit_manifest_sha256=file_sha256(clock/'manifest.json'),
        cohort_path=rel(cp),cohort_sha256=file_sha256(cp),
        member_records_sha256=cohort['member_records_sha256'],
        eligibility_path=rel(eligibility),eligibility_sha256=file_sha256(eligibility))
    e = read_json(repo/E_BINDING)
    load_stage_inputs(repo,'e',repo/e['cohort_path'])
    staged = dict(schema_version='google2019-staged-inventory-v1',source_commit=source,
        design_sha256=fingerprint(design),e=dict(binding=e,binding_sha256=file_sha256(repo/E_BINDING)),
        g=dict(binding=binding,binding_sha256=fingerprint(binding)),raw_lineage_sha256=fingerprint(raw),
        phases={n:digest(n) for n in ('canonical','availability','cohort')},
        pooled_outcomes=False,stage_b_executed=False)
    dest = root/'staged-inventory.json'
    if not dest.exists():
        publish_record(dest,staged)
    if read_json(dest)!=staged:
        raise ValueError('staged_inventory_changed')
    return binding,dest


@contextmanager
def campaign_lock(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


@contextmanager
def idle_v8(repo):
    """Hold the existing V8 campaign lock without changing its evidence."""
    path = repo/V8_CAMPAIGN
    lock = path/'.lock'
    if lock.is_symlink() or not lock.is_file():
        raise ValueError('existing_v8_campaign_lock_required')
    with lock.open('rb') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        completed_attempts(path)
        if subprocess.check_output(['docker','--context','desktop-linux','ps','-q'],cwd=repo).strip():
            raise ValueError('docker_workload_active')
        yield


def run(repo, month, ledger_path, execute, project=None):
    if repo!=Path(__file__).resolve().parents[2]:
        raise ValueError('repo_must_match_running_acquisition_source')
    source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    status = subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).splitlines()
    if subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!='dynapm':
        raise ValueError('dynapm_branch_required')
    root = repo/ROOT
    final = root/'staged-inventory.json'
    if status and not (status==[f'?? {G_BINDING}'] and final.exists()
                       and read_json(repo/G_BINDING)==read_json(final)['g']['binding']):
        raise ValueError('clean_frozen_source_required')
    design = frozen_design(repo)
    protocol = validate_protocol_v2(repo)
    queries = frozen_queries()
    streaming = validate_streaming_plan()['plan_fingerprint']
    state = root/'run.json'
    previous = read_json(state) if state.exists() else None
    ledger = read_ledger(repo,month,ledger_path,previous['run_id'] if previous else None)
    storage = disk_safe_for_g_after_e()
    if not previous and not storage['safe']:
        raise ValueError('frozen_g_storage_guard_failed')
    if not execute:
        return dict(mode='OFFLINE_NO_CLOUD',source=source,month=month,ledger_bytes=ledger['cumulative_executed_bytes'],
                    disk=storage,queries=queries)
    if datetime.now(timezone.utc).strftime('%Y-%m')!=month:
        raise ValueError('execution_month_mismatch')
    with idle_v8(repo), campaign_lock(root):
        import google.auth
        from google.cloud import bigquery
        project = resolve_quota_project(project)
        if not project:
            raise ValueError('explicit_or_adc_quota_project_required')
        billing = require_zero_cost_project(project)
        credentials,_ = google.auth.default(quota_project_id=billing.project_id,
                                             scopes=['https://www.googleapis.com/auth/cloud-platform'])
        client = bigquery.Client(project=billing.project_id,credentials=credentials)
        runtime = dict(python=sys.version,packages={name:version(name) for name in
            ('google-cloud-bigquery','google-cloud-bigquery-storage','pandas','numpy','pyarrow')})
        header = dict(cell='g',month=month,ledger_path=LEDGER,initial_ledger_sha256=ZERO_LEDGER_SHA,runtime=runtime,
            source_commit=source,protocol=protocol,streaming_plan_sha256=streaming,
            design_sha256=fingerprint(design),project=billing.project_id,queries=queries,monthly_cap_bytes=CAP)
        run_id = fingerprint(header)
        if state.exists():
            previous = read_json(state)
            if {k:v for k,v in previous.items() if k!='preflight'}!=dict(run_id=run_id,**header):
                raise ValueError('incompatible_acquisition_resume')
        else:
            if previous or any(x.name!='.lock' for x in root.iterdir()) or (repo/G_BINDING).exists():
                raise ValueError('unmanaged_prior_cell_g_state')
            if (repo/'data/google2019/raw/g').exists() or (repo/'data/google2019/checkpoints/g.json').exists():
                raise ValueError('legacy_cell_g_state_requires_reconciliation')
            for job in client.list_jobs(all_users=True,min_creation_time=datetime(2026,11,1,tzinfo=timezone.utc),timeout=30):
                if job.job_type=='query' and not getattr(job,'dry_run',False):
                    raise ValueError('unreconciled_november_query')
            dry = {k:dry_run(client,billing.project_id,k,s,require_zero_cost_project) for k,s in queries.items()}
            if sum(s['maximum_bytes_billed'] for s in queries.values())+ledger['cumulative_executed_bytes']>CAP:
                raise ValueError('projected_monthly_cap_exceeded')
            e = read_json(repo/E_BINDING)
            load_stage_inputs(repo,'e',repo/e['cohort_path'])
            preflight = dict(run_id=run_id,disk=storage,dry_runs=dry,billing_enabled=False)
            publish_record(state,dict(run_id=run_id,preflight=preflight,**header))
            previous = read_json(state)
        preflight = previous['preflight']
        if (preflight['run_id']!=run_id or preflight['billing_enabled'] is not False
                or not preflight['disk']['safe'] or set(preflight['dry_runs'])!=set(queries)):
            raise ValueError('preflight_binding_changed')
        raw,files = {},{}
        for kind,spec in queries.items():
            raw[kind],files[kind] = acquire(repo,root,billing.project_id,client,run_id,spec,kind,credentials)
        binding,dest = finish(repo,root,source,raw,files,protocol,design)
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()!=source:
            raise ValueError('acquisition_source_changed')
        final_status = subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).splitlines()
        if final_status not in ([],[f'?? {G_BINDING}']):
            raise ValueError('acquisition_working_tree_changed')
        if not (repo/G_BINDING).exists():
            publish_record(repo/G_BINDING,binding)
        if read_json(repo/G_BINDING)!=binding:
            raise ValueError('stage_g_binding_changed')
        load_stage_inputs(repo,'g',repo/binding['cohort_path'])
        return dict(status='CELL_G_READY',run_id=run_id,inventory=dest.relative_to(repo).as_posix(),
                    inventory_sha256=file_sha256(dest))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--month',required=True)
    p.add_argument('--ledger',required=True,type=Path)
    p.add_argument('--billing-project')
    p.add_argument('--execute',action='store_true')
    args = p.parse_args()
    repo = args.repo.resolve()
    ledger = args.ledger if args.ledger.is_absolute() else repo/args.ledger
    print(canonical_json(run(repo,args.month,ledger,args.execute,args.billing_project)))


if __name__=='__main__':
    main()
