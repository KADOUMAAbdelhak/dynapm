"""Production observation policies behind a separate localhost profile service."""
import argparse,json,os,resource,subprocess,sys,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import numpy as np
import pandas as pd
from dynapm.core.schema import ProfileInstance,StaticFields,DynamicFields
from dynapm.core.discretization import compute_thresholds
from dynapm.core.temporal import METRICS,trailing_observations
from dynapm.experiments.confirmatory_execution import factory_for
from dynapm.core.provenance import canonical_json,read_json
from dynapm.system_validation.design import frozen_design


def current_rss_bytes():
    try:
        if sys.platform.startswith('linux'):return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]))*1024
    except (OSError,ValueError,subprocess.CalledProcessError):return None


def aggregate_bucket(samples,start_ns,end_ns,design):
    t=design['telemetry'];inside=sorted([s for s in samples if start_ns<=s['sample_time_ns']<=end_ns],key=lambda x:x['sample_time_ns'])
    if end_ns-start_ns!=t['bucket_seconds']*10**9 or len(inside)<t['min_samples']:raise ValueError('incomplete_telemetry_bucket')
    times=np.array([s['sample_time_ns'] for s in inside],dtype=np.int64)
    if np.any(np.diff(times)<=0) or len({s['instance_id'] for s in inside})!=1:raise ValueError('reset_or_duplicate_telemetry')
    span=(times[-1]-times[0])/1e9
    if span<t['min_span_seconds'] or any(b['cpu_seconds']<a['cpu_seconds'] for a,b in zip(inside,inside[1:])):raise ValueError('short_or_reset_measurement_span')
    cpu=(inside[-1]['cpu_seconds']-inside[0]['cpu_seconds'])/span*1000
    mem=float(np.mean([s['memory_working_set_bytes'] for s in inside]))/2**20
    if not np.isfinite([cpu,mem]).all() or min(cpu,mem)<0:raise ValueError('invalid_telemetry_value')
    return dict(logical_slot_ns=int(end_ns),source_start_ns=int(times[0]),source_end_ns=int(times[-1]),
        available_at_ns=max(int(end_ns),max(s['received_at_ns'] for s in inside)),
        cpu_percent=100*cpu/design['references']['cpu_millicores'],memory_percent=100*mem/design['references']['memory_mib'],
        real_samples=len(inside),source_span_seconds=span,source='REAL_COMPLETED_CGROUP_BUCKET')


