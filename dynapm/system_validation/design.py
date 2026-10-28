"""V7A fixed consumer/scenarios/endpoints. No claim-generating run path."""
from pathlib import Path
from dynapm.core.provenance import read_json,fingerprint,file_sha256,canonical_json
from dynapm.core.run_store import write_json
from dynapm.core.temporal import TEMPORAL_PROTOCOL,EVALUATION_GRID
from dynapm.core.accounting import ACCOUNTING_SCHEMA
from dynapm.experiments.confirmatory_design import PRIMARY_METHODS,emit_yaml

SPEC='configs/system_validation_v1.json'
YAML='configs/system_validation_v1.yaml'
RUNTIME=('.dockerignore','dynapm/system_validation/design.py','dynapm/system_validation/application.py',
    'dynapm/system_validation/workloads.py','dynapm/system_validation/install_tools.py','dynapm/system_validation/adapter.py',
    'dynapm/system_validation/consumer.py','dynapm/system_validation/smoke.py',
    'dynapm/scripts/task32_system_harness.py','harness/system/Prometheus.Dockerfile','harness/system/Dockerfile','harness/system/kind.yaml',
    'harness/system/resources.json','harness/system/fixtures/smoke/bootstrap.json',
    'harness/system/fixtures/smoke/workload.json',
    'dynapm/core/temporal.py','dynapm/core/accounting.py','dynapm/core/schema.py',
    'dynapm/core/discretization.py','dynapm/core/forecasting.py','dynapm/methods/baselines_v2.py',
    'dynapm/methods/factories.py','dynapm/experiments/confirmatory_execution.py')


