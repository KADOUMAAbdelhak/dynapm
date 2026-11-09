"""Versioned direct-Service primary lifecycle. No old/new application data mixing."""
from collections import Counter
from copy import deepcopy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json, utc_now
from dynapm.scripts.task41_bounded_v8 import completed_attempts, read_bundle
from dynapm.system_validation.bounded_v8 import (ARTIFACT, NS, REFERENCE, accepted_samples, cells,
    load_contract, plan, qualified_bootstrap, inventory)
from dynapm.system_validation.bounded_v8_runtime import (OperationalStop, actuate, confirm, _wait_until, pinned_images)
from dynapm.system_validation.bounded_v8_metrics import resource_endpoints
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.clock_observations import ObservationClock, MAX_CLOCK_DELTA_NS
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.reservation_protocol import reservation_recommendation
from dynapm.system_validation.service_transport import (campaign_generator_config, generator_resources,
    start_stack, export_records, validate_download, endpoint_metrics)
from dynapm.system_validation.service_checkpoint import (Checkpoint, atomic_record, campaign_lock,
    next_slot, stop_after_seal)
from dynapm.system_validation.smoke import Commands
from dynapm.system_validation.v8_host_identity import (SCIENTIFIC_SOURCE, UUIDPowerGuard,
    read_boot, same_boot, qualification_inputs)
from dynapm.system_validation.host_power import command

TRANSPORT = 'b3fd0d1fa095dbaa13c2b035624d6336b24d60ca'
AMENDMENT = '286c6bb99d5e293c5ce6085ce7d80c9c258518063ec66d0a57bcc112e6ed65f8'
QUALIFICATION = 'e6b480ef662054ece2c56b5ed561033490088e2a0d4f9bfbf57c2d479943cf54'
CONTRACT = '71fced9df98304f44dd8fd10c28e26e978d4a65330cc49d7d750433055f4b780'
SNAPSHOTS = '3b9b443d18706589a6c8fb87654d7c89170e891dda9c93b0cac37bef4e49de94'
GENERATOR_BUDGET = 64*2**20
OBSERVER_BUDGET = 64*2**20
SLOT_BUDGET = 144*2**20
DOCKER_GROWTH = 3*2**30
RESERVE = 20*2**30
BATTERY_SCOPE = 'DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'


def stable_spec_hash(spec):
    return fingerprint({k:v for k,v in spec.items() if k not in ('host_amendment_path','host_amendment_sha256')})


def resolve_runtime_images(design, environment):
    """Canonical aliases only; frozen config and the exact image IDs are immutable."""
    runtime=deepcopy(design);resolved=deepcopy(environment);aliases={}
    for key in ('application_image','prometheus_local_image'):
        frozen=design['kubernetes'][key]
        if frozen not in environment['image_ids']:
            raise ValueError('frozen_image_identity_missing')
        canonical='docker.io/library/'+frozen if '/' not in frozen else frozen
        expected=environment['image_ids'][frozen]
        if canonical in resolved['image_ids'] and resolved['image_ids'][canonical]!=expected:
            raise ValueError('canonical_image_identity_conflict')
        runtime['kubernetes'][key]=canonical
        resolved['image_ids'][canonical]=expected
        aliases[frozen]=dict(resolved_reference=canonical,expected_image_id=expected)
    return runtime,resolved,aliases


def storage_requirement(remaining):
    if type(remaining) is not int or not 1 <= remaining <= 18:
        raise ValueError('remaining_slot_count_required')
    return RESERVE + remaining*SLOT_BUDGET + GENERATOR_BUDGET + DOCKER_GROWTH + 512*2**20


def clock_domain(kube):
    code="import json,os;print(json.dumps(dict(boot_id=open('/proc/sys/kernel/random/boot_id').read().strip(),time_namespace=os.readlink('/proc/self/ns/time'))))"
    return json.loads(kube.call(['exec','application','--','python','-c',code],timeout=5))


def primary_config(planned, ident, url, snapshot, domain):
    cfg=campaign_generator_config(planned,ident,url)
    cfg.update(expected_clock_domain=domain,snapshot_sha256=fingerprint(snapshot),maximum_record_bytes=GENERATOR_BUDGET)
    return cfg


