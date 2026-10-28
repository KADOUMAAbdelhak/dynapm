"""V7A contracts; no cluster launch or scientific comparative execution."""
from pathlib import Path
from copy import deepcopy
import pandas as pd
import pytest
from dynapm.core.provenance import read_json
from dynapm.system_validation.design import parameters,frozen_design,resource_manifests,RUNTIME
from dynapm.system_validation.adapter import ProfileAdapter,aggregate_bucket
from dynapm.system_validation.consumer import recommend,resource_patch,resources_match,summarize_requests,resource_metrics
from dynapm.system_validation.workloads import offered_trace,workload_state
from dynapm.system_validation.application import read_cgroup,metrics
from dynapm.system_validation.smoke import guard_local_endpoint,guard_local_api,Kube,output_specs,wait_http
ROOT=Path(__file__).resolve().parents[2]
ANCHOR=pd.Timestamp('2026-01-01T00:00Z').value
D=parameters()
FIXTURE={'role':'SYNTHETIC_SMOKE_FIXTURE','slots':288,'cpu_millicores':50,'memory_mib':48}


def payload(step=1):
    t=ANCHOR+step*300*10**9
    return dict(logical_slot_ns=t,source_start_ns=t-299*10**9,source_end_ns=t-10**9,available_at_ns=t,cpu_percent=5.,memory_percent=9.375)


@pytest.mark.parametrize('method',D['methods'])
def test_five_existing_observation_policies(method):
    a=ProfileAdapter(method,ANCHOR,D,FIXTURE);p=payload()
    assert not a.policy.requires_predictors and not a.policy.requires_residuals
    assert a.snapshot()['accounting']['n_initialization_events']==1
    r=a.observe(p,wall_ns=p['logical_slot_ns'])
    assert r['real_observations']==1 and r['accounting']['n_refresh_events']==int(method=='full_rewrite')
    assert recommend(r['profile'],D)==dict(controller_version=D['consumer']['version'],cpu_millicores=60,memory_mib=64)
    if method.startswith('pw_'):assert a.policy._period_hours==float(method[3:-1])


def test_overhead_post_commit_and_duplicate_rejection():
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload();r=a.observe(p,wall_ns=p['logical_slot_ns'])
    assert r['accounting']['n_refresh_events']==1 and r['accounting']['n_field_writes']==4
    assert len(r['maintenance_step_wall_seconds'])==1
    assert 'dynapm_profile_process_cpu_seconds_total' in a.metrics()
    assert 'dynapm_profile_process_resident_memory_bytes' in a.metrics()
    with pytest.raises(ValueError,match='nonincreasing'):a.observe(p,wall_ns=p['logical_slot_ns'])


@pytest.mark.parametrize('field,delta',[('available_at_ns',1),('source_end_ns',10**9+1),('source_start_ns',-2*10**9)])
def test_future_or_outside_bucket_invisible(field,delta):
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload();now=p['logical_slot_ns'];p[field]+=delta
    with pytest.raises(ValueError,match='incomplete_or_future'):a.observe(p,wall_ns=now)
    assert a.snapshot()['real_observations']==0


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1])
def test_nonfinite_negative_never_committed(value):
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload();p['cpu_percent']=value
    with pytest.raises(ValueError):a.observe(p,wall_ns=p['logical_slot_ns'])
    assert a.snapshot()['accounting']['n_refresh_events']==0


def test_gap_absent_not_filled_and_predictors_rejected():
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload(2);a.observe(p,wall_ns=p['logical_slot_ns'])
    assert pd.Timestamp(ANCHOR+300*10**9,tz='UTC') not in a.history.index
    assert len(a.history)==289
    with pytest.raises(ValueError):ProfileAdapter('dynapm_v3',ANCHOR,D,FIXTURE)
    with pytest.raises(ValueError):ProfileAdapter('static',ANCHOR,D,{**FIXTURE,'role':'real'})


def samples():
    return [dict(sample_time_ns=i*5*10**9,received_at_ns=i*5*10**9,instance_id='pod',cpu_seconds=i*.01,
        memory_working_set_bytes=48*2**20,cpu_limit_cores=1,memory_limit_bytes=512*2**20,
        cpu_throttled_periods=0,cpu_periods=i,oom_kills=0) for i in range(60)]


def test_bucket_actual_span_fixed_reference():
    s=samples();r=aggregate_bucket(s,0,300*10**9,D)
    assert r['available_at_ns']==300*10**9 and r['source_end_ns']==295*10**9
    assert r['cpu_percent']==pytest.approx(.2) and r['memory_percent']==9.375
    for x in s:x['cpu_limit_cores']=.1
    assert aggregate_bucket(s,0,300*10**9,D)==r


