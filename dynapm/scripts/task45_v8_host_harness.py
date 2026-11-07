"""Explicit V8 host-identity harness amendment. No policy/design changes."""
import argparse
import shutil
import subprocess
import time
import traceback
import uuid
from pathlib import Path

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.scripts.task41_bounded_v8 import (CAMPAIGN, clean_source, completed_attempts,
    locked_campaign, next_attempt, read_bundle, seal_attempt)
from dynapm.system_validation.bounded_v8 import (ARTIFACT, MEASURED, NS, REFERENCE,
    cells, load_contract, plan, qualified_bootstrap)
from dynapm.system_validation.bounded_v8_runtime import (
    OperationalStop, boot_identity, episode, local_kind, _wait_until, pinned_images)
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.host_power import PowerGuardError, command
from dynapm.system_validation.reservation_protocol import read_protocol
from dynapm.system_validation.smoke import Commands
from dynapm.system_validation.v8_campaign import publish_record
from dynapm.system_validation.v8_host_identity import (
    SCIENTIFIC_SOURCE, UUIDPowerGuard, harness_source, require_amended_endurance)

CONTRACT = '71fced9df98304f44dd8fd10c28e26e978d4a65330cc49d7d750433055f4b780'
SNAPSHOTS = '3b9b443d18706589a6c8fb87654d7c89170e891dda9c93b0cac37bef4e49de94'


def scientific_binding(repo, root, contract_sha, design):
    harness_source(repo)
    expected = dict(source_commit=SCIENTIFIC_SOURCE, boot_identity=boot_identity(),
        contract_sha256=contract_sha, config_sha256=fingerprint(design),
        reservation_sha256=file_sha256(repo/'configs/system_resource_actuation_v2.json'),
        taxonomy_sha256=file_sha256(repo/'dynapm/system_validation/outcome_taxonomy.py'),
        bootstrap_sha256=ARTIFACT)
    if read_json(root/'campaign.json') != expected:
        raise ValueError('scientific_campaign_or_boot_mismatch')
    return expected


def run_primary(repo, root, planned, contract_sha, design, args):
    if not args.authorize_live:raise ValueError('explicit_live_run_authorization_required')
    provenance = harness_source(repo)
    require_amended_endurance(repo,args.host_endurance_run,args.amendment,args.amendment_sha256)
    if shutil.disk_usage(root).free < 24*2**30:raise ValueError('bounded_v8_24GiB_start_guard')
    campaign = scientific_binding(repo,root,contract_sha,design)
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
                  replacement=replacement, harness_provenance=dict(provenance,
                  host_identity_amendment_sha256=args.amendment_sha256))
    publish_record(run/'intent.json',intent)
    (root/'issued').mkdir(exist_ok=True)
    publish_record(root/'issued'/f'{ident}.json',intent)
    context = dict(run_id=ident,source_commit=provenance['execution_harness_commit'],frozen_scientific_source=SCIENTIFIC_SOURCE,experiment_fingerprint=fingerprint(intent))
    wall = origin = None
    try:
        environment = read_json(repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']
        with UUIDPowerGuard(run,context) as guard:
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
        if clean_source(repo)!=provenance['execution_harness_commit'] or load_contract(repo)!=contract_sha:
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


def preflight(repo, root, args, contract_sha, design):
    import os
    provenance = harness_source(repo)
    scientific_binding(repo, root, contract_sha, design)
    current = require_amended_endurance(repo,args.host_endurance_run,args.amendment,args.amendment_sha256)
    attempts = completed_attempts(root)
    bundle = read_bundle(root,SNAPSHOTS,design,contract_sha,attempts)
    qualified_bootstrap(repo,design)
    if load_contract(repo)!=CONTRACT or read_protocol(repo) is None:
        raise ValueError('frozen_contract_or_reservation_changed')
    parent = repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json'
    environment = read_json(parent)['experiment']['config']['preprocessing']['execution_environment']
    tools = str(repo/design['kubernetes']['tools_directory'])
    env = dict(os.environ,PATH=tools+os.pathsep+os.environ['PATH'])
    commands = Commands(env,repo)
    cli = {}
    for binary in ('kind','kubectl'):
        path = shutil.which(binary,path=env['PATH'])
        if not path or file_sha256(path)!=environment['cli_binary_sha256'][binary]:
            raise ValueError('qualified_cli_mismatch')
        cli[binary]=dict(path=path,sha256=file_sha256(path))
    images = pinned_images(commands,
        [design['kubernetes'][k] for k in ('application_image','prometheus_local_image','node_image')],
        environment['image_ids'])
    if commands.run(['docker','ps','-aq']).strip() or commands.run(['kind','get','clusters']).strip():
        raise ValueError('engine_not_isolated')
    if 'lowpowermode         0' not in command(['/usr/bin/pmset','-g','custom']):
        raise ValueError('low_power_mode_not_disabled')
    if shutil.disk_usage(root).free<int(25.25*2**30):
        raise ValueError('campaign_storage_headroom')
    if args.record.exists():
        raise ValueError('preflight_record_exists')
    guardroot = args.record.parent/('guard-'+uuid.uuid4().hex)
    context = dict(run_id=guardroot.name,source_commit=provenance['execution_harness_commit'],
                   frozen_scientific_source=SCIENTIFIC_SOURCE,experiment_fingerprint=contract_sha)
    with UUIDPowerGuard(guardroot,context) as guard:
        time.sleep(6)
        guard.checkpoint(force_power=True)
    result = dict(status='PASS',**provenance,host_identity_amendment_sha256=args.amendment_sha256,
        current_boot=current,contract_sha256=contract_sha,snapshot_sha256=SNAPSHOTS,
        cli=cli,images=images,free_bytes=shutil.disk_usage(root).free,
        host_guard_path=str(guardroot),host_guard_sha256=file_sha256(guardroot/'outputs/power_guard.json'),
        frozen_order=cells(),structural_targets=bundle['structural_targets'],treatments_started=0)
    publish_record(args.record,result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preflight','run'))
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--host-endurance-run',type=Path,required=True)
    parser.add_argument('--amendment',type=Path,required=True)
    parser.add_argument('--amendment-sha256',required=True)
    parser.add_argument('--expected-harness-commit',required=True)
    parser.add_argument('--record',type=Path)
    parser.add_argument('--sequence',type=int)
    parser.add_argument('--authorize-live',action='store_true')
    parser.add_argument('--replacement-approval',type=Path)
    args=parser.parse_args()
    repo=args.repo.resolve()
    provenance=harness_source(repo)
    if provenance['execution_harness_commit']!=args.expected_harness_commit:
        raise ValueError('unexpected_execution_harness_commit')
    contract_sha=load_contract(repo)
    if contract_sha!=CONTRACT:
        raise ValueError('frozen_execution_contract_changed')
    design=frozen_spec(repo)
    root=repo/CAMPAIGN
    args.snapshot_sha256=SNAPSHOTS
    if args.action=='preflight':
        if args.record is None or args.sequence is not None or args.authorize_live:
            parser.error('preflight requires --record and forbids live flags')
        result=preflight(repo,root,args,contract_sha,design)
    else:
        if args.sequence is None or args.record is not None:
            parser.error('run requires --sequence')
        with locked_campaign(root):
            result=run_primary(repo,root,plan('primary',sequence=args.sequence),contract_sha,design,args)
    print(canonical_json(result))


if __name__=='__main__':
    main()
