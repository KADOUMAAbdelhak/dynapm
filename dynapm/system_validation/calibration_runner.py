"""Managed neutral-method calibration with a real 24h bootstrap and no comparisons."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json,os,resource,shutil,signal,subprocess,sys,tempfile,time,uuid
import numpy as np

from dynapm.core.provenance import (SourceProvenance,DataConfig,ModelConfig,PolicyConfig,StatisticsConfig,
 ExperimentConfigProvenance,CohortManifest,CohortEntity,prepare_experiment,read_json,file_sha256,fingerprint,utc_now)
from dynapm.core.run_store import RunSession,OutputSpec,write_json,check_cache
from dynapm.data.manifests import build_dataset_manifest
from dynapm.system_validation.design import resource_manifests
from dynapm.system_validation.estimation_design import frozen_spec,calibration_plan
from dynapm.system_validation.calibration_workers import process_stats,write_line
from dynapm.system_validation.clock_observations import ObservationClock,receive_observation
from dynapm.system_validation.host_power import ManagedPowerGuard
from dynapm.system_validation.host_endurance import require_endurance
from dynapm.system_validation.trial_preparation import measured_bootstrap
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.consumer import summarize_requests,resource_metrics
from dynapm.system_validation.system_estimation import allocation_integrals
from dynapm.system_validation.smoke import Commands,Kube,http,text_http,free_port,guard_local_endpoint,guard_local_api,environment,resize_preflight,wait_http

JSONS=('plan','resources','runtime_environment','resize_preflight','status','bootstrap_summary',
 'profile_initial','profile_final','generator_status','controller_status','summary','attribution','diagnostics')
LINES=('telemetry','bootstrap_samples','bucket_diagnostics','requests','controller_commands','decisions','profiles','overhead','host_diagnostics','neutral_timing')
LOGS=('build','kind','generator','profile','controller','application','prometheus','app_portforward','prom_portforward')


def output_specs():
    return [OutputSpec('outputs/'+x+'.json','calibration-'+x) for x in JSONS]+[
        OutputSpec('outputs/'+x+'.jsonl','calibration-'+x) for x in LINES]+[
        OutputSpec('logs/'+x+'.log','calibration-'+x) for x in LOGS]+[
        OutputSpec('outputs/clock_rejections.jsonl','rejected-nonscientific-clock-evidence'),
        OutputSpec('outputs/clock_observations.jsonl','accepted-clock-diagnostics'),
        OutputSpec('outputs/clock_evidence_manifest.json','clock-evidence-integrity'),
        OutputSpec('outputs/power_guard.json','owned-power-assertion-lifecycle'),
        OutputSpec('outputs/host_continuity.jsonl','independent-host-continuity'),
        OutputSpec('outputs/host_continuity_summary.json','host-continuity-summary'),
        OutputSpec('outputs/host_continuity_failure.json','host-continuity-rejection')]


def local_host_diagnostics():
    def capture(args):
        try:
            p=subprocess.run(args,capture_output=True,text=True,timeout=10)
            return dict(available=p.returncode==0,stdout=p.stdout,stderr=p.stderr)
        except (OSError,subprocess.TimeoutExpired) as exc:return dict(available=False,error=type(exc).__name__)
    return dict(wall_ns=time.time_ns(),process=process_stats(),load_average=list(os.getloadavg()),
        power=capture(['pmset','-g','batt']),thermal_status=capture(['pmset','-g','therm']),
        processes=capture(['ps','-axo','pid,pcpu,pmem,comm']),
        context='research workstation, reservation not asserted; not a practical-benefit threshold')


def require_isolated_engine(commands,cluster=None):
    names=commands.run(['docker','ps','--format','{{.Names}}']).splitlines()
    allowed={cluster+'-control-plane',cluster+'-worker'} if cluster else set()
    external=[name for name in names if name and name not in allowed]
    if external:raise ValueError('external_containers_preserved_isolated_engine_required:'+','.join(external))
    return names


def _clean(repo):
    if subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip():raise ValueError('clean_committed_source_required')


def _json_lines(path):
    with Path(path).open() as file:
        for line in file:
            if line.strip():yield json.loads(line)


def verify_request_stream(path,expected):
    ids=[r['request_id'] for r in _json_lines(path)]
    if len(ids)!=expected or len(set(ids))!=expected or (expected and (min(ids)!=0 or max(ids)!=expected-1)):
        raise ValueError('incomplete_or_duplicate_request_stream')
    return expected


def _prom_process(prom):
    text=text_http(prom+'/metrics');wanted={}
    for line in text.splitlines():
        if not line.startswith('#') and line.split(' ',1)[0] in ('process_cpu_seconds_total','process_resident_memory_bytes'):
            key,val=line.split()[:2];wanted[key]=float(val)
    if len(wanted)!=2:raise ValueError('prometheus_process_overhead_unavailable')
    return wanted


def summarize(root,plan):
    """One independent run; request observations never become inference replicates."""
    start=plan['measurement_start_seconds'];end=plan['measurement_end_seconds']
    requests=[];completed_in_window=0
    for r in _json_lines(root/'outputs/requests.jsonl'):
        if start<=r['scheduled_at']<end:requests.append(r)
        if r['success'] and start<=r['completed_at']<end:completed_in_window+=1
    telemetry=[r for r in _json_lines(root/'outputs/telemetry.jsonl') if start*1e9<=r['sample_time_ns']<=end*1e9]
    workload=summarize_requests(requests,start,end,plan['design']['slo']['latency_seconds'])
    workload['scope']='CALIBRATION_ONE_NEUTRAL_METHOD_NO_POLICY_COMPARISON'
    workload['successful_completed_in_window']=completed_in_window;workload['successful_throughput_rps']=completed_in_window/(end-start)
    rm=resource_metrics(telemetry)
    controller=read_json(root/'outputs/controller_status.json')
    attribution=read_json(root/'outputs/attribution.json')
    latest=list(_json_lines(root/'outputs/overhead.jsonl'))
    decisions=list(_json_lines(root/'outputs/decisions.jsonl'))
    initial=read_json(root/'outputs/resize_preflight.json')['unchanged_actual_resources']
    intervals=[(a['sample_time_ns']/1e9,b['sample_time_ns']/1e9) for a,b in zip(telemetry,telemetry[1:])
        if a['instance_id']==b['instance_id'] and b['cpu_seconds']>=a['cpu_seconds']]
    allocation=allocation_integrals(start,end,initial,decisions,intervals=intervals)
    row=dict(scenario=plan['scenario'],block=plan['block'],method='pw_6h',
        **workload,**{k:rm[k] for k in ('mean_cpu_requested_cores','mean_memory_requested_bytes',
            'cpu_utilization_efficiency','memory_utilization_efficiency')},
        resources=rm,allocation=allocation,controller=controller['counters'],practical_benefit='NOT_DEFINED',
        independent_unit='one run/scenario',policy_comparison=False)
    row.update({k:allocation[k] for k in ('mean_cpu_requested_cores','mean_memory_requested_bytes','mean_cpu_allocated_cores','mean_memory_allocated_bytes')})
    for resource_name,numerator,denominator in [('cpu',rm['mean_cpu_used_cores'],allocation['covered_cpu_requested_core_seconds']),
        ('memory',rm['mean_memory_used_bytes'],allocation['covered_memory_requested_byte_seconds'])]:
        row[resource_name+'_utilization_efficiency']=numerator*rm['valid_seconds']/denominator if numerator is not None and denominator else None
    row['resource_observed_seconds']=rm['valid_seconds']
    row['application_handler_cpu_seconds']={}
    for field in ('work_handler_cpu_seconds_total','telemetry_handler_cpu_seconds_total','health_handler_cpu_seconds_total'):
        deltas=[b[field]-a[field] for a,b in zip(telemetry,telemetry[1:]) if a['instance_id']==b['instance_id'] and b[field]>=a[field]]
        row['application_handler_cpu_seconds'][field]=sum(deltas)
    row['application_attribution_note']='handler counters cover observed same-instance intervals; app container CPU also includes server/thread overhead; resets and uncovered intervals retained'
    bootstrap=read_json(root/'outputs/profile_initial.json')['profile']['dynamic']
    observations=[r for r in decisions if r['kind']=='POD_OBSERVATION']
    restarts=lambda r:r['status']['containerStatuses'][0].get('restartCount',0)
    prior=[r for r in observations if r['wall_ns']<=start*1e9]
    measured_obs=[r for r in observations if start*1e9<=r['wall_ns']<=end*1e9]
    row['application_restarts_observed']=max([restarts(r) for r in measured_obs],default=restarts(prior[-1]) if prior else 0)-(restarts(prior[-1]) if prior else 0)
    terminations=[r['status']['containerStatuses'][0].get('lastState',{}).get('terminated',{}) for r in measured_obs]
    row['observed_oom_terminations_lower_bound']=len({r.get('finishedAt') for r in terminations if r.get('reason')=='OOMKilled' and r.get('finishedAt')})
    row['pod_observation_count']=len(measured_obs)
    row['accounting']=read_json(root/'outputs/profile_final.json')['accounting']
    row['n_refresh_events']=row['accounting']['n_refresh_events']
    profile_final=read_json(root/'outputs/profile_final.json')
    row['bootstrap_thresholds']=read_json(root/'outputs/profile_initial.json')['bootstrap_thresholds']
    row['mean_cpu_used_cores']=rm['mean_cpu_used_cores'];row['mean_memory_used_bytes']=rm['mean_memory_used_bytes']
    row['maintenance_step_wall_seconds_total']=sum(profile_final['maintenance_step_wall_seconds'])
    row['maintenance_step_thread_cpu_seconds_total']=sum(attribution['thread_step_cpu_seconds'])
    measured_overhead=[r for r in latest if r['phase']=='MEASUREMENT']
    for component in ('profile','controller','generator'):
        rss=[r[component]['rss_bytes'] for r in measured_overhead if r[component].get('rss_bytes') is not None]
        row[component+'_rss_p95_bytes']=float(np.quantile(rss,.95)) if rss else None
    prom_rss=[r['prometheus']['process_resident_memory_bytes'] for r in measured_overhead]
    row['prometheus_rss_p95_bytes']=float(np.quantile(prom_rss,.95)) if prom_rss else None
    row['bootstrap_cpu_p95']=bootstrap['predicted_cpu_p95_next_24h'];row['bootstrap_memory_p95']=bootstrap['predicted_mem_p95_next_24h']
    starts=[r for r in _json_lines(root/'outputs/overhead.jsonl') if r['phase']=='measurement_start_before_initialization']
    before=starts[0] if starts else None
    attribution=read_json(root/'outputs/attribution.json')
    row['maintenance_process_cpu_seconds']=attribution['process']['cpu_seconds']-before['profile']['cpu_seconds'] if before else None
    row['controller_process_cpu_seconds']=controller['process']['cpu_seconds']-before['controller']['cpu_seconds'] if before else None
    latest=list(_json_lines(root/'outputs/overhead.jsonl'))
    last=latest[-1] if latest else None
    row['prometheus_process_cpu_seconds']=last['prometheus']['process_cpu_seconds_total']-before['prometheus']['process_cpu_seconds_total'] if before and last else None
    row['overhead_scope']='separate processes; profile/controller deltas include finalization, Prometheus last sampled boundary; raw timestamps retained'
    for name,key,kind in [('recommendation','compute_wall_seconds','RECOMMENDATION'),('actuation','actuation_latency_seconds','ENFORCED')]:
        values=[r[key] for r in decisions if r['kind']==kind]
        row[name+'_latency_seconds']=dict(count=len(values),median=float(np.median(values)) if values else None,
            p95=float(np.quantile(values,.95)) if values else None)
        row[name+'_latency_p95_seconds']=row[name+'_latency_seconds']['p95']
    return row


def run_trial(repo,trial,*,plumbing_only=False,host_endurance_run=None,bootstrap_only=False):
    repo=Path(repo).resolve();spec=frozen_spec(repo);_clean(repo)
    if not plumbing_only:require_endurance(repo,host_endurance_run)
    if plumbing_only and bootstrap_only:raise ValueError('exclusive_collection_modes')
    if trial['method']!='pw_6h' or trial['scenario'] not in spec['engineering_plan']['calibration_scenarios']:
        raise ValueError('neutral_pw6_stable_periodic_only')
    if shutil.disk_usage(repo).free<20*2**30:raise ValueError('20GiB_reserve_required')
    source=SourceProvenance.capture(repo);d=deepcopy(spec)
    if bootstrap_only:
        trial=dict(trial,minimum_wall_seconds=d['engineering_plan']['cooldown_seconds']+d['engineering_plan']['warmup_seconds']+86400)
    endpoint=os.environ.get('DOCKER_HOST') or subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    guard_local_endpoint(endpoint)
    inputs=repo/'results/system_calibration/inputs'/fingerprint({'design':fingerprint(spec),'scenario':trial['scenario'],'plumbing':plumbing_only,'bootstrap_only':bootstrap_only})/trial['scenario']
    inputs.mkdir(parents=True,exist_ok=True)
    descriptor=dict(design=spec,scenario=trial['scenario'],method='pw_6h',mode='plumbing' if plumbing_only else 'bootstrap-only' if bootstrap_only else 'calibration')
    target=inputs/'input.json'
    if target.exists() and read_json(target)!=descriptor:raise ValueError('immutable_input_descriptor_mismatch')
    if not target.exists():write_json(target,descriptor)
    dataset=build_dataset_manifest(inputs.parent,dataset_id='system-calibration-v2',source_name='frozen generator/controller design, no corpus outcomes',
        trace_names=(trial['scenario'],),schema_identity='system-calibration-input-v2')
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'one-neutral-application-v2',{'minimum_observations':200,'expected_nominal_slots':288 if bootstrap_only else 864,'role':'fixed live application; actual samples generated during run'},
        (CohortEntity(trial['scenario'],'application',True,None,0,temporal_characterization={'count_role':'no preobserved samples; planned grid '+str(288 if bootstrap_only else 864)}),),utc_now())
    with tempfile.TemporaryDirectory(prefix='dynapm-calibration-private-') as temporary:
        private=Path(temporary);private.chmod(0o700);dc=private/'docker';dc.mkdir();(dc/'config.json').write_text('{"auths":{}}')
        env={**os.environ,'DOCKER_HOST':endpoint,'DOCKER_CONFIG':str(dc),'KUBECONFIG':str(private/'kubeconfig'),
            'PATH':str(repo/d['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH']}
        commands=Commands(env,repo);require_isolated_engine(commands);details=environment(commands,d)
        if details['kubectl_client']['gitVersion']!=d['kubernetes']['kubectl_version'] or not details['kind'].startswith('kind '+d['kubernetes']['kind_version']+' '):raise ValueError('pinned_cli_version_required')
        host=local_host_diagnostics()
        if sys.platform=='darwin' and (not host['power']['available'] or 'AC Power' not in host['power']['stdout']):raise ValueError('mains_power_required')
        build_log=private/'build.log'
        # Minimal isolated build context avoids changing or bypassing V7A's frozen Docker ignore rules.
        build_context=private/'application-build'
        for rel in ('dynapm/system_validation/application.py','dynapm/system_validation/application_instrumented.py','harness/system/Calibration.Dockerfile'):
            dest=build_context/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/rel,dest)
        commands.run(['docker','build','-f',str(build_context/'harness/system/Calibration.Dockerfile'),'-t',d['kubernetes']['application_image'],str(build_context)],log=build_log)
        commands.run(['docker','build','-f','harness/system/Prometheus.Dockerfile','-t',d['kubernetes']['prometheus_local_image'],'.'],log=build_log)
        details['image_ids']={image:json.loads(commands.run(['docker','image','inspect',image]))[0]['Id'] for image in (d['kubernetes']['application_image'],d['kubernetes']['prometheus_local_image'])}
        cfg=ExperimentConfigProvenance(DataConfig(dataset.dataset_id,bootstrap_fraction=1.0 if bootstrap_only else 1/3,minimum_observations=200),
            ModelConfig(family='unused-observation-only'),(PolicyConfig('pw_6h',periodic_interval_hours=6,observation_window_hours=24),),
            StatisticsConfig(bootstrap_repetitions=0,bootstrap_seed=20251022,test_specification={'enabled':False,'unit':'independent run/scenario'}),
            preprocessing=dict(design_sha256=fingerprint(spec),execution_environment=deepcopy(details),
                mode='PARTIAL_REAL_COLLECTION_SMOKE' if plumbing_only else 'MEASURED_BOOTSTRAP_ONLY_V1' if bootstrap_only else 'NEUTRAL_CALIBRATION_REAL_BOOTSTRAP'),
            analysis=dict(comparative=False,practical_benefit='NOT_DEFINED',scenario=trial['scenario']))
        exp,env_record=prepare_experiment(repo,inputs.parent,cfg,dataset,cohort,{'workload':d['workload']['seed']},
            execution_compatibility_keys=tuple(d['hardware']['compatibility_keys']))
        with RunSession(repo/'results/system_calibration',exp,env_record,repo=repo,dataset_root=inputs.parent,
                purpose='smoke' if plumbing_only else 'pilot',required_outputs=output_specs()) as run:
            for n in JSONS:write_json(run.path/'outputs'/f'{n}.json',dict(status='PENDING'))
            for n in LINES:(run.path/'outputs'/f'{n}.jsonl').touch()
            for n in LOGS:(run.path/'logs'/f'{n}.log').touch()
            clock=ObservationClock(run.path,dict(run_id=run.manifest.run_id,
                experiment_fingerprint=exp.fingerprint,source_commit=source.commit))
            with ManagedPowerGuard(run.path,dict(run_id=run.manifest.run_id,
                    experiment_fingerprint=exp.fingerprint,source_commit=source.commit)) as power:
                shutil.copyfile(build_log,run.path/'logs/build.log')
                cluster=d['kubernetes']['cluster']+'-'+uuid.uuid4().hex[:8];config=private/'kubeconfig'
                kube=Kube(commands,config,cluster,d);children=[];handles=[];created=False
                clock.check_host(time.time_ns(),time.monotonic_ns())
                last_heartbeat=0;last_host=0;locals_generator=[None,float('inf')]
                def status(stage,**extra):
                    value=dict(stage=stage,source_commit=source.commit,run_id=run.manifest.run_id,pid=os.getpid(),
                        scenario=trial['scenario'],method='pw_6h',block=trial['block'],free_disk_bytes=shutil.disk_usage(repo).free,
                        wall_time=utc_now(),measurement_complete=(stage=='FINISHED' and not plumbing_only and not bootstrap_only),practical_benefit='NOT_DEFINED',**extra)
                    write_json(run.path/'outputs/status.json',value)
                    print(json.dumps(value),flush=True)
                def check():
                    if shutil.disk_usage(repo).free<20*2**30:raise ValueError('disk_reserve_exhausted')
                    power.raise_if_failed()
                    clock.check_host(time.time_ns(),time.monotonic_ns())
                    for p in children:
                        if p.poll() is not None:
                            if p is locals_generator[0] and p.returncode==0 and time.time()>=locals_generator[1]-1:continue
                            raise RuntimeError('worker_exited:'+str(p.args[0]))
                def spawn(args,log):
                    f=(run.path/'logs'/log).open('a');handles.append(f)
                    p=subprocess.Popen(args,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT);children.append(p);return p
                try:
                    cooldown=0 if plumbing_only else d['engineering_plan']['cooldown_seconds']
                    status('COOLDOWN',seconds_remaining=cooldown)
                    deadline=time.time()+cooldown
                    while time.time()<deadline:time.sleep(min(30,max(0,deadline-time.time())));check()
                    require_isolated_engine(commands)
                    if cluster in commands.run(['kind','get','clusters']).splitlines():raise ValueError('preexisting_cluster_preserved')
                    created=True
                    commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(config),'--wait','120s'],log=run.path/'logs/kind.log',timeout=300)
                    config.chmod(0o600);guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
                    version=json.loads(kube.call(['version','-o','json']))
                    if version['serverVersion']['gitVersion']!=d['kubernetes']['server_version']:raise ValueError('server_version_mismatch')
                    details.update(kubernetes=version,nodes=json.loads(kube.call(['get','nodes','-o','json'])),host_context=host)
                    write_json(run.path/'outputs/runtime_environment.json',details)
                    for image in (d['kubernetes']['application_image'],d['kubernetes']['prometheus_local_image']):commands.run(['kind','load','docker-image',image,'--name',cluster],log=run.path/'logs/kind.log')
                    manifests=resource_manifests(d)
                    for item in manifests['items']:
                        if item['kind']=='Pod':item['metadata']['labels']={'app':'dynapm-workload' if item['metadata']['name']=='application' else 'dynapm-prometheus'}
                    write_json(run.path/'outputs/resources.json',manifests)
                    kube.call(['apply','-f',str(run.path/'outputs/resources.json')],log=run.path/'logs/kind.log')
                    kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],log=run.path/'logs/kind.log',timeout=150)
                    write_json(run.path/'outputs/resize_preflight.json',resize_preflight(kube,d))
                    app_port,prom_port,profile_port,gen_port,ctrl_port=[free_port() for _ in range(5)]
                    prefix=['kubectl','--kubeconfig',str(config),'--context','kind-'+cluster,'-n',d['kubernetes']['namespace']]
                    spawn(prefix+['port-forward','service/application',f'{app_port}:8080','--address','127.0.0.1'],'app_portforward.log')
                    spawn(prefix+['port-forward','service/prometheus',f'{prom_port}:9090','--address','127.0.0.1'],'prom_portforward.log')
                    app=f'http://127.0.0.1:{app_port}';prom=f'http://127.0.0.1:{prom_port}'
                    wait_http(app+'/healthz');wait_http(prom+'/-/ready')
                    load_start=(int(time.time())//300+1)*300
                    boot_start=load_start+(0 if plumbing_only else d['engineering_plan']['warmup_seconds'])
                    measured=boot_start+d['bootstrap']['duration_seconds'];end=measured+(0 if bootstrap_only else d['engineering_plan']['measurement_seconds'])
                    plan=dict(**trial,design=d,cluster=cluster,app_url=app,load_start_seconds=load_start,
                        bootstrap_start_seconds=boot_start,measurement_start_seconds=measured,measurement_end_seconds=end,
                        bootstrap_source_pod_uid=kube.pod()['metadata']['uid'],
                        profile_url=f'http://127.0.0.1:{profile_port}',generator_stats_url=f'http://127.0.0.1:{gen_port}',
                        controller_stats_url=f'http://127.0.0.1:{ctrl_port}',plumbing_only=plumbing_only,bootstrap_only=bootstrap_only)
                    if plumbing_only:plan['measurement_end_seconds']=load_start+300
                    plan_file=run.path/'outputs/plan.json';write_json(plan_file,plan)
                    worker=[sys.executable,'-u','-m','dynapm.system_validation.calibration_workers']
                    spawn(worker+['profile','--plan',str(plan_file),'--root',str(run.path),'--port',str(profile_port)],'profile.log')
                    generator=spawn(worker+['generator','--plan',str(plan_file),'--root',str(run.path),'--port',str(gen_port)],'generator.log')
                    locals_generator[:]=[generator,plan['measurement_end_seconds']]
                    ctrl=spawn(worker+['controller','--plan',str(plan_file),'--root',str(run.path),'--port',str(ctrl_port),'--kubeconfig',str(config)],'controller.log')
                    wait_http(plan['profile_url']+'/healthz');wait_http(plan['generator_stats_url']+'/stats');wait_http(plan['controller_stats_url']+'/stats')
                    next_q=load_start+300;samples=[];initialized=False;accepted=0;missing=0
                    with (run.path/'outputs/telemetry.jsonl').open('a',buffering=1) as raw, (run.path/'outputs/bootstrap_samples.jsonl').open('a',buffering=1) as boot, (run.path/'outputs/bucket_diagnostics.jsonl').open('a',buffering=1) as bd, (run.path/'outputs/overhead.jsonl').open('a',buffering=1) as overhead, (run.path/'outputs/profiles.jsonl').open('a',buffering=1) as profiles, (run.path/'outputs/controller_commands.jsonl').open('a',buffering=1) as requests, (run.path/'outputs/host_diagnostics.jsonl').open('a',buffering=1) as hosts:
                        while time.time()<plan['measurement_end_seconds']+1:
                            check()
                            now=time.time();stage='WAITING' if now<load_start else 'WARMUP' if now<boot_start else 'BOOTSTRAP' if now<measured else 'MEASUREMENT'
                            if now>=load_start:
                                try:
                                    observation=receive_observation(app+'/telemetry')
                                except (OSError,RuntimeError) as exc:write_line(bd,dict(kind='MISSING_TELEMETRY',wall_ns=time.time_ns(),error=str(exc)))
                                else:
                                    # Evidence/persistence failures abort; never downgrade to missing data.
                                    sample=clock.accept(observation,raw)
                                    if sample['sample_time_ns']<=int(next_q*1e9):samples.append(sample)
                            if now>=next_q:
                                payload=None
                                try:
                                    payload=aggregate_bucket(samples,int((next_q-300)*1e9),int(next_q*1e9),d)
                                except ValueError as exc:missing+=1;write_line(bd,dict(kind='INVALID_BUCKET',end_ns=int(next_q*1e9),error=str(exc)))
                                if boot_start<next_q<=measured and payload:
                                    write_line(boot,dict(role='MEASURED_CGROUP_SAMPLES',end_ns=int(next_q*1e9),samples=samples));accepted+=1
                                if next_q==measured and kube.pod()['metadata']['uid']!=plan['bootstrap_source_pod_uid']:
                                    raise ValueError('bootstrap_source_pod_replaced')
                                if next_q==measured and bootstrap_only:
                                    boot.flush()
                                    entries=list(_json_lines(run.path/'outputs/bootstrap_samples.jsonl'))
                                    measured_history=measured_bootstrap(entries,int(boot_start*1e9),int(measured*1e9),time.time_ns(),d)
                                    write_json(run.path/'outputs/bootstrap_summary.json',dict(accepted_slots=measured_history.accepted_slots,
                                        missing_slots=measured_history.missing_slots,evidence_sha256=measured_history.evidence_sha256,
                                        real_duration_seconds=86400,source_pod_uid=plan['bootstrap_source_pod_uid']))
                                elif next_q==measured:
                                    before=http(plan['profile_url']+'/healthz');write_line(overhead,dict(phase='measurement_start_before_initialization',profile=before['process'],controller=http(plan['controller_stats_url']+'/stats'),generator=http(plan['generator_stats_url']+'/stats'),prometheus=_prom_process(prom),collector=process_stats()))
                                    initial=http(plan['profile_url']+'/initialize',{});initialized=True
                                    write_json(run.path/'outputs/profile_initial.json',initial)
                                    write_json(run.path/'outputs/bootstrap_summary.json',dict(accepted_slots=initial['accepted_bootstrap_slots'],missing_slots=initial['missing_bootstrap_slots'],evidence_sha256=initial['bootstrap_evidence_sha256'],real_duration_seconds=86400,source_pod_uid=plan['bootstrap_source_pod_uid']))
                                elif initialized and payload and next_q<end:http(plan['profile_url']+'/observe',payload)
                                if initialized:
                                    started=time.time_ns();snapshot=http(plan['profile_url']+'/snapshot')
                                    write_line(profiles,dict(nominal_time_ns=int(next_q*1e9),snapshot=snapshot))
                                    if next_q<end:write_line(requests,dict(nominal_time_ns=int(next_q*1e9),snapshot_read_started_ns=started,snapshot=snapshot))
                                samples=[];next_q+=300
                            if time.monotonic()-last_host>=1800:
                                _clean(repo)
                                if SourceProvenance.capture(repo).commit!=source.commit:raise ValueError('source_commit_changed_during_calibration')
                                h=local_host_diagnostics();h['docker_containers']=require_isolated_engine(commands,cluster);write_line(hosts,h);last_host=time.monotonic()
                                if sys.platform=='darwin' and (not h['power']['available'] or 'AC Power' not in h['power']['stdout']):raise ValueError('mains_power_lost')
                            if time.monotonic()-last_heartbeat>=30:
                                status(stage,accepted_bootstrap_slots=accepted,invalid_buckets=missing,
                                    bootstrap_end_seconds=measured,measurement_end_seconds=plan['measurement_end_seconds'],overall_percent=max(0,min(100,(now-load_start)/(plan['measurement_end_seconds']-load_start)*100)))
                                write_line(overhead,dict(phase=stage,profile=http(plan['profile_url']+'/healthz')['process'],controller=http(plan['controller_stats_url']+'/stats'),generator=http(plan['generator_stats_url']+'/stats'),prometheus=_prom_process(prom),collector=process_stats()))
                                last_heartbeat=time.monotonic()
                            if plumbing_only and time.time()>=load_start+300:break
                            time.sleep(min(5,max(.05,next_q-time.time())))
                        write_line(requests,dict(stop=True))
                    # Expected exits are checked explicitly; no worker failure is silently accepted.
                    generator.wait(timeout=d['workload']['timeout_seconds']+20);ctrl.wait(timeout=20)
                    if generator.returncode or ctrl.returncode:raise RuntimeError('calibration_worker_failed')
                    children.remove(generator);children.remove(ctrl)
                    verify_request_stream(run.path/'outputs/requests.jsonl',read_json(run.path/'outputs/generator_status.json')['offered'])
                    if plumbing_only:
                        for name in ('bootstrap_summary','profile_initial','profile_final','attribution'):
                            write_json(run.path/'outputs'/f'{name}.json',dict(status='NOT_INITIALIZED_PARTIAL_REAL_COLLECTION_ONLY'))
                        write_json(run.path/'outputs/summary.json',dict(scope='REAL_COLLECTION_SMOKE_NOT_CALIBRATION',real_completed_buckets=accepted,profile_initializations=0,comparisons=0))
                    elif bootstrap_only:
                        if read_json(run.path/'outputs/bootstrap_summary.json').get('real_duration_seconds')!=86400:
                            raise ValueError('bootstrap_collection_incomplete')
                        for name in ('profile_initial','profile_final','attribution'):
                            write_json(run.path/'outputs'/f'{name}.json',dict(status='NOT_INITIALIZED_BOOTSTRAP_ACQUISITION_ONLY'))
                        write_json(run.path/'outputs/summary.json',dict(scope='MEASURED_BOOTSTRAP_ONLY_NO_POLICY_OUTCOMES',
                            comparisons=0,profile_initializations=0,measurement_seconds=0))
                    else:
                        write_json(run.path/'outputs/profile_final.json',http(plan['profile_url']+'/snapshot'))
                        write_json(run.path/'outputs/attribution.json',http(plan['profile_url']+'/stats'))
                        write_json(run.path/'outputs/summary.json',summarize(run.path,plan))
                    write_json(run.path/'outputs/diagnostics.json',dict(operationally_meaningful_benefit='NOT_DEFINED',
                        method='pw_6h',comparisons_run=0,synthetic_bootstrap_used=False,real_bootstrap_complete=initialized or bootstrap_only,
                        host_reserved=False,neutral_trial_measurement_complete=not plumbing_only and not bootstrap_only,source_commit=source.commit))
                    status('FINISHED',calibration_result='PARTIAL_SMOKE' if plumbing_only else 'COMPLETE_MEASURED_BOOTSTRAP_ONLY' if bootstrap_only else 'COMPLETE_NEUTRAL_TRIAL')
                finally:
                    clock.finalize()
                    for name in ('application','prometheus'):
                        if config.exists():
                            try:(run.path/'logs'/f'{name}.log').write_text(kube.call(['logs',name]))
                            except Exception:pass
                    for p in children:
                        p.terminate()
                        try:p.wait(timeout=10)
                        except subprocess.TimeoutExpired:p.kill();p.wait()
                    for f in handles:f.close()
                    if created:commands.run(['kind','delete','cluster','--name',cluster],log=run.path/'logs/kind.log',timeout=120)
            run.complete()
            return run.path


def campaign(repo,*,maximum_trials=6,host_endurance_run=None):
    """At most the six predeclared neutral trials; stop on first failed attempt."""
    from dynapm.system_validation.system_estimation import calibration_noise
    repo=Path(repo).resolve();d=frozen_spec(repo);_clean(repo)
    require_endurance(repo,host_endurance_run)
    if type(maximum_trials) is not int or not 1<=maximum_trials<=6:raise ValueError('neutral_campaign_cap_1_to_6')
    root=repo/'results/system_calibration';root.mkdir(parents=True,exist_ok=True)
    active=root/'ACTIVE.json'
    fd=os.open(active,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    campaign_id=uuid.uuid4().hex;record=root/'campaigns'/f'{campaign_id}.json'
    state=dict(schema_version='neutral-calibration-campaign-v2',campaign_id=campaign_id,pid=os.getpid(),
        source_commit=SourceProvenance.capture(repo).commit,design_sha256=fingerprint(d),status='RUNNING',
        completed_runs=[],attempted_runs=0,maximum_trials=maximum_trials,comparisons=0,
        practical_benefit='NOT_DEFINED',calibration_replicates_target=3,scenario_count=2,
        precision_target=None,frozen_comparative_N=None)
    with os.fdopen(fd,'w') as file:json.dump(state,file)
    write_json(record,state)
    try:
        for trial in calibration_plan(repo)[:maximum_trials]:
            state['attempted_runs']+=1;state['current_trial']=trial;write_json(record,state)
            path=run_trial(repo,trial,host_endurance_run=host_endurance_run)
            manifest=read_json(path/'manifest.json')
            state['completed_runs'].append(dict(run_path=str(path.relative_to(repo)),run_id=manifest['run_id'],
                experiment_fingerprint=manifest['experiment_fingerprint'],output_manifest_sha256=manifest['output_manifest_sha256']))
            rows=[read_json(repo/r['run_path']/'outputs/summary.json') for r in state['completed_runs']]
            state['noise']=calibration_noise(rows);write_json(record,state)
        state['status']='CALIBRATION_COMPLETE_NO_COMPARATIVE_N_FROZEN' if maximum_trials==6 else 'BOUNDED_CALIBRATION_SUBSET_COMPLETE'
        return record
    except BaseException as exc:
        state['status']='FAILED';state['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        state['ended_at']=utc_now();write_json(record,state);active.unlink(missing_ok=True)
