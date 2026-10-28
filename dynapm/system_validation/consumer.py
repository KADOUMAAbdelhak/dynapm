"""One fixed, observation-only profile-to-resource consumer for all five methods."""
import math
import numpy as np


def recommend(profile,design):
    dynamic=profile['dynamic'];refs=design['references'];c=design['consumer']
    cpu=float(dynamic['predicted_cpu_p95_next_24h'])*refs['cpu_millicores']/100
    mem=float(dynamic['predicted_mem_p95_next_24h'])*refs['memory_mib']/100
    if not all(math.isfinite(x) and x>=0 for x in (cpu,mem)):raise ValueError('finite_nonnegative_profile_required')
    def quantity(value,resource):
        raw=math.ceil(c['headroom']*value/c[resource+'_quantum'])*c[resource+'_quantum']
        return int(min(c[resource+'_maximum'],max(c[resource+'_minimum'],raw)))
    return dict(controller_version=c['version'],cpu_millicores=quantity(cpu,'cpu_millicores'),memory_mib=quantity(mem,'memory_mib'))


def resource_patch(recommendation):
    resources={'cpu':str(recommendation['cpu_millicores'])+'m','memory':str(recommendation['memory_mib'])+'Mi'}
    return {'spec':{'containers':[{'name':'workload','resources':{'requests':resources.copy(),'limits':resources.copy()}}]}}


def cpu_millicores(value):
    return float(value[:-1]) if value.endswith('m') else float(value)*1000


def memory_bytes(value):
    for suffix,power in [('Ki',10),('Mi',20),('Gi',30)]:
        if value.endswith(suffix):return int(float(value[:-len(suffix)])*2**power)
    return int(value)


def resources_match(resources,recommendation):
    try:
        return all(abs(cpu_millicores(resources[k]['cpu'])-recommendation['cpu_millicores'])<1e-6 and
            memory_bytes(resources[k]['memory'])==recommendation['memory_mib']*2**20 for k in ['requests','limits'])
    except (KeyError,TypeError,ValueError):return False


def summarize_requests(records,start,end,slo):
    selected=[r for r in records if start<=r['scheduled_at']<end]
    successful=[r['latency_seconds'] for r in selected if r['success']]
    return dict(scope='SMOKE_DIAGNOSTICS_NOT_COMPARATIVE_EVIDENCE',offered=len(selected),successful=len(successful),
        failures=sum(not r['success'] for r in selected),generator_drops=sum(r['dropped'] for r in selected),
        slo_violation_rate=sum(not r['success'] or r['latency_seconds']>slo for r in selected)/len(selected) if selected else None,
        successful_latency_p50_seconds=float(np.quantile(successful,.5)) if successful else None,
        successful_latency_p95_seconds=float(np.quantile(successful,.95)) if successful else None,
        successful_latency_p99_seconds=float(np.quantile(successful,.99)) if successful else None,
        successful_completed_in_window=sum(r['success'] and start<=r['completed_at']<end for r in records),
        successful_throughput_rps=sum(r['success'] and start<=r['completed_at']<end for r in records)/(end-start))


def resource_metrics(samples):
    """Measured-used resource proxies, not uncensored latent demand or money."""
    intervals=[]
    for previous,current in zip(samples,samples[1:]):
        dt=(current['sample_time_ns']-previous['sample_time_ns'])/1e9
        if dt<=0 or current['instance_id']!=previous['instance_id'] or current['cpu_seconds']<previous['cpu_seconds']:continue
        used=(current['cpu_seconds']-previous['cpu_seconds'])/dt
        requested=previous['cpu_limit_cores'];memory_request=previous['memory_limit_bytes'];memory_used=previous['memory_working_set_bytes']
        if requested is None or memory_request is None:continue
        intervals.append(dict(seconds=dt,cpu_used_cores=used,cpu_requested_cores=requested,memory_used_bytes=memory_used,
            memory_requested_bytes=memory_request,cpu_unused_reservation_core_seconds=max(0,requested-used)*dt,
            memory_unused_reservation_byte_seconds=max(0,memory_request-memory_used)*dt,
            cpu_observed_deficit_core_seconds=max(0,used-requested)*dt,
            memory_observed_deficit_byte_seconds=max(0,memory_used-memory_request)*dt,
            cpu_throttled_periods=max(0,current['cpu_throttled_periods']-previous['cpu_throttled_periods']),
            cpu_periods=max(0,current['cpu_periods']-previous['cpu_periods']),oom_kills=max(0,current['oom_kills']-previous['oom_kills'])))
    seconds=sum(r['seconds'] for r in intervals)
    cpu_budget=sum(r['cpu_requested_cores']*r['seconds'] for r in intervals);memory_budget=sum(r['memory_requested_bytes']*r['seconds'] for r in intervals)
    return dict(valid_interval_count=len(intervals),valid_seconds=seconds,
        requested_source='observed cgroup limits; requests equal limits under fixed Guaranteed QoS, validated against Pod status',
        mean_cpu_requested_cores=cpu_budget/seconds if seconds else None,
        mean_cpu_used_cores=sum(r['cpu_used_cores']*r['seconds'] for r in intervals)/seconds if seconds else None,
        mean_memory_requested_bytes=memory_budget/seconds if seconds else None,
        mean_memory_used_bytes=sum(r['memory_used_bytes']*r['seconds'] for r in intervals)/seconds if seconds else None,
        cpu_utilization_efficiency=sum(r['cpu_used_cores']*r['seconds'] for r in intervals)/cpu_budget if cpu_budget else None,
        memory_utilization_efficiency=sum(r['memory_used_bytes']*r['seconds'] for r in intervals)/memory_budget if memory_budget else None,
        **{key:sum(r[key] for r in intervals) for key in ['cpu_unused_reservation_core_seconds','memory_unused_reservation_byte_seconds',
            'cpu_observed_deficit_core_seconds','memory_observed_deficit_byte_seconds','cpu_throttled_periods','cpu_periods','oom_kills']},
        limitation='CPU/memory limits censor demand; observed deficits are lower-bound proxies, report throttling/OOM/SLO jointly')
