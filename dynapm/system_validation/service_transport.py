"""Versioned direct-Service transport: durable generator Pod and sealed file export."""
import json,os,shutil,subprocess,time,uuid
from pathlib import Path
from dynapm.core.provenance import file_sha256,fingerprint,canonical_json
from dynapm.system_validation import service_generator
from dynapm.system_validation.bounded_v8 import offers as frozen_offers
from dynapm.system_validation.calibration_runner import require_isolated_engine
from dynapm.system_validation.smoke import Commands,Kube,guard_local_api
from dynapm.system_validation.bounded_v8_runtime import NodeObserver,pinned_images
from dynapm.system_validation.reservation_protocol import reservation_resources

SCHEMA='v8-direct-service-transport-v1'
ARTIFACT='51aad0e364d6f4774f8c51ab2cb7544eac87d7ebdb36e492eba648c014dffd2b'

def campaign_generator_config(plan,run_id,service_url):
    config=dict(scope='AMENDED_V8_PRIMARY',run_id=run_id,plan=plan,warmup_seconds=1800,lead_seconds=10,service_url=service_url)
    if [event for phase,event in service_generator.offers(config)]!=list(frozen_offers(plan)):
        raise ValueError('frozen_offer_schedule_mismatch')
    return config

def generator_resources(design,cluster,config,source_path):
    ns=design['kubernetes']['namespace'];name='request-generator';node=cluster+'-control-plane';path='/var/local/dynapm-v8c5/'+config['run_id']
    return dict(apiVersion='v1',kind='List',items=[
        dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=name,namespace=ns),data={'generator.py':Path(source_path).read_text(),'plan.json':canonical_json(config)}),
        dict(apiVersion='v1',kind='Pod',metadata=dict(name=name,namespace=ns,labels={'scope':'diagnostic' if config['scope']=='DIAGNOSTIC_NON_CLAIM' else 'amended-v8'}),spec=dict(
            restartPolicy='Never',nodeName=node,automountServiceAccountToken=False,terminationGracePeriodSeconds=15,
            securityContext=dict(runAsUser=1000,runAsGroup=1000,runAsNonRoot=True),
            containers=[dict(name='generator',image=design['kubernetes']['application_image'],imagePullPolicy='Never',
                command=['python','/generator/generator.py','/generator/plan.json','/records'],
                env=[dict(name='POD_UID',valueFrom=dict(fieldRef=dict(fieldPath='metadata.uid')))],
                resources=dict(requests=dict(cpu='1000m',memory='512Mi'),limits=dict(cpu='1000m',memory='512Mi')),
                volumeMounts=[dict(name='code',mountPath='/generator',readOnly=True),dict(name='records',mountPath='/records')])],
            volumes=[dict(name='code',configMap=dict(name=name)),dict(name='records',hostPath=dict(path=path,type='Directory'))]))]),node,path


def validate_download(root,config):
    root=Path(root);done=json.loads((root/'DONE.json').read_bytes());start=json.loads((root/'START.json').read_bytes())
    if done['status']!='COMPLETE' or done['run_id']!=config['run_id'] or done['config_sha256']!=fingerprint(config):raise ValueError('generator_completion_or_config_mismatch')
    if done['start_sha256']!=file_sha256(root/'START.json') or done['requests_sha256']!=file_sha256(root/'requests.jsonl'):raise ValueError('generator_file_hash_mismatch')
    records=[json.loads(s) for s in (root/'requests.jsonl').read_text().splitlines()]
    actual=sorted(records,key=lambda x:x['request_id']);expected=list(service_generator.offers(config))
    if len(actual)!=done['records'] or len(actual)!=len(expected) or len(actual)!=done['expected_records']:raise ValueError('generator_record_count_mismatch')
    for row,(phase,offer) in zip(actual,expected,strict=True):
        if row['offer']!=offer or row['request_id']!=offer['request_id'] or row['intended_phase']!=phase or row['retries']!=0:raise ValueError('generator_offer_or_retry_mismatch')
        if row['scheduled_monotonic_ns']!=start['origin_monotonic_ns']+offer['offset_ns']:raise ValueError('generator_clock_binding_mismatch')
        if row['completed_monotonic_ns']-start['origin_monotonic_ns']!=row['completed_offset_ns'] or row['latency_ns']!=row['completed_offset_ns']-offer['offset_ns'] or row['latency_ns']<0:raise ValueError('generator_outcome_clock_mismatch')
        if not isinstance(row.get('completed_wall_ns'),int) or row.get('exception','MISSING')=='MISSING':raise ValueError('missing_request_measurement_fields')
        if row['sent_offset_ns'] is not None and not offer['offset_ns']<=row['sent_offset_ns']<=row['completed_offset_ns']:raise ValueError('invalid_request_program_order')
        if row['success']!=(row['outcome']=='success') or (row['sent_offset_ns'] is None)!=(row['outcome']=='overload_drop'):raise ValueError('generator_outcome_mismatch')
    return records,start,done


