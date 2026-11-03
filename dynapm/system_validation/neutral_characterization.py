"""Bounded neutral PW6 engineering timing, never a compressed treatment trace.

Actuator stimuli are explicit engineering targets. Production PW6 recommendations
and isolated refresh-component benchmarks are recorded separately, never spoofed
into profile history or used to choose a compression duration.
"""
from copy import deepcopy
from pathlib import Path
import argparse, concurrent.futures, json, os, shutil, subprocess, sys, tempfile, threading, time, uuid
import numpy as np
import pandas as pd
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen

from dynapm.core.provenance import (SourceProvenance, DataConfig, ModelConfig, PolicyConfig,
 StatisticsConfig, ExperimentConfigProvenance, CohortManifest, CohortEntity, prepare_experiment,
 fingerprint, canonical_json, file_sha256, read_json, utc_now)
from dynapm.core.run_store import RunSession, OutputSpec, write_json
from dynapm.data.manifests import build_dataset_manifest
from dynapm.core.accounting import Trigger
from dynapm.core.temporal import trailing_observations
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.design import resource_manifests
from dynapm.system_validation.shared_bootstrap import load_artifact, freeze_blocks, TreatmentRegistry, StartupEvidence
from dynapm.system_validation.host_power import ManagedPowerGuard, power_state
from dynapm.system_validation.clock_observations import ObservationClock, receive_observation, validate_clock_evidence
from dynapm.system_validation.calibration_runner import require_isolated_engine, local_host_diagnostics
from dynapm.system_validation.smoke import Commands, Kube, http, free_port, guard_local_endpoint, guard_local_api, wait_http, resize_preflight, environment
from dynapm.system_validation.consumer import recommend, resources_match, cpu_millicores, memory_bytes
from dynapm.system_validation.timing_probes import ResizeProbe, distribution

ARTIFACT='51aad0e364d6f4774f8c51ab2cb7544eac87d7ebdb36e492eba648c014dffd2b'
QUALIFICATION='b0e4e3c1dcaf87de424cb6bb070341da4fc69ad96b63558bf910255807775a93'
SCHEMA='bounded-neutral-characterization-v1'
# This is an engineering stimulus ladder, NOT a recommendation/policy schedule.
TARGETS=((None,None),(250,128),(1000,512),(250,128),(500,128),(100,128),
         (100,256),(100,64),(1000,512),(100,64),(100,64),(500,128),(1000,512))
SETTLE_RESPONSES=20  # Descriptive window, never a steady-state acceptance threshold.
MAX_ACTIVE_SECONDS=240
MAX_RESIZE_SECONDS=60
JSONS=('plan','runtime_environment','preflight','initialization','summary','status','host_before','host_after')
LINES=('decisions','timing','telemetry','requests','pod_observations')
LOGS=('kind','application','portforward','profile','generator','controller')


def append(path,row):
    with Path(path).open('a') as f:f.write(canonical_json(row)+'\n');f.flush()


def rows(path):
    with Path(path).open() as f:return [json.loads(line) for line in f if line.strip()]


def qualification(repo):
    q=Path(repo)/'results/shared_bootstrap/qualifications/block0001/qualification.json'
    if file_sha256(q)!=QUALIFICATION:raise ValueError('qualification_hash_mismatch')
    value=read_json(q)
    if value['artifact_sha256']!=ARTIFACT or value['disposition']!='CLAIM_ELIGIBLE_BOOTSTRAP':
        raise ValueError('qualified_block_required')
    marker=read_json(q.parent/'COMPLETE')
    if marker['qualification_sha256']!=QUALIFICATION:raise ValueError('qualification_marker_mismatch')
    a=Path(repo)/'results/shared_bootstrap/artifacts'/ARTIFACT
    m,b=load_artifact(a,ARTIFACT,frozen_spec(repo))
    if m['acquisition_run_id']!=value['parent_run_id'] or b.accepted_slots!=288:
        raise ValueError('qualification_lineage_mismatch')
    return a,value


