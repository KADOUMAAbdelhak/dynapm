"""Bounded real cluster/host clock observation only; no workload or profile state."""
from pathlib import Path
from dataclasses import replace
import json,os,shutil,subprocess,sys,tempfile,time,uuid

from dynapm.core.provenance import (SourceProvenance,CohortManifest,CohortEntity,
    prepare_experiment,fingerprint,utc_now,canonical_json)
from dynapm.core.run_store import RunSession,OutputSpec,write_json
from dynapm.data.manifests import build_dataset_manifest
from dynapm.system_validation.host_endurance import observation_config
from dynapm.system_validation.host_power import ManagedPowerGuard
from dynapm.system_validation.clock_observations import ObservationClock,receive_observation,validate_clock_evidence,SCHEMA
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.design import resource_manifests
from dynapm.system_validation.calibration_runner import require_isolated_engine
from dynapm.system_validation.smoke import Commands,Kube,environment,guard_local_endpoint,guard_local_api,free_port,wait_http

SECONDS=900
POLL_SECONDS=1


def probe_config(dataset_id,descriptor):
    config=observation_config(dataset_id,descriptor)
    return replace(config,data=replace(config.data,sampling_cadence_seconds=POLL_SECONDS,
        evaluation_cadence_seconds=POLL_SECONDS))


