"""V7B attribution wrapper; unchanged workload CPU/memory operations and responses."""
import base64,hashlib,json,os,socket,threading,time,urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
from dynapm.system_validation import application as base

LOCK=threading.Lock()
CPU={'work':0.,'telemetry':0.,'health':0.}


def attribution():
    with LOCK:
        return dict(work_handler_cpu_seconds_total=CPU['work'],telemetry_handler_cpu_seconds_total=CPU['telemetry'],
            health_handler_cpu_seconds_total=CPU['health'],persistent_workset_bytes=len(base.MEMORY),
            attribution='handler thread CPU; container CPU also includes thread/server/background overhead; counters reset on restart')


def clock_domain():
    """Both telemetry and loopback receiver execute in this exact Linux namespace."""
    return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        time_namespace=os.readlink('/proc/self/ns/time'),hostname=socket.gethostname())


def receive_in_cluster(url):
    start_wall,start_mono=time.time_ns(),time.monotonic_ns()
    with urllib.request.urlopen(url,timeout=5) as response:
        raw=response.read()
        receipt_wall,receipt_mono=time.time_ns(),time.monotonic_ns()
    return dict(schema_version='cluster-clock-envelope-v1',
        raw_payload_base64=base64.b64encode(raw).decode(),raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
        cluster_request_wall_ns=start_wall,cluster_request_monotonic_ns=start_mono,
        cluster_received_at_ns=receipt_wall,cluster_receipt_monotonic_ns=receipt_mono,
        cluster_clock_domain=clock_domain())


class Handler(base.Handler):
    def do_GET(self):
        path=urlparse(self.path).path;kind='work' if path=='/work' else 'telemetry' if path in ('/telemetry','/clock-observation','/metrics') else 'health'
        cpu=time.thread_time()
        try:
            if path=='/clock-observation':
                # Complete source HTTP body is received inside the same OS/time namespace.
                return self.send(200,receive_in_cluster(f'http://127.0.0.1:{self.server.server_port}/telemetry'))
            if path=='/telemetry':
                sample=base.read_cgroup()
                # Same-process clock pair; monotonic epochs are never compared across hosts.
                sample['source_clock']=dict(wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),
                    hostname=socket.gethostname(),pid=os.getpid(),domain=clock_domain())
                return self.send(200,{**sample,**attribution()})
            if path=='/metrics':
                text=base.metrics();values=attribution()
                for key in ('work_handler_cpu_seconds_total','telemetry_handler_cpu_seconds_total','health_handler_cpu_seconds_total','persistent_workset_bytes'):
                    text+=f'dynapm_application_{key} {values[key]}\n'
                return self.send(200,text,'text/plain; version=0.0.4')
            return super().do_GET()
        finally:
            with LOCK:CPU[kind]+=time.thread_time()-cpu


def main():ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()

if __name__=='__main__':main()