def pending_opportunity(pending):
    """A decision opportunity is observable while pending; no overlapping patch."""
    return 'SKIPPED_PENDING' if pending is not None else 'READY'


def require_idle(pending):
    if pending is not None:raise ValueError('overlapping_actuation_forbidden')


def observe_probe(probe,pod_end_ns,observed_ns,wall_ns,actual,sample):
    if not pod_end_ns<=sample['host_receipt_monotonic_ns']<=observed_ns:raise ValueError('ordered_response_receipts_required')
    previous=set(probe.first_observed)
    probe.observe(observed_ns,wall_ns,pod_cpu_millicores=cpu_millicores(actual['requests']['cpu']),
        pod_memory_mib=memory_bytes(actual['requests']['memory'])/2**20,cgroup_cpu_cores=sample['cpu_limit_cores'],
        cgroup_memory_bytes=sample['memory_limit_bytes'],persistent_workset_bytes=sample['persistent_workset_bytes'])
    # Separate complete-response upper bounds: Pod GET vs telemetry envelope.
    for key in set(probe.first_observed)-previous:
        mono=pod_end_ns if key.startswith('pod_') else sample['host_receipt_monotonic_ns']
        probe.first_observed[key]=(mono,wall_ns if key.startswith('pod_') else sample.get('received_at_ns',wall_ns))


def component_refresh(adapter):
    """Real CPU/wall computation on a disposable production-policy copy.

    Bypasses due/eligibility scheduling ONLY in this isolated component benchmark.
    No runtime observation, clock, refresh or recommendation in the live PW6
    state is changed; no six-hour scheduler event is claimed.
    """
    policy=deepcopy(adapter.policy);t=pd.Timestamp.now(tz='UTC')
    begin=time.monotonic_ns();cpu=time.thread_time_ns()
    history=adapter.history
    c=trailing_observations(history.iloc[:,0],history.index[-1],24)
    m=trailing_observations(history.iloc[:,1],history.index[-1],24)
    policy._commit_forecast(t,c,m,trigger=Trigger.PERIODIC,nominal_scheduled_time=t)
    return dict(start_monotonic_ns=begin,end_monotonic_ns=time.monotonic_ns(),thread_cpu_ns=time.thread_time_ns()-cpu,
        role='ISOLATED_REFRESH_COMPONENT_NOT_SCHEDULER_EVENT',history_slots=len(history),
        live_runtime_refreshes=adapter.policy.accounting_metrics()['n_refresh_events'])