def probe(repo):
    repo=Path(repo).resolve();source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean_committed_source_required')
    d=frozen_spec(repo)
    if shutil.disk_usage(repo).free<20*2**30:raise ValueError('disk_reserve')
    endpoint=subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    guard_local_endpoint(endpoint)
    descriptor=dict(schema_version='cluster-host-clock-probe-v1',clock_schema=SCHEMA,
        duration_seconds=SECONDS,poll_seconds=POLL_SECONDS,workloads=0,bootstrap_slots=0,
        profile_initializations=0,comparisons=0,clock_tolerance_tuning=False,
        system_design_sha256=fingerprint(d),seeds={'clock_probe':0})
    inputs=repo/'results/clock_probe/inputs'/fingerprint(descriptor);inputs.mkdir(parents=True,exist_ok=True)
    write_json(inputs/'probe/input.json',descriptor)
    dataset=build_dataset_manifest(inputs,dataset_id='cluster-host-clock-probe-v1',source_name='bounded timing protocol',trace_names=('probe',),schema_identity='clock-probe-input-v1')
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'one-idle-source-v1',{},(CohortEntity('probe','application',True,None,0),),utc_now())
    with tempfile.TemporaryDirectory(prefix='dynapm-clock-probe-') as tmp:
        private=Path(tmp);private.chmod(0o700);dc=private/'docker';dc.mkdir();(dc/'config.json').write_text('{"auths":{}}')
        config=private/'kubeconfig'
        env={**os.environ,'DOCKER_HOST':endpoint,'DOCKER_CONFIG':str(dc),'KUBECONFIG':str(config),'PATH':str(repo/d['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH']}
        commands=Commands(env,repo);require_isolated_engine(commands);details=environment(commands,d)
        build=private/'build.log';image=d['kubernetes']['application_image']
        commands.run(['docker','build','-f','harness/system/Calibration.Dockerfile','-t',image,'.'],log=build)
        details['image_id']=json.loads(commands.run(['docker','image','inspect',image]))[0]['Id']
        cfg=probe_config(dataset.dataset_id,{**descriptor,'execution_environment':details})
        exp,record=prepare_experiment(repo,inputs,cfg,dataset,cohort,descriptor['seeds'],execution_compatibility_keys=tuple(d['hardware']['compatibility_keys']))
        names=['summary.json','environment.json','status.json','samples.jsonl','clock_observations.jsonl','clock_rejections.jsonl','clock_evidence_manifest.json','power_guard.json','host_continuity.jsonl','host_continuity_summary.json','host_continuity_failure.json']
        specs=[OutputSpec('outputs/'+n,'clock-probe-'+n) for n in names]+[OutputSpec('logs/'+n+'.log','clock-probe-'+n) for n in ('build','kind','forward')]
        with RunSession(repo/'results/clock_probe',exp,record,repo=repo,dataset_root=inputs,purpose='smoke',required_outputs=specs) as run:
            context=dict(run_id=run.manifest.run_id,experiment_fingerprint=exp.fingerprint,source_commit=source.commit)
            clock=ObservationClock(run.path,context);cluster=d['kubernetes']['cluster']+'-clock-'+uuid.uuid4().hex[:8];kube=Kube(commands,config,cluster,d)
            created=False;forward=None;handle=None
            shutil.copyfile(build,run.path/'logs/build.log');(run.path/'logs/forward.log').touch()
            with ManagedPowerGuard(run.path,context) as power:
                try:
                    created=True
                    commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(config),'--wait','120s'],log=run.path/'logs/kind.log',timeout=300)
                    config.chmod(0o600);guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
                    version=json.loads(kube.call(['version','-o','json']))
                    if version['serverVersion']['gitVersion']!=d['kubernetes']['server_version']:raise ValueError('server_version_mismatch')
                    commands.run(['kind','load','docker-image',image,'--name',cluster],log=run.path/'logs/kind.log')
                    objects=resource_manifests(d);objects['items']=[x for x in objects['items'] if x['kind']=='Namespace' or x.get('metadata',{}).get('name')=='application']
                    for x in objects['items']:
                        if x['kind']=='Pod':x['metadata']['labels']={'app':'dynapm-workload'}
                    write_json(private/'resources.json',objects);kube.call(['apply','-f',str(private/'resources.json')])
                    kube.call(['wait','--for=condition=Ready','pod/application','--timeout=120s'],timeout=150)
                    initial=json.loads(kube.call(['get','pod','application','-o','json']));port=free_port();handle=(run.path/'logs/forward.log').open('a')
                    forward=subprocess.Popen(['kubectl','--kubeconfig',str(config),'--context','kind-'+cluster,'-n',d['kubernetes']['namespace'],'port-forward','pod/application',f'{port}:8080','--address','127.0.0.1'],cwd=repo,env=env,stdout=handle,stderr=subprocess.STDOUT)
                    url=f'http://127.0.0.1:{port}';wait_http(url+'/healthz')
                    details.update(kubernetes=version,pod=initial,nodes=json.loads(kube.call(['get','nodes','-o','json'])),
                        linux_node_boot_id=commands.run(['docker','exec',cluster+'-worker','cat','/proc/sys/kernel/random/boot_id']).strip())
                    write_json(run.path/'outputs/environment.json',details)
                    start=time.monotonic();values=[];deltas=[];host=[];last_report=-30
                    with (run.path/'outputs/samples.jsonl').open('w') as raw:
                        while True:
                            power.raise_if_failed();clock.check_host(time.time_ns(),time.monotonic_ns())
                            if forward.poll() is not None:raise ValueError('portforward_exited')
                            before=time.monotonic();s=clock.accept(receive_observation(url+'/clock-observation'),raw)
                            values.append(s['received_at_ns']-s['sample_time_ns']);deltas.append(s['cluster_received_at_ns']-s['sample_time_ns'])
                            host.append(s['received_at_ns']);elapsed=time.monotonic()-start
                            if elapsed-last_report>=30:
                                status={**context,'stage':'CLOCK_PROBE','elapsed_seconds':elapsed,'observations':len(values),'cross_domain_difference_ns_range':[min(values),max(values)]}
                                write_json(run.path/'outputs/status.json',status);print(canonical_json(status),flush=True);last_report=elapsed
                                if SourceProvenance.capture(repo).identity()!=source.identity():raise ValueError('source_changed')
                            if elapsed>=SECONDS:break
                            time.sleep(max(0,POLL_SECONDS-(time.monotonic()-before)))
                    final=json.loads(kube.call(['get','pod','application','-o','json']))
                    if final['metadata']['uid']!=initial['metadata']['uid'] or final['status']['containerStatuses'][0]['restartCount']!=0:raise ValueError('probe_source_restarted')
                    if len(values)<800:raise ValueError('insufficient_clock_probe_observations')
                    clock.finalize();validate_clock_evidence(run.path,context)
                    write_json(run.path/'outputs/summary.json',dict(**descriptor,elapsed_seconds=time.monotonic()-start,
                        observations=len(values),source_clock_domain=s['cluster_clock_domain'],linux_node_boot_id=details['linux_node_boot_id'],cross_domain_difference_role='NON_CAUSAL_DIAGNOSTIC_ONLY_NOT_SYNCHRONIZATION_ESTIMATE',
                        host_minus_source_ns_min=min(values),host_minus_source_ns_max=max(values),host_minus_source_first_ns=values[0],host_minus_source_last_ns=values[-1],
                        cross_domain_difference_change_ns=values[-1]-values[0],cluster_age_ns_min=min(deltas),cluster_age_ns_max=max(deltas),
                        same_domain_causal_violations=0,host_admission_valid=True,bootstrap_artifact_created=False))
                finally:
                    clock.finalize()
                    if forward is not None:
                        forward.terminate()
                        try:forward.wait(timeout=10)
                        except subprocess.TimeoutExpired:forward.kill();forward.wait()
                    if handle:handle.close()
                    if created:commands.run(['kind','delete','cluster','--name',cluster],log=run.path/'logs/kind.log',timeout=120)
            run.complete();print(canonical_json(dict(status='COMPLETE',run_path=str(run.path),output_manifest_sha256=run.manifest.output_manifest_sha256)),flush=True)
            return run.path