@pytest.mark.parametrize('fault',['short','duplicate','reset','restart','too_few'])
def test_invalid_bucket(fault):
    s=samples()
    if fault=='short':s=s[:51]
    if fault=='too_few':s=s[:20]
    if fault=='duplicate':s[1]['sample_time_ns']=0
    if fault=='reset':s[30]['cpu_seconds']=0
    if fault=='restart':s[30]['instance_id']='different'
    with pytest.raises(ValueError):aggregate_bucket(s,0,300*10**9,D)


def test_recommendation_clamps_quantizes_and_matches_real_resources():
    p={'dynamic':{'predicted_cpu_p95_next_24h':0,'predicted_mem_p95_next_24h':0}}
    r=recommend(p,D);assert (r['cpu_millicores'],r['memory_mib'])==(50,64)
    p['dynamic']={k:1e6 for k in p['dynamic']};r=recommend(p,D)
    assert (r['cpu_millicores'],r['memory_mib'])==(1000,512)
    assert resources_match(resource_patch(r)['spec']['containers'][0]['resources'],r)
    assert not resources_match(None,r)
    assert not resources_match({'limits':{'cpu':'1','memory':'64Mi'}},r)
    p['dynamic']['predicted_cpu_p95_next_24h']=float('nan')
    with pytest.raises(ValueError):recommend(p,D)


@pytest.mark.parametrize('scenario',D['scenarios'])
def test_deterministic_shared_offered_trace(scenario):
    a=offered_trace(scenario,10,D);assert a==offered_trace(scenario,10,D)
    assert all(x['seed']==20251022 for x in a)
    assert len({x['offset_seconds'] for x in a})==len(a)


def test_scenario_boundaries():
    assert workload_state('periodic',0,D)==(2,32)
    assert workload_state('periodic',3.5*3600,D)==(12,96)
    assert workload_state('burst',3600,D)==(20,160)
    assert workload_state('abrupt_regime_shift',24*3600,D)==(12,96)
    assert len(offered_trace('stable',300,D,smoke=True))==600


def test_slo_denominator_failure_and_completion_throughput():
    r=[dict(scheduled_at=0.,completed_at=.1,latency_seconds=.1,success=True,dropped=False),
       dict(scheduled_at=1.,completed_at=1.,latency_seconds=None,success=False,dropped=True),
       dict(scheduled_at=2.,completed_at=10.,latency_seconds=8.,success=True,dropped=False)]
    m=summarize_requests(r,0,3,.25)
    assert m['slo_violation_rate']==pytest.approx(2/3)
    assert m['generator_drops']==1 and m['successful_throughput_rps']==pytest.approx(1/3)
    assert m['successful_latency_p95_seconds']>m['successful_latency_p50_seconds']


def test_cgroup_values_and_prometheus_export(monkeypatch,tmp_path):
    from dynapm.system_validation import application
    for name,text in {'cpu.stat':'usage_usec 2000000\nnr_periods 10\nnr_throttled 2\nthrottled_usec 400\n',
        'memory.stat':'inactive_file 10\n','memory.events':'oom_kill 0\n','cpu.max':'6000 100000',
        'memory.max':'67108864','memory.current':'1000'}.items():(tmp_path/name).write_text(text)
    c=read_cgroup(tmp_path);assert c['cpu_seconds']==2 and c['cpu_limit_cores']==.06
    assert c['memory_working_set_bytes']==990
    monkeypatch.setattr(application,'read_cgroup',lambda:c)
    text=metrics();assert text.endswith('\n') and '# TYPE dynapm_application_handler_seconds histogram' in text
    assert 'dynapm_application_cgroup_cpu_seconds_total 2.0' in text


def test_measured_resource_metrics_censored_demand_caveat():
    m=resource_metrics(samples());assert m['valid_seconds']==295
    assert m['mean_cpu_used_cores']==pytest.approx(.002)
    assert m['cpu_utilization_efficiency']==pytest.approx(.002)
    assert m['cpu_observed_deficit_core_seconds']==0 and 'censor' in m['limitation']


@pytest.mark.parametrize('endpoint',['tcp://localhost:2375','ssh://host','https://remote'])
def test_remote_docker_rejected(endpoint):
    with pytest.raises(ValueError):guard_local_endpoint(endpoint)


@pytest.mark.parametrize('endpoint',['https://prod.example:6443','http://localhost:6443','https://10.0.0.1'])
def test_remote_kubernetes_rejected(endpoint):
    with pytest.raises(ValueError):guard_local_api(endpoint)


