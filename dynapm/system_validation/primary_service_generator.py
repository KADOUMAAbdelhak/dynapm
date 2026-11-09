"""Primary scheduling adapter; qualified request/offer/terminal arithmetic is reused."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import signal
import socket
import threading
import time
from urllib.parse import urlsplit
try:  # In the Pod, always use the exact helper mounted in the sealed ConfigMap.
    import transport_generator as g
except ModuleNotFoundError as exc:
    if exc.name != 'transport_generator':
        raise
    from dynapm.system_validation import service_generator as g


def run(config, root):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root/'OWNER', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.write(fd, config['run_id'].encode()); os.fsync(fd); os.close(fd)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    now, wall = time.monotonic_ns(), time.time_ns()
    origin = now+(config['lead_seconds']+config['warmup_seconds'])*g.NS
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    namespace = os.readlink('/proc/self/ns/time')
    domain = config['expected_clock_domain']
    if boot != domain['boot_id'] or namespace != domain['time_namespace']:
        raise ValueError('generator_clock_domain_or_warmup_start_mismatch')
    start = dict(scope=config['scope'],claim_qualification_eligible=config['scope']=='DIAGNOSTIC_NON_CLAIM',schema=g.SCHEMA, run_id=config['run_id'], config_sha256=g.hashlib.sha256(g.canonical(config).encode()).hexdigest(),
                 origin_monotonic_ns=origin, origin_wall_ns=wall+origin-now,
                 clock_pair_monotonic_ns=now, clock_pair_wall_ns=wall,
                 boot_id=boot, time_namespace=namespace, pod_uid=os.environ.get('POD_UID'),
                 snapshot_sha256=config['snapshot_sha256'], expected_clock_domain=domain,
                 resolved_addresses=sorted({x[4][0] for x in socket.getaddrinfo(urlsplit(config['service_url']).hostname,8080,type=socket.SOCK_STREAM)}))
    g.atomic(root/'START.json', start)
    lock = threading.Lock(); slots = threading.BoundedSemaphore(32)
    count = size = 0; error = None
    with (root/'requests.jsonl').open('x') as sink:
        def emit(row):
            nonlocal count, size
            row=dict(row,scope=config['scope'],claim_outcome_eligible=config['scope']=='AMENDED_V8_PRIMARY',
                     claim_qualification_eligible=config['scope']=='DIAGNOSTIC_NON_CLAIM')
            raw = g.canonical(row)+'\n'
            with lock:
                if size+len(raw.encode()) > config['maximum_record_bytes']:
                    stop.set(); raise ValueError('generator_output_budget_exhausted')
                sink.write(raw); sink.flush(); os.fsync(sink.fileno())
                size += len(raw.encode()); count += 1
        def send(phase, event):
            try: emit(g.request(config['service_url'],event,phase,origin))
            finally: slots.release()
        try:
            with ThreadPoolExecutor(max_workers=32) as pool:
                pending = set()
                for phase,event in g.offers(config):
                    if stop.wait(max(0,(origin+event['offset_ns']-time.monotonic_ns())/g.NS)): break
                    done = {f for f in pending if f.done()}
                    for f in done: f.result()
                    pending -= done
                    if event['offset_ns']==0:
                        g.atomic(root/'T0.json',dict(run_id=config['run_id'],origin_monotonic_ns=origin,
                            emitted_monotonic_ns=time.monotonic_ns(),emitted_wall_ns=time.time_ns(),
                            boot_id=boot,time_namespace=namespace,snapshot_sha256=config['snapshot_sha256']))
                    if slots.acquire(blocking=False): pending.add(pool.submit(send,phase,event))
                    else:
                        at = time.monotonic_ns()
                        emit(dict(schema=g.SCHEMA,request_id=event['request_id'],offer=event,intended_phase=phase,
                                  sent_offset_ns=None,completed_offset_ns=at-origin,completed_monotonic_ns=at,
                                  completed_wall_ns=time.time_ns(),scheduled_monotonic_ns=origin+event['offset_ns'],
                                  latency_ns=at-origin-event['offset_ns'],success=False,outcome='overload_drop',
                                  http_status=None,failure_layer='GENERATOR_CONCURRENCY_CAP',exception=None,retries=0))
                for f in pending: f.result()
        except BaseException as exc:
            stop.set(); error = g.exception_details(exc)
    if not stop.is_set(): stop.wait(max(0,(origin+config['plan']['measurement_seconds']*g.NS-time.monotonic_ns())/g.NS))
    expected = sum(1 for _ in g.offers(config))
    result = dict(scope=config['scope'],claim_qualification_eligible=config['scope']=='DIAGNOSTIC_NON_CLAIM',schema=g.SCHEMA,run_id=config['run_id'],status='COMPLETE' if not stop.is_set() and count==expected else 'INTERRUPTED',
                  records=count,expected_records=expected,requests_sha256=g.sha(root/'requests.jsonl'),start_sha256=g.sha(root/'START.json'),
                  config_sha256=start['config_sha256'],completed_monotonic_ns=time.monotonic_ns(),completed_wall_ns=time.time_ns(),error=error)
    g.atomic(root/'DONE.json',result)
    return 0 if result['status']=='COMPLETE' else 2


if __name__ == '__main__':
    import json, sys
    sys.exit(run(json.loads(Path(sys.argv[1]).read_text()),sys.argv[2]))