def profile_worker(plan,root,port):
    repo=Path(plan['repo']);d=plan['design'];artifact=repo/'results/shared_bootstrap/artifacts'/ARTIFACT
    state={};identity=uuid.uuid4().hex
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value):
            raw=canonical_json(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            try:
                if self.path=='/healthz':return self.reply(dict(ready=True,initialized='adapter' in state,pid=os.getpid(),profile_instance_id=identity))
                if 'adapter' not in state:raise ValueError('not_initialized')
                adapter=state['adapter']
                if self.path=='/snapshot':return self.reply(adapter.snapshot())
                if self.path=='/maintenance-component':return self.reply(component_refresh(adapter))
                raise ValueError('unknown_endpoint')
            except Exception as exc:self.send_error(400,str(exc))
        def do_POST(self):
            try:
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path!='/initialize' or state:raise ValueError('exactly_one_initialization')
                if payload['profile_instance_id']!=identity:raise ValueError('fresh_profile_identity_required')
                startup=StartupEvidence(**payload['startup']);blocks=freeze_blocks([(artifact,ARTIFACT)],d,common_stable_prehistory=True,purpose='pilot')
                registry=TreatmentRegistry(blocks);origin=(time.time_ns()//(300*10**9))*(300*10**9)
                start=time.monotonic_ns();adapter=registry.initialize(0,'pw_6h',artifact,d,origin,startup,read_wall_ns=time.time_ns())
                state['adapter']=adapter
                snap=adapter.snapshot();value=dict(profile_instance_id=identity,pid=os.getpid(),startup=vars(startup),
                    initialization_seconds=(time.monotonic_ns()-start)/1e9,origin_ns=origin,snapshot=snap,
                    cpu_thresholds=adapter.policy.cpu_thresholds,memory_thresholds=adapter.policy.mem_thresholds,
                    input_history_sha256=fingerprint(adapter.history.to_numpy().tolist()),
                    initial_dynamic_sha256=fingerprint(snap['profile']['dynamic']),method='pw_6h')
                write_json(Path(root)/'outputs/initialization.json',value);return self.reply(value)
            except Exception as exc:self.send_error(400,str(exc))
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


def generator_worker(plan,root):
    """Unchanged stable RPS/work, with complete-body and local monotonic clocks."""
    d=plan['design'];rate=d['scenarios']['stable']['rps'];work=d['scenarios']['stable']['memory_mib']
    start=plan['load_start_seconds'];origin=time.monotonic()+start-time.time();slots=threading.BoundedSemaphore(d['workload']['max_concurrency'])
    output=Path(root)/'outputs/requests.jsonl';lock=threading.Lock();errors=[]
    def emit(value):
        with lock:append(output,value)
    def send(i):
        sent_ns=time.monotonic_ns();wall_ns=time.time_ns()
        url=plan['app_url']+f"/work?iterations={d['workload']['iterations']}&memory_mib={work}&seed={d['workload']['seed']}"
        try:
            with urlopen(url,timeout=d['workload']['timeout_seconds']) as response:
                raw=response.read();complete=time.monotonic_ns();status=response.status;body=json.loads(raw)
            ok=status==200 and body['iterations']==d['workload']['iterations'] and body['memory_mib']==work;error=None
        except Exception as exc:complete=time.monotonic_ns();ok=False;status=None;error=type(exc).__name__;body=None
        try:emit(dict(request_id=i,scheduled_at=start+i/rate,sent_at=wall_ns/1e9,completed_at=time.time(),
            sent_monotonic_ns=sent_ns,completed_monotonic_ns=complete,success=ok,http_status=status,error=error,dropped=False,
            latency_seconds=(complete-sent_ns)/1e9,response=body))
        except Exception as exc:errors.append(type(exc).__name__)
        finally:slots.release()
    count=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=d['workload']['max_concurrency']) as pool:
        for i in range(int(MAX_ACTIVE_SECONDS*rate)):
            if (Path(root)/'STOP_LOAD').exists():break
            time.sleep(max(0,origin+i/rate-time.monotonic()))
            if slots.acquire(blocking=False):pool.submit(send,i)
            else:emit(dict(request_id=i,scheduled_at=start+i/rate,sent_at=None,completed_at=time.time(),success=False,dropped=True,error='capacity',latency_seconds=None))
            count+=1
    write_json(Path(root)/'outputs/generator_final.json',dict(count=count,errors=errors,complete=True,pid=os.getpid()))


def controller_worker(plan,root,config):
    root=Path(root);o=root/'outputs';d=plan['design'];env=dict(os.environ);commands=Commands(env,plan['repo']);kube=Kube(commands,config,plan['cluster'],d)
    context=dict(run_id=plan['run_id'],experiment_fingerprint=plan['fingerprint'],source_commit=plan['source_commit'])
    clock=ObservationClock(root,context);pending=None;events=[];baseline_pod=kube.pod();uid=baseline_pod['metadata']['uid'];app_instance=None
    def collect():
        nonlocal app_instance
        start=time.monotonic_ns();e=receive_observation(plan['app_url']+'/clock-observation');body=time.monotonic_ns()
        with (o/'telemetry.jsonl').open('a') as f:s=clock.accept(e,f)
        end=time.monotonic_ns()
        if app_instance is None:app_instance=s['instance_id']
        if s['instance_id']!=app_instance or s['oom_kills']!=0:raise ValueError('app_restart_or_oom')
        append(o/'timing.jsonl',dict(kind='TELEMETRY',start_monotonic_ns=start,body_receipt_monotonic_ns=e['receipt_monotonic_ns'],accepted_monotonic_ns=end,
            complete_observation_seconds=(end-start)/1e9,transport_seconds=(e['receipt_monotonic_ns']-start)/1e9,admission_seconds=(end-e['receipt_monotonic_ns'])/1e9))
        return s
    try:
        collect();health=http(plan['profile_url']+'/healthz')
        startup=StartupEvidence(*[uuid.uuid4().hex for _ in range(6)],initial_runtime_refreshes=0,initial_observations=0,initial_resource_changes=0,pending_resize=False)
        startup=StartupEvidence(startup.treatment_id,uid,app_instance,health['profile_instance_id'],plan['controller_instance_id'],plan['telemetry_instance_id'],0,0,0,False)
        http(plan['profile_url']+'/initialize',dict(profile_instance_id=health['profile_instance_id'],startup=vars(startup)))
        while time.time()<plan['load_start_seconds']+3:collect();time.sleep(.2)
        for decision,(target_cpu,target_mem) in enumerate(TARGETS):
            if time.time()>=plan['load_start_seconds']+MAX_ACTIVE_SECONDS-10:raise ValueError('bounded_probe_deadline')
            begin=time.monotonic_ns();sample=collect();profile=http(plan['profile_url']+'/snapshot')
            maintenance=http(plan['profile_url']+'/maintenance-component');recommend_start=time.monotonic_ns();recommended=recommend(profile['profile'],d);recommend_end=time.monotonic_ns()
            if target_cpu is None:
                target_cpu=recommended['cpu_millicores'];target_mem=recommended['memory_mib']
            target=dict(cpu_millicores=target_cpu,memory_mib=target_mem)
            pod=kube.pod();before=pod['spec']['containers'][0]['resources']
            event=dict(decision=decision,decision_start_monotonic_ns=begin,method='pw_6h',policy_recommendation=recommended,
                applied_target=target,target_role='PRODUCTION_PW6_RECOMMENDATION' if decision==0 else 'ENGINEERING_ACTUATION_STIMULUS_NOT_POLICY_OUTCOME',
                recommendation_seconds=(recommend_end-recommend_start)/1e9,maintenance_component_seconds=(maintenance['end_monotonic_ns']-maintenance['start_monotonic_ns'])/1e9,
                maintenance=maintenance,before_resources=before)
            require_idle(pending)
            if resources_match(before,target):
                event.update(disposition='NO_OP',pending_at_next_opportunity=False);append(o/'decisions.jsonl',event);events.append(event)
                time.sleep(.3);continue
            submit=time.monotonic_ns();wall=time.time_ns();ack=kube.resize(target);ack_mono=time.monotonic_ns()
            pending=target
            probe=ResizeProbe(str(decision),submit,wall,target_cpu,target_mem,
                cpu_millicores(before['requests']['cpu'])!=target_cpu,memory_bytes(before['requests']['memory'])!=target_mem*2**20)
            probe.acknowledged(ack_mono,time.time_ns())
            # Real adjacent opportunity while pending: observe skip, never queue another patch.
            assert pending_opportunity(pending)=='SKIPPED_PENDING'
            append(o/'timing.jsonl',dict(kind='SKIPPED_PENDING',decision=decision,pending=target,monotonic_ns=time.monotonic_ns()))
            final=None
            while time.monotonic_ns()-submit<MAX_RESIZE_SECONDS*1e9:
                pod_start=time.monotonic_ns();p=kube.pod();pod_end=time.monotonic_ns();pod_wall=time.time_ns();sample=collect();observed=time.monotonic_ns()
                if p['metadata']['uid']!=uid or p['status']['containerStatuses'][0]['restartCount']!=0:raise ValueError('pod_replaced_or_restarted')
                actual=p['status']['containerStatuses'][0].get('resources')
                append(o/'pod_observations.jsonl',dict(decision=decision,start_monotonic_ns=pod_start,end_monotonic_ns=pod_end,pod=p,telemetry_index=sample['sample_index']))
                if actual:
                    observe_probe(probe,pod_end,observed,pod_wall,actual,sample)
                if resources_match(actual,target) and abs(sample['cpu_limit_cores']*1000-target_cpu)<1e-6 and sample['memory_limit_bytes']==target_mem*2**20:
                    final=sample;break
                time.sleep(.2)
            if final is None:
                event.update(disposition='UNRESOLVED_PENDING',timing=probe.record(skipped_decisions=1,timeout=True));append(o/'decisions.jsonl',event)
                raise ValueError('resize_not_enforced_within_bound')
            enforced=time.monotonic_ns();pending=None
            event.update(disposition='ENFORCED',decision_to_enforcement_seconds=(enforced-begin)/1e9,
                timing=probe.record(pending_end_monotonic_ns=enforced,skipped_decisions=1),enforced_monotonic_ns=enforced,
                app_instance_id=app_instance,pod_uid=uid,controller_pid=os.getpid())
            # Drain old requests and retain a fixed descriptive post-enforcement window.
            deadline=time.monotonic()+15;post=[];old=[]
            while time.monotonic()<deadline:
                req=rows(o/'requests.jsonl');old=[r for r in req if r.get('sent_monotonic_ns',enforced)>=0 and r.get('sent_monotonic_ns',enforced)<enforced<=r.get('completed_monotonic_ns',0)]
                post=[r for r in req if r.get('sent_monotonic_ns',0)>=enforced]
                if len(post)>=SETTLE_RESPONSES:break
                collect();time.sleep(.25)
            if len(post)<SETTLE_RESPONSES:raise ValueError('post_enforcement_window_incomplete')
            after=collect();p=kube.pod()
            if not resources_match(p['status']['containerStatuses'][0].get('resources'),target) or after['memory_limit_bytes']!=target_mem*2**20 or after['cpu_limit_cores']*1000!=target_cpu:
                raise ValueError('hidden_pending_or_enforcement_regression')
            event.update(pending_at_next_opportunity=False,old_request_drain_seconds=max([(r['completed_monotonic_ns']-enforced)/1e9 for r in old],default=0),
                old_inflight_requests=len(old),post_enforcement_requests=post[:SETTLE_RESPONSES],
                post_window_seconds=(post[SETTLE_RESPONSES-1]['completed_monotonic_ns']-enforced)/1e9,
                persistent_workset_bytes=after['persistent_workset_bytes'],settling_status='MECHANICAL_DRAIN_AND_DESCRIPTIVE_WINDOW_ONLY_NOT_STEADY_STATE')
            append(o/'decisions.jsonl',event);events.append(event)
        write_json(o/'controller_final.json',dict(complete=True,decisions=len(events),pending=pending,pid=os.getpid(),app_instance_id=app_instance,pod_uid=uid))
    finally:
        clock.finalize();(root/'STOP_LOAD').touch()


def summary(root):
    o=Path(root)/'outputs';decisions=rows(o/'decisions.jsonl');timing=rows(o/'timing.jsonl');enforced=[x for x in decisions if x['disposition']=='ENFORCED']
    values={}
    def metric(k,seq):values[k]=distribution(seq)
    metric('telemetry_completion',[t['complete_observation_seconds'] for t in timing if t['kind']=='TELEMETRY'])
    metric('profile_refresh_component',[x['maintenance_component_seconds'] for x in decisions])
    metric('recommendation_compute',[x['recommendation_seconds'] for x in decisions])
    for key in ['api_ack','pod_cpu','pod_memory','cgroup_cpu','cgroup_memory']:
        metric(key,[x['timing']['seconds'][key] for x in enforced if key in x['timing']['seconds']])
    for key in ['pending_seconds']:
        metric(key,[x['timing'][key] for x in enforced])
    for key in ['decision_to_enforcement_seconds','old_request_drain_seconds','post_window_seconds']:
        metric(key,[x[key] for x in enforced])
    req=rows(o/'requests.jsonl')
    return dict(schema_version=SCHEMA,method='pw_6h',comparative=False,claim_generating=False,
        compression_duration_selected=False,distributions=values,decisions=len(decisions),enforced=len(enforced),
        no_ops=sum(x['disposition']=='NO_OP' for x in decisions),skipped_pending=sum(t['kind']=='SKIPPED_PENDING' for t in timing),
        hidden_pending=False,overlapping_actuation=False,requests=len(req),request_errors=sum(not r['success'] for r in req),
        worst_path=max(enforced,key=lambda x:x['decision_to_enforcement_seconds']) if enforced else None,
        component_benchmark_limitation='PW6 refresh computation timed on disposable production copies; six-hour runtime cadence NOT observed or accelerated',
        application_settling='old-request drain plus descriptive 20-response windows; statistical steady state NOT_ESTABLISHED')


def prepare_inputs(repo,config):
    inputs=Path(repo)/'results/neutral_characterization/inputs'/fingerprint(config)
    trace=inputs/'stable';trace.mkdir(parents=True,exist_ok=True);target=trace/'input.json'
    if target.exists() and canonical_json(read_json(target))!=canonical_json(config):raise ValueError('immutable_probe_descriptor_mismatch')
    if not target.exists():write_json(target,config)
    dataset=build_dataset_manifest(inputs,dataset_id='bounded-neutral-characterization',source_name='prospective neutral engineering timing stimuli',trace_names=('stable',),schema_identity=SCHEMA)
    return inputs,dataset


def run_one(repo,index):
    repo=Path(repo).resolve();source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean_committed_source_required')
    d=frozen_spec(repo);artifact,q=qualification(repo);artifact_inventory=q['artifact_files']
    power_state();endpoint=os.environ.get('DOCKER_HOST') or subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip();guard_local_endpoint(endpoint)
    if shutil.disk_usage(repo).free<20*2**30:raise ValueError('20GiB_reserve_required')
    config=dict(schema_version=SCHEMA,method='pw_6h',qualification_sha256=QUALIFICATION,artifact_sha256=ARTIFACT,
        targets=TARGETS,max_active_seconds=MAX_ACTIVE_SECONDS,max_resize_seconds=MAX_RESIZE_SECONDS,settle_responses=SETTLE_RESPONSES,
        stimulus_role='engineering actuator targets; not a compressed policy schedule',compression_duration_selected=False,comparative=False,index=index,
        implementation_sha256=file_sha256(Path(__file__)),base_source='5460c86dc4385ade3198dc01c9cd4184c0a8e45b')
    inputs,dataset=prepare_inputs(repo,config)
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'neutral-engineering-v1',{'minimum_observations':200},(CohortEntity('stable','application',True,None,0),),utc_now())
    cfg=ExperimentConfigProvenance(DataConfig(dataset.dataset_id,bootstrap_fraction=1.,minimum_observations=200),ModelConfig(family='unused-observation-only'),
        (PolicyConfig('pw_6h',periodic_interval_hours=6,observation_window_hours=24),),StatisticsConfig(bootstrap_repetitions=0,bootstrap_seed=20251022,test_specification={'enabled':False}),
        preprocessing=config,analysis=dict(comparative=False,claim_generating=False))
    exp,env_record=prepare_experiment(repo,inputs,cfg,dataset,cohort,{'workload':d['workload']['seed']},execution_compatibility_keys=tuple(d['hardware']['compatibility_keys']))
    specs=[OutputSpec('outputs/'+n+'.json','neutral-characterization') for n in JSONS]+[OutputSpec('outputs/'+n+'.jsonl','neutral-characterization') for n in LINES]+[OutputSpec('logs/'+n+'.log','bounded-worker-log') for n in LOGS]+[OutputSpec('outputs/'+n,'guard-clock-evidence') for n in ['clock_observations.jsonl','clock_rejections.jsonl','clock_evidence_manifest.json','host_continuity.jsonl','host_continuity_summary.json','host_continuity_failure.json','power_guard.json','controller_final.json','generator_final.json']]
    with tempfile.TemporaryDirectory(prefix='dynapm-neutral-private-') as temp:
        private=Path(temp);private.chmod(0o700);dc=private/'docker';dc.mkdir();(dc/'config.json').write_text('{"auths":{}}')
        env={**os.environ,'DOCKER_HOST':endpoint,'DOCKER_CONFIG':str(dc),'KUBECONFIG':str(private/'kubeconfig'),'PATH':str(repo/d['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH']}
        commands=Commands(env,repo);require_isolated_engine(commands);details=environment(commands,d)
        expected_images=read_json(artifact/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']['image_ids']
        details['image_ids']={}
        for image in [d['kubernetes']['application_image'],d['kubernetes']['prometheus_local_image'],d['kubernetes']['node_image']]:
            info=json.loads(commands.run(['docker','image','inspect',image]))[0]
            details['image_ids'][image]=info['Id']
            if image in expected_images and info['Id']!=expected_images[image]:raise ValueError('qualified_image_identity_changed')  # Cache required; no remote acquisition.
        with RunSession(repo/'results/neutral_characterization',exp,env_record,repo=repo,dataset_root=inputs,purpose='pilot',required_outputs=specs) as run:
            o=run.path/'outputs';logs=run.path/'logs';logs.mkdir(exist_ok=True)
            for n in JSONS:write_json(o/(n+'.json'),dict(status='PENDING'))
            for n in LINES:(o/(n+'.jsonl')).touch()
            for n in LOGS:(logs/(n+'.log')).touch()
            context=dict(run_id=run.manifest.run_id,experiment_fingerprint=exp.fingerprint,source_commit=source.commit)
            cluster=d['kubernetes']['cluster']+'-timing-'+uuid.uuid4().hex[:8];kube=Kube(commands,private/'kubeconfig',cluster,d);children=[];handles=[];created=False
            write_json(o/'host_before.json',local_host_diagnostics())
            with ManagedPowerGuard(run.path,context) as power:
                def spawn(args,log):
                    handle=(logs/log).open('a');handles.append(handle);p=subprocess.Popen(args,env=env,cwd=repo,stdout=handle,stderr=subprocess.STDOUT);children.append(p);return p
                try:
                    print(canonical_json(dict(stage='SETUP',run_id=run.manifest.run_id,fingerprint=exp.fingerprint,index=index)),flush=True)
                    created=True;commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(private/'kubeconfig'),'--wait','120s'],log=logs/'kind.log',timeout=300)
                    guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
                    details['nodes']=json.loads(kube.call(['get','nodes','-o','json']));details['version']=json.loads(kube.call(['version','-o','json']))
                    if details['version']['serverVersion']['gitVersion']!=d['kubernetes']['server_version']:raise ValueError('pinned_server_version_required')
                    for image in [d['kubernetes']['application_image'],d['kubernetes']['prometheus_local_image']]:commands.run(['kind','load','docker-image',image,'--name',cluster],log=logs/'kind.log')
                    objects=resource_manifests(d)
                    for item in objects['items']:
                        if item['kind']=='Pod':item['metadata']['labels']={'app':'dynapm-workload' if item['metadata']['name']=='application' else 'dynapm-prometheus'}
                    write_json(o/'resources.json',objects);kube.call(['apply','-f',str(o/'resources.json')],log=logs/'kind.log')
                    kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],log=logs/'kind.log',timeout=150)
                    write_json(o/'preflight.json',resize_preflight(kube,d));power.raise_if_failed()
                    app_port,profile_port=free_port(),free_port()
                    prefix=['kubectl','--kubeconfig',str(private/'kubeconfig'),'--context','kind-'+cluster,'-n',d['kubernetes']['namespace']]
                    spawn(prefix+['port-forward','service/application',f'{app_port}:8080','--address','127.0.0.1'],'portforward.log');wait_http(f'http://127.0.0.1:{app_port}/healthz')
                    plan=dict(repo=str(repo),design=d,source_commit=source.commit,run_id=run.manifest.run_id,fingerprint=exp.fingerprint,cluster=cluster,
                        app_url=f'http://127.0.0.1:{app_port}',profile_url=f'http://127.0.0.1:{profile_port}',load_start_seconds=time.time()+15,
                        controller_instance_id=uuid.uuid4().hex,telemetry_instance_id=uuid.uuid4().hex,config=config)
                    write_json(o/'plan.json',plan);write_json(o/'runtime_environment.json',details)
                    worker=[sys.executable,'-u','-m','dynapm.system_validation.neutral_characterization']
                    spawn(worker+['worker','profile','--plan',str(o/'plan.json'),'--root',str(run.path),'--port',str(profile_port)],'profile.log');wait_http(plan['profile_url']+'/healthz')
                    generator=spawn(worker+['worker','generator','--plan',str(o/'plan.json'),'--root',str(run.path)],'generator.log')
                    controller=spawn(worker+['worker','controller','--plan',str(o/'plan.json'),'--root',str(run.path),'--kubeconfig',str(private/'kubeconfig')],'controller.log')
                    deadline=time.monotonic()+MAX_ACTIVE_SECONDS+30
                    while controller.poll() is None:
                        power.raise_if_failed()
                        if time.monotonic()>deadline:raise ValueError('bounded_controller_timeout')
                        if children[0].poll() is not None or children[1].poll() is not None:raise ValueError('probe_service_exited')
                        time.sleep(1)
                    if controller.returncode:raise ValueError('controller_failed_see_log')
                    generator.wait(timeout=10)
                    if generator.returncode:raise ValueError('generator_failed_see_log')
                    validate_clock_evidence(run.path,context);require_isolated_engine(commands,cluster)
                    write_json(o/'summary.json',summary(run.path));write_json(o/'status.json',dict(stage='COMPLETE',comparative=False,claim_generating=False))
                finally:
                    (run.path/'STOP_LOAD').touch()
                    for p in children:
                        if p.poll() is None:p.terminate()
                        try:p.wait(timeout=10)
                        except subprocess.TimeoutExpired:p.kill();p.wait()
                    for f in handles:f.close()
                    try:(logs/'application.log').write_text(kube.call(['logs','application']))
                    except Exception:pass
                    if created:commands.run(['kind','delete','cluster','--name',cluster],log=logs/'kind.log',timeout=120)
            write_json(o/'host_after.json',local_host_diagnostics())
            # All qualified artifact bytes remain untouched.
            from dynapm.system_validation.receipt_derivation import _inventory
            if _inventory(artifact)!=artifact_inventory:raise ValueError('artifact_changed_during_probe')
            if SourceProvenance.capture(repo).commit!=source.commit or SourceProvenance.capture(repo).dirty:raise ValueError('source_changed_during_probe')
            run.complete();print(canonical_json(dict(stage='COMPLETE',run_path=str(run.path),run_id=run.manifest.run_id)),flush=True);return run.path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);s=p.add_subparsers(dest='action',required=True)
    s.add_parser('run-two')
    w=s.add_parser('worker');w.add_argument('kind',choices=['profile','generator','controller']);w.add_argument('--plan',type=Path,required=True);w.add_argument('--root',type=Path,required=True);w.add_argument('--port',type=int);w.add_argument('--kubeconfig',type=Path)
    a=p.parse_args()
    if a.action=='run-two':
        paths=[]
        for index in (1,2):paths.append(str(run_one(a.repo,index)))
        print(canonical_json(dict(completed_runs=paths,compression_duration_selected=False)),flush=True)
    else:
        plan=read_json(a.plan)
        if a.kind=='profile':profile_worker(plan,a.root,a.port)
        elif a.kind=='generator':generator_worker(plan,a.root)
        else:controller_worker(plan,a.root,a.kubeconfig)


if __name__=='__main__':main()