def validate_t0_handoff(config, start, envelope, before, after):
    """Program order encloses the source T0 in a host-local observation bracket.

    No subtraction or equality between host and Linux monotonic epochs is used.
    The 2 s upper limit is an engineering observation-latency ceiling, not future
    tolerance or a change to source/admission clock rules.
    """
    marker=envelope['marker'];origin=start['origin_monotonic_ns']
    if not 0<=after-before<=MAX_CLOCK_DELTA_NS:
        raise ValueError('t0_handoff_observation_bracket_exceeded')
    if not envelope['watch_start_monotonic_ns']<origin<=marker['emitted_monotonic_ns']<=envelope['watch_end_monotonic_ns']:
        raise ValueError('t0_handoff_program_order_invalid')
    if (marker['origin_monotonic_ns']!=origin or marker['run_id']!=config['run_id']
            or marker['snapshot_sha256']!=config['snapshot_sha256']
            or any(marker[k]!=config['expected_clock_domain'][k] or start[k]!=marker[k] for k in ('boot_id','time_namespace'))):
        raise ValueError('t0_marker_identity_invalid')
    return dict(source_marker=marker,source_envelope=envelope,host_request_monotonic_ns=before,
                host_receipt_monotonic_ns=after,host_t0_admission_monotonic_ns=after,
                host_bracket_width_ns=after-before,epoch_conversion_used=False)


def receive_t0(commands,kube,node,path,config,guard):
    deadline=time.monotonic()+120
    while True:
        guard.raise_if_failed()
        reply=commands.run(['docker','exec',node,'sh','-ec',
            'if test -f "$1/START.json"; then cat "$1/START.json"; else printf WAIT; fi','clock',path],timeout=5)
        if reply.strip()!='WAIT':start=json.loads(reply);break
        if time.monotonic()>deadline:raise ValueError('generator_start_not_observed')
        time.sleep(.2)
    # A duration read wholly in the Linux domain schedules only when to issue
    # the blocking observation. The returned event, not a converted epoch,
    # establishes availability for host actuation and resource integration.
    uptime=float(commands.run(['docker','exec',node,'cat','/proc/uptime'],timeout=5).split()[0])
    remaining=(start['origin_monotonic_ns']/NS)-uptime
    if remaining<=1:raise ValueError('missed_prospective_t0_watch')
    _wait_until(time.monotonic_ns()+int((remaining-1)*NS),guard)
    script="import time,json,pathlib;begin=time.monotonic_ns();p=pathlib.Path('/records/T0.json');exec('while not p.exists(): time.sleep(.005)');marker=json.loads(p.read_text());print(json.dumps(dict(watch_start_monotonic_ns=begin,watch_end_monotonic_ns=time.monotonic_ns(),marker=marker)))"
    before=time.monotonic_ns();request_wall=time.time_ns()
    raw=kube.call(['exec','request-generator','--','python','-c',script],timeout=3)
    after=time.monotonic_ns();receipt_wall=time.time_ns()
    handoff=validate_t0_handoff(config,start,json.loads(raw),before,after)
    handoff.update(raw_utf8=raw,raw_sha256=__import__('hashlib').sha256(raw.encode()).hexdigest(),host_request_wall_ns=request_wall,host_receipt_wall_ns=receipt_wall)
    return start,handoff


def source_binding(repo, spec):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    if head!=spec['executor_commit'] or subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip() or subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!=spec['executor_branch']:
        raise ValueError('clean_exact_executor_commit_required')
    subprocess.run(['git','merge-base','--is-ancestor',TRANSPORT,head],cwd=repo,check=True,capture_output=True)
    changes=subprocess.check_output(['git','diff','--name-status',TRANSPORT,head],cwd=repo,text=True).splitlines()
    additions={}
    for line in changes:
        status,path=line.split('\t')
        if status!='A':raise ValueError('approved_transport_or_scientific_file_modified')
        additions[path]=file_sha256(repo/path)
    if additions!=spec['executor_files'] or load_contract(repo)!=CONTRACT:
        raise ValueError('executor_source_or_contract_mismatch')
    base=repo/'results/v8c5_service/20261108-v1'
    if file_sha256(base/'amendment-v2.json')!=AMENDMENT or file_sha256(base/'qualification-summary.json')!=QUALIFICATION:
        raise ValueError('transport_qualification_changed')
    if file_sha256(base/'OUTPUT_MANIFEST.json')!='97bb6096def48e4386e911870e02488c85e25aef3fb3b50b369041a98c632fdd':
        raise ValueError('transport_evidence_manifest_changed')
    evidence=read_json(base/'OUTPUT_MANIFEST.json')
    if any(file_sha256(base/path)!=digest for path,digest in evidence['files'].items()):
        raise ValueError('transport_qualification_evidence_changed')
    if subprocess.check_output(['git','rev-parse','refs/heads/v8b-reference-freeze'],cwd=repo,text=True).strip()!='39082cf6ffdfe1884194f4160131fa82c58676f1':
        raise ValueError('v8b_evidence_ref_changed')
    seal=read_json(base/'PROSPECTIVE_SEAL-v2.json')
    if any(file_sha256(repo/p)!=h for p,h in seal['code_hashes'].items()):
        raise ValueError('qualified_transport_code_changed')
    if spec.get('t0_policy')!='FROZEN_T0_INCLUDES_ENFORCEMENT_TRANSITION':
        raise ValueError('prospective_t0_policy_required')
    return dict(scientific_source=SCIENTIFIC_SOURCE,transport_commit=TRANSPORT,executor_commit=head,
                amendment_sha256=AMENDMENT,transport_qualification_sha256=QUALIFICATION)


