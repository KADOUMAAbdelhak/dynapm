"""Synthetic tests only; never comparative Kubernetes outcomes."""
from pathlib import Path
from copy import deepcopy
import io,json,sys,threading,subprocess,time
import numpy as np
import pytest
from dynapm.core.provenance import fingerprint,read_json,canonical_json
from dynapm.system_validation.estimation_design import frozen_spec,calibration_plan
from dynapm.system_validation.system_estimation import pareto_relation,paired_effects,calibration_noise,allocation_integrals,PARETO
from dynapm.system_validation.calibration_workers import request_events,stream_load
from dynapm.system_validation.calibration_runner import output_specs
ROOT=Path(__file__).resolve().parents[2]


def point():return {k:1. for k in PARETO}


def test_no_practical_margins_blocker_and_no_claims_enabled():
    d=frozen_spec(ROOT)
    assert d['study_framing']=='ESTIMATION_FIRST' and d['operationally_meaningful_benefit']=='NOT_DEFINED'
    assert d['calibration_execution_enabled'] and not d['comparative_execution_enabled']
    assert 'operational_margins_unjustified' not in d['blockers']
    assert d['operational_contract']['acceptable_slo_harm'] is None
    assert d['operational_contract']['application_latency_target_seconds']==.25
    assert d['consumer']['headroom']==1.2
    assert not d['estimation']['pvalue_recommendations']
    assert d['precision']['chosen_repetitions'] is None


def test_six_predeclared_neutral_only_trials_and_fresh_bootstrap():
    p=calibration_plan(ROOT)
    assert len(p)==6 and {r['method'] for r in p}=={'pw_6h'}
    assert {r['scenario'] for r in p}=={'stable','periodic'}
    assert all(r['recreate'] and not r['reuse_bootstrap'] for r in p)
    assert sum(r['minimum_wall_seconds'] for r in p)==436.5*3600


@pytest.mark.parametrize('key',PARETO)
def test_strict_dominance_requires_no_better_dimension_and_one_worse(key):
    a=point();b=point();a[key]+=1
    assert pareto_relation(a,b)=='A_STRICTLY_DOMINATED_POINT_ESTIMATES'
    assert pareto_relation(b,a)=='B_STRICTLY_DOMINATED_POINT_ESTIMATES'


def test_equal_or_tradeoff_is_not_strictly_dominated():
    a=point();b=point();assert pareto_relation(a,b)=='EQUAL_POINT_ESTIMATES'
    a['mean_cpu_requested_cores']-=.5;a['slo_violation_rate']+=.1
    assert pareto_relation(a,b)=='RESOURCE_SLO_TRADEOFF_NO_WINNER'
    a['mean_cpu_allocated_cores']=None
    assert pareto_relation(a,b)=='INDETERMINATE_MISSING_ENDPOINT'


def rows():
    return [dict(scenario=s,block=b,method=m,endpoint=value) for s in ('stable','periodic')
        for b in range(4) for m,value in [('pw_6h',float(b)),('static',float(b)+1)]]


def test_pairing_is_run_level_scenario_specific_and_deterministic():
    data=rows();a=paired_effects(data,'stable','pw_6h','static','endpoint',B=200)
    b=paired_effects(data,'stable','pw_6h','static','endpoint',B=200)
    assert a==b and a['n_pairs']==4 and a['mean_effect']==a['median_effect']==-1
    assert a['mean_ci95']==[-1.,-1.] and a['winner'] is None
    assert a['practical_benefit']=='NOT_DEFINED'
    altered=deepcopy(data)
    for row in altered:
        if row['scenario']=='periodic':row['endpoint']*=1e8
    assert paired_effects(altered,'stable','pw_6h','static','endpoint',B=200)==a


def test_undefined_endpoints_or_missing_pairs_are_not_silently_excluded():
    data=rows();data[0]['endpoint']=None
    with pytest.raises(ValueError,match='undefined'):paired_effects(data,'stable','pw_6h','static','endpoint',B=20)
    with pytest.raises(ValueError,match='pairs'):paired_effects(rows()[1:],'stable','pw_6h','static','endpoint',B=20)
    with pytest.raises(ValueError,match='duplicate'):paired_effects(rows()+[rows()[0]],'stable','pw_6h','static','endpoint',B=20)


def test_noise_rejects_multiple_methods_and_does_not_choose_N():
    with pytest.raises(ValueError):calibration_noise([dict(scenario='stable',block=0,method='static')])
    data=[dict(scenario='stable',block=b,method='pw_6h',**{k:float(b) for k in (
        'slo_violation_rate','successful_latency_p95_seconds','mean_cpu_requested_cores','mean_memory_requested_bytes',
        'cpu_utilization_efficiency','memory_utilization_efficiency')}) for b in range(3)]
    report=calibration_noise(data)
    assert report[0]['sample_sd']==1 and report[0]['precision_disposition']=='TARGET_NOT_DEFINED_NO_N_FROZEN'