def parameters():
    return dict(schema_version='system-profile-provisioning-v1',gate='V7A',scope='SCAFFOLD_AND_LOCAL_SMOKE_ONLY',
        question='How do the five maintained observation-profile contracts affect the same resource recommender, enforced Kubernetes allocations, application SLO and resource use?',
        methods=list(PRIMARY_METHODS),consumer_only_difference='profile maintenance policy; same workload/seed/consumer/limits/actuation/read rules',
        core_protocol=TEMPORAL_PROTOCOL,accounting_schema=ACCOUNTING_SCHEMA,offline_evaluation_grid=EVALUATION_GRID,
        system_clock='system-completed-bucket-wall-read-v1',claim_trials_enabled=False,
        references=dict(cpu_millicores=1000,memory_mib=512,rule='fixed bootstrap reference, never current changing requests'),
        consumer=dict(version='p95-fixed-headroom-quantized-v1',headroom=1.2,
            cpu_millicores_quantum=10,cpu_millicores_minimum=50,cpu_millicores_maximum=1000,
            memory_mib_quantum=4,memory_mib_minimum=64,memory_mib_maximum=512,
            rule='ceil(headroom * maintained p95 physical value / quantum) * quantum then clamp; requests=limits; classes diagnostic only',
            decision_cadence_seconds=300,one_inflight_resize=True,changed_quantities_only=True,
            signal_inputs='CPU/memory maintained p95 only; no SLO feedback, prediction, adaptive detector, smoothing or tuned hysteresis'),
        telemetry=dict(bucket_seconds=300,poll_seconds=5,min_samples=50,min_span_seconds=270,
            fence='all source sample times inside [bucket_start,bucket_end]; available only after bucket_end and receipt; incomplete buckets absent',
            cpu='counter difference over actual in-bucket source span, cores; no extrapolation',
            memory='mean of actual cgroup working-set bytes in bucket',max_clock_skew_seconds=2,
            no_interpolation=True,no_clipping=True,late_read='record wall receive/commit/read times separately from nominal policy slot; never consume incomplete source'),
        workload=dict(seed=20251022,iterations=30000,timeout_seconds=5,max_concurrency=32,arrival='deterministic open loop; overload drops recorded as failures',
            generator_location='host through fixed localhost kubectl port-forward; transport part of measured system, not production ingress'),
        scenarios=dict(stable=dict(rps=4,memory_mib=32),
            periodic=dict(low_rps=2,high_rps=12,low_memory_mib=32,high_memory_mib=96,period_seconds=7*3600),
            burst=dict(low_rps=4,high_rps=20,low_memory_mib=32,high_memory_mib=160,period_seconds=5*3600,first_burst_seconds=3600,burst_seconds=20*60),
            abrupt_regime_shift=dict(low_rps=4,high_rps=12,low_memory_mib=32,high_memory_mib=96,shift_seconds=24*3600)),
        future_trials=dict(bootstrap_seconds=24*3600,measurement_seconds=48*3600,bootstrap_workload='stable',
            bootstrap_source='actual completed telemetry only; no fixture or time compression',
            primary_unit='independent run/scenario replicate, never requests or telemetry points',
            repeats=None,precision_power_plan_required=True,randomized_counterbalanced_order_required=True,
            practical_margins=None,enabled=False,independent_run_reset=True),
        slo=dict(latency_seconds=.250,violation='failed/timed-out/dropped OR arrival-to-completion > target, divided by offered requests'),
        endpoints=dict(slo_violation_rate='all offered requests, failures included; run-level endpoint',
            latency_p50_p95_p99='successful arrival-to-completion latency including generator lag; failure/timeout denominator reported separately',
            throughput='successful completions within fixed window / window seconds',
            requested_cpu_memory='desired Pod spec and observed status; Guaranteed requests=limits; cgroup confirmation',
            used_cpu_memory='actual CPU-counter rates and cgroup memory working set',
            utilization_efficiency='resource-time used / resource-time requested, separately CPU and memory',
            over_provisioning='integral max(request-used,0), resource-time units; not money',
            under_provisioning='observed deficit lower bounds plus CPU throttled-period fraction, memory OOM and SLO; enforced limits censor latent demand',
            resource_changes='actual changed CPU/memory allocations, distinct from profile refreshes; churn=sum absolute per-resource changes',
            recommendation_latency='snapshot read through recommendation computation, wall and process CPU timers',
            actuation_latency='patch submission through status.resources AND cgroup enforcement; record rejected/deferred/timeouts/restarts',
            maintenance_overhead='separate profile service process CPU/RSS, per-step wall/CPU duration, state bytes and refresh/write/change counts'),
        smoke=dict(method='full_rewrite',scenario='stable',real_buckets=1,rps=2,iterations=1000,memory_mib=8,
            post_actuation_seconds=30,scope='NON_CLAIM_PLUMBING_ONLY',synthetic_bootstrap_slots=288,
            synthetic_cpu_millicores=50,synthetic_memory_mib=48,comparative_runs=False,max_elapsed_seconds=1800),
        kubernetes=dict(cluster='dynapm-v7a-smoke',namespace='dynapm-v7a-smoke',context='kind-dynapm-v7a-smoke',
            workload_pod='application',container='workload',server_version='v1.35.8',kind_version='v0.33.0',kubectl_version='v1.35.8',
            tools_directory='.local-tools/system-v1/bin',
            tools_by_platform={'darwin-arm64':{
                'kind':dict(url='https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-darwin-arm64',sha256='0c8c7dbe5e23594a198b786c4bc13dacc101fa6196b0cb0b23a1ca44e61f4b4f'),
                'kubectl':dict(url='https://dl.k8s.io/release/v1.35.8/bin/darwin/arm64/kubectl',sha256='b8be50ae0c6665b646fb009f904a52cad30806deee19ab3b4fe5af2d68bd82eb')}},
            node_image='kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0',
            python_image='python:3.13.2-slim@sha256:6b3223eb4d93718828223966ad316909c39813dee3ee9395204940500792b740',
            prometheus_image='prom/prometheus:v3.2.1@sha256:6927e0919a144aa7616fd0137d4816816d42f6b816de3af269ab065250859a62',
            application_image='dynapm-system-workload:v7a',prometheus_local_image='dynapm-system-prometheus:v7a',actuation='pods/resize strategic merge; NotRequired restart policy; no rollout fallback',
            resource_qos='Guaranteed: requests equal limits before/after resize',local_docker_only=True,
            note='pinned stable in-place resize environment; 1.33 rejected no-restart memory decrease; no controller parameter changes'),
        sources=['https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0',
            'https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/',
            'https://prometheus.io/docs/instrumenting/exposition_formats/'])


