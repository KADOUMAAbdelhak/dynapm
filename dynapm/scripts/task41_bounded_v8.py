"""Bounded V8 plan, compilation, audited single-attempt launcher, and analysis."""
import argparse
from contextlib import contextmanager
import fcntl
import os
import tempfile
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import uuid

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.system_validation.bounded_v8 import (ARTIFACT, MEASURED, NS, PHASES, REFERENCE, cells,
    compile_snapshots, inventory, load_contract, plan, qualified_bootstrap, reference_library,
    structural_targets)
from dynapm.system_validation.bounded_v8_metrics import paired_analysis
from dynapm.system_validation.bounded_v8_runtime import OperationalStop, boot_identity, episode, local_kind, _wait_until
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.host_endurance import require_endurance
from dynapm.system_validation.host_power import ManagedPowerGuard, PowerGuardError
from dynapm.system_validation.reservation_protocol import read_protocol
from dynapm.system_validation.v8_campaign import publish_record

CAMPAIGN = 'results/bounded_v8/campaign-v1'


def clean_source(repo):
    if subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip():
        raise ValueError('clean_committed_source_required')
    if subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!='dynapm':
        raise ValueError('dynapm_branch_required')
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()


@contextmanager
def locked_campaign(root):
    for path in (root,root.parent,root.parent.parent):
        if path.is_symlink():raise ValueError('linked_campaign_path')
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def identity(repo, root, contract_sha, design):
    expected = dict(source_commit=clean_source(repo),boot_identity=boot_identity(),
                    contract_sha256=contract_sha,config_sha256=fingerprint(design),
                    reservation_sha256=file_sha256(repo/'configs/system_resource_actuation_v2.json'),
                    taxonomy_sha256=file_sha256(repo/'dynapm/system_validation/outcome_taxonomy.py'),
                    bootstrap_sha256=ARTIFACT)
    path = root/'campaign.json'
    if path.exists():
        if read_json(path)!=expected:raise ValueError('campaign_source_config_artifact_or_boot_mismatch')
    else:
        publish_record(path,expected)
    return expected


def completed_attempts(root):
    """An interrupted START blocks the next launch. No elapsed exposure is spliced."""
    attempts = []
    paths = sorted((root/'attempts').glob('*'))
    issued = {p.stem:read_json(p) for p in (root/'issued').glob('*.json')}
    if set(issued)!={p.name for p in paths}:
        raise ValueError('attempt_index_mismatch_requires_reconciliation')
    for ordinal,path in enumerate(paths,1):
        if path.is_symlink():raise ValueError('linked_attempt_path')
        intent = read_json(path/'intent.json')
        p = intent['plan']
        expected = plan(p['mode'],phase=p.get('phase'),sequence=p.get('cell',{}).get('sequence'))
        if intent['ordinal']!=ordinal or intent!=issued[path.name] or p!=expected:
            raise ValueError('attempt_order_or_issued_intent_changed')
        if not (path/'terminal.json').is_file() or not (path/'SEALED').is_file():
            raise ValueError(f'unresolved_attempt_requires_reconciliation:{path.name}')
        terminal = read_json(path/'terminal.json')
        if (read_json(path/'SEALED') != {'terminal_sha256':file_sha256(path/'terminal.json')}
                or terminal['files'] != inventory(path)
                or terminal['intent_sha256'] != file_sha256(path/'intent.json')):
            raise ValueError('attempt_tampered')
        status = terminal['status']
        if (status not in {'COMPLETE','OPERATIONAL_CENSORED','HARNESS_FAILED'}
                or (status=='COMPLETE') != (terminal['metrics'] is not None)
                or status=='COMPLETE' and terminal['measurement_seconds']!=intent['plan']['measurement_seconds']):
            raise ValueError('invalid_terminal_attempt_status')
        attempts.append((path,intent,terminal))
    return attempts


