"""Physical transport for the bounded study. Imported and tested without starting kind."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
from urllib.request import urlopen
import uuid

from dynapm.core.provenance import canonical_json, file_sha256
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.bounded_v8 import NS, SLOT, WARMUP, REFERENCE, accepted_samples, inventory, new_profile, offers, rows
from dynapm.system_validation.bounded_v8_metrics import request_metrics, resource_endpoints
from dynapm.system_validation.calibration_runner import require_isolated_engine
from dynapm.system_validation.clock_observations import ObservationClock
from dynapm.system_validation.outcome_taxonomy import control_enforcement
from dynapm.system_validation.reservation_protocol import reservation_patch, reservation_recommendation, reservation_resources, resources_match
from dynapm.system_validation.smoke import Commands, Kube, free_port, guard_local_api, guard_local_endpoint, wait_http
from dynapm.system_validation.v8_campaign import publish_record

# Source and receipt clocks are sampled inside one Linux process namespace.
# stdout is the exact cluster envelope, not reconstructed from host times.
NODE_SAMPLE = r'''
set -eu
mono() { awk '{printf "%.0f", $1*1000000000}' /proc/uptime; }
wall() { date +%s%N; }
start_wall=$(wall); start_mono=$(mono)
boot=$(cat /proc/sys/kernel/random/boot_id); ns=$(readlink /proc/self/ns/time); host=$(hostname)
domain=$(printf '{"boot_id":"%s","time_namespace":"%s","hostname":"%s"}' "$boot" "$ns" "$host")
cpu=$(awk '$1=="usage_usec" {printf "%.6f",$2/1000000}' "$1/cpu.stat")
quota=$(cat "$1/cpu.max"); cores=$(printf '%s\n' "$quota" | awk '{printf "%.9f",$1/$2}')
current=$(cat "$1/memory.current"); cap=$(cat "$1/memory.max"); swap=$(cat "$1/memory.swap.current")
inactive=$(awk '$1=="inactive_file" {print $2}' "$1/memory.stat")
workset=$((current-inactive)); if [ "$workset" -lt 0 ]; then workset=0; fi
oom=$(awk '$1=="oom_kill" {print $2}' "$1/memory.events")
sw=$(wall); sm=$(mono)
payload=$(printf '{"instance_id":"%s","sample_time_ns":%s,"source_clock":{"domain":%s,"wall_ns":%s,"monotonic_ns":%s},"cpu_seconds":%s,"cpu_limit_cores":%s,"memory_limit_bytes":%s,"memory_current_bytes":%s,"memory_working_set_bytes":%s,"memory_swap_bytes":%s,"oom_kills":%s}' "$2" "$sw" "$domain" "$sw" "$sm" "$cpu" "$cores" "$cap" "$current" "$workset" "$swap" "$oom")
rw=$(wall); rm=$(mono)
encoded=$(printf '%s' "$payload" | base64 -w0)
digest=$(printf '%s' "$payload" | sha256sum | cut -d' ' -f1)
printf '{"schema_version":"cluster-clock-envelope-v1","raw_payload_base64":"%s","raw_payload_sha256":"%s","cluster_clock_domain":%s,"cluster_request_wall_ns":%s,"cluster_request_monotonic_ns":%s,"cluster_received_at_ns":%s,"cluster_receipt_monotonic_ns":%s}' "$encoded" "$digest" "$domain" "$start_wall" "$start_mono" "$rw" "$rm"
'''


def workload_container(pod):
    return next(c for c in pod['status']['containerStatuses'] if c['name']=='workload')


class OperationalStop(RuntimeError):
    pass


class NodeObserver:
    def __init__(self, commands, pod):
        self.commands = commands
        self.node = pod['spec']['nodeName']
        self.container = workload_container(pod)['containerID'].split('://',1)[1]
        if not re.fullmatch('[a-f0-9]{64}', self.container):
            raise ValueError('invalid_container_identity')
        details = json.loads(commands.run(['docker','exec',self.node,'crictl','inspect',self.container],timeout=10))
        pid = str(details['info']['pid'])
        if not pid.isdigit():
            raise ValueError('invalid_container_pid')
        group = commands.run(['docker','exec',self.node,'cat',f'/proc/{pid}/cgroup'],timeout=10).strip()
        if not re.fullmatch(r'0::/[\w.\-/:]+',group) or '..' in Path(group[3:]).parts:
            raise ValueError('invalid_cgroup_binding')
        self.group = '/sys/fs/cgroup'+group[3:]

    def capture(self):
        wall,mono = time.time_ns(),time.monotonic_ns()
        raw = self.commands.run(['docker','exec',self.node,'sh','-c',NODE_SAMPLE,'observer',self.group,self.container],timeout=2).encode()
        receipt,receipt_mono = time.time_ns(),time.monotonic_ns()
        return dict(raw_payload_base64=base64.b64encode(raw).decode(),raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
                    request_wall_ns=wall,request_monotonic_ns=mono,received_at_ns=receipt,receipt_monotonic_ns=receipt_mono)

    def enforcement(self):
        start = time.monotonic_ns()
        keys = ('cpu.max','memory.max','memory.min','memory.low','memory.swap.current')
        values = self.commands.run(['docker','exec',self.node,'sh','-ec',
            'dir=$1; shift; for name; do cat "$dir/$name"; done','observer',self.group,*keys],timeout=5).splitlines()
        return dict(start_monotonic_ns=start,end_monotonic_ns=time.monotonic_ns(),
                    binding=dict(container_id=self.container,node=self.node),values=dict(zip(keys,values,strict=True)))


def append(handle, value):
    handle.write(canonical_json(value)+'\n')
    handle.flush()


def confirm(kube, observer, uid, target, generation, ack_ns, evidence):
    pod = kube.pod()
    received = time.monotonic_ns()
    node = observer.enforcement()
    result = control_enforcement(pod,node,target,pod_uid=uid,generation=generation,ack_ns=ack_ns,
                                 pod_received_ns=received,now_ns=time.monotonic_ns())
    if any(node['values'][k]!='0' for k in ('memory.min','memory.low','memory.swap.current')):
        raise ValueError('memory_qos_or_swap_changed')
    append(evidence,dict(pod=pod,node=node,target=vars(target),check=result,receipt_monotonic_ns=received))
    return result['complete']


def actuate(kube, observer, uid, target, evidence, emit, guard):
    begin = time.monotonic_ns()
    pod = kube.pod()
    if pod['metadata']['uid'] != uid:
        raise ValueError('pod_uid_changed')
    current = next(c['resources'] for c in pod['spec']['containers'] if c['name']=='workload')
    generation = pod['metadata']['generation']
    status = 'NO_OP'
    append(evidence,dict(event='INTENDED',target=vars(target),monotonic_ns=begin))
    if not resources_match(current,target):
        payload = reservation_patch(target,pod)
        append(evidence,dict(event='PATCH_SUBMITTED',payload=payload,monotonic_ns=time.monotonic_ns()))
        try:
            ack = json.loads(kube.call(['patch','pod','application','--subresource=resize','--type=strategic',
                                        '-p',canonical_json(payload),'-o','json'],controller=True,timeout=60))
        except subprocess.TimeoutExpired as exc:
            raise OperationalStop('patch_acceptance_unknown_right_censored') from exc
        except RuntimeError as exc:
            # Only an explicit server rejection is a known operational failure.
            if 'Error from server' in str(exc) and not any(x in str(exc) for x in ('(Unauthorized)','(Forbidden)','(NotFound)')):
                raise OperationalStop('api_rejected_resize') from exc
            raise
        ack_ns = time.monotonic_ns()
        if ack['metadata']['uid']!=uid or not resources_match(next(c['resources'] for c in ack['spec']['containers'] if c['name']=='workload'),target):
            raise ValueError('resize_ack_target_mismatch')
        generation = ack['metadata']['generation']
        append(evidence,dict(event='ACCEPTED',monotonic_ns=ack_ns,pod=ack))
        status = 'ENFORCED'
    else:
        ack_ns = begin
    while time.monotonic_ns()-begin<60*NS:
        guard.raise_if_failed()
        if confirm(kube,observer,uid,target,generation,ack_ns,evidence):
            enforced = time.monotonic_ns()
            if enforced-begin>=60*NS:
                break
            row = dict(status=status,**vars(target),ack_monotonic_ns=ack_ns,enforced_monotonic_ns=enforced,
                       actuation_latency_seconds=(enforced-begin)/NS if status=='ENFORCED' else None)
            emit(row)
            return row
        time.sleep(.2)
    raise OperationalStop('resize_watchdog_right_censored')


def stream_requests(url, plan, origin, stop, sink):
    lock = threading.Lock()
    slots = threading.BoundedSemaphore(32)
    def record(row):
        with lock:append(sink,row)
    def send(event):
        sent = time.monotonic_ns()-origin
        outcome = 'success'
        status = None
        try:
            query = f"iterations={event['iterations']}&memory_mib={event['memory_mib']}&seed={event['seed']}"
            with urlopen(url+'/work?'+query,timeout=5) as response:
                raw = response.read()
                completed = time.monotonic_ns()-origin
                status = response.status
                body = json.loads(raw)
                if status!=200 or not isinstance(body,dict) or body.get('ok') is not True or body.get('iterations')!=event['iterations'] or body.get('memory_mib')!=event['memory_mib']:
                    outcome = 'application_error'
        except urllib.error.HTTPError as exc:
            completed = time.monotonic_ns()-origin
            outcome, status = 'http_error', exc.code
            exc.close()
        except TimeoutError:
            completed = time.monotonic_ns()-origin
            outcome = 'request_timeout'
        except (OSError, ValueError) as exc:
            completed = time.monotonic_ns()-origin
            outcome = 'request_timeout' if isinstance(getattr(exc,'reason',None),TimeoutError) else 'application_error'
        finally:
            slots.release()
        record(dict(request_id=event['request_id'],offer=event,sent_offset_ns=sent,
                    completed_offset_ns=completed,success=outcome=='success',outcome=outcome,http_status=status))
    pending = set()
    with ThreadPoolExecutor(max_workers=32) as pool:
        for event in offers(plan):
            due = origin+event['offset_ns']
            while time.monotonic_ns()<due:
                if stop.wait(max(0,(due-time.monotonic_ns())/NS)):
                    break
            if stop.is_set():
                break
            finished = {f for f in pending if f.done()}
            for future in finished:future.result()
            pending -= finished
            if slots.acquire(blocking=False):
                pending.add(pool.submit(send,event))
            else:
                record(dict(request_id=event['request_id'],offer=event,sent_offset_ns=None,
                            completed_offset_ns=time.monotonic_ns()-origin,success=False,
                            outcome='overload_drop',http_status=None))
        for future in pending:future.result()


def boot_identity():
    return subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()


def pinned_images(commands, images, expected_images):
    observed = {}
    for image in images:
        details = json.loads(commands.run(['docker','image','inspect',image],timeout=10))[0]
        if image in expected_images:
            if details['Id'] != expected_images[image]:
                raise ValueError('qualified_image_mismatch')
        else:
            name, digest = image.split('@',1)
            reference = name.rsplit(':',1)[0]+'@'+digest
            if reference not in {item.removeprefix('docker.io/') for item in details.get('RepoDigests',[])}:
                raise ValueError('pinned_kind_node_digest_missing')
        observed[image] = details['Id']
    return observed


@contextmanager
def local_kind(repo, design, run, cluster, expected_environment):
    endpoint = os.environ.get('DOCKER_HOST') or subprocess.check_output(
        ['docker','context','inspect','--format','{{.Endpoints.docker.Host}}'],text=True).strip()
    guard_local_endpoint(endpoint)
    with tempfile.TemporaryDirectory(prefix='bounded-v8-') as tmp:
        config = Path(tmp)/'kubeconfig'
        docker = Path(tmp)/'docker';docker.mkdir()
        (docker/'config.json').write_text('{"auths":{}}')
        env = dict(os.environ,DOCKER_HOST=endpoint,DOCKER_CONFIG=str(docker),KUBECONFIG=str(config),
                   PATH=str(repo/design['kubernetes']['tools_directory'])+os.pathsep+os.environ['PATH'])
        commands = Commands(env,repo)
        kube = Kube(commands,config,cluster,design)
        require_isolated_engine(commands)
        if cluster in commands.run(['kind','get','clusters']).splitlines():
            raise ValueError('preexisting_cluster_preserved')
        images = [design['kubernetes'][k] for k in ('application_image','prometheus_local_image','node_image')]
        cli = {}
        for binary in ('kind','kubectl'):
            path = shutil.which(binary,path=env['PATH'])
            if path is None or file_sha256(path)!=expected_environment['cli_binary_sha256'][binary]:
                raise ValueError('qualified_cli_mismatch')
            cli[binary] = file_sha256(path)
        observed = pinned_images(commands,images,expected_environment['image_ids'])
        publish_record(run/'outputs/environment.json',dict(cli_binary_sha256=cli,image_ids=observed))
        child = None
        log = run/'outputs/kind.log'
        try:
            commands.run(['kind','create','cluster','--name',cluster,'--config','harness/system/kind.yaml',
                          '--kubeconfig',str(config),'--wait','120s'],log=log,timeout=300)
            guard_local_api(kube.call(['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}']))
            version = json.loads(kube.call(['version','-o','json']))
            if version['serverVersion']['gitVersion']!=design['kubernetes']['server_version']:
                raise ValueError('pinned_kubernetes_required')
            for node in (cluster+'-control-plane',cluster+'-worker'):
                if commands.run(['docker','inspect','--format','{{.Image}}',node],timeout=10).strip()!=observed[images[2]]:
                    raise ValueError('running_kind_node_image_mismatch')
                config_text = commands.run(['docker','exec',node,'cat','/var/lib/kubelet/config.yaml'])
                if 'MemoryQoS: true' in config_text:
                    raise ValueError('memory_qos_changed')
            for image in images[:2]:
                commands.run(['kind','load','docker-image',image,'--name',cluster],log=log,timeout=120)
            resource_file = run/'outputs/resources.json'
            publish_record(resource_file,reservation_resources(design))
            kube.call(['apply','-f',str(resource_file)],log=log)
            kube.call(['wait','--for=condition=Ready','pod/application','pod/prometheus','--timeout=120s'],timeout=150,log=log)
            port = free_port()
            with (run/'outputs/portforward.log').open('w') as handle:
                child = subprocess.Popen(['kubectl','--kubeconfig',str(config),'--context','kind-'+cluster,
                    '-n',design['kubernetes']['namespace'],'port-forward','service/application',f'{port}:8080',
                    '--address','127.0.0.1'],env=env,stdout=handle,stderr=subprocess.STDOUT)
                url = f'http://127.0.0.1:{port}'
                wait_http(url+'/healthz')
                def check_forward():
                    if child.poll() is not None:
                        raise ValueError('workload_port_forward_exited')
                yield kube, NodeObserver(commands,kube.pod()), url, check_forward
                check_forward()
            require_isolated_engine(commands,cluster)
        finally:
            if child is not None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait()
            commands.run(['kind','delete','cluster','--name',cluster],log=log,timeout=120)
            require_isolated_engine(commands)


def _wait_until(deadline, guard):
    while time.monotonic_ns()<deadline:
        guard.raise_if_failed()
        time.sleep(min(.25,max(0,(deadline-time.monotonic_ns())/NS)))


def observe_live(profile, bucket, offset, *, wall_ns=None):
    old = profile.policy.accounting_metrics()['n_refresh_events']
    begin,cpu = time.perf_counter_ns(),time.thread_time_ns()
    observed = profile.observe(bucket,wall_ns=wall_ns)
    count = observed['accounting']['n_refresh_events']
    if count!=old and (offset!=10800 or count!=1):
        raise ValueError('unexpected_native_refresh')
    cost = dict(kind='step',offset_seconds=offset,wall_ns=time.perf_counter_ns()-begin,
                cpu_ns=time.thread_time_ns()-cpu)
    return dict(kind='LIVE_BUCKET',bucket=bucket,offset_seconds=offset,refresh_count=count,
                profile=observed['profile'],cost=cost), count!=old


def integration_disposition(refresh_actuation, requests, origin):
    if not refresh_actuation:
        return 'NATIVE_REFRESH_MISSING'
    if refresh_actuation['status']=='NO_OP':
        return 'NO_OP_OBJECTIVE_NOT_DEMONSTRATED'
    after = any(r['sent_offset_ns'] is not None and
                r['sent_offset_ns']+origin>=refresh_actuation['enforced_monotonic_ns'] for r in requests)
    return 'DEMONSTRATED' if after else 'POST_ENFORCEMENT_OUTCOMES_MISSING'


def episode(run, plan, design, bootstrap, snapshot, kube, node, url, check_forward, guard, context, origin_wall, origin):
    """Real monotonic scheduling. Collection runs independently of resize and request workers."""
    out = run/'outputs'
    clock = ObservationClock(run,context)
    samples, actuations = [], []
    stop_load, stop_collect = threading.Event(),threading.Event()
    changed = threading.Condition()
    pod = kube.pod();uid = pod['metadata']['uid']
    target = REFERENCE
    step_costs, refresh_actuation = [], None
    with (out/'requests.jsonl').open('w') as requests, (out/'telemetry.jsonl').open('w') as telemetry, \
         (out/'enforcement.jsonl').open('w') as enforcement, (out/'actuations.jsonl').open('w') as acts, \
         (out/'profile_events.jsonl').open('w') as profiles, ThreadPoolExecutor(max_workers=2) as pool:
        def emit(row):
            actuations.append(row);append(acts,row)
        if not confirm(kube,node,uid,target,pod['metadata']['generation'],0,enforcement):
            raise ValueError('reference_resources_unverified')
        if time.monotonic_ns()>=origin-WARMUP*NS:
            raise ValueError('reference_preflight_missed_warmup_start')
        def collect():
            next_poll = time.monotonic_ns()
            while not stop_collect.is_set():
                guard.raise_if_failed()
                check_forward()
                sample = clock.accept(node.capture(),telemetry)
                with changed:
                    samples.append(sample);changed.notify_all()
                next_poll += 5*NS
                stop_collect.wait(max(0,(next_poll-time.monotonic_ns())/NS))
        collector = pool.submit(collect)
        load = pool.submit(stream_requests,url,plan,origin,stop_load,requests)
        try:
            _wait_until(origin,guard)
            profile = None
            controller_cpu = 0
            def dispatch(target, trigger):
                nonlocal controller_cpu
                begin = time.thread_time_ns()
                result = actuate(kube,node,uid,target,enforcement,lambda row:emit(dict(row,trigger=trigger)),guard)
                controller_cpu += time.thread_time_ns()-begin
                return result
            if plan['mode']=='integration':
                start = time.thread_time_ns()
                profile = new_profile('pw_3h',bootstrap,design,origin_wall,42)
                step_costs.append(dict(kind='initialization',cpu_ns=time.thread_time_ns()-start))
                append(profiles,dict(kind='INITIALIZED',profile=profile.policy.profile.to_json()))
            if snapshot is not None or profile is not None:
                start = time.thread_time_ns()
                target = reservation_recommendation(snapshot['profile'] if snapshot else profile.policy.profile.to_json(),design)
                controller_cpu += time.thread_time_ns()-start
                if snapshot and target.resources()!=snapshot['target']:
                    raise ValueError('snapshot_recommendation_drift')
                if snapshot is not None:
                    append(profiles,dict(kind='FROZEN_SNAPSHOT_LOADED_AT_T0',snapshot=snapshot))
                dispatch(target,'T0')
            for offset in range(SLOT,plan['measurement_seconds']+1,SLOT):
                _wait_until(origin+offset*NS,guard)
                end = origin_wall+offset*NS
                deadline = time.monotonic()+10
                with changed:
                    while not samples or samples[-1]['received_at_ns']<end:
                        if collector.done():collector.result()
                        if time.monotonic()>=deadline:raise ValueError('missing_terminal_bucket_observation')
                        changed.wait(.2)
                    bucket = aggregate_bucket(samples,end-SLOT*NS,end,design)
                # Independent spec/status/cgroup reconciliation also covers reference runs.
                current = kube.pod()
                if not confirm(kube,node,uid,target,current['metadata']['generation'],0,enforcement):
                    raise ValueError('observed_allocation_unverifiable')
                if profile is not None:
                    event, refreshed = observe_live(profile,bucket,offset)
                    step_costs.append(event['cost']);append(profiles,event)
                    if refreshed:
                        start = time.thread_time_ns()
                        target = reservation_recommendation(event['profile'],design)
                        controller_cpu += time.thread_time_ns()-start
                        refresh_actuation = dispatch(target,'NATIVE_T_PLUS_3H')
                if load.done():load.result()
                guard.raise_if_failed()
            load.result()
            stop_collect.set();collector.result()
        finally:
            stop_load.set();stop_collect.set()
            try:collector.result()
            finally:clock.finalize()
    requests = list(rows(out/'requests.jsonl'))
    metrics = request_metrics(plan,requests)
    sealed = list(accepted_samples(run,context))
    if any(s['memory_limit_bytes']!=1024*2**20 or s['memory_swap_bytes'] for s in sealed):
        raise ValueError('fixed_memory_limit_or_swap_changed')
    for name,row in metrics.items():
        start,end = {'primary':(0,plan['measurement_seconds']),'transition':(0,300),
                     'followup':(300,1800),'after_refresh':(10800,12600)}[name]
        row.update(resource_endpoints(sealed,origin,actuations,start,end))
    previous = REFERENCE
    churn_cpu = churn_memory = 0
    for row in actuations:
        churn_cpu += abs(row['cpu_millicores']-previous.cpu_millicores)/1000
        churn_memory += abs(row['memory_request_mib']-previous.memory_request_mib)*2**20
        previous = type(REFERENCE)(row['cpu_millicores'],row['memory_request_mib'])
    metrics['primary'].update(cpu_churn_cores=churn_cpu,memory_churn_bytes=churn_memory,
                              controller_cpu_seconds=controller_cpu/NS)
    integration = integration_disposition(refresh_actuation,requests,origin) if profile is not None else None
    after = None
    if refresh_actuation:
        enforced_offset = refresh_actuation['enforced_monotonic_ns']-origin
        subsequent = [r for r in requests if r['sent_offset_ns'] is not None and r['sent_offset_ns']>=enforced_offset]
        after = dict(enforced_offset_ns=enforced_offset,requests=len(subsequent),
                     outcomes=dict(Counter(r['outcome'] for r in subsequent)))
    return dict(metrics=metrics,actuations=actuations,maintenance=step_costs,integration=integration,
                post_refresh_request_evidence=after)
