"""Separate long-run generator, measured-profile and resource-consumer processes."""
from __future__ import annotations
import argparse,concurrent.futures,json,math,os,resource,signal,sys,threading,time,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from dynapm.core.provenance import canonical_json,read_json
from dynapm.core.run_store import write_json
from dynapm.system_validation.adapter import current_rss_bytes
from dynapm.system_validation.trial_preparation import measured_bootstrap,MeasuredProfileAdapter
from dynapm.system_validation.workloads import workload_state
from dynapm.system_validation.consumer import recommend,resources_match
from dynapm.system_validation.smoke import Commands,Kube,http


def process_stats():
    r=resource.getrusage(resource.RUSAGE_SELF)
    return dict(pid=os.getpid(),cpu_seconds=r.ru_utime+r.ru_stime,rss_bytes=current_rss_bytes(),wall_time_ns=time.time_ns(),instrumentation_child_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime)


def stats_server(port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            body=canonical_json(process_stats()).encode();self.send_response(200)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    threading.Thread(target=ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever,daemon=True).start()


def write_line(file,value):
    file.write(canonical_json(value)+'\n');file.flush()


def request_events(plan):
    """Same predefined V7A scenario/CPU work, continuous open-loop offered trace."""
    d=plan['design'];offset=0.;start=plan['load_start_seconds'];end=plan['measurement_end_seconds']
    while start+offset<end:
        elapsed=start+offset-plan['measurement_start_seconds']
        scenario='stable' if elapsed<0 else plan['scenario']
        rate,memory=workload_state(scenario,max(0,elapsed),d)
        yield dict(offset_seconds=offset,iterations=d['workload']['iterations'],memory_mib=memory,seed=d['workload']['seed'])
        offset+=1/rate


def stream_load(url,events,start_wall,output,*,timeout=5.,concurrency=32,stop=None):
    """Bounded outstanding requests and streaming sink; no 72h in-memory result list."""
    lock=threading.Lock();slots=threading.BoundedSemaphore(concurrency)
    start_mono=time.monotonic()+start_wall-time.time();count=0
    def emit(row):
        with lock:write_line(output,row)
    def send(i,event):
        due=start_mono+event['offset_seconds'];sent=time.time()
        try:
            q=f"iterations={event['iterations']}&memory_mib={event['memory_mib']}&seed={event['seed']}"
            with urllib.request.urlopen(url+'/work?'+q,timeout=timeout) as response:
                status=response.status;response.read();success=status==200
            error=None
        except Exception as exc:success=False;status=None;error=type(exc).__name__
        completed=time.time()
        emit(dict(request_id=i,scheduled_at=start_wall+event['offset_seconds'],sent_at=sent,completed_at=completed,
            latency_seconds=time.monotonic()-due,success=success,http_status=status,error=error,dropped=False))
        slots.release()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i,event in enumerate(events):
            delay=max(0,start_mono+event['offset_seconds']-time.monotonic())
            if stop is not None:
                if stop.wait(delay):break
            else:time.sleep(delay)
            count+=1
            if slots.acquire(blocking=False):pool.submit(send,i,event)
            else:emit(dict(request_id=i,scheduled_at=start_wall+event['offset_seconds'],sent_at=None,
                completed_at=time.time(),latency_seconds=None,success=False,http_status=None,error='generator_capacity',dropped=True))
    return count


class CalibrationProfile(MeasuredProfileAdapter):
    def __init__(self,*args,**kwargs):
        self.thread_cpu=[];super().__init__(*args,**kwargs)
    def observe(self,payload,**kwargs):
        before=time.thread_time();result=super().observe(payload,**kwargs)
        with self.lock:
            self.thread_cpu.append(time.thread_time()-before)
            result['step_thread_cpu_seconds']=list(self.thread_cpu)
        return result


def profile_service(plan,root,port):
    state={'adapter':None,'initialization':None}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value):
            body=canonical_json(value).encode();self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/healthz':return self.reply(200,dict(ready=True,initialized=state['adapter'] is not None,process=process_stats()))
            if state['adapter'] is None:return self.reply(409,dict(error='bootstrap_not_initialized'))
            if self.path=='/snapshot':return self.reply(200,state['adapter'].snapshot())
            if self.path=='/stats':return self.reply(200,dict(process=process_stats(),initialization=state['initialization'],
                thread_step_cpu_seconds=list(state['adapter'].thread_cpu)))
            self.reply(404,dict(error='unknown_endpoint'))
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=100000:raise ValueError('bounded_body_required')
                payload=json.loads(self.rfile.read(n))
                if self.path=='/initialize':
                    if state['adapter'] is not None:raise ValueError('already_initialized')
                    evidence=[json.loads(line) for line in (root/'outputs/bootstrap_samples.jsonl').read_text().splitlines() if line]
                    wall=time.perf_counter();cpu=time.thread_time()
                    boot=measured_bootstrap(evidence,int(plan['bootstrap_start_seconds']*1e9),
                        int(plan['measurement_start_seconds']*1e9),time.time_ns(),plan['design'])
                    state['adapter']=CalibrationProfile('pw_6h',boot,plan['design'],planned_streaming_slots=576)
                    state['initialization']=dict(wall_seconds=time.perf_counter()-wall,thread_cpu_seconds=time.thread_time()-cpu,
                        bootstrap_evidence_sha256=boot.evidence_sha256,accepted_slots=boot.accepted_slots,missing_slots=boot.missing_slots)
                    return self.reply(200,state['adapter'].snapshot())
                if self.path=='/observe' and state['adapter'] is not None:
                    return self.reply(200,state['adapter'].observe(payload))
                self.reply(409,dict(error='bootstrap_not_initialized'))
            except (ValueError,KeyError,TypeError) as exc:self.reply(400,dict(error=str(exc)))
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