def host_qualification(repo,spec):
    path=repo/spec['host_amendment_path']
    if file_sha256(path)!=spec['host_amendment_sha256']:
        raise ValueError('approved_host_amendment_changed')
    amendment=read_json(path)
    inputs,guard=qualification_inputs(repo,repo/amendment['qualification']['path'])
    if inputs!=amendment['qualification']:
        raise ValueError('endurance_evidence_changed')
    for witness in amendment['witnesses']:
        root=repo/witness['path']
        if (file_sha256(root/'terminal.json')!=witness['terminal_sha256']
                or file_sha256(root/'intent.json')!=witness['intent_sha256']
                or witness['boot_uuid']!=amendment['boot_uuid']):
            raise ValueError('boot_witness_changed')
    current=read_boot();same_boot(amendment['boot_uuid'],current,legacy_epoch=inputs['legacy_epoch'])
    if command(['/usr/bin/pmset','-g','custom'])!=guard['power_settings']:
        raise ValueError('endurance_power_policy_changed')
    return current


def experiment_processes(text, own_pid):
    """Inspect only known experiment entry points; never persist unrelated arguments."""
    rows={}
    for line in text.splitlines():
        parts=line.strip().split(None,2)
        if len(parts)==3 and parts[0].isdigit() and parts[1].isdigit():
            rows[int(parts[0])]=(int(parts[1]),parts[2])
    own=set();pid=own_pid
    while pid in rows and pid not in own:
        own.add(pid);pid=rows[pid][0]
    return [pid for pid,(_,args) in rows.items() if pid not in own and
            ('dynapm.scripts.task' in args or 'dynapm/scripts/task' in args
             or ('bq ' in args and 'query' in args))]