def next_attempt(attempts, planned, snapshot_sha, approval):
    if planned['mode']!='primary':
        if approval is not None or any(i['plan']==planned for _,i,_ in attempts):
            raise ValueError('single_reference_or_integration_attempt_required')
        return None
    primary = [(p,i,t) for p,i,t in attempts if i['plan']['mode']=='primary']
    if any(i['snapshot_sha256']!=snapshot_sha for _,i,_ in primary):
        raise ValueError('snapshot_substitution_forbidden')
    terminal_cells = {i['plan']['cell']['sequence'] for _,i,t in primary if t['status']!='HARNESS_FAILED'}
    remaining = [i for i in range(1,19) if i not in terminal_cells]
    sequence = planned['cell']['sequence']
    if not remaining or sequence!=remaining[0]:raise ValueError('next_frozen_cell_required')
    failed = [(p,i,t) for p,i,t in primary if i['plan']['cell']['sequence']==sequence]
    if not failed:
        if approval is not None:raise ValueError('replacement_requires_failed_parent')
        return None
    p,i,t = failed[-1]
    consumed = [x['replacement'] for _,x,_ in attempts if x['replacement'] is not None]
    if (approval is None or len(consumed)>=2 or t['status']!='HARNESS_FAILED'
            or approval.get('failed_terminal_sha256')!=file_sha256(p/'terminal.json')
            or approval.get('exogenous') is not True or not approval.get('authorization_id')
            or not approval.get('evidence') or approval['authorization_id'] in {x['authorization_id'] for x in consumed}):
        raise ValueError('explicit_exogenous_replacement_review_required')
    return approval