def test_requests_and_actual_allocations_have_separate_integrals():
    initial={'requests':{'cpu':'1','memory':'100Mi'},'limits':{'cpu':'1','memory':'100Mi'}}
    events=[dict(kind='RECOMMENDATION',disposition='SUBMITTED',acknowledged_ns=2*10**9,recommendation={'cpu_millicores':500,'memory_mib':50}),
        dict(kind='ENFORCED',confirmed_ns=4*10**9,actual_resources={'requests':{'cpu':'500m','memory':'50Mi'}})]
    a=allocation_integrals(0,10,initial,events)
    assert a['mean_cpu_requested_cores']==.6 and a['mean_cpu_allocated_cores']==.7
    assert a['mean_memory_requested_bytes']==60*2**20 and a['mean_memory_allocated_bytes']==70*2**20
    empty=allocation_integrals(0,10,initial,events,intervals=[])
    assert empty['covered_cpu_requested_core_seconds']==0


def test_rejected_request_is_not_resource_savings():
    initial={'requests':{'cpu':'1','memory':'100Mi'}}
    a=allocation_integrals(0,10,initial,[dict(kind='RECOMMENDATION',disposition='REJECTED_OPERATIONAL')])
    assert a['mean_cpu_requested_cores']==a['mean_cpu_allocated_cores']==1


def test_event_stream_uses_stable_bootstrap_and_frozen_dynamic_phase():
    from itertools import islice
    d=frozen_spec(ROOT);p=dict(design=d,load_start_seconds=0,measurement_start_seconds=1,measurement_end_seconds=2,scenario='periodic')
    trace=list(request_events(p))
    assert [r['offset_seconds'] for r in trace]==[0,.25,.5,.75,1.,1.5]
    assert all(r['iterations']==30000 and r['seed']==20251022 for r in trace)
    assert [r['memory_mib'] for r in trace]==[32,32,32,32,32,32]


def test_streaming_generator_retains_late_arrival_latency(monkeypatch):
    from dynapm.system_validation import calibration_workers as w
    monkeypatch.setattr(w.time,'time',lambda:100.)
    monkeypatch.setattr(w.time,'monotonic',lambda:50.)
    monkeypatch.setattr(w.time,'sleep',lambda n:None)
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return b'{}'
    monkeypatch.setattr(w.urllib.request,'urlopen',lambda *a,**k:Reply())
    sink=io.StringIO();n=w.stream_load('http://not-requested.invalid',[dict(offset_seconds=0,iterations=1,memory_mib=0,seed=1)],90.,sink)
    record=json.loads(sink.getvalue())
    assert n==1 and record['latency_seconds']==10 and record['completed_at']-record['scheduled_at']==10


def test_output_inventory_unique_and_no_comparative_cli():
    specs=output_specs();assert len(specs)==len({s.path for s in specs})
    assert any(s.path=='outputs/bootstrap_samples.jsonl' for s in specs)
    result=subprocess.run([sys.executable,'-m','dynapm.scripts.task34_system_calibration','--method','static'],cwd=ROOT,capture_output=True)
    assert result.returncode==2