def preflight(repo, root, spec, remaining):
    provenance=source_binding(repo,spec)
    processes=subprocess.check_output(['ps','-axo','pid=,ppid=,args='],text=True)
    if experiment_processes(processes,os.getpid()):raise ValueError('another_experiment_process_active')
    design=frozen_spec(repo)
    old=repo/'results/bounded_v8/campaign-v1'
    bundle=read_bundle(old,SNAPSHOTS,design,CONTRACT,completed_attempts(old))
    qualified_bootstrap(repo,design)
    boot=host_qualification(repo,spec)
    environment=read_json(repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']
    env=dict(os.environ,PATH=str(repo/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH'])
    commands=Commands(env,repo)
    for name,h in environment['cli_binary_sha256'].items():
        path=shutil.which(name,path=env['PATH'])
        if not path or file_sha256(path)!=h:raise ValueError('qualified_cli_changed')
    runtime_design,runtime_environment,aliases=resolve_runtime_images(design,environment)
    images=pinned_images(commands,[runtime_design['kubernetes'][key] for key in ('application_image','prometheus_local_image','node_image')],runtime_environment['image_ids'])
    if commands.run(['docker','ps','-aq']).strip() or commands.run(['kind','get','clusters']).strip():
        raise ValueError('engine_not_isolated')
    if 'lowpowermode         0' not in command(['/usr/bin/pmset','-g','custom']):
        raise ValueError('low_power_not_disabled')
    if shutil.disk_usage(repo).free < storage_requirement(remaining):
        raise ValueError('complete_campaign_storage_headroom')
    root.mkdir(parents=True,exist_ok=False)
    context=dict(run_id=root.name,source_commit=provenance['executor_commit'],experiment_fingerprint=fingerprint(spec))
    with UUIDPowerGuard(root,context) as guard:
        time.sleep(6);guard.checkpoint(force_power=True)
    record=dict(status='PASS',**provenance,host_amendment_path=spec['host_amendment_path'],host_amendment_sha256=spec['host_amendment_sha256'],boot=boot,images=images,image_aliases=aliases,free_bytes=shutil.disk_usage(repo).free,
                required_free_bytes=storage_requirement(remaining),remaining_slots=remaining,
                contract_sha256=CONTRACT,snapshot_sha256=SNAPSHOTS,
                guard_sha256=file_sha256(root/'outputs/power_guard.json'))
    atomic_record(root/'preflight.json',record)
    return dict(record,preflight_sha256=file_sha256(root/'preflight.json')),design,bundle,environment


def battery_preflight(repo, root, spec, remaining):
    from dynapm.system_validation.battery_diagnostic_guard import BatteryDiagnosticGuard
    provenance=source_binding(repo,spec)
    processes=subprocess.check_output(['ps','-axo','pid=,ppid=,args='],text=True)
    if experiment_processes(processes,os.getpid()):raise ValueError('another_experiment_process_active')
    design=frozen_spec(repo)
    old=repo/'results/bounded_v8/campaign-v1'
    bundle=read_bundle(old,SNAPSHOTS,design,CONTRACT,completed_attempts(old))
    qualified_bootstrap(repo,design)
    boot=host_qualification(repo,spec)
    environment=read_json(repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']
    env=dict(os.environ,PATH=str(repo/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH'])
    commands=Commands(env,repo)
    for name,h in environment['cli_binary_sha256'].items():
        path=shutil.which(name,path=env['PATH'])
        if not path or file_sha256(path)!=h:raise ValueError('qualified_cli_changed')
    runtime_design,runtime_environment,aliases=resolve_runtime_images(design,environment)
    images=pinned_images(commands,[runtime_design['kubernetes'][key] for key in ('application_image','prometheus_local_image','node_image')],runtime_environment['image_ids'])
    if commands.run(['docker','ps','-aq']).strip() or commands.run(['kind','get','clusters']).strip():
        raise ValueError('engine_not_isolated')
    if 'lowpowermode         0' not in command(['/usr/bin/pmset','-g','custom']):
        raise ValueError('low_power_not_disabled')
    if shutil.disk_usage(repo).free < storage_requirement(remaining):
        raise ValueError('complete_campaign_storage_headroom')
    root.mkdir(parents=True,exist_ok=False)
    context=dict(run_id=root.name,source_commit=provenance['executor_commit'],experiment_fingerprint=fingerprint(spec))
    with BatteryDiagnosticGuard(root,context) as guard:
        time.sleep(6);guard.checkpoint(force_power=True)
    record=dict(status='NON_QUALIFYING_DIAGNOSTIC_ADMISSION',claim_qualification_eligible=False,strict_ac_gate_passed=False,scope=BATTERY_SCOPE,**provenance,host_amendment_path=spec['host_amendment_path'],host_amendment_sha256=spec['host_amendment_sha256'],boot=boot,images=images,image_aliases=aliases,free_bytes=shutil.disk_usage(repo).free,
                required_free_bytes=storage_requirement(remaining),remaining_slots=remaining,
                contract_sha256=CONTRACT,snapshot_sha256=SNAPSHOTS,
                guard_sha256=file_sha256(root/'outputs/power_guard.json'))
    atomic_record(root/'preflight.json',record)
    return dict(record,preflight_sha256=file_sha256(root/'preflight.json')),design,bundle,environment


class BudgetWriter:
    def __init__(self,path,budget):
        self.handle=Path(path).open('x');self.budget=budget
    def write(self,value):
        size=len(value.encode())
        with self.budget['lock']:
            if self.budget['written']+size>OBSERVER_BUDGET or shutil.disk_usage(self.budget['root']).free-size<22*2**30:
                raise ValueError('observer_storage_buffer_or_budget')
            result=self.handle.write(value);self.budget['written']+=size
            return result
    def flush(self):self.handle.flush();os.fsync(self.handle.fileno())
    def close(self):self.flush();self.handle.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def power_guard_for_scope(root,context,scope):
    if scope==BATTERY_SCOPE:
        from dynapm.system_validation.battery_diagnostic_guard import BatteryDiagnosticGuard
        return BatteryDiagnosticGuard(root,context)
    if scope not in ('DIAGNOSTIC_NON_CLAIM','AMENDED_V8_PRIMARY'):
        raise ValueError('explicit_power_scope_required')
    return UUIDPowerGuard(root,context)


def treatment(repo,root,planned,snapshot,design,environment,identity):
    """Same implementation for claim and non-claim; only identity scope differs."""
    out=root/'outputs';out.mkdir(parents=True)
    ident=root.name;cluster=design['kubernetes']['cluster']+'-v8r2-'+uuid.uuid4().hex[:10]
    context=dict(run_id=ident,source_commit=identity['executor_commit'],experiment_fingerprint=fingerprint(identity),frozen_scientific_source=SCIENTIFIC_SOURCE,scope=identity['scope'],claim_qualification_eligible=identity['scope']!=BATTERY_SCOPE)
    budget=dict(root=root,lock=threading.Lock(),written=0)
    stop=threading.Event();errors=[];samples=[];health=[];threads=[]
    commands=kube=node=None;copied=False;result=None;failure=None
    atomic_record(root/'intent.json',dict(identity=identity,plan=planned,snapshot_sha256=fingerprint(snapshot),cluster=cluster,context=context))
    def emit(row):
        with BudgetWriter(out/(uuid.uuid4().hex+'.event.json'),budget) as handle:
            handle.write(canonical_json(dict(host_monotonic_ns=time.monotonic_ns(),recorded_at=utc_now(),**row))+'\n')
    def collect(clock):
        try:
            with BudgetWriter(out/'telemetry.jsonl',budget) as sink:
                next_poll=time.monotonic()
                while not stop.is_set():
                    sample=clock.accept(node.capture(),sink);samples.append(sample)
                    next_poll+=5;stop.wait(max(0,next_poll-time.monotonic()))
        except BaseException as exc:errors.append(repr(exc))
        finally:
            try:clock.finalize()
            except BaseException as exc:errors.append(repr(exc))
    def observe(uid):
        try:
            with BudgetWriter(out/'lifecycle.jsonl',budget) as sink:
                while not stop.is_set():
                    observed={}
                    for key,args in [('pods',['get','pods','-o','json']),('service',['get','service','application','-o','json']),('endpoints',['get','endpoints','application','-o','json']),('nodes',['get','nodes','-o','json']),('events',['get','events','-o','json'])]:
                        observed[key]=json.loads(kube.call(args,timeout=5))
                    observed.update(host_monotonic_ns=time.monotonic_ns(),host_wall_ns=time.time_ns(),free_bytes=shutil.disk_usage(root).free)
                    if observed['free_bytes']<22*2**30 or sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>SLOT_BUDGET:
                        raise ValueError('slot_storage_buffer_or_budget_exhausted')
                    sink.write(canonical_json(observed)+'\n');sink.flush();health.append(observed)
                    if not any(x['metadata']['uid']==uid for x in observed['pods']['items']):raise ValueError('application_identity_disappeared')
                    for item in observed['nodes']['items']:
                        if not any(c['type']=='Ready' and c['status']=='True' for c in item['status']['conditions']):raise ValueError('node_not_ready')
                    stop.wait(5)
        except BaseException as exc:errors.append(repr(exc))
    try:
        with power_guard_for_scope(root,context,identity['scope']) as guard:
            emit(dict(event='COOLDOWN_BEGIN'));_wait_until(time.monotonic_ns()+900*NS,guard);emit(dict(event='COOLDOWN_END'))
            runtime_design,runtime_environment,aliases=resolve_runtime_images(design,environment)
            atomic_record(out/'image-aliases.json',aliases)
            commands,kube,node=start_stack(repo,runtime_design,root,cluster,runtime_environment)
            pod=kube.pod();uid=pod['metadata']['uid']
            runtime=dict(cluster=cluster,pod_uid=uid,container=node.container,controller=uuid.uuid4().hex,telemetry=uuid.uuid4().hex)
            atomic_record(out/'runtime.json',runtime)
            with BudgetWriter(out/'enforcement.jsonl',budget) as enforcement:
                if not confirm(kube,node,uid,REFERENCE,pod['metadata']['generation'],0,enforcement):raise ValueError('reference_resources_unverified')
                target=reservation_recommendation(snapshot['profile'],design)
                if target.resources()!=snapshot['target']:raise ValueError('frozen_target_recomputation_failed')
                domain=clock_domain(kube)
                cfg=primary_config(planned,ident,'http://application.'+design['kubernetes']['namespace']+'.svc.cluster.local:8080',snapshot,domain)
                cfg['scope']=identity['scope']
                resources,generator_node,node_path=generator_resources(runtime_design,cluster,cfg,repo/'dynapm/system_validation/primary_service_generator.py')
                if identity['scope']==BATTERY_SCOPE:
                    resources['items'][1]['metadata']['labels']['scope']='battery-diagnostic-nonqualifying'
                resources['items'][0]['data']['transport_generator.py']=(repo/'dynapm/system_validation/service_generator.py').read_text()
                commands.run(['docker','exec',generator_node,'mkdir','-p',node_path]);commands.run(['docker','exec',generator_node,'chmod','0777',node_path])
                atomic_record(root/'recovery.json',dict(cluster=cluster,generator_node=generator_node,node_path=node_path,config=cfg,kubeconfig=str(kube.config)))
                atomic_record(out/'generator-resources.json',resources)
                atomic_record(out/'snapshot-binding.json',dict(snapshot_sha256=fingerprint(snapshot),target=snapshot['target'],t0_policy=identity['t0_policy']))
                clock=ObservationClock(root,context)
                for fn,args in [(collect,(clock,)),(observe,(uid,))]:
                    thread=threading.Thread(target=fn,args=args,daemon=True);thread.start();threads.append(thread)
                kube.call(['apply','-f',str(out/'generator-resources.json')],timeout=15)
                emit(dict(event='GENERATOR_APPLIED'))
                start,handoff=receive_t0(commands,kube,generator_node,node_path,cfg,guard)
                host_origin=handoff['host_t0_admission_monotonic_ns']
                origin_wall=handoff['host_receipt_wall_ns']
                atomic_record(out/'timing.json',dict(handoff,host_origin_monotonic_ns=host_origin,
                    generator_origin_monotonic_ns=start['origin_monotonic_ns'],t0_policy=identity['t0_policy']))
                if errors:raise ValueError('measurement_collector_failure:'+repr(errors))
                cpu_start=time.thread_time_ns()
                target=reservation_recommendation(snapshot['profile'],design)
                if target.resources()!=snapshot['target']:raise ValueError('t0_recommendation_drift')
                emit(dict(event='FROZEN_SNAPSHOT_LOADED_AT_T0',snapshot_sha256=fingerprint(snapshot)))
                acts=[]
                act=actuate(kube,node,uid,target,enforcement,lambda row:acts.append(dict(row,trigger='T0')),guard)
                controller_cpu=(time.thread_time_ns()-cpu_start)/NS
                emit(dict(event='TARGET_ENFORCEMENT',actuation=act))
                # Enforcement is inside the fixed transition; offers started independently at T0.
                for offset in range(300,1801,300):
                    _wait_until(host_origin+offset*NS,guard)
                    deadline=time.monotonic()+10
                    while not samples or samples[-1]['host_receipt_monotonic_ns']<host_origin+offset*NS:
                        if errors:raise ValueError('telemetry_failed:'+repr(errors))
                        if time.monotonic()>deadline:raise ValueError('terminal_bucket_observation_missing')
                        time.sleep(.1)
                    bucket=aggregate_bucket(samples,origin_wall+(offset-300)*NS,origin_wall+offset*NS,design)
                    emit(dict(event='BUCKET_VALIDATED',offset_seconds=offset,bucket=bucket))
                    current=kube.pod()
                    if not confirm(kube,node,uid,target,current['metadata']['generation'],0,enforcement):raise ValueError('allocation_unverifiable')
                    if shutil.disk_usage(repo).free<22*2**30:raise ValueError('storage_reserve_buffer')
                    if errors:raise ValueError('measurement_collector_failure:'+repr(errors))
                deadline=time.monotonic()+90
                while True:
                    guard.raise_if_failed()
                    if errors:raise ValueError('measurement_collector_failure:'+repr(errors))
                    gen=json.loads(kube.call(['get','pod','request-generator','-o','json'],timeout=5))
                    if gen['status'].get('phase') in ('Succeeded','Failed'):break
                    if time.monotonic()>deadline:raise ValueError('generator_watchdog_right_censored')
                    time.sleep(1)
                export_records(commands,generator_node,node_path,out/'generator')
                records,start,done=validate_download(out/'generator',cfg)
                state=gen['status']['containerStatuses'][0]
                if state['restartCount'] or state['state'].get('terminated',{}).get('exitCode')!=0:raise ValueError('generator_lifecycle_invalid')
                if start['snapshot_sha256']!=fingerprint(snapshot) or start['boot_id']!=domain['boot_id'] or start['time_namespace']!=domain['time_namespace']:raise ValueError('generator_start_binding_invalid')
                service=json.loads(kube.call(['get','service','application','-o','json']))
                if service['spec']['clusterIP'] not in start['resolved_addresses']:raise ValueError('service_dns_identity_invalid')
                # DONE binds the authoritative node bytes; independent second read verifies export identity.
                remote=commands.run(['docker','exec',generator_node,'sha256sum',node_path+'/requests.jsonl']).split()[0]
                if remote!=file_sha256(out/'generator/requests.jsonl'):raise ValueError('node_host_request_hash_mismatch')
                copied=True
                stop.set()
                for thread in threads:thread.join(timeout=15)
                if any(t.is_alive() for t in threads) or errors:raise ValueError('collector_termination_or_integrity_failure')
                sealed=list(accepted_samples(root,context))
                if not health or any(s['memory_limit_bytes']!=1024*2**20 or s['memory_swap_bytes'] for s in sealed):raise ValueError('fixed_limit_or_observability_failed')
                metrics=endpoint_metrics(planned,records)
                for name,(lo,hi) in {'primary':(0,1800),'transition':(0,300),'followup':(300,1800)}.items():
                    cohort=[r for r in records if lo*NS<=r['offer']['offset_ns']<hi*NS]
                    counts=Counter('connection_refusal' if r['outcome']=='transport_error' and (r.get('exception') or {}).get('type')=='ConnectionRefusedError' else
                                   'connection_deadline' if r.get('failure_layer')=='CONNECTION_DEADLINE' else
                                   'response_deadline' if r['outcome']=='request_timeout' else r['outcome'] for r in cohort)
                    metrics[name].update(scheduled_offers=len(cohort),sent_attempts=sum(r['sent_offset_ns'] is not None for r in cohort),
                        cap_drops=counts['overload_drop'],failure_class_counts=dict(counts),failure_class_rates={k:v/len(cohort) for k,v in counts.items()},
                        cap_drop_rate=counts['overload_drop']/len(cohort))
                for name,(lo,hi) in {'primary':(0,1800),'transition':(0,300),'followup':(300,1800)}.items():
                    metrics[name].update(resource_endpoints(sealed,host_origin,acts,lo,hi))
                metrics['primary'].update(cpu_churn_cores=abs(target.cpu_millicores-REFERENCE.cpu_millicores)/1000,
                    memory_churn_bytes=abs(target.memory_request_mib-REFERENCE.memory_request_mib)*2**20,controller_cpu_seconds=controller_cpu)
                result=dict(status='SEALED_VALID',scope=identity['scope'],claim_qualification_eligible=identity['scope']!=BATTERY_SCOPE,runtime=runtime,metrics=metrics,actuations=acts,
                    maintenance=dict(scope='FROZEN_OFFLINE_SNAPSHOT_COMPILATION_COST_NOT_LIVE_MAINTENANCE',
                        record=next(row for row in read_json(repo/'results/bounded_v8/campaign-v1/snapshots/maintenance.json')
                            if row['method']==planned['cell']['method'] and row['scenario']==planned['cell']['scenario']),
                        runtime_refresh_events=0),
                    request_reconciliation=dict(expected=done['expected_records'],records=len(records),missing=0,duplicates=0,
                        scheduled=len(records),sent=sum(r['sent_offset_ns'] is not None for r in records),outcomes=dict(Counter(r['outcome'] for r in records))),
                    node_host_sha256=remote,clock_context=context,source_commit=SCIENTIFIC_SOURCE,executor_commit=identity['executor_commit'])
                atomic_record(out/'endpoint.json',result)
                atomic_record(out/'RAW_SEALED.json',dict(requests_sha256=remote,clock_context=context))
            guard.checkpoint(force_power=True)
    except BaseException as exc:
        failure=dict(type=type(exc).__name__,error=repr(exc),category='OPERATIONAL_CENSORED' if isinstance(exc,OperationalStop) else 'INTERRUPTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'HARNESS_MEASUREMENT_FAILURE');result=dict(status='INTERRUPTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'SEALED_INVALID',failure=failure,metrics=None)
    finally:
        stop.set()
        for thread in threads:thread.join(timeout=15)
        cleanup=dict(cluster=cluster,deleted=False,node_copy_preserved=not copied)
        if commands and copied:
            try:
                commands.run(['kind','delete','cluster','--name',cluster],log=out/'kind.log',timeout=120)
                cleanup.update(deleted=True,node_copy_preserved=False)
            except Exception as exc:
                result=dict(status='SEALED_INVALID',failure=dict(error='cleanup_failed:'+repr(exc)),metrics=None)
        atomic_record(out/'cleanup.json',cleanup)
        result.update(scope=identity['scope'],claim_qualification_eligible=identity['scope']!=BATTERY_SCOPE)
        atomic_record(out/'endpoint.json',result)
        if not (out/'generator/requests.jsonl').exists():
            # This is an explicitly partial/undefined endpoint, never an empty valid request stream.
            atomic_record(out/'REQUESTS_UNAVAILABLE.json',dict(status='UNDEFINED',failure=failure,node_preserved=True))
        continuity=out/'power_guard.json'
        if not continuity.exists():atomic_record(out/'CONTINUITY_UNAVAILABLE.json',dict(status='UNDEFINED'))
        request=out/'generator/requests.jsonl' if (out/'generator/requests.jsonl').exists() else out/'REQUESTS_UNAVAILABLE.json'
        continuity=continuity if continuity.exists() else out/'CONTINUITY_UNAVAILABLE.json'
        return dict(result,scope=identity['scope'],claim_qualification_eligible=identity['scope']!=BATTERY_SCOPE,requests_path=str(request),endpoint_path=str(out/'endpoint.json'),continuity_path=str(continuity))


def campaign(repo,root,spec,scope,*,resume=False,max_slots=None,stop_after_slot=None,qualification=None):
    if scope not in ('DIAGNOSTIC_NON_CLAIM','AMENDED_V8_PRIMARY',BATTERY_SCOPE):raise ValueError('explicit_scope_required')
    required_power_mode='BATTERY_DIAGNOSTIC_ONLY' if scope==BATTERY_SCOPE else 'STRICT_AC'
    if spec.get('power_mode','STRICT_AC')!=required_power_mode:raise ValueError('power_scope_spec_mismatch')
    # Validate limits before ownership or any live action.
    stop_after_seal(0,0,max_slots=max_slots,stop_after_slot=stop_after_slot)
    if scope=='AMENDED_V8_PRIMARY':
        if (qualification is None or qualification.get('status')!='PASS'
                or qualification.get('schema')!='v8-primary-service-qualification-v1'
                or qualification.get('scope')!='DIAGNOSTIC_NON_CLAIM'
                or qualification.get('qualification_mode')!='STRICT_AC_PRIMARY_LIFECYCLE'
                or qualification.get('claim_qualification_eligible') is not True
                or qualification.get('full_lifecycle_verified') is not True
                or qualification.get('executor_commit')!=spec['executor_commit']
                or not qualification.get('storage_certified')):
            raise ValueError('prospective_primary_qualification_required')
    provenance=source_binding(repo,spec)
    identity=dict(provenance,scope=scope,contract_sha256=CONTRACT,snapshot_sha256=SNAPSHOTS,
        spec_sha256=stable_spec_hash(spec),t0_policy=spec['t0_policy'],campaign_generation='v8-direct-service-primary-v1')
    root.mkdir(parents=True,exist_ok=True)
    with campaign_lock(root):
        checkpoint=Checkpoint(root,identity,resume=resume);completed=0
        while True:
            cell=next_slot(root,checkpoint.state,identity)
            if cell is None:
                if scope=='AMENDED_V8_PRIMARY':
                    from dynapm.system_validation.bounded_v8_metrics import paired_analysis
                    terminals=[]
                    for slot in checkpoint.state['slots']:
                        terminal=read_json(root/slot['manifest'])
                        terminals.append(dict(sequence=slot['cell']['sequence'],status='COMPLETE',metrics=terminal['metrics']))
                    bundle=read_json(repo/'results/bounded_v8/campaign-v1/snapshots/snapshots.json')
                    atomic_record(root/'paired-analysis.json',paired_analysis(terminals,bundle))
                return checkpoint.state
            if stop_after_slot is not None and cell['sequence']>stop_after_slot:return checkpoint.state
            sessionroot=root/'sessions'/uuid.uuid4().hex;sessionroot.parent.mkdir(exist_ok=True)
            admit=battery_preflight if scope==BATTERY_SCOPE else preflight
            session,design,bundle,environment=admit(repo,sessionroot,spec,19-cell['sequence'])
            snapshot=next(s for s in bundle['snapshots'] if s['scenario']==cell['scenario'] and s['method']==cell['method'])
            ident=f"slot-{cell['sequence']:02d}-"+uuid.uuid4().hex
            run=root/'attempts'/ident
            checkpoint.begin(cell,ident,session)
            try:
                result=treatment(repo,run,plan('primary',sequence=cell['sequence']),snapshot,design,environment,identity)
                source_binding(repo,spec)
                if result.get('runtime'):
                    current=set(result['runtime'].values())
                    for old_slot in checkpoint.state['slots'][:cell['sequence']-1]:
                        previous=read_json(root/old_slot['manifest']).get('runtime',{})
                        if current & set(previous.values()):raise ValueError('runtime_identity_reused')
                atomic_record(run/'session.json',session)
                manifest=dict(result,campaign_identity_sha256=fingerprint(identity),cell=cell,treatment_id=ident,scope=scope,
                    files={str(p.relative_to(root)):file_sha256(p) for directory in (run,sessionroot) for p in directory.rglob('*') if p.is_file()})
                for name in ('requests','endpoint','continuity'):
                    manifest[name+'_path']=str(Path(result[name+'_path']).relative_to(root))
                atomic_record(run/'manifest.json',manifest)
                if result['status']=='INTERRUPTED':
                    checkpoint.interrupt()
                    raise ValueError('interrupted_treatment_requires_review')
                checkpoint.seal(cell['sequence'],str((run/'manifest.json').relative_to(root)))
                for path in run.rglob('*'):
                    if path.is_file():path.chmod(0o444)
                if result['status']!='SEALED_VALID':raise ValueError('invalid_treatment_requires_review')
            except BaseException:
                if checkpoint.state['slots'][cell['sequence']-1]['status']=='RUNNING':checkpoint.interrupt()
                raise
            completed+=1
            if stop_after_seal(completed,cell['sequence'],max_slots=max_slots,stop_after_slot=stop_after_slot):return checkpoint.state
