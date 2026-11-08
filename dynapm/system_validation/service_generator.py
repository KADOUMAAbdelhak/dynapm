"""Standalone stdlib in-cluster generator. Application traffic never traverses the host."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,http.client,json,os,signal,socket,threading,time
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA='v8-service-generator-v1'
NS=10**9
PHASES={'low2':(2,32),'low4':(4,32),'high12':(12,96)}

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,value):
    path=Path(path);tmp=path.with_suffix('.tmp')
    with tmp.open('x') as f:f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def offers(config):
    plan=config['plan'];warm=config['warmup_seconds'];segments=([[-warm,plan['warmup_phase']]] if warm else [])+plan['segments']
    ends=[s[0] for s in segments[1:]]+[plan['measurement_seconds']];index=0
    for (start,phase),end in zip(segments,ends):
        rps,mib=PHASES[phase]
        for n in range((end-start)*rps):
            yield phase,dict(request_id=index,offset_ns=start*NS+n*NS//rps,memory_mib=mib,iterations=30000,seed=plan['seed'])
            index+=1

def exception_details(exc):
    return dict(type=type(exc).__name__,message=str(exc),errno=getattr(exc,'errno',None))

def request(url,event,phase,origin,*,connection_factory=http.client.HTTPConnection):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or not (parsed.hostname or '').endswith('.svc.cluster.local') or parsed.username or parsed.query or parsed.path not in ('','/'):
        raise ValueError('plain_internal_service_endpoint_required')
    sent=time.monotonic_ns();sent_wall=time.time_ns();stage='connect';status=None;error=None;layer=None;result='success';body=None
    conn=connection_factory(parsed.hostname,parsed.port or 80,timeout=5)
    try:
        conn.connect();stage='send_request'
        query=f"/work?iterations={event['iterations']}&memory_mib={event['memory_mib']}&seed={event['seed']}"
        conn.request('GET',query,headers={'Connection':'close'});stage='response_headers'
        response=conn.getresponse();status=response.status
        if status>=400:result='http_error';layer='APPLICATION_HTTP_RESPONSE'
        elif 300<=status<400:result='transport_error';layer='UNEXPECTED_REDIRECT_NO_RETRY'
        else:
            stage='response_body';body=response.read();stage='decode_body';decoded=json.loads(body)
            if status!=200 or not isinstance(decoded,dict) or decoded.get('ok') is not True or decoded.get('iterations')!=event['iterations'] or decoded.get('memory_mib')!=event['memory_mib']:
                result='application_error';layer='APPLICATION_RESPONSE'
    except TimeoutError as exc:
        result='request_timeout';layer='CONNECTION_DEADLINE' if stage=='connect' else 'RESPONSE_DEADLINE_CAUSE_UNRESOLVED';error=exception_details(exc)
    except (OSError,http.client.HTTPException,ValueError) as exc:
        error=exception_details(exc)
        result='application_error' if stage=='decode_body' else 'transport_error'
        layer='APPLICATION_RESPONSE' if stage=='decode_body' else 'SERVICE_TRANSPORT'
    finally:conn.close()
    completed=time.monotonic_ns();wall=time.time_ns()
    return dict(schema=SCHEMA,request_id=event['request_id'],offer=event,intended_phase=phase,
        sent_offset_ns=sent-origin,completed_offset_ns=completed-origin,
        sent_monotonic_ns=sent,sent_wall_ns=sent_wall,completed_monotonic_ns=completed,completed_wall_ns=wall,
        scheduled_monotonic_ns=origin+event['offset_ns'],latency_ns=completed-origin-event['offset_ns'],
        network_attempt_latency_ns=completed-sent,success=result=='success',outcome=result,http_status=status,
        failure_layer=layer,failure_stage=stage if error else None,exception=error,retries=0,
        response_sha256=hashlib.sha256(body).hexdigest() if body is not None else None)

def run(config,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    fd=os.open(root/'OWNER',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644);os.write(fd,config['run_id'].encode());os.fsync(fd);os.close(fd)
    stopping=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopping.set())
    # All offsets/latencies have one local monotonic domain. Wall time is provenance only.
    now=time.monotonic_ns();wall=time.time_ns();origin=now+(config['lead_seconds']+config['warmup_seconds'])*NS
    start=dict(schema=SCHEMA,run_id=config['run_id'],config_sha256=hashlib.sha256(canonical(config).encode()).hexdigest(),
        origin_monotonic_ns=origin,origin_wall_ns=wall+origin-now,clock_pair_monotonic_ns=now,clock_pair_wall_ns=wall,
        resolved_addresses=sorted({x[4][0] for x in socket.getaddrinfo(urlsplit(config['service_url']).hostname,8080,type=socket.SOCK_STREAM)}),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),time_namespace=os.readlink('/proc/self/ns/time'),pod_uid=os.environ.get('POD_UID'))
    atomic(root/'START.json',start)
    lock=threading.Lock();slots=threading.BoundedSemaphore(32);count=0;error=None
    with (root/'requests.jsonl').open('x') as sink:
        def emit(row):
            nonlocal count
            with lock:sink.write(canonical(row)+'\n');sink.flush();os.fsync(sink.fileno());count+=1
        def send(phase,event):
            try:emit(request(config['service_url'],event,phase,origin))
            finally:slots.release()
        try:
            with ThreadPoolExecutor(max_workers=32) as pool:
                pending=set()
                for phase,event in offers(config):
                    if stopping.wait(max(0,(origin+event['offset_ns']-time.monotonic_ns())/NS)):break
                    done={f for f in pending if f.done()}
                    for f in done:f.result()
                    pending-=done
                    if slots.acquire(blocking=False):pending.add(pool.submit(send,phase,event))
                    else:
                        at=time.monotonic_ns()
                        emit(dict(schema=SCHEMA,request_id=event['request_id'],offer=event,intended_phase=phase,
                            sent_offset_ns=None,completed_offset_ns=at-origin,completed_monotonic_ns=at,completed_wall_ns=time.time_ns(),
                            scheduled_monotonic_ns=origin+event['offset_ns'],latency_ns=at-origin-event['offset_ns'],
                            success=False,outcome='overload_drop',http_status=None,failure_layer='GENERATOR_CONCURRENCY_CAP',exception=None,retries=0))
                for f in pending:f.result()
        except BaseException as exc:error=exception_details(exc);stopping.set()
    if not stopping.is_set():stopping.wait(max(0,(origin+config['plan']['measurement_seconds']*NS-time.monotonic_ns())/NS))
    expected=sum(1 for _ in offers(config))
    result=dict(schema=SCHEMA,run_id=config['run_id'],status='COMPLETE' if not stopping.is_set() and count==expected else 'INTERRUPTED',
        expected_records=expected,records=count,requests_sha256=sha(root/'requests.jsonl'),start_sha256=sha(root/'START.json'),
        config_sha256=start['config_sha256'],completed_monotonic_ns=time.monotonic_ns(),completed_wall_ns=time.time_ns(),error=error)
    atomic(root/'DONE.json',result)
    return 0 if result['status']=='COMPLETE' else 2

if __name__=='__main__':
    import sys
    sys.exit(run(json.loads(Path(sys.argv[1]).read_text()),sys.argv[2]))