def test_context_private_config_least_privilege():
    class Fake:
        def run(self,args,**kw):self.args=args;return '{}'
    c=Fake();k=Kube(c,'/tmp/private/config','dynapm-v7a-smoke-test',D);k.pod()
    assert '--kubeconfig' in c.args and '--context' in c.args and '--as' in c.args
    assert 'system:serviceaccount:dynapm-v7a-smoke:profile-consumer' in c.args
    with pytest.raises(ValueError):Kube(c,'x','unrelated',D)
    role=next(x for x in resource_manifests(D)['items'] if x['kind']=='Role')
    assert role['rules']==[dict(apiGroups=[''],resources=['pods'],resourceNames=['application'],verbs=['get']),
        dict(apiGroups=[''],resources=['pods/resize'],resourceNames=['application'],verbs=['patch'])]


def test_frozen_config_and_no_comparative_path():
    d=frozen_design(ROOT);assert not d['claim_trials_enabled'] and not d['future_trials']['enabled']
    assert d['methods']==['static','pw_12h','pw_6h','pw_3h','full_rewrite']
    assert d['core_protocol']=='causal-timeline-v3' and d['smoke']['real_buckets']==1
    assert d['future_trials']['repeats'] is None and set(RUNTIME)==set(d['scientific_runtime_sha256'])
    specs=output_specs();assert len({s.path for s in specs})==len(specs)
    assert any(s.path=='outputs/actuation.json' for s in specs)


def test_manifests_qos_tokens_labels_pinned_images():
    r=read_json(ROOT/'harness/system/resources.json')
    a=next(x for x in r['items'] if x['kind']=='Pod' and x['metadata']['name']=='application')
    c=a['spec']['containers'][0];assert c['resources']['requests']==c['resources']['limits']
    assert not a['spec']['automountServiceAccountToken']
    assert all(x['restartPolicy']=='NotRequired' for x in c['resizePolicy'])
    assert a['metadata']['labels']['app']=='dynapm-workload'
    assert '@sha256:' in D['kubernetes']['python_image'] and '@sha256:' in D['kubernetes']['node_image']


def test_prometheus_plain_text_readiness(monkeypatch):
    from dynapm.system_validation import smoke
    monkeypatch.setattr(smoke,'text_http',lambda url:'Prometheus Server is Ready.\n')
    assert 'Ready' in wait_http('http://localhost/-/ready')


def test_prometheus_native_wrapper_retains_pinned_upstream_and_no_remote_pull():
    d=frozen_design(ROOT)
    dockerfile=(ROOT/'harness/system/Prometheus.Dockerfile').read_text()
    assert dockerfile.splitlines()[0]=='FROM '+d['kubernetes']['prometheus_image']
    assert len(dockerfile.splitlines())==2 and dockerfile.splitlines()[1].startswith('LABEL ')
    r=read_json(ROOT/'harness/system/resources.json')
    p=next(x for x in r['items'] if x['kind']=='Pod' and x['metadata']['name']=='prometheus')
    assert p['spec']['containers'][0]['image']==d['kubernetes']['prometheus_local_image']
    assert p['spec']['containers'][0]['imagePullPolicy']=='Never'


def test_success_must_follow_confirmed_enforcement_not_patch_acknowledgement():
    from dynapm.system_validation.smoke import successful_post_enforcement
    records=[dict(success=True,sent_at=1.5)]
    assert not successful_post_enforcement(records,2*10**9)
    records.append(dict(success=True,sent_at=2.1))
    assert successful_post_enforcement(records,2*10**9)


def test_snapshot_explicitly_records_actual_wall_read_after_commit():
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload()
    r=a.observe(p,wall_ns=p['logical_slot_ns'])
    assert r['snapshot_wall_time_ns']>=r['last_commit_wall_ns']
    assert r['last_nominal_slot_ns']==p['logical_slot_ns']


def test_committed_refresh_is_canonical_json_serializable():
    from dynapm.core.provenance import canonical_json
    a=ProfileAdapter('full_rewrite',ANCHOR,D,FIXTURE);p=payload()
    r=a.observe(p,wall_ns=p['logical_slot_ns'])
    assert '2026-01-01T00:05:00+00:00' in canonical_json(r)
    assert isinstance(r['refresh_log'][0]['actual_commit_time'],str)


def test_profile_service_real_http_round_trip():
    import subprocess,sys,time
    from dynapm.system_validation.smoke import http,free_port,wait_http
    port=free_port();url=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([sys.executable,'-m','dynapm.system_validation.adapter','--repo',str(ROOT),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        wait_http(url+'/healthz',timeout=20)
        initial=http(url+'/initialize',dict(method='full_rewrite',anchor_ns=ANCHOR))
        assert initial['accounting']['n_refresh_events']==0
        result=http(url+'/observe',payload())
        assert result['accounting']['n_refresh_events']==1
        assert isinstance(result['refresh_log'][0]['actual_commit_time'],str)
        assert http(url+'/snapshot')['real_observations']==1
    finally:
        process.terminate();process.communicate(timeout=10)