def export_records(commands,node,node_path,destination):
    """Idempotent sealed file-copy, independent of the application Service. Never reruns load."""
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    for name in ('DONE.json','START.json','requests.jsonl'):
        final=dest/name
        if final.exists():continue
        if shutil.disk_usage(dest).free<22*2**30:raise ValueError('storage_reserve_export_buffer')
        partial=dest/(name+'.partial')
        with partial.open('wb') as out:
            result=subprocess.run(['docker','exec',node,'cat',node_path+'/'+name],cwd=commands.cwd,env=commands.env,stdout=out,stderr=subprocess.PIPE,timeout=60)
            out.flush();os.fsync(out.fileno())
        if result.returncode:raise RuntimeError('sealed_export_failed_preserve_node:'+result.stderr.decode(errors='replace'))
        os.replace(partial,final)


def start_stack(repo,design,run,cluster,environment):
    """Same pinned stack without creating any port-forward process. Caller owns retention."""
    repo=Path(repo);run=Path(run);out=run/'outputs';out.mkdir(parents=True,exist_ok=True)
    endpoint=os.environ.get('DOCKER_HOST') or subprocess.check_output(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    if not endpoint.startswith('unix:///'):raise ValueError('local_docker_required')
    local=run/'control';local.mkdir();(local/'docker').mkdir();(local/'docker/config.json').write_text('{"auths":{}}')
    config=local/'kubeconfig';env=dict(os.environ,DOCKER_HOST=endpoint,DOCKER_CONFIG=str(local/'docker'),KUBECONFIG=str(config),PATH=str(repo/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH'])
    commands=Commands(env,repo);require_isolated_engine(commands)
    for binary in ('kind','kubectl'):
        path=shutil.which(binary,path=env['PATH'])
        if not path or file_sha256(path)!=environment['cli_binary_sha256'][binary]:raise ValueError('pinned_cli_mismatch')
    images=[design['kubernetes'][k] for k in ('application_image','prometheus_local_image','node_image')]
    ids=pinned_images(commands,images,environment['image_ids']);(out/'environment.json').write_text(canonical_json(dict(images=ids,cli=environment['cli_binary_sha256'])))
    log=out/'kind.log'
    commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml','--kubeconfig',str(config),'--wait','120s'],log=log,timeout=300)
    kube=Kube(commands,config,cluster,design);guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
    if json.loads(kube.call(['version','-o','json']))['serverVersion']['gitVersion']!=design['kubernetes']['server_version']:raise ValueError('pinned_kubernetes_mismatch')
    for node in (cluster+'-control-plane',cluster+'-worker'):
        if commands.run(['docker','inspect','--format','{{.Image}}',node]).strip()!=ids[images[2]]:raise ValueError('node_image_mismatch')
        if 'MemoryQoS: true' in commands.run(['docker','exec',node,'cat','/var/lib/kubelet/config.yaml']):raise ValueError('memory_qos_changed')
    for image in images[:2]:commands.run(['kind','load','docker-image',image,'--name',cluster],log=log,timeout=120)
    resources=out/'resources.json';resources.write_text(canonical_json(reservation_resources(design)));kube.call(['apply','-f',str(resources)],log=log)
    kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],log=log,timeout=150)
    return commands,kube,NodeObserver(commands,kube.pod())


def endpoint_metrics(plan,records):
    """Frozen arithmetic, explicitly disaggregated Service-client failure attribution."""
    from dynapm.system_validation.bounded_v8_metrics import request_metrics
    result=request_metrics(plan,records)
    for name,(lo,hi) in {'primary':(0,plan['measurement_seconds']),'transition':(0,300),'followup':(300,1800)}.items():
        if name not in result:continue
        cohort=[r for r in records if lo*10**9<=r['offer']['offset_ns']<hi*10**9]
        result[name].update(failed_attempts=sum(not r['success'] for r in cohort),
            application_response_errors=sum(r['outcome'] in ('http_error','application_error') for r in cohort),
            service_transport_errors=sum(r['outcome']=='transport_error' for r in cohort),
            connection_deadlines=sum(r.get('failure_layer')=='CONNECTION_DEADLINE' for r in cohort),
            response_deadlines=sum(r.get('failure_layer')=='RESPONSE_DEADLINE_CAUSE_UNRESOLVED' for r in cohort))
    return result


def require_new_campaign_rows(rows,amendment_sha256,implementation_commit):
    """Old COMPLETE records can never be admitted to the restarted paired analysis."""
    from dynapm.system_validation.bounded_v8 import cells
    if len(rows)!=18:raise ValueError('new_complete_18_required')
    for row,cell in zip(rows,cells(),strict=True):
        if (row.get('scope')!='AMENDED_V8_PRIMARY' or row.get('campaign_generation')!='v8-direct-service-v1'
            or row.get('amendment_sha256')!=amendment_sha256 or row.get('implementation_commit')!=implementation_commit
            or row.get('cell')!=cell or row.get('status')!='COMPLETE'):
            raise ValueError('old_new_mixing_or_incomplete_campaign_forbidden')
    return True