def compile_bundle(root, repo, design, contract_sha):
    attempts = completed_attempts(root)
    paths = [p for p,i,t in attempts if i['plan']['mode']=='reference']
    library = reference_library(paths,design,contract_sha)
    snapshots,costs = compile_snapshots(library,qualified_bootstrap(repo,design),design)
    dest = root/'snapshots'
    if dest.exists():raise ValueError('snapshot_bundle_already_frozen')
    with tempfile.TemporaryDirectory(prefix='.snapshot-build-',dir=root) as temporary:
        stage = Path(temporary)/'bundle';stage.mkdir()
        for name,value in [('library.json',library),('snapshots.json',snapshots),('maintenance.json',costs)]:
            publish_record(stage/name,value)
        publish_record(stage/'FROZEN',{p.name:file_sha256(p) for p in stage.iterdir()})
        os.rename(stage,dest)
        fd = os.open(root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return dict(snapshot_sha256=file_sha256(dest/'FROZEN'),structural_targets=snapshots['structural_targets'])


def read_bundle(root, expected, design, contract_sha, attempts):
    dest = root/'snapshots';seal = dest/'FROZEN'
    if not expected or file_sha256(seal)!=expected:raise ValueError('reviewed_snapshot_digest_required')
    hashes = read_json(seal)
    if set(hashes)!={'library.json','snapshots.json','maintenance.json'} or any(
            file_sha256(dest/k)!=v for k,v in hashes.items()):raise ValueError('snapshot_bundle_tampered')
    snapshots = read_json(dest/'snapshots.json')
    library = reference_library([p for p,i,t in attempts if i['plan']['mode']=='reference'],design,contract_sha)
    if (snapshots['scope']!=MEASURED or snapshots['contract_sha256']!=contract_sha
            or snapshots['library_sha256']!=fingerprint(library) or read_json(dest/'library.json')!=library
            or snapshots['bootstrap_sha256']!=ARTIFACT
            or snapshots['structural_targets']!=structural_targets(snapshots['snapshots'])):
        raise ValueError('snapshot_lineage_or_target_gate_mismatch')
    return snapshots


def seal_attempt(run, result):
    result = dict(result, intent_sha256=file_sha256(run/'intent.json'),files=inventory(run))
    publish_record(run/'terminal.json',result)
    publish_record(run/'SEALED',{'terminal_sha256':file_sha256(run/'terminal.json')})
    return result


def run_one(repo, root, planned, contract_sha, design, args):
    if not args.authorize_live:raise ValueError('explicit_live_run_authorization_required')
    require_endurance(repo,args.host_endurance_run)
    if shutil.disk_usage(root).free < 24*2**30:raise ValueError('bounded_v8_24GiB_start_guard')
    campaign = identity(repo,root,contract_sha,design)
    attempts = completed_attempts(root)
    if any(i['campaign']!=campaign for _,i,_ in attempts):raise ValueError('attempt_campaign_binding_mismatch')
    snapshot = None
    snapshot_sha = args.snapshot_sha256 if planned['mode']=='primary' else None
    approval = read_json(args.replacement_approval) if args.replacement_approval else None
    replacement = next_attempt(attempts,planned,snapshot_sha,approval)
    bootstrap = qualified_bootstrap(repo,design)
    if planned['mode']=='primary':
        bundle = read_bundle(root,snapshot_sha,design,contract_sha,attempts)
        cell = planned['cell']
        snapshot = next(x for x in bundle['snapshots'] if x['method']==cell['method'] and x['scenario']==cell['scenario'])
    elif planned['mode']=='reference' and (root/'snapshots').exists():
        raise ValueError('reference_library_already_frozen')
    ordinal = len(attempts)+1
    ident = f'{ordinal:03d}-'+utc_now().replace(':','').replace('.','-')+'-'+uuid.uuid4().hex[:12]
    cluster = design['kubernetes']['cluster']+'-v8a-'+uuid.uuid4().hex[:10]
    run = root/'attempts'/ident;out=run/'outputs';out.mkdir(parents=True,exist_ok=False)
    intent = dict(run_id=ident,ordinal=ordinal,plan=planned,campaign=campaign,cluster=cluster,snapshot_sha256=snapshot_sha,
                  replacement=replacement)
    publish_record(run/'intent.json',intent)
    (root/'issued').mkdir(exist_ok=True)
    publish_record(root/'issued'/f'{ident}.json',intent)
    context = dict(run_id=ident,source_commit=campaign['source_commit'],experiment_fingerprint=fingerprint(intent))
    wall = origin = None
    try:
        environment = read_json(repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']
        with ManagedPowerGuard(run,context) as guard:
            _wait_until(time.monotonic_ns()+planned['cooldown_seconds']*NS,guard)
            with local_kind(repo,design,run,cluster,environment) as (kube,node,url,check_forward):
                pod = kube.pod()
                runtime = dict(cluster=cluster,pod_uid=pod['metadata']['uid'],container=node.container,
                               controller=uuid.uuid4().hex,telemetry=uuid.uuid4().hex,profile=uuid.uuid4().hex)
                for p,_,_ in attempts:
                    if (p/'manifest.json').exists():
                        previous = read_json(p/'manifest.json')['runtime']
                        if set(previous.values()) & set(runtime.values()):raise ValueError('runtime_identity_reused')
                delay = (planned['warmup_seconds']+10)*NS
                wall,origin = time.time_ns()+delay,time.monotonic_ns()+delay
                manifest = dict(**intent,scope=MEASURED,contract_sha256=contract_sha,runtime=runtime,
                                reference_resources=REFERENCE.resources(),clock_context=context,
                                origin_wall_ns=wall,origin_monotonic_ns=origin,
                                snapshot_state_sha256=fingerprint(snapshot) if snapshot else None)
                publish_record(run/'manifest.json',manifest)
                measured = episode(run,planned,design,bootstrap,snapshot,kube,node,url,check_forward,guard,context,wall,origin)
            guard.checkpoint(force_power=True)
        if clean_source(repo)!=campaign['source_commit'] or load_contract(repo)!=contract_sha:
            raise ValueError('source_or_contract_changed_during_attempt')
        result = dict(status='COMPLETE',measurement_seconds=planned['measurement_seconds'],
                      measurement_origin_wall_ns=wall,**measured)
    except BaseException as exc:
        # Operational failure and harness failure are distinct. Neither fabricates a complete endpoint.
        result = dict(status='OPERATIONAL_CENSORED' if isinstance(exc,OperationalStop) else 'HARNESS_FAILED',
                      failure_category='OPERATIONAL_OUTCOME' if isinstance(exc,OperationalStop) else 'HARNESS_MEASUREMENT_FAILURE',
                      failure_kind='resize_operational_failure' if isinstance(exc,OperationalStop) else
                      'host_continuity_failure' if isinstance(exc,PowerGuardError) else 'controller_crash',
                      failure=str(exc),traceback=traceback.format_exc(),metrics=None,actuations=[],
                      measurement_seconds=None)
        seal_attempt(run,result)
        raise
    seal_attempt(run,result)
    return str(run)


def recover(repo, root, record, contract_sha, design):
    import os
    from dynapm.system_validation.calibration_runner import require_isolated_engine
    from dynapm.system_validation.smoke import Commands, guard_local_endpoint

    campaign = identity(repo,root,contract_sha,design)
    attempt = record.get('run_id','')
    if not attempt or Path(attempt).name!=attempt or not record.get('authorization_id') or not record.get('evidence'):
        raise ValueError('reviewed_interruption_record_required')
    path = root/'attempts'/attempt
    intent = read_json(path/'intent.json')
    if (path.is_symlink() or (path/'SEALED').exists() or intent['campaign']!=campaign
            or read_json(root/'issued'/f'{attempt}.json')!=intent
            or record.get('intent_sha256')!=file_sha256(path/'intent.json')):
        raise ValueError('interruption_binding_mismatch')
    endpoint = os.environ.get('DOCKER_HOST') or subprocess.check_output(
        ['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    guard_local_endpoint(endpoint)
    commands = Commands(dict(os.environ,DOCKER_HOST=endpoint,
                             PATH=str(repo/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH']),repo)
    require_isolated_engine(commands)
    if intent['cluster'] in commands.run(['kind','get','clusters']).splitlines():
        raise ValueError('owned_cluster_still_present_requires_manual_cleanup')
    if (path/'terminal.json').exists():
        terminal = read_json(path/'terminal.json')
        if (record.get('terminal_sha256')!=file_sha256(path/'terminal.json')
                or terminal['files']!=inventory(path)):
            raise ValueError('interrupted_terminal_requires_exact_review')
        publish_record(path/'SEALED',{'terminal_sha256':record['terminal_sha256']})
        return terminal
    return seal_attempt(path,dict(status='HARNESS_FAILED',failure_kind='controller_crash',failure_category='HARNESS_MEASUREMENT_FAILURE',
                                  measurement_seconds=None,metrics=None,actuations=[],reconciliation=record))


def analysis(root, snapshot_sha, design, contract_sha):
    attempts = completed_attempts(root)
    binding = read_json(root/'campaign.json')
    if binding['contract_sha256']!=contract_sha or any(i['campaign']!=binding for _,i,_ in attempts):
        raise ValueError('analysis_campaign_binding_mismatch')
    snapshots = read_bundle(root,snapshot_sha,design,contract_sha,attempts)
    selected,failures = [],[]
    for path,i,t in attempts:
        if i['plan']['mode']!='primary':continue
        if i['snapshot_sha256']!=snapshot_sha:raise ValueError('analysis_snapshot_binding_mismatch')
        row = dict(sequence=i['plan']['cell']['sequence'],run_id=i['run_id'],
                   terminal_sha256=file_sha256(path/'terminal.json'),status=t['status'],metrics=t['metrics'])
        (failures if t['status']=='HARNESS_FAILED' else selected).append(row)
    result = paired_analysis(selected,snapshots)
    result.update(snapshot_sha256=snapshot_sha,failed_attempts=failures,
                  offline_maintenance=read_json(root/'snapshots/maintenance.json'))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan','compile','run','analyze','recover'))
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--mode',choices=('reference','primary','integration'))
    p.add_argument('--phase',choices=tuple(PHASES));p.add_argument('--sequence',type=int)
    p.add_argument('--host-endurance-run',type=Path);p.add_argument('--snapshot-sha256')
    p.add_argument('--replacement-approval',type=Path);p.add_argument('--authorize-live',action='store_true')
    p.add_argument('--recovery-record',type=Path)
    a=p.parse_args();repo=a.repo.resolve();contract_sha=load_contract(repo);root=repo/CAMPAIGN
    if a.action=='plan':
        result=dict(contract_sha256=contract_sha,references=[plan('reference',phase=x) for x in PHASES],
                    treatments=[plan('primary',sequence=x['sequence']) for x in cells()],integration=plan('integration'))
    else:
        design=frozen_spec(repo);read_protocol(repo)
        with locked_campaign(root):
            if a.action=='compile':
                binding = read_json(root/'campaign.json')
                if clean_source(repo)!=binding['source_commit'] or contract_sha!=binding['contract_sha256']:
                    raise ValueError('compiler_source_or_contract_mismatch')
                result=compile_bundle(root,repo,design,contract_sha)
            elif a.action=='analyze':result=analysis(root,a.snapshot_sha256,design,contract_sha)
            elif a.action=='recover':result=recover(repo,root,read_json(a.recovery_record),contract_sha,design)
            else:result=run_one(repo,root,plan(a.mode,phase=a.phase,sequence=a.sequence),contract_sha,design,a)
    print(canonical_json(result))


if __name__=='__main__':main()
