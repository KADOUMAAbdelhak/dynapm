"""Small real CPU/memory HTTP workload; standard library only, Linux cgroup v2."""
import argparse,hashlib,json,math,os,threading,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs

INSTANCE=uuid.uuid4().hex
LOCK=threading.Lock()
MEMORY=bytearray()
COUNTS={'requests':0,'errors':0,'seconds_sum':0.,'buckets':[0]*10}
BUCKETS=[.005,.01,.025,.05,.1,.25,.5,1,2,5]


def read_cgroup(root='/sys/fs/cgroup'):
    p=Path(root)
    def fields(name):return {k:int(v) for k,v in (s.split() for s in (p/name).read_text().splitlines())}
    cpu=fields('cpu.stat');memory=fields('memory.stat');events=fields('memory.events')
    quota,period=(p/'cpu.max').read_text().split();cap=(p/'memory.max').read_text().strip()
    current=int((p/'memory.current').read_text())
    return dict(sample_time_ns=time.time_ns(),instance_id=INSTANCE,cpu_seconds=cpu['usage_usec']/1e6,
        memory_current_bytes=current,
        memory_working_set_bytes=max(0,current-memory.get('inactive_file',0)),
        cpu_limit_cores=None if quota=='max' else int(quota)/int(period),memory_limit_bytes=None if cap=='max' else int(cap),
        cpu_periods=cpu.get('nr_periods',0),cpu_throttled_periods=cpu.get('nr_throttled',0),
        cpu_throttled_seconds=cpu.get('throttled_usec',0)/1e6,oom_kills=events.get('oom_kill',0))


def metrics():
    c=read_cgroup();lines=[]
    mapping={'cpu_seconds':('dynapm_application_cgroup_cpu_seconds_total','counter'),
        'memory_working_set_bytes':('dynapm_application_cgroup_memory_working_set_bytes','gauge'),
        'memory_current_bytes':('dynapm_application_cgroup_memory_current_bytes','gauge'),
        'cpu_limit_cores':('dynapm_application_cgroup_cpu_limit_cores','gauge'),
        'memory_limit_bytes':('dynapm_application_cgroup_memory_limit_bytes','gauge'),
        'cpu_throttled_periods':('dynapm_application_cgroup_throttled_periods_total','counter'),
        'oom_kills':('dynapm_application_cgroup_oom_kills_total','counter')}
    for key,(name,kind) in mapping.items():
        if c[key] is not None:lines.extend([f'# TYPE {name} {kind}',f'{name} {c[key]}'])
    with LOCK:
        lines.extend(['# TYPE dynapm_application_requests_total counter',f"dynapm_application_requests_total {COUNTS['requests']}",
            '# TYPE dynapm_application_errors_total counter',f"dynapm_application_errors_total {COUNTS['errors']}",
            '# TYPE dynapm_application_handler_seconds histogram'])
        for bound,count in zip(BUCKETS,COUNTS['buckets']):lines.append(f'dynapm_application_handler_seconds_bucket{{le="{bound}"}} {count}')
        lines.extend([f'dynapm_application_handler_seconds_bucket{{le="+Inf"}} {COUNTS["requests"]}',
            f'dynapm_application_handler_seconds_count {COUNTS["requests"]}',f'dynapm_application_handler_seconds_sum {COUNTS["seconds_sum"]}'])
    return '\n'.join(lines)+'\n'


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,value,content='application/json'):
        body=(json.dumps(value,sort_keys=True,allow_nan=False) if content=='application/json' else value).encode()
        self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        global MEMORY
        u=urlparse(self.path)
        try:
            if u.path=='/healthz':return self.send(200,{'ready':True})
            if u.path=='/telemetry':return self.send(200,read_cgroup())
            if u.path=='/metrics':return self.send(200,metrics(),'text/plain; version=0.0.4')
            if u.path!='/work':return self.send(404,{'error':'unknown_endpoint'})
            args=parse_qs(u.query);iterations=int(args.get('iterations',['30000'])[0]);mib=int(args.get('memory_mib',['32'])[0]);seed=int(args.get('seed',['20251022'])[0])
            if not 1<=iterations<=100000 or not 0<=mib<=192:raise ValueError('bounded_workload_parameters_required')
            start=time.perf_counter()
            with LOCK:
                if len(MEMORY)!=mib*2**20:
                    MEMORY=bytearray(mib*2**20)
                    for i in range(0,len(MEMORY),4096):MEMORY[i]=1
            hashlib.pbkdf2_hmac('sha256',str(seed).encode(),b'dynapm-system-v1',iterations)
            elapsed=time.perf_counter()-start
            with LOCK:
                COUNTS['requests']+=1;COUNTS['seconds_sum']+=elapsed
                for i,b in enumerate(BUCKETS):COUNTS['buckets'][i]+=int(elapsed<=b)
            return self.send(200,dict(ok=True,handler_seconds=elapsed,iterations=iterations,memory_mib=mib))
        except (ValueError,OSError,KeyError) as e:
            with LOCK:COUNTS['errors']+=1
            return self.send(400,{'error':str(e)})


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8080);a=p.parse_args()
    ThreadingHTTPServer(('0.0.0.0',a.port),Handler).serve_forever()

if __name__=='__main__':main()
