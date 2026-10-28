"""Bounded real kind plumbing smoke, always non-claim and single-method."""
from __future__ import annotations
from pathlib import Path
import json,os,shutil,socket,subprocess,sys,tempfile,threading,time,uuid,urllib.request
from urllib.parse import urlparse,quote
from dynapm.core.provenance import (SourceProvenance,DataConfig,ModelConfig,PolicyConfig,StatisticsConfig,
    ExperimentConfigProvenance,CohortManifest,CohortEntity,prepare_experiment,read_json,fingerprint,file_sha256,utc_now)
from dynapm.core.run_store import RunSession,OutputSpec,write_json
from dynapm.data.manifests import build_dataset_manifest
from dynapm.system_validation.design import frozen_design
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.consumer import recommend,resource_patch,resources_match,summarize_requests,resource_metrics
from dynapm.system_validation.workloads import offered_trace,run_load

JSON_OUTPUTS=['design','kubernetes_environment','resources','trace','telemetry','requests','profile_before','profile_after',
    'recommendation','actuation','metrics','prometheus_up','smoke_diagnostics']
LOGS=['build','kind','application','prometheus','profile_service','application_portforward','prometheus_portforward']


def http(url,payload=None):
    data=None if payload is None else json.dumps(payload,allow_nan=False).encode()
    request=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)


def text_http(url):
    with urllib.request.urlopen(url,timeout=5) as response:return response.read().decode()


def successful_post_enforcement(records,confirmed_at_ns):
    """A patch acknowledgement is not actual allocation enforcement."""
    return any(r['success'] and r['sent_at'] is not None and r['sent_at']>confirmed_at_ns/1e9 for r in records)


def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def guard_local_endpoint(endpoint):
    if not endpoint.startswith('unix:///'):raise ValueError('local_unix_docker_required_no_remote_engine')


def guard_local_api(endpoint):
    u=urlparse(endpoint)
    if u.scheme!='https' or u.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('local_kind_api_required')