def test_measured_worker_http_initialize_and_periodic_commit(tmp_path):
    """UNIT fixture, not an elapsed real bootstrap or system comparison."""
    from dynapm.tests.test_system_trial_preparation import unit_evidence,START,END,STEP
    from dynapm.system_validation.smoke import free_port,http,wait_http
    from dynapm.core.run_store import write_json
    root=tmp_path/'run';(root/'outputs').mkdir(parents=True)
    with (root/'outputs/bootstrap_samples.jsonl').open('w') as file:
        for entry in unit_evidence():file.write(canonical_json(entry)+'\n')
    plan=tmp_path/'plan.json';write_json(plan,dict(design=frozen_spec(ROOT),bootstrap_start_seconds=START//10**9,
        measurement_start_seconds=END//10**9))
    port=free_port();url=f'http://127.0.0.1:{port}'
    p=subprocess.Popen([sys.executable,'-m','dynapm.system_validation.calibration_workers','profile',
        '--plan',str(plan),'--root',str(root),'--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        wait_http(url+'/healthz',timeout=20)
        initial=http(url+'/initialize',{})
        assert initial['accepted_bootstrap_slots']==288
        for slot in range(1,73):
            q=END+slot*STEP
            after=http(url+'/observe',dict(logical_slot_ns=q,host_receipt_start_ns=q-299*10**9,
                host_receipt_end_ns=q-10**9,available_at_ns=q,cpu_percent=1.,memory_percent=100*40/512))
        assert after['accounting']['n_refresh_events']==after['accounting']['n_periodic_refreshes']==1
        assert after['accounting']['n_field_writes']==4
        stats=http(url+'/stats')
        assert len(stats['thread_step_cpu_seconds'])==72 and stats['process']['rss_bytes']>0
        assert stats['initialization']['accepted_slots']==288
    finally:p.terminate();p.communicate(timeout=10)


def test_controller_worker_preserves_actual_enforcement_and_costs(monkeypatch,tmp_path):
    from dynapm.system_validation import calibration_workers as w
    root=tmp_path;out=root/'outputs';out.mkdir()
    d=frozen_spec(ROOT);commands=out/'controller_commands.jsonl'
    snapshot={'profile':{'dynamic':{'predicted_cpu_p95_next_24h':5.,'predicted_mem_p95_next_24h':9.375}}}
    commands.write_text(canonical_json(dict(nominal_time_ns=1,snapshot_read_started_ns=time.time_ns(),snapshot=snapshot))+'\n'+canonical_json({'stop':True})+'\n')
    class FakeKube:
        def __init__(self,*args):self.changed=False
        def pod(self):
            r={'requests':{'cpu':'60m' if self.changed else '1','memory':'64Mi' if self.changed else '512Mi'},
                'limits':{'cpu':'60m' if self.changed else '1','memory':'64Mi' if self.changed else '512Mi'}}
            return {'metadata':{'uid':'fixed'},'spec':{'containers':[{'resources':r}]},
                'status':{'containerStatuses':[{'resources':r,'restartCount':0}]}}
        def resize(self,*args):self.changed=True;return {'metadata':{'generation':2}}
    monkeypatch.setattr(w,'Kube',FakeKube)
    monkeypatch.setattr(w,'http',lambda url:dict(cpu_limit_cores=.06,memory_limit_bytes=64*2**20))
    monkeypatch.setattr(w.time,'sleep',lambda n:None)
    w.controller(dict(design=d,cluster='unit',app_url='http://not-requested.invalid'),root,'unused-private-config')
    status=read_json(out/'controller_status.json')
    assert status['complete'] and status['counters']['resource_changes']==1
    events=[json.loads(s) for s in (out/'decisions.jsonl').read_text().splitlines()]
    assert events[0]['disposition']=='SUBMITTED' and events[1]['kind']=='ENFORCED'
    assert status['counters']['cpu_churn_millicores']==940 and status['counters']['memory_churn_mib']==448


def test_application_handler_attribution_keeps_workload_and_telemetry_separate(monkeypatch):
    import urllib.request
    from http.server import ThreadingHTTPServer
    from dynapm.system_validation import application_instrumented as a
    monkeypatch.setattr(a.base,'read_cgroup',lambda:dict(instance_id='UNIT',cpu_seconds=1,memory_current_bytes=1,
        memory_working_set_bytes=1,cpu_limit_cores=1,memory_limit_bytes=512*2**20,cpu_throttled_periods=0,oom_kills=0))
    monkeypatch.setattr(a,'clock_domain',lambda:dict(boot_id='UNIT',time_namespace='UNIT',hostname='UNIT'))
    server=ThreadingHTTPServer(('127.0.0.1',0),a.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        with urllib.request.urlopen(url+'/work?iterations=100&memory_mib=0&seed=20251022') as r:assert json.load(r)['ok']
        with urllib.request.urlopen(url+'/telemetry') as r:sample=json.load(r)
        assert sample['work_handler_cpu_seconds_total']>0 and sample['persistent_workset_bytes']==0
        with urllib.request.urlopen(url+'/metrics') as r:text=r.read().decode()
        assert 'dynapm_application_work_handler_cpu_seconds_total' in text
        assert 'dynapm_application_telemetry_handler_cpu_seconds_total' in text
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


def test_other_containers_are_preserved_and_refused():
    from dynapm.system_validation.calibration_runner import require_isolated_engine
    class Fake:
        def run(self,args):
            assert args==['docker','ps','--format','{{.Names}}']
            return 'unrelated-database\n'
    with pytest.raises(ValueError,match='preserved'):require_isolated_engine(Fake())


def test_only_owned_cluster_nodes_are_allowed_during_collection():
    from dynapm.system_validation.calibration_runner import require_isolated_engine
    class Fake:
        def run(self,args):return 'unit-control-plane\nunit-worker\n'
    assert len(require_isolated_engine(Fake(),'unit'))==2


def test_complete_trial_summary_with_operational_harm_and_cost_attribution(tmp_path):
    """Complete synthetic result schema catches errors before a multi-day trial."""
    from dynapm.system_validation.calibration_runner import summarize
    from dynapm.core.run_store import write_json
    root=tmp_path;out=root/'outputs';out.mkdir()
    def lines(name,rows):
        (out/(name+'.jsonl')).write_text(''.join(canonical_json(r)+'\n' for r in rows))
    initial={'requests':{'cpu':'1','memory':'100Mi'},'limits':{'cpu':'1','memory':'100Mi'}}
    lines('requests',[dict(scheduled_at=t,completed_at=t+.1,latency_seconds=.1,success=True,dropped=False) for t in (-.05,1.,5.)])
    lines('telemetry',[dict(sample_time_ns=i*5*10**9,received_at_ns=i*5*10**9,instance_id='UNIT',cpu_seconds=i*.2,
        memory_working_set_bytes=40*2**20,cpu_limit_cores=1.,memory_limit_bytes=100*2**20,
        cpu_throttled_periods=0,cpu_periods=i,oom_kills=0,
        work_handler_cpu_seconds_total=i*.15,telemetry_handler_cpu_seconds_total=i*.025,
        health_handler_cpu_seconds_total=i*.025) for i in range(3)])
    events=[dict(kind='RECOMMENDATION',disposition='SUBMITTED',acknowledged_ns=2*10**9,
        recommendation=dict(cpu_millicores=500,memory_mib=50),compute_wall_seconds=.001),
        dict(kind='ENFORCED',confirmed_ns=4*10**9,actual_resources={'requests':{'cpu':'500m','memory':'50Mi'}},actuation_latency_seconds=2.),
        dict(kind='POD_OBSERVATION',wall_ns=0,status={'containerStatuses':[dict(restartCount=0,lastState={})]}),
        dict(kind='POD_OBSERVATION',wall_ns=5*10**9,status={'containerStatuses':[dict(restartCount=1,
            lastState={'terminated':{'reason':'OOMKilled','finishedAt':'unit-clock'}})]})]
    lines('decisions',events)
    baseline=dict(phase='measurement_start_before_initialization',profile={'cpu_seconds':1.},
        controller={'cpu_seconds':2.},generator={'cpu_seconds':3.},prometheus={'process_cpu_seconds_total':4.})
    measure=dict(phase='MEASUREMENT',profile={'rss_bytes':100},controller={'rss_bytes':200},
        generator={'rss_bytes':300},prometheus={'process_cpu_seconds_total':5.,'process_resident_memory_bytes':400})
    lines('overhead',[baseline,measure])
    write_json(out/'resize_preflight.json',{'unchanged_actual_resources':initial})
    write_json(out/'controller_status.json',dict(process={'cpu_seconds':3.},counters={'resource_changes':1}))
    write_json(out/'profile_initial.json',dict(profile={'dynamic':{'predicted_cpu_p95_next_24h':1.,'predicted_mem_p95_next_24h':10.}},
        bootstrap_thresholds={'cpu':{'p95':1.},'memory':{'p95':10.}}))
    write_json(out/'profile_final.json',dict(accounting={'n_refresh_events':0},maintenance_step_wall_seconds=[.002]))
    write_json(out/'attribution.json',dict(process={'cpu_seconds':2.},thread_step_cpu_seconds=[.001]))
    r=summarize(root,dict(measurement_start_seconds=0.,measurement_end_seconds=10.,scenario='stable',block=0,design=frozen_spec(ROOT)))
    assert r['method']=='pw_6h' and r['offered']==2 and r['successful_throughput_rps']==.3
    assert r['mean_cpu_requested_cores']==.6 and r['mean_cpu_allocated_cores']==.7
    assert r['application_restarts_observed']==r['observed_oom_terminations_lower_bound']==1
    assert r['maintenance_process_cpu_seconds']==r['controller_process_cpu_seconds']==r['prometheus_process_cpu_seconds']==1.
    assert r['maintenance_step_thread_cpu_seconds_total']==.001
    assert r['profile_rss_p95_bytes']==100 and r['actuation_latency_p95_seconds']==2.
    assert r['practical_benefit']=='NOT_DEFINED' and not r['policy_comparison']
    assert isinstance(canonical_json(r),str)


@pytest.mark.parametrize('ids',[[0,0],[0],[0,2]])
def test_missing_duplicate_request_records_rejected(tmp_path,ids):
    from dynapm.system_validation.calibration_runner import verify_request_stream
    p=tmp_path/'requests.jsonl';p.write_text(''.join(canonical_json({'request_id':i})+'\n' for i in ids))
    with pytest.raises(ValueError,match='request_stream'):verify_request_stream(p,2)
