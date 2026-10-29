"""V7B attribution wrapper; unchanged workload CPU/memory operations and responses."""
import os,socket,threading,time
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


class Handler(base.Handler):
    def do_GET(self):
        path=urlparse(self.path).path;kind='work' if path=='/work' else 'telemetry' if path in ('/telemetry','/metrics') else 'health'
        cpu=time.thread_time()
        try:
            if path=='/telemetry':
                sample=base.read_cgroup()
                # Same-process clock pair; monotonic epochs are never compared across hosts.
                sample['source_clock']=dict(wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),
                    hostname=socket.gethostname(),pid=os.getpid())
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