class Commands:
    def __init__(self,env,cwd):self.env=env;self.cwd=Path(cwd)
    def run(self,args,*,log=None,timeout=300):
        r=subprocess.run(args,cwd=self.cwd,env=self.env,capture_output=True,text=True,timeout=timeout)
        if log is not None:
            with Path(log).open('a') as out:out.write(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('command_failed:'+args[0]+':'+r.stderr[-2000:])
        return r.stdout


class Kube:
    def __init__(self,commands,kubeconfig,cluster,design):
        self.commands=commands;self.config=Path(kubeconfig);self.cluster=cluster;self.design=design
        if not cluster.startswith(design['kubernetes']['cluster']+'-'):raise ValueError('isolated_harness_cluster_required')
    def call(self,args,*,controller=False,log=None,timeout=60):
        ns=self.design['kubernetes']['namespace']
        prefix=['kubectl','--kubeconfig',str(self.config),'--context','kind-'+self.cluster,'--namespace',ns]
        if controller:prefix+=['--as',f'system:serviceaccount:{ns}:profile-consumer']
        return self.commands.run(prefix+args,log=log,timeout=timeout)
    def pod(self):return json.loads(self.call(['get','pod','application','-o','json'],controller=True))


def wait_http(url,timeout=90):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        try:return text_http(url)
        except Exception:time.sleep(1)
    raise RuntimeError('http_readiness_timeout:'+url)


def wait_until(target):
    last=0
    while time.time()<target:
        if time.monotonic()-last>=30:
            print(json.dumps(dict(stage='waiting_for_nominal_bucket',seconds_remaining=round(target-time.time(),1))),flush=True);last=time.monotonic()
        time.sleep(max(0,min(1,target-time.time())))


def environment(commands,design):
    docker=json.loads(commands.run(['docker','info','--format','{{json .}}']))
    return dict(docker={k:docker.get(k) for k in ['ServerVersion','OperatingSystem','Architecture','KernelVersion','NCPU','MemTotal','CgroupVersion']},
        kind=commands.run(['kind','version']).strip(),kubectl_client=json.loads(commands.run(['kubectl','version','--client','-o','json']))['clientVersion'],
        node_image=design['kubernetes']['node_image'])


def output_specs():
    return [OutputSpec('outputs/'+n+'.json','smoke-'+n) for n in JSON_OUTPUTS]+[
        OutputSpec('outputs/application_metrics.prom','real-application-prometheus-exposition'),
        OutputSpec('outputs/profile_metrics.prom','real-profile-service-process-and-step-overhead')]+[
        OutputSpec('logs/'+n+'.log','smoke-'+n+'-log') for n in LOGS]


def run_smoke(repo):
    repo=Path(repo).resolve();d=frozen_design(repo)
    if SourceProvenance.capture(repo).dirty:raise ValueError('commit_harness_before_managed_smoke')
    if d['claim_trials_enabled'] or d['future_trials']['enabled'] or d['smoke']['real_buckets']!=1 or d['smoke']['method']!='full_rewrite':raise ValueError('bounded_single_method_smoke_required')
    if shutil.disk_usage(repo).free<20*2**30:raise ValueError('20GiB_local_disk_reserve_required')
    endpoint=os.environ.get('DOCKER_HOST')
    if not endpoint:
        endpoint=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    guard_local_endpoint(endpoint)
    with tempfile.TemporaryDirectory(prefix='dynapm-system-private-') as temporary:
        private=Path(temporary);os.chmod(private,0o700);dc=private/'docker';dc.mkdir();(dc/'config.json').write_text('{"auths":{}}')
        env={**os.environ,'DOCKER_HOST':endpoint,'DOCKER_CONFIG':str(dc)}
        commands=Commands(env,repo);details=environment(commands,d)
        if not details['kind'].startswith('kind '+d['kubernetes']['kind_version']+' '):raise ValueError('kind_version_mismatch')
        image=d['kubernetes']['application_image'];build_log=private/'build.log'
        commands.run(['docker','build','-f','harness/system/Dockerfile','-t',image,'.'],log=build_log)
        image_info=json.loads(commands.run(['docker','image','inspect',image]))[0]
        details['application_image_id']=image_info['Id'];details['application_rootfs_layers']=image_info['RootFS']['Layers']
        # Docker's containerd store may export a multiarch index with absent foreign-platform
        # blobs. A metadata-only build materializes the pinned native image for kind import.
        prom_image=d['kubernetes']['prometheus_local_image']
        commands.run(['docker','build','-f','harness/system/Prometheus.Dockerfile','-t',prom_image,'.'],log=build_log)
        prom_info=json.loads(commands.run(['docker','image','inspect',prom_image]))[0]
        details['prometheus_image_id']=prom_info['Id'];details['prometheus_rootfs_layers']=prom_info['RootFS']['Layers']
        dataset=build_dataset_manifest(repo/'harness/system/fixtures',dataset_id='dynapm-system-smoke-v1',source_name='explicit synthetic smoke fixtures',
            trace_names=('smoke',),schema_identity='system-bootstrap-and-workload-fixtures-v1')
        cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'single-application-plumbing-v1',{'minimum_observations':289},
            (CohortEntity('smoke','application',True,None,289),),utc_now())
        config=ExperimentConfigProvenance(DataConfig(dataset.dataset_id,bootstrap_fraction=288/289,minimum_observations=289,evaluation_cadence_seconds=300),
            ModelConfig(family='unused-observation-only'),(PolicyConfig('full_rewrite',observation_window_hours=24),),
            StatisticsConfig(bootstrap_repetitions=0,bootstrap_seed=d['workload']['seed'],test_specification={'enabled':False,'unit':'independent_run_scenario'}),
            preprocessing=dict(system_design_sha256=fingerprint(d),mode='NON_CLAIM_SMOKE_SYNTHETIC_BOOTSTRAP',environment=json.loads(json.dumps(details))),
            analysis=dict(comparative=False,claim_eligible=False,synthetic_bootstrap=True,real_completed_buckets=1))
        experiment,environment_record=prepare_experiment(repo,repo/'harness/system/fixtures',config,dataset,cohort,{'workload':d['workload']['seed']},
            execution_compatibility_keys=('logical_cpus','memory_bytes'))
        with RunSession(repo/'results/system',experiment,environment_record,repo=repo,dataset_root=repo/'harness/system/fixtures',purpose='smoke',required_outputs=output_specs()) as run:
            for name in LOGS:(run.path/'logs'/f'{name}.log').touch()
            shutil.copyfile(build_log,run.path/'logs/build.log')
            write_json(run.path/'outputs/design.json',d);write_json(run.path/'outputs/resources.json',read_json(repo/'harness/system/resources.json'))
            cluster=d['kubernetes']['cluster']+'-'+uuid.uuid4().hex[:8];kubeconfig=private/'kubeconfig';kube=Kube(commands,kubeconfig,cluster,d)
            processes=[];files=[];created=False;stop=threading.Event();load_thread=None;answer={};start_overall=time.monotonic()
            try:
                existing=commands.run(['kind','get','clusters']).splitlines()
                if cluster in existing:raise ValueError('never_replace_preexisting_cluster')
                created=True
                commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(kubeconfig),'--wait','120s'],log=run.path/'logs/kind.log',timeout=300)
                os.chmod(kubeconfig,0o600)
                api=kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']);guard_local_api(api)
                version=json.loads(kube.call(['version','-o','json']))
                if version['serverVersion']['gitVersion']!=d['kubernetes']['server_version']:raise ValueError('kubernetes_version_mismatch')
                details.update(kubernetes=version,nodes=json.loads(kube.call(['get','nodes','-o','json'])),cluster_name=cluster,api_server=api)
                write_json(run.path/'outputs/kubernetes_environment.json',details)
                commands.run(['kind','load','docker-image',image,'--name',cluster],log=run.path/'logs/kind.log')
                # Pre-load the public pinned image rather than asking containerd for credentials/network.
                commands.run(['kind','load','docker-image',d['kubernetes']['prometheus_local_image'],'--name',cluster],log=run.path/'logs/kind.log')
                kube.call(['apply','-f','harness/system/resources.json'],log=run.path/'logs/kind.log')
                kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],log=run.path/'logs/kind.log',timeout=150)
                app_port,prom_port,profile_port=free_port(),free_port(),free_port()
                def spawn(args,logname):
                    f=(run.path/'logs'/logname).open('a');files.append(f)
                    p=subprocess.Popen(args,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);processes.append(p)
                prefix=['kubectl','--kubeconfig',str(kubeconfig),'--context','kind-'+cluster,'-n',d['kubernetes']['namespace']]
                spawn(prefix+['port-forward','service/application',f'{app_port}:8080','--address','127.0.0.1'],'application_portforward.log')
                spawn(prefix+['port-forward','service/prometheus',f'{prom_port}:9090','--address','127.0.0.1'],'prometheus_portforward.log')
                spawn([sys.executable,'-u','-m','dynapm.system_validation.adapter','--repo',str(repo),'--port',str(profile_port)],'profile_service.log')
                app=f'http://127.0.0.1:{app_port}';prom=f'http://127.0.0.1:{prom_port}';profile=f'http://127.0.0.1:{profile_port}'
                wait_http(app+'/healthz');wait_http(profile+'/healthz');wait_http(prom+'/-/ready')
                b=(int(time.time())//300+1)*300;q=b+300;wait_until(b)
                before=http(profile+'/initialize',dict(anchor_ns=b*10**9,method=d['smoke']['method']))
                write_json(run.path/'outputs/profile_before.json',before)
                duration=300+d['smoke']['post_actuation_seconds'];trace=offered_trace('stable',duration,d,smoke=True)
                write_json(run.path/'outputs/trace.json',trace)
                def load():answer['requests']=run_load(app,trace,b,timeout=d['workload']['timeout_seconds'],concurrency=d['workload']['max_concurrency'],stop_event=stop)
                load_thread=threading.Thread(target=load);load_thread.start();samples=[]
                while time.time()<q-1:
                    sample=http(app+'/telemetry');sample['received_at_ns']=time.time_ns()
                    if abs(sample['sample_time_ns']-sample['received_at_ns'])>d['telemetry']['max_clock_skew_seconds']*10**9:raise ValueError('unacceptable_container_host_clock_skew')
                    samples.append(sample)
                    if time.monotonic()-start_overall>d['smoke']['max_elapsed_seconds']:raise RuntimeError('bounded_smoke_deadline')
                    if len(samples)%6==0:print(json.dumps(dict(stage='collecting_real_bucket',samples=len(samples),seconds_remaining=round(q-time.time(),1))),flush=True)
                    time.sleep(min(d['telemetry']['poll_seconds'],max(0,q-1-time.time())))
                wait_until(q);payload=aggregate_bucket(samples,b*10**9,q*10**9,d)
                after=http(profile+'/observe',payload);write_json(run.path/'outputs/profile_after.json',after)
                if after['real_observations']!=1 or after['accounting']['n_refresh_events']!=1:raise ValueError('smoke_profile_commit_missing')
                start=time.perf_counter();cpu_start=time.process_time();snapshot=http(profile+'/snapshot');recommendation=recommend(snapshot['profile'],d)
                rec_latency=time.perf_counter()-start;rec_cpu=time.process_time()-cpu_start
                write_json(run.path/'outputs/recommendation.json',dict(recommendation=recommendation,wall_seconds=rec_latency,cpu_seconds=rec_cpu))
                initial=kube.pod();initial_id=initial['metadata']['uid'];initial_restarts=initial['status']['containerStatuses'][0]['restartCount']
                if resources_match(initial['spec']['containers'][0]['resources'],recommendation):raise ValueError('smoke_must_demonstrate_real_allocation_change')
                sent=time.time_ns();start=time.perf_counter();patched=json.loads(kube.call(['patch','pod','application','--subresource=resize','--type=strategic','-p',json.dumps(resource_patch(recommendation))],controller=True))
                actual=None;observed=None
                while time.perf_counter()-start<60:
                    actual=kube.pod();observed=http(app+'/telemetry');state=actual['status']['containerStatuses'][0]
                    if actual['metadata']['uid']!=initial_id or state['restartCount']!=initial_restarts:raise ValueError('unexpected_workload_restart_during_resize')
                    if resources_match(state.get('resources'),recommendation) and resources_match(actual['spec']['containers'][0]['resources'],recommendation) and abs(observed['cpu_limit_cores']*1000-recommendation['cpu_millicores'])<1e-6 and observed['memory_limit_bytes']==recommendation['memory_mib']*2**20:break
                    time.sleep(1)
                else:raise RuntimeError('resize_not_confirmed_by_status_and_cgroup')
                actuation_latency=time.perf_counter()-start;confirmed_at_ns=time.time_ns()
                write_json(run.path/'outputs/actuation.json',dict(initial=initial,patch=patched,observed=actual,cgroup=observed,
                    patch_submitted_at_ns=sent,confirmed_at_ns=confirmed_at_ns,latency_seconds=actuation_latency,
                    resource_change_count=1,cpu_churn_millicores=abs(1000-recommendation['cpu_millicores']),memory_churn_mib=abs(512-recommendation['memory_mib']),same_pod_uid=True))
                while time.time()<b+duration:
                    sample=http(app+'/telemetry');sample['received_at_ns']=time.time_ns();samples.append(sample);time.sleep(1)
                load_thread.join(timeout=d['workload']['timeout_seconds']+10)
                if load_thread.is_alive() or not answer.get('requests'):raise RuntimeError('generator_did_not_complete')
                requests=answer['requests']
                if not successful_post_enforcement(requests,confirmed_at_ns):raise ValueError('no_successful_request_after_actual_resize')
                up=http(prom+'/api/v1/query?query='+quote('up{job="dynapm-application"}'))
                if up.get('status')!='success' or not any(v['value'][1]=='1' for v in up['data']['result']):raise ValueError('prometheus_target_not_scraped')
                write_json(run.path/'outputs/prometheus_up.json',up)
                (run.path/'outputs/application_metrics.prom').write_text(text_http(app+'/metrics'))
                profile_metrics=text_http(profile+'/metrics');(run.path/'outputs/profile_metrics.prom').write_text(profile_metrics)
                if 'dynapm_profile_process_resident_memory_bytes' not in profile_metrics:raise ValueError('profile_process_rss_unavailable')
                write_json(run.path/'outputs/requests.json',requests);write_json(run.path/'outputs/telemetry.json',dict(bucket=payload,samples=samples))
                write_json(run.path/'outputs/metrics.json',dict(workload=summarize_requests(requests,b,b+duration,d['slo']['latency_seconds']),
                    resources=resource_metrics(samples),recommendation_latency_seconds=rec_latency,actuation_latency_seconds=actuation_latency,
                    maintenance_accounting=after['accounting'],maintenance_step_wall_seconds=after['maintenance_step_wall_seconds'],
                    maintenance_step_cpu_seconds=after['maintenance_step_cpu_seconds']))
                write_json(run.path/'outputs/smoke_diagnostics.json',dict(status='PLUMBING_VERIFIED_NOT_SYSTEM_EVIDENCE',
                    methods_executed=1,method=d['smoke']['method'],scenarios_executed=1,scenario='stable',synthetic_bootstrap_slots=288,
                    real_completed_buckets=1,real_bucket_seconds=300,real_request_count=len(requests),
                    no_comparative_trials=True,no_claim_eligible_results=True,wall_seconds=time.monotonic()-start_overall))
            finally:
                stop.set()
                if load_thread:load_thread.join(timeout=10)
                for name in ['application','prometheus']:
                    if kubeconfig.exists():
                        try:(run.path/'logs'/f'{name}.log').write_text(kube.call(['logs',name]))
                        except Exception:pass
                for process in processes:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                for f in files:f.close()
                if created:commands.run(['kind','delete','cluster','--name',cluster],log=run.path/'logs/kind.log',timeout=120)
            if frozen_design(repo)!=d:raise ValueError('system_design_changed_during_smoke')
            run.complete();return run.path
