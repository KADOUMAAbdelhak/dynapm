"""Explicit non-claim direct-Service transport qualification; cannot launch primary V8."""
import argparse,base64,collections,json,os,shutil,subprocess,threading,time,uuid
from pathlib import Path
from dynapm.core.provenance import canonical_json,file_sha256,fingerprint,read_json,utc_now
from dynapm.system_validation import service_generator as generator
from dynapm.system_validation.service_transport import ARTIFACT,SCHEMA,start_stack,generator_resources,export_records,validate_download
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.v8_host_identity import UUIDPowerGuard
from dynapm.system_validation.bounded_v8_runtime import actuate
from dynapm.system_validation.reservation_protocol import Target
from dynapm.system_validation.clock_observations import ObservationClock,validate_clock_evidence

SCOPE='DIAGNOSTIC_NON_CLAIM'

def qualify(repo,root,spec,expected_sha):
    repo=Path(repo);root=Path(root)
    if file_sha256(spec)!=expected_sha:raise ValueError('amendment_sha_mismatch')
    amendment=read_json(spec);commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    if commit!=amendment['implementation_commit'] or subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip():raise ValueError('clean_exact_implementation_required')
    if shutil.disk_usage(repo).free<25.25*2**30:raise ValueError('qualification_storage_start_gate')
    design=frozen_spec(repo);environment=read_json(repo/'results/shared_bootstrap/artifacts'/ARTIFACT/'generation/parent/manifest.json')['experiment']['config']['preprocessing']['execution_environment']
    outcomes=[]
    for condition in amendment['qualification_conditions']:
        run=root/condition['name'];out=run/'outputs';out.mkdir(parents=True,exist_ok=False)
        ident=uuid.uuid4().hex;cluster=design['kubernetes']['cluster']+'-v8c5-'+ident[:10]
        config=dict(scope=SCOPE,run_id=ident,plan=dict(mode='qualification',seed=2026110502,warmup_phase='high12',segments=condition['segments'],measurement_seconds=condition['seconds']),warmup_seconds=0,lead_seconds=10,
                    service_url='http://application.'+design['kubernetes']['namespace']+'.svc.cluster.local:8080',amendment_sha256=expected_sha,implementation_commit=commit)
        context=dict(run_id=ident,source_commit=commit,frozen_scientific_source=amendment['scientific_source'],experiment_fingerprint=fingerprint(config))
        (run/'intent.json').write_text(canonical_json(dict(scope=SCOPE,config=config,context=context,condition=condition,cluster=cluster,amendment_sha256=expected_sha))+'\n')
        log=(out/'observations.jsonl').open('x');lock=threading.Lock();commands=kube=node=None;collector=None;stop=threading.Event();collected=[];safe_cleanup=False;error=None;result=None
        def emit(row):
            with lock:log.write(canonical_json(dict(recorded_at=utc_now(),host_monotonic_ns=time.monotonic_ns(),**row))+'\n');log.flush()
        try:
            with UUIDPowerGuard(run,context) as guard:
                commands,kube,node=start_stack(repo,design,run,cluster,environment)
                with (out/'enforcement.jsonl').open('x') as enforcement:
                    act=actuate(kube,node,kube.pod()['metadata']['uid'],Target(condition['cpu'],condition['memory']),enforcement,lambda x:emit(dict(event='ACTUATION',data=x)),guard)
                manifest,gen_node,gen_path=generator_resources(design,cluster,config,repo/'dynapm/system_validation/service_generator.py')
                commands.run(['docker','exec',gen_node,'mkdir','-p',gen_path]);commands.run(['docker','exec',gen_node,'chmod','0777',gen_path])
                (run/'recovery.json').write_text(canonical_json(dict(cluster=cluster,generator_node=gen_node,node_path=gen_path,kubeconfig=str(kube.config),config=config))+'\n')
                resource=out/'generator-resources.json';resource.write_text(canonical_json(manifest));kube.call(['apply','-f',str(resource)],timeout=30)
                clock=ObservationClock(run,context)
                def collect():
                    with (out/'telemetry.jsonl').open('x') as sink:
                        while not stop.is_set():
                            try:clock.accept(node.capture(),sink)
                            except BaseException as exc:collected.append(repr(exc));emit(dict(event='RESOURCE_COLLECTION_ERROR',error=repr(exc)));break
                            stop.wait(5)
                    clock.finalize()
                collector=threading.Thread(target=collect,daemon=True);collector.start()
                deadline=time.monotonic()+condition['seconds']+180;first_seen=None;pause_done=False;last_pods=None
                while True:
                    guard.raise_if_failed()
                    if shutil.disk_usage(repo).free<22*2**30:raise ValueError('storage_buffer_preserve_generator_node')
                    if time.monotonic()>deadline:raise ValueError('generator_completion_watchdog_censored')
                    try:
                        pods=json.loads(kube.call(['get','pods','-o','json'],timeout=5));last_pods=pods
                        gen=next((p for p in pods['items'] if p['metadata']['name']=='request-generator'),None)
                        emit(dict(event='PODS',data=pods))
                        for label,args in [('SERVICE',['get','service','application','-o','json']),('ENDPOINTS',['get','endpoints','application','-o','json']),('NODES',['get','nodes','-o','json']),('EVENTS',['get','events','-o','json'])]:
                            try:emit(dict(event=label,data=json.loads(kube.call(args,timeout=5))))
                            except Exception as exc:emit(dict(event=label,error=repr(exc)))
                        if gen and gen['status'].get('phase')=='Running' and first_seen is None:first_seen=time.monotonic()
                        if gen and gen['status'].get('phase') in ('Succeeded','Failed'):
                            emit(dict(event='GENERATOR_TERMINAL',pod=gen));break
                    except Exception as exc:emit(dict(event='API_OBSERVATION_ERROR',error=repr(exc)))
                    # Intentional observer pause demonstrates workload results do not depend on host polling.
                    if condition['name']=='neutral' and first_seen and not pause_done and time.monotonic()-first_seen>120:
                        emit(dict(event='HOST_RESULT_OBSERVER_PAUSE_BEGIN',seconds=15));time.sleep(15);emit(dict(event='HOST_RESULT_OBSERVER_PAUSE_END'));pause_done=True
                    time.sleep(5)
                export_records(commands,gen_node,gen_path,out/'generator')
                records,start,done=validate_download(out/'generator',config)
                service=json.loads(kube.call(['get','service','application','-o','json']))
                if service['spec']['clusterIP'] not in start['resolved_addresses']:raise ValueError('service_dns_identity_mismatch')
                emit(dict(event='SERVICE_DNS_VERIFIED',cluster_ip=service['spec']['clusterIP'],resolved=start['resolved_addresses']))
                status=next(x for x in gen['status']['containerStatuses'] if x['name']=='generator')
                if status['restartCount']!=0 or status['state'].get('terminated',{}).get('exitCode')!=0:raise ValueError('generator_lifecycle_failure')
                if (done['completed_monotonic_ns']-start['origin_monotonic_ns'])/1e9<condition['seconds']:raise ValueError('qualification_physical_horizon_incomplete')
                if collected:raise ValueError('resource_collection_failed')
                result=dict(scope=SCOPE,status='PASS',config=config,generator_start=start,generator_done=done,expected=len(list(generator.offers(config))),records=len(records),outcomes=dict(collections.Counter(x['outcome'] for x in records)),failure_layers=dict(collections.Counter(str(x.get('failure_layer')) for x in records)),actuation=act,generator_exit_code=0,generator_restart_count=0,host_pause_performed=pause_done)
                safe_cleanup=True
        except BaseException as exc:error=repr(exc);emit(dict(event='QUALIFICATION_FAILURE',error=error))
        finally:
            stop.set()
            if collector:collector.join(timeout=15)
            log.close()
            if safe_cleanup and commands:
                try:commands.run(['kind','delete','cluster','--name',cluster],log=out/'kind.log',timeout=120)
                except Exception as exc:error=repr(exc)
            else:
                (run/'PRESERVED_FOR_RECOVERY').write_text('No automatic cluster deletion: generator/node files may be authoritative.\n')
            if result is None or error:result=dict(scope=SCOPE,status='BLOCKED',error=error,cluster_preserved=not safe_cleanup)
            if result['status']=='PASS':validate_clock_evidence(run,context)
            result.update(files={str(p.relative_to(run)):file_sha256(p) for p in sorted(run.rglob('*')) if p.is_file()})
            (run/'terminal.json').write_text(canonical_json(result)+'\n');(run/'SEALED').write_text(canonical_json(dict(terminal_sha256=file_sha256(run/'terminal.json')))+'\n')
            print(canonical_json(dict(condition=condition['name'],status=result['status'],outcomes=result.get('outcomes'),error=error)),flush=True);outcomes.append(result['status'])
        if result['status']!='PASS':break
    return outcomes

def main():
    p=argparse.ArgumentParser();p.add_argument('--amendment',required=True);p.add_argument('--sha256',required=True);p.add_argument('--root',required=True);p.add_argument('--authorize-diagnostic',action='store_true');a=p.parse_args()
    if not a.authorize_diagnostic:raise SystemExit('explicit diagnostic authorization required')
    result=qualify(Path.cwd(),a.root,a.amendment,a.sha256)
    if result!=['PASS']*3:raise SystemExit(1)
if __name__=='__main__':main()