class ProfileAdapter:
    def __init__(self,method,anchor_ns,design,fixture):
        if method not in design['methods']:raise ValueError('observation_only_method_required')
        if fixture['role']!='SYNTHETIC_SMOKE_FIXTURE' or fixture['slots']!=288:raise ValueError('smoke_bootstrap_fixture_required')
        self.design=design;self.method_id=method;self.anchor_ns=anchor_ns;self.lock=threading.Lock()
        anchor=pd.Timestamp(anchor_ns,unit='ns',tz='UTC');idx=pd.date_range(end=anchor,periods=288,freq='5min')
        self.history=pd.DataFrame({METRICS[0]:100*fixture['cpu_millicores']/design['references']['cpu_millicores'],
            METRICS[1]:100*fixture['memory_mib']/design['references']['memory_mib']},index=idx)
        cpu_th=compute_thresholds(self.history,METRICS[0]);mem_th=compute_thresholds(self.history,METRICS[1])
        profile=ProfileInstance(StaticFields('application','kind-local-smoke',None,None,idx[0],anchor,288),
            DynamicFields('idle','idle',0.,0.),{k:anchor for k in ['cpu_class','memory_class','predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h']})
        self.policy=factory_for(method)(profile,cpu_th,mem_th,bootstrap_cpu_series=self.history[METRICS[0]],bootstrap_mem_series=self.history[METRICS[1]])
        self.last_slot=anchor_ns;self.last_commit_wall_ns=time.time_ns();self.step_wall=[];self.step_cpu=[];self.observations=[]

    def observe(self,payload,*,wall_ns=None):
        now=time.time_ns() if wall_ns is None else wall_ns;t=payload['logical_slot_ns']
        if any(type(payload[k]) is not int for k in ['logical_slot_ns','source_start_ns','source_end_ns','available_at_ns']):raise ValueError('integer_source_clocks_required')
        if payload['available_at_ns']>now or payload['available_at_ns']<t or payload['source_end_ns']>t or payload['source_start_ns']<t-300*10**9 or payload['source_start_ns']>=payload['source_end_ns']:
            raise ValueError('incomplete_or_future_measurement_invisible')
        if (t-self.anchor_ns)%(300*10**9) or not np.isfinite([payload['cpu_percent'],payload['memory_percent']]).all() or min(payload['cpu_percent'],payload['memory_percent'])<0:
            raise ValueError('invalid_nominal_observation')
        with self.lock:
            if t<=self.last_slot:raise ValueError('nonincreasing_observation')
            stamp=pd.Timestamp(t,unit='ns',tz='UTC');start=time.perf_counter();cpu=time.process_time();before=self.policy.accounting_metrics()['n_refresh_events']
            self.history.loc[stamp]=[payload['cpu_percent'],payload['memory_percent']]
            self.policy.step(stamp,trailing_observations(self.history[METRICS[0]],stamp,24),trailing_observations(self.history[METRICS[1]],stamp,24))
            self.step_wall.append(time.perf_counter()-start);self.step_cpu.append(time.process_time()-cpu)
            self.last_slot=t;self.observations.append(payload)
            if self.policy.accounting_metrics()['n_refresh_events']!=before:self.last_commit_wall_ns=time.time_ns()
            return self._snapshot()

    def _snapshot(self):
        return dict(scope='NON_CLAIM_SMOKE_SYNTHETIC_BOOTSTRAP',snapshot_wall_time_ns=time.time_ns(),method_id=self.method_id,profile=self.policy.profile.to_json(),
            accounting=self.policy.accounting_metrics(),last_nominal_slot_ns=self.last_slot,last_commit_wall_ns=self.last_commit_wall_ns,
            refresh_log=[e.to_dict() for e in self.policy.accounting.refresh_events],real_observations=len(self.observations),
            maintenance_step_wall_seconds=list(self.step_wall),maintenance_step_cpu_seconds=list(self.step_cpu),
            state_bytes=len(canonical_json(self.policy.profile.to_json()).encode()))

    def snapshot(self):
        with self.lock:return self._snapshot()

    def metrics(self):
        with self.lock:
            counts=self.policy.accounting_metrics();usage=resource.getrusage(resource.RUSAGE_SELF)
            values={**counts,'maintenance_step_wall_seconds_total':sum(self.step_wall),'maintenance_step_cpu_seconds_total':sum(self.step_cpu),
                'maintenance_steps_total':len(self.step_wall),'process_cpu_seconds_total':usage.ru_utime+usage.ru_stime,
                'process_resident_memory_bytes':current_rss_bytes(),'profile_state_bytes':len(canonical_json(self.policy.profile.to_json()).encode())}
            return '\n'.join(f'dynapm_profile_{k} {v}' for k,v in values.items() if v is not None)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--port',type=int,required=True);a=p.parse_args()
    design=frozen_design(a.repo);fixture=read_json(a.repo/'harness/system/fixtures/smoke/bootstrap.json');state={'adapter':None}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value,content='application/json'):
            body=(canonical_json(value) if content=='application/json' else value).encode();self.send_response(status);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/healthz':return self.reply(200,{'ready':True,'initialized':state['adapter'] is not None})
            if state['adapter'] is None:return self.reply(409,{'error':'not_initialized'})
            if self.path=='/snapshot':return self.reply(200,state['adapter'].snapshot())
            if self.path=='/metrics':return self.reply(200,state['adapter'].metrics(),'text/plain; version=0.0.4')
            self.reply(404,{'error':'unknown_endpoint'})
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=100000:raise ValueError('bounded_body_required')
                body=json.loads(self.rfile.read(n))
                if self.path=='/initialize':
                    if state['adapter'] is not None:raise ValueError('already_initialized')
                    if body['anchor_ns']>time.time_ns():raise ValueError('future_bootstrap_anchor')
                    state['adapter']=ProfileAdapter(body['method'],body['anchor_ns'],design,fixture)
                    return self.reply(200,state['adapter'].snapshot())
                if self.path=='/observe' and state['adapter'] is not None:return self.reply(200,state['adapter'].observe(body))
                self.reply(404,{'error':'unknown_endpoint'})
            except (ValueError,KeyError,TypeError) as e:self.reply(400,{'error':str(e)})
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()

if __name__=='__main__':main()