def controller(plan,root,kubeconfig):
    d=plan['design'];commands=Commands(dict(os.environ),root);last_status=0;last_pod_observation=0
    kube=Kube(commands,kubeconfig,plan['cluster'],d);pending=None;partial_command=''
    counters=dict(recommendations=0,resource_changes=0,rejected=0,timeout_events=0,skipped_pending=0,
        cpu_churn_millicores=0.,memory_churn_mib=0.,control_observation_failures=0)
    with (root/'outputs/controller_commands.jsonl').open() as incoming, (root/'outputs/decisions.jsonl').open('w',buffering=1) as out:
        while True:
            piece=incoming.readline()
            if piece and not piece.endswith('\n'):partial_command+=piece;line=''
            elif piece:line=partial_command+piece;partial_command=''
            else:line=''
            if line:
                command=json.loads(line)
                if command.get('stop'):break
                counters['recommendations']+=1
                if pending is not None:
                    counters['skipped_pending']+=1;write_line(out,dict(kind='SKIPPED_INFLIGHT',nominal_time_ns=command['nominal_time_ns']))
                else:
                    start=time.perf_counter();cpu=time.thread_time();r=recommend(command['snapshot']['profile'],d)
                    event=dict(kind='RECOMMENDATION',nominal_time_ns=command['nominal_time_ns'],recommendation=r,
                        compute_wall_seconds=time.perf_counter()-start,compute_thread_cpu_seconds=time.thread_time()-cpu,
                        snapshot_to_recommendation_seconds=(time.time_ns()-command['snapshot_read_started_ns'])/1e9)
                    try:pod=kube.pod();before=pod['spec']['containers'][0]['resources']
                    except (OSError,RuntimeError,KeyError,IndexError,TypeError) as exc:
                        counters['control_observation_failures']+=1
                        write_line(out,{**event,'disposition':'CONTROL_OBSERVATION_UNAVAILABLE_OPERATIONAL','error':type(exc).__name__})
                        write_json(root/'outputs/controller_status.json',dict(process=process_stats(),counters=counters,pending=pending,complete=False))
                        time.sleep(.5);continue
                    event['before_resources']=before
                    if resources_match(before,r):event['disposition']='UNCHANGED'
                    else:
                        try:
                            submitted=time.time_ns();ack=kube.resize(r)
                            event.update(disposition='SUBMITTED',submitted_ns=submitted,acknowledged_ns=time.time_ns(),
                                requested_generation=ack['metadata'].get('generation'),pod_uid=pod['metadata']['uid'])
                            pending=dict(recommendation=r,submitted_ns=submitted,before=before,pod_uid=pod['metadata']['uid'],timeout_recorded=False)
                        except RuntimeError as exc:
                            counters['rejected']+=1;event.update(disposition='REJECTED_OPERATIONAL',error=str(exc))
                    write_line(out,event)
            if pending is not None:
                try:
                    p=kube.pod();sample=http(plan['app_url']+'/telemetry');s=p['status']['containerStatuses'][0];r=pending['recommendation']
                    if p['metadata']['uid']!=pending['pod_uid']:raise ValueError('unexpected_pod_replacement')
                    if resources_match(s.get('resources'),r) and abs(sample['cpu_limit_cores']*1000-r['cpu_millicores'])<1e-6 and sample['memory_limit_bytes']==r['memory_mib']*2**20:
                        from dynapm.system_validation.consumer import cpu_millicores,memory_bytes
                        counters['resource_changes']+=1
                        counters['cpu_churn_millicores']+=abs(cpu_millicores(pending['before']['requests']['cpu'])-r['cpu_millicores'])
                        counters['memory_churn_mib']+=abs(memory_bytes(pending['before']['requests']['memory'])/2**20-r['memory_mib'])
                        write_line(out,dict(kind='ENFORCED',confirmed_ns=time.time_ns(),submitted_ns=pending['submitted_ns'],
                            actual_resources=s['resources'],cgroup=sample,restarts=s['restartCount'],
                            actuation_latency_seconds=(time.time_ns()-pending['submitted_ns'])/1e9))
                        pending=None
                    elif time.time_ns()-pending['submitted_ns']>60*10**9 and not pending['timeout_recorded']:
                        counters['timeout_events']+=1;pending['timeout_recorded']=True
                        write_line(out,dict(kind='DEFERRED_BEYOND_60S_OPERATIONAL',wall_ns=time.time_ns(),submitted_ns=pending['submitted_ns']))
                except (OSError,RuntimeError,KeyError,IndexError,TypeError) as exc:
                    write_line(out,dict(kind='ACTUATION_OBSERVATION_UNAVAILABLE',error=type(exc).__name__,wall_ns=time.time_ns()))
            if time.monotonic()-last_pod_observation>=30:
                try:
                    observation=kube.pod()
                    write_line(out,dict(kind='POD_OBSERVATION',wall_ns=time.time_ns(),pod_uid=observation['metadata']['uid'],status=observation['status']))
                except (OSError,RuntimeError,KeyError,IndexError,TypeError) as exc:
                    write_line(out,dict(kind='POD_OBSERVATION_UNAVAILABLE',wall_ns=time.time_ns(),error=type(exc).__name__))
                last_pod_observation=time.monotonic()
            if line or time.monotonic()-last_status>=5:
                write_json(root/'outputs/controller_status.json',dict(process=process_stats(),counters=counters,pending=pending,complete=False));last_status=time.monotonic()
            time.sleep(1 if pending else .5)
        if pending:write_line(out,dict(kind='PENDING_AT_END_OPERATIONAL',submitted_ns=pending['submitted_ns']))
        write_json(root/'outputs/controller_status.json',dict(process=process_stats(),counters=counters,pending=pending,complete=True))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('worker',choices=['generator','profile','controller'])
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--port',type=int);p.add_argument('--kubeconfig',type=Path)
    a=p.parse_args();plan=read_json(a.plan)
    if a.worker!='profile':stats_server(a.port)
    if a.worker=='profile':profile_service(plan,a.root,a.port)
    elif a.worker=='controller':controller(plan,a.root,a.kubeconfig)
    else:
        with (a.root/'outputs/requests.jsonl').open('w',buffering=1) as out:
            n=stream_load(plan['app_url'],request_events(plan),plan['load_start_seconds'],out,
                timeout=plan['design']['workload']['timeout_seconds'],concurrency=plan['design']['workload']['max_concurrency'])
        write_json(a.root/'outputs/generator_status.json',dict(process=process_stats(),offered=n,complete=True))

if __name__=='__main__':main()
