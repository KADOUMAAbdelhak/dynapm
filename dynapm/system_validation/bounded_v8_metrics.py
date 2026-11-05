"""Run-level endpoints for fixed physical episodes and paired inference."""
from collections import Counter
from math import isfinite

import numpy as np

from dynapm.system_validation.bounded_v8 import CHECKPOINTS, METHODS, NS, cells, offers
from dynapm.system_validation.system_estimation import PARETO, pareto_relation
from dynapm.system_validation.v8_analysis import ENDPOINTS, interval


def request_metrics(plan, records):
    actual = sorted(records, key=lambda row: row['request_id'])
    for row, expected in zip(actual, offers(plan), strict=True):
        if row['offer'] != expected or row['request_id'] != expected['request_id']:
            raise ValueError('request_stream_does_not_match_frozen_offers')
        due, end, sent = expected['offset_ns'], row['completed_offset_ns'], row['sent_offset_ns']
        if (type(end) is not int or end < due or type(row['success']) is not bool
                or (sent is None) != (row['outcome'] == 'overload_drop')
                or (sent is not None and not due <= sent <= end)
                or row['success'] != (row['outcome'] == 'success')):
            raise ValueError('invalid_request_outcome_or_clock')
    windows = {'primary': (0, plan['measurement_seconds'])}
    if plan['mode'] == 'primary':
        windows.update(transition=(0,300), followup=(300,1800))
    if plan['mode'] == 'integration':
        windows['after_refresh'] = (10800,12600)
    summaries = {}
    for name, (a,b) in windows.items():
        cohort = [r for r in actual if a*NS <= r['offer']['offset_ns'] < b*NS]
        latencies = [(r['completed_offset_ns']-r['offer']['offset_ns'])/NS for r in cohort if r['success']]
        outcomes = Counter(r['outcome'] for r in cohort)
        failures = len(cohort)-len(latencies)
        summaries[name] = dict(offered_requests=len(cohort), application_failures=failures,
            outcomes=dict(outcomes), request_timeouts=outcomes['request_timeout'],
            slo_violation_rate=(failures+sum(x>.25 for x in latencies))/len(cohort),
            successful_latency_p95_seconds=float(np.quantile(latencies,.95)) if latencies else None,
            successful_throughput_rps=sum(r['success'] and a*NS<=r['completed_offset_ns']<b*NS
                                          and r['offer']['offset_ns']>=0 for r in actual)/(b-a))
    return summaries


def _integrate(initial, events, start, end):
    state = initial
    left = start
    totals = [0.,0.]
    for timestamp, value in events:
        if timestamp <= start:
            state = value
        elif timestamp < end:
            for i in (0,1):
                totals[i] += state[i]*(timestamp-left)/NS
            state, left = value, timestamp
        else:
            break
    return [totals[i]+state[i]*(end-left)/NS for i in (0,1)]