def resource_manifests(d):
    k=d['kubernetes'];ns=k['namespace'];labels={'app':'dynapm-workload'}
    def obj(kind,name,spec=None,**extra):
        o=dict(apiVersion='v1',kind=kind,metadata=dict(name=name,namespace=ns))
        if spec is not None:o['spec']=spec
        return {**o,**extra}
    app=obj('Pod','application',dict(automountServiceAccountToken=False,nodeSelector={'dynapm-role':'workload'},
        securityContext=dict(runAsNonRoot=True,runAsUser=1000,runAsGroup=1000,seccompProfile={'type':'RuntimeDefault'}),
        containers=[dict(name='workload',image=k['application_image'],imagePullPolicy='Never',ports=[dict(containerPort=8080)],
            resources=dict(requests=dict(cpu='1000m',memory='512Mi'),limits=dict(cpu='1000m',memory='512Mi')),
            resizePolicy=[dict(resourceName=r,restartPolicy='NotRequired') for r in ('cpu','memory')],
            securityContext=dict(allowPrivilegeEscalation=False,readOnlyRootFilesystem=True,capabilities={'drop':['ALL']}),
            readinessProbe=dict(httpGet=dict(path='/healthz',port=8080),initialDelaySeconds=1,periodSeconds=2))]))
    prom_config='global:\n  scrape_interval: 5s\nscrape_configs:\n  - job_name: dynapm-application\n    static_configs:\n      - targets: ["application:8080"]\n'
    prom=obj('Pod','prometheus',dict(automountServiceAccountToken=False,nodeSelector={'dynapm-role':'control'},
        tolerations=[dict(key='node-role.kubernetes.io/control-plane',operator='Exists',effect='NoSchedule')],
        securityContext=dict(runAsNonRoot=True,runAsUser=65534,runAsGroup=65534,fsGroup=65534),
        containers=[dict(name='prometheus',image=k['prometheus_local_image'],imagePullPolicy='Never',
            args=['--config.file=/etc/prometheus/prometheus.yml','--storage.tsdb.path=/prometheus','--storage.tsdb.retention.time=1h'],
            ports=[dict(containerPort=9090)],resources=dict(requests=dict(cpu='50m',memory='128Mi'),limits=dict(cpu='200m',memory='256Mi')),
            volumeMounts=[dict(name='config',mountPath='/etc/prometheus',readOnly=True),dict(name='data',mountPath='/prometheus')])],
        volumes=[dict(name='config',configMap={'name':'prometheus-config'}),dict(name='data',emptyDir={'sizeLimit':'512Mi'})]))
    role=dict(apiVersion='rbac.authorization.k8s.io/v1',kind='Role',metadata=dict(name='profile-consumer',namespace=ns),
        rules=[dict(apiGroups=[''],resources=['pods'],resourceNames=['application'],verbs=['get']),
               dict(apiGroups=[''],resources=['pods/resize'],resourceNames=['application'],verbs=['get','patch'])])
    binding=dict(apiVersion='rbac.authorization.k8s.io/v1',kind='RoleBinding',metadata=dict(name='profile-consumer',namespace=ns),
        roleRef=dict(apiGroup='rbac.authorization.k8s.io',kind='Role',name='profile-consumer'),
        subjects=[dict(kind='ServiceAccount',name='profile-consumer',namespace=ns)])
    return dict(apiVersion='v1',kind='List',items=[dict(apiVersion='v1',kind='Namespace',metadata={'name':ns}),
        obj('ServiceAccount','profile-consumer'),role,binding,app,
        obj('Service','application',dict(selector=labels,ports=[dict(port=8080,targetPort=8080)])),
        obj('ConfigMap','prometheus-config',data={'prometheus.yml':prom_config}),prom,
        obj('Service','prometheus',dict(selector={'app':'dynapm-prometheus'},ports=[dict(port=9090,targetPort=9090)]))])


def write_design(repo):
    repo=Path(repo);d=parameters();objects=resource_manifests(d)
    for o in objects['items']:
        if o['kind']=='Pod':o['metadata']['labels']={'app':'dynapm-workload' if o['metadata']['name']=='application' else 'dynapm-prometheus'}
    write_json(repo/'harness/system/resources.json',objects)
    image=d['kubernetes']['node_image']
    kind={'kind':'Cluster','apiVersion':'kind.x-k8s.io/v1alpha4',
        'nodes':[{'role':'control-plane','image':image,'labels':{'dynapm-role':'control'}},
                 {'role':'worker','image':image,'labels':{'dynapm-role':'workload'}}]}
    (repo/'harness/system/kind.yaml').write_text(emit_yaml(kind))
    write_json(repo/'harness/system/fixtures/smoke/bootstrap.json',dict(role='SYNTHETIC_SMOKE_FIXTURE',slots=288,
        sample_seconds=300,cpu_millicores=d['smoke']['synthetic_cpu_millicores'],memory_mib=d['smoke']['synthetic_memory_mib']))
    write_json(repo/'harness/system/fixtures/smoke/workload.json',dict(role='SMOKE_ONLY',**d['smoke'],seed=d['workload']['seed']))
    d['scientific_runtime_sha256']={p:file_sha256(repo/p) for p in RUNTIME}
    write_json(repo/SPEC,d);(repo/YAML).write_text('# V7A scaffold; no comparative trials enabled.\n'+emit_yaml(read_json(repo/SPEC)))
    return fingerprint(d)


def frozen_design(repo):
    repo=Path(repo);d=read_json(repo/SPEC);expected=parameters();expected['scientific_runtime_sha256']={p:file_sha256(repo/p) for p in RUNTIME}
    if canonical_json(d)!=canonical_json(expected):raise ValueError('system_design_or_source_mismatch')
    if (repo/YAML).read_text()!='# V7A scaffold; no comparative trials enabled.\n'+emit_yaml(d):raise ValueError('system_design_yaml_mismatch')
    return d
