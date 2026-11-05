"""V7D run-level estimator over validated terminal summaries."""
from math import isfinite, sqrt
from statistics import mean, median, stdev

from scipy.stats import t

from dynapm.core.provenance import fingerprint
from dynapm.system_validation.system_estimation import PARETO, pareto_relation
from dynapm.system_validation.v8_campaign import BLOCKS, SCENARIOS, SCOPE, expected_sequence

ENDPOINTS = ('slo_violation_rate', 'successful_latency_p95_seconds',
             'mean_cpu_requested_cores', 'mean_memory_requested_bytes',
             'cpu_utilization_efficiency', 'memory_utilization_efficiency')
CONTRASTS = (('pw_12h', 'static'), ('pw_3h', 'static'), ('full_rewrite', 'static'),
             ('pw_3h', 'pw_12h'), ('full_rewrite', 'pw_3h'))
FAMILY = 60


def validate_summary(row):
    if not isinstance(row, dict):
        raise ValueError('run_summary_required')
    for field in set(ENDPOINTS) | set(PARETO) | {'maintenance_cpu_seconds', 'cpu_churn_cores', 'memory_churn_bytes'}:
        value = row[field]
        if value is not None and (type(value) not in (int, float) or not isfinite(value) or value < 0):
            raise ValueError('nonfinite_or_negative_endpoint')
    offered = row['offered_requests']
    errors = row['application_failures']
    violations = row['slo_violations']
    if (any(type(x) is not int for x in (offered, errors, violations))
            or not 0 <= errors <= violations <= offered or offered == 0
            or row['slo_violation_rate'] != violations / offered):
        raise ValueError('offered_request_denominator_mismatch')
    if errors == offered and row['successful_latency_p95_seconds'] is not None:
        raise ValueError('successful_latency_undefined_without_successes')


def interval(values):
    if len(values) != 3 or any(x is None for x in values):
        return dict(status='NOT_ESTIMABLE', mean=None, median=None, range=None,
                    pointwise_95=None, bonferroni_95=None)
    center = mean(values)
    sd = stdev(values)
    result = dict(status='DEGENERATE_DATA' if sd == 0 else 'ESTIMATED_MODEL_BASED',
                  mean=center, median=median(values), range=[min(values), max(values)],
                  pointwise_95=None, bonferroni_95=None)
    if sd:
        for key, alpha in [('pointwise_95', .05), ('bonferroni_95', .05 / FAMILY)]:
            width = float(t.ppf(1 - alpha / 2, 2)) * sd / sqrt(3)
            result[key] = [center - width, center + width]
    return result


def analyze(campaign):
    state = campaign.state()
    terminal = {r['sequence']: r for r in state['completed']}
    rows = []
    for cell in expected_sequence():
        attempt = terminal.get(cell['sequence'])
        rows.append(dict(cell, terminal=attempt, endpoints=attempt['endpoints'] if attempt else None))
    contrasts = []
    pareto = []
    for scenario in (*SCENARIOS, 'stable', 'burst'):
        secondary = scenario not in SCENARIOS
        pairs = [('pw_3h', 'static')] if secondary else CONTRASTS
        for method, control in pairs:
            a = {x['bootstrap_block']: x for x in rows if x['scenario'] == scenario and x['method'] == method}
            b = {x['bootstrap_block']: x for x in rows if x['scenario'] == scenario and x['method'] == control}
            blocks = BLOCKS[:1] if secondary else BLOCKS
            av = [a[k]['endpoints'] for k in blocks]
            bv = [b[k]['endpoints'] for k in blocks]
            for field in ENDPOINTS:
                diffs = [x[field] - y[field] if x and y and x[field] is not None and y[field] is not None else None
                         for x, y in zip(av, bv)]
                summary = (dict(status='DESCRIPTIVE_ONLY', mean=diffs[0], pointwise_95=None,
                                bonferroni_95=None) if secondary else interval(diffs))
                contrasts.append(dict(scenario=scenario, method=method, control=control,
                                      endpoint=field, differences=dict(zip(blocks, diffs)), **summary))
            if all(x and all(x[k] is not None for k in PARETO) for x in av + bv):
                relation = pareto_relation({k: mean(x[k] for x in av) for k in PARETO},
                                           {k: mean(x[k] for x in bv) for k in PARETO})
            else:
                relation = 'INDETERMINATE_MISSING_ENDPOINT'
            pareto.append(dict(scenario=scenario, method=method, control=control, relation=relation))
    return dict(schema='v8-analysis-manifest-v1', scope=SCOPE, campaign_sha256=fingerprint(campaign.header),
                source_commit=campaign.header['source_commit'], design_sha256=campaign.header['design_sha256'],
                evidence_sha256=fingerprint(state), unit='physical treatment run in the frozen design',
                model='paired t with df=2, independent normal block differences assumed', family_size=FAMILY,
                rows=rows, contrasts=contrasts, pareto=pareto, failed_attempts=state['failures'],
                practical_superiority='NOT_DEFINED', scientific_claims_enabled=False)


def request_endpoints(records, offered_times, start, end):
    """Validate one outcome per offered trace entry and aggregate its 48h cohort.

    Caller supplies the immutable trace times. Host-monotonic completion must
    include final drain. Failed attempts contribute to the denominator.
    """
    from dynapm.system_validation.consumer import summarize_requests

    if end - start != 172800:
        raise ValueError('full_horizon_required')
    cohort = []
    for index, pair in enumerate(zip(records, offered_times, strict=True)):
        row, due = pair
        if row['request_id'] != index or row['scheduled_at'] != due:
            raise ValueError('offered_trace_reconciliation_failed')
        if row['success'] and (row['dropped'] or not isfinite(row['latency_seconds'])
                               or row['latency_seconds'] < 0):
            raise ValueError('invalid_successful_request')
        if start <= due < end:
            cohort.append(row)
    if not cohort:
        raise ValueError('empty_measurement_request_cohort')
    summary = summarize_requests(cohort, start, end, .25)
    violations = sum(not row['success'] or row['latency_seconds'] > .25 for row in cohort)
    return dict(offered_requests=len(cohort), application_failures=summary['failures'],
                slo_violations=violations, slo_violation_rate=summary['slo_violation_rate'],
                successful_latency_p95_seconds=summary['successful_latency_p95_seconds'])