def resource_endpoints(samples, origin_ns, actuations, start, end):
    """Use measured coverage only for usage and efficiency. Resource-time uses observed edges."""
    initial = (1.,512*2**20)
    changed = [x for x in actuations if x['status']=='ENFORCED']
    def value(x):
        return x['cpu_millicores']/1000,x['memory_request_mib']*2**20
    requested = sorted((x['ack_monotonic_ns'],value(x)) for x in changed)
    allocated = sorted((x['enforced_monotonic_ns'],value(x)) for x in changed)
    lo, hi = origin_ns+start*NS, origin_ns+end*NS
    req = _integrate(initial,requested,lo,hi)
    alloc = _integrate(initial,allocated,lo,hi)
    inside = [s for s in samples if lo<=s['host_receipt_monotonic_ns']<hi]
    coverage = source_coverage = cpu_used = memory_used = 0.
    req_cov, alloc_cov = [0.,0.], [0.,0.]
    for a,b in zip(inside,inside[1:]):
        left,right = a['host_receipt_monotonic_ns'],b['host_receipt_monotonic_ns']
        dt = (right-left)/NS
        source_dt = (b['source_clock']['monotonic_ns']-a['source_clock']['monotonic_ns'])/NS
        if dt<=0 or source_dt<=0 or b['cpu_seconds']<a['cpu_seconds']:
            raise ValueError('invalid_resource_interval')
        if dt>10:
            continue
        coverage += dt
        source_coverage += source_dt
        cpu_used += b['cpu_seconds']-a['cpu_seconds']
        memory_used += a['memory_working_set_bytes']*dt
        for totals,events in ((req_cov,requested),(alloc_cov,allocated)):
            piece = _integrate(initial,events,left,right)
            for i in (0,1):totals[i] += piece[i]
    return dict(mean_cpu_requested_cores=req[0]/(end-start), mean_memory_requested_bytes=req[1]/(end-start),
        mean_cpu_allocated_cores=alloc[0]/(end-start), mean_memory_allocated_bytes=alloc[1]/(end-start),
        mean_cpu_used_cores=cpu_used/source_coverage if source_coverage else None,
        mean_memory_used_bytes=memory_used/coverage if coverage else None,
        cpu_utilization_efficiency=cpu_used/req_cov[0] if req_cov[0] else None,
        memory_utilization_efficiency=memory_used/req_cov[1] if req_cov[1] else None,
        cpu_allocated_utilization=cpu_used/alloc_cov[0] if alloc_cov[0] else None,
        memory_allocated_utilization=memory_used/alloc_cov[1] if alloc_cov[1] else None,
        resource_coverage_seconds=coverage, cpu_source_coverage_seconds=source_coverage)


def paired_analysis(terminal, snapshots):
    """One summary per frozen run. Undefined pairs stay visible in the output."""
    by_seq = {r['sequence']:r for r in terminal}
    if len(by_seq)!=len(terminal) or set(by_seq)-set(range(1,19)):
        raise ValueError('duplicate_or_unknown_treatment')
    rows = [dict(c,terminal=by_seq.get(c['sequence'])) for c in cells()]
    targets = {(r['scenario'],r['left'],r['right']):r['status'] for r in snapshots['structural_targets']}
    contrasts = []
    fields = (*ENDPOINTS, 'application_failures','request_timeouts','successful_throughput_rps',
              'mean_cpu_allocated_cores','mean_memory_allocated_bytes','mean_cpu_used_cores','mean_memory_used_bytes',
              'cpu_churn_cores','memory_churn_bytes','controller_cpu_seconds')
    for scenario in CHECKPOINTS:
        for method,control in (('pw_12h','static'),('pw_3h','static'),('pw_3h','pw_12h')):
            state = targets[scenario,control,method]
            def endpoints(m,i):
                row = next(r for r in rows if (r['scenario'],r['method'],r['repetition'])==(scenario,m,i))
                t = row['terminal']
                return t['metrics']['primary'] if t and t['status']=='COMPLETE' else {}
            a = [endpoints(method,i) for i in (1,2,3)]
            b = [endpoints(control,i) for i in (1,2,3)]
            estimates = {}
            for field in fields:
                differences = [x[field]-y[field] if x.get(field) is not None and y.get(field) is not None else None
                               for x,y in zip(a,b)]
                summary = interval(differences)
                summary.pop('bonferroni_95')
                estimates[field] = dict(differences=differences,**summary)
            complete = all(all(r.get(k) is not None and isfinite(r[k]) for k in PARETO) for r in a+b)
            relation = (pareto_relation({k:sum(r[k] for r in a)/3 for k in PARETO},
                                        {k:sum(r[k] for r in b)/3 for k in PARETO}) if complete
                        else 'INDETERMINATE_MISSING_ENDPOINT')
            contrasts.append(dict(scenario=scenario, method=method, control=control, target_status=state,
                identifies_target_effect=state=='DISTINCT_TARGET', estimates=estimates, pareto=relation))
    return dict(scope=snapshots['scope'], unit='physical treatment run', rows=rows, contrasts=contrasts,
                interval='pointwise paired t, df=2, model-based', secondary_slices='descriptive only',
                practical_superiority='NOT_DEFINED')
