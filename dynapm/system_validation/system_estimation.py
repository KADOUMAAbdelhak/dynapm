"""Run-level estimation and Pareto diagnostics; no recommendation from p-values."""
import math
import numpy as np
from dynapm.core.provenance import fingerprint
from dynapm.system_validation.trial_preparation import PRIMARY

PARETO=('mean_cpu_requested_cores','mean_memory_requested_bytes','mean_cpu_allocated_cores','mean_memory_allocated_bytes','slo_violation_rate','successful_latency_p95_seconds')


def pareto_relation(a,b):
    """All dimensions minimized; label estimates, never infer population dominance."""
    try:x=np.array([a[k] for k in PARETO],dtype=float);y=np.array([b[k] for k in PARETO],dtype=float)
    except (KeyError,ValueError,TypeError):return 'INDETERMINATE_MISSING_ENDPOINT'
    if not np.isfinite(x).all() or not np.isfinite(y).all():return 'INDETERMINATE_MISSING_ENDPOINT'
    if np.array_equal(x,y):return 'EQUAL_POINT_ESTIMATES'
    if np.all(x>=y) and np.any(x>y):return 'A_STRICTLY_DOMINATED_POINT_ESTIMATES'
    if np.all(y>=x) and np.any(y>x):return 'B_STRICTLY_DOMINATED_POINT_ESTIMATES'
    return 'RESOURCE_SLO_TRADEOFF_NO_WINNER'


def paired_effects(rows,scenario,method,control,endpoint,*,B=10000,seed=20251022):
    """Bootstrap independent paired blocks within exactly one scenario."""
    selected=[r for r in rows if r['scenario']==scenario and r['method'] in (method,control)]
    values={}
    for r in selected:
        key=(r['block'],r['method'])
        if key in values:raise ValueError('duplicate_run_block_method')
        value=r[endpoint]
        if value is None or not math.isfinite(float(value)):raise ValueError('undefined_endpoint_report_limitation_do_not_exclude_run')
        values[key]=float(value)
    blocks=sorted({k[0] for k in values})
    if len(blocks)<2 or any((b,m) not in values for b in blocks for m in (method,control)):
        raise ValueError('complete_independent_run_pairs_required')
    diffs=np.array([values[(b,method)]-values[(b,control)] for b in blocks])
    rng=np.random.default_rng(seed);sample=diffs[rng.integers(len(diffs),size=(B,len(diffs)))]
    return dict(scenario=scenario,method=method,control=control,endpoint=endpoint,n_pairs=len(blocks),
        mean_effect=float(diffs.mean()),median_effect=float(np.median(diffs)),
        mean_ci95=np.quantile(sample.mean(axis=1),[.025,.975]).tolist(),
        median_ci95=np.quantile(np.median(sample,axis=1),[.025,.975]).tolist(),
        inference_unit='independent paired run block',ci_scope='pointwise; not practical significance',
        practical_benefit='NOT_DEFINED',winner=None,negative_null_retained=True)


def calibration_noise(rows):
    """Neutral-method diagnostics only. Never substitutes requests for runs."""
    if any(r['method']!='pw_6h' for r in rows):raise ValueError('calibration_one_neutral_method_only')
    out=[]
    for scenario in sorted({r['scenario'] for r in rows}):
        group=[r for r in rows if r['scenario']==scenario]
        if len({r['block'] for r in group})!=len(group):raise ValueError('duplicate_calibration_replicate')
        for endpoint in PRIMARY+('mean_cpu_allocated_cores','mean_memory_allocated_bytes','bootstrap_cpu_p95','bootstrap_memory_p95','maintenance_process_cpu_seconds','controller_process_cpu_seconds','prometheus_process_cpu_seconds','successful_latency_p50_seconds','successful_latency_p99_seconds','successful_throughput_rps','mean_cpu_used_cores','mean_memory_used_bytes','actuation_latency_p95_seconds','recommendation_latency_p95_seconds','maintenance_step_wall_seconds_total','maintenance_step_thread_cpu_seconds_total','profile_rss_p95_bytes','controller_rss_p95_bytes','prometheus_rss_p95_bytes'):
            values=[r.get(endpoint) for r in group]
            valid=all(v is not None and math.isfinite(float(v)) for v in values)
            out.append(dict(scenario=scenario,endpoint=endpoint,n_runs=len(group),
                mean=float(np.mean(values)) if valid else None,
                median=float(np.median(values)) if valid else None,
                sample_sd=float(np.std(values,ddof=1)) if valid and len(values)>1 else None,
                precision_disposition='TARGET_NOT_DEFINED_NO_N_FROZEN',
                missing_endpoints=sum(v is None or not math.isfinite(float(v)) for v in values)))
    return out


def allocation_integrals(start,end,initial_resources,decisions,*,intervals=None):
    """API-acknowledged requests and confirmed allocations are separate clocks.

    Integrate exact recorded step boundaries; never infer requests from changed-field
    log rows or silently treat an acknowledged resize as enforced allocation.
    """
    from dynapm.system_validation.consumer import cpu_millicores,memory_bytes
    initial=(cpu_millicores(initial_resources['requests']['cpu'])/1000,
             memory_bytes(initial_resources['requests']['memory']))
    desired=[];allocated=[]
    for row in decisions:
        if row['kind']=='RECOMMENDATION' and row.get('disposition')=='SUBMITTED':
            r=row['recommendation'];desired.append((row['acknowledged_ns']/1e9,r['cpu_millicores']/1000,r['memory_mib']*2**20))
        if row['kind']=='ENFORCED':
            r=row['actual_resources']['requests'];allocated.append((row['confirmed_ns']/1e9,cpu_millicores(r['cpu'])/1000,memory_bytes(r['memory'])))
    def integrate(events,low,high):
        cpu,mem=initial;previous=low;cpu_total=0.;mem_total=0.
        for when,new_cpu,new_mem in sorted(events):
            if when<=low:cpu,mem=new_cpu,new_mem;continue
            if when>=high:break
            cpu_total+=cpu*(when-previous);mem_total+=mem*(when-previous)
            previous=when;cpu,mem=new_cpu,new_mem
        return cpu_total+cpu*(high-previous),mem_total+mem*(high-previous)
    requested=integrate(desired,start,end);enforced=integrate(allocated,start,end)
    covered=[(max(start,a),min(end,b)) for a,b in ([(start,end)] if intervals is None else intervals) if max(start,a)<min(end,b)]
    covered_requested=[integrate(desired,a,b) for a,b in covered]
    return dict(mean_cpu_requested_cores=requested[0]/(end-start),mean_memory_requested_bytes=requested[1]/(end-start),
        mean_cpu_allocated_cores=enforced[0]/(end-start),mean_memory_allocated_bytes=enforced[1]/(end-start),
        cpu_requested_core_seconds=requested[0],memory_requested_byte_seconds=requested[1],
        covered_cpu_requested_core_seconds=sum(x[0] for x in covered_requested),
        covered_memory_requested_byte_seconds=sum(x[1] for x in covered_requested),
        definition='desired requests at API acknowledgement; allocation at status+cgroup confirmation; boundary uncertainty retained in raw events')
