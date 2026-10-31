"""V7B preparation only. Measured bootstrap, outcome-blind plans, conditional precision.

There is deliberately no Kubernetes campaign executor or comparative run command.
An unresolved operational contract must not be turned into a confirmatory freeze.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
import statistics

import numpy as np
import pandas as pd
from scipy.stats import chi2, t as student_t

from dynapm.core.discretization import compute_thresholds
from dynapm.core.provenance import fingerprint, file_sha256, read_json
from dynapm.core.run_store import write_json
from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.core.temporal import METRICS, FEATURE_HISTORY_SLOTS, HORIZON_STEPS, MIN_OBSERVATIONS
from dynapm.experiments.confirmatory_execution import factory_for
from dynapm.system_validation.adapter import ProfileAdapter, aggregate_bucket
from dynapm.system_validation.design import frozen_design

SCHEMA = 'system-trial-preparation-v1'
BOOTSTRAP_SCHEMA = 'measured-system-bootstrap-v2'
PRIMARY = ('slo_violation_rate', 'successful_latency_p95_seconds',
           'mean_cpu_requested_cores', 'mean_memory_requested_bytes',
           'cpu_utilization_efficiency', 'memory_utilization_efficiency')
SPEC = 'configs/system_trials_v8_draft_v1.json'


def draft_spec(repo):
    """Explicitly incomplete design, preserving the V7A physical workload settings."""
    base = frozen_design(repo)
    return dict(schema_version=SCHEMA, gate='V7B', status='BLOCKED', frozen=False,
        comparative_execution_enabled=False, calibration_execution_enabled=False,
        base_design_sha256=fingerprint(base), core_protocol=base['core_protocol'],
        accounting_schema=base['accounting_schema'], system_clock=base['system_clock'],
        methods=base['methods'], consumer=deepcopy(base['consumer']),
        references=deepcopy(base['references']), kubernetes=deepcopy(base['kubernetes']),
        workload=deepcopy(base['workload']), scenarios=deepcopy(base['scenarios']),
        primary_endpoints=list(PRIMARY), secondary_endpoints=[
            'successful_latency_p50_seconds', 'successful_latency_p99_seconds',
            'successful_throughput_rps', 'under_over_provisioning_proxies',
            'resource_change_count', 'resource_churn', 'recommendation_latency_seconds',
            'actuation_latency_seconds', 'maintenance_process_cpu_rss_step_runtime'],
        experimental_unit='independent run/scenario replicate, never requests',
        bootstrap=dict(schema=BOOTSTRAP_SCHEMA, duration_seconds=86400, nominal_slots=288,
            slot_seconds=300, minimum_paired_slots=200, last_complete_slots=96,
            workload='stable', initialization='thresholds from valid bootstrap only; production factory initialization',
            missing='absent slots remain missing; no fill or extension; reject insufficient fixed bootstrap',
            visibility='completed host-receipt bucket; host admission <= initialization read; cluster source <= cluster receipt'),
        engineering_plan=dict(warmup_seconds=1800, cooldown_seconds=900,
            measurement_seconds=172800, neutral_method='pw_6h', calibration_scenarios=['stable', 'periodic'],
            calibration_repetitions_per_scenario=3, calibration_count_status='proposal, not executed or final precision evidence',
            ordering_seed=20251022, ordering='identity-hash-ranked base permutations, cyclic blocks',
            recreate_cluster_every_run=True, reuse_bootstrap_between_runs=False,
            automatic_retries=0, serial_only=True, approval='host reservation not yet recorded'),
        hardware=dict(reservation=None, host_fingerprint=None, dedicated_host_required=True,
            mains_power_required=True, sleeping_or_time_compression_forbidden=True,
            compatibility_keys=['platform','architecture','cpu_model','physical_cpus','logical_cpus','memory_bytes'],
            diagnostics=['wall_monotonic_delta','loadavg','background_process_cpu_memory',
                'power_source','thermal_status_if_available','docker_resources','node_conditions'],
            unavailable_diagnostics='record unavailable; no fabricated thermal readings'),
        operational_contract=dict(evidence_reference=None, application_latency_target_seconds=base['slo']['latency_seconds'],
            latency_target_status='V7A engineering target, not an approved operational SLO',
            slo_error_budget=None, acceptable_slo_harm=None, maximum_p95_latency_harm=None,
            meaningful_cpu_allocation_reduction=None, meaningful_memory_allocation_reduction=None,
            meaningful_cpu_efficiency_gain=None, meaningful_memory_efficiency_gain=None,
            maximum_resource_changes_per_hour=None, maximum_cpu_memory_churn=None,
            maximum_maintenance_cpu=None, maximum_maintenance_memory_bytes=None,
            maximum_maintenance_runtime_seconds=None),
        precision=dict(confidence_level=.95, targets={name:None for name in PRIMARY},
            maximum_repetitions_per_method_scenario=None, maximum_total_host_hours=None,
            chosen_repetitions=None, calibration_manifest=None,
            rule='conditional variance upper bound; no significance-based N; zero variance does not imply precision'),
        attribution=dict(application='application cgroup CPU, memory, throttle and OOM',
            telemetry='Prometheus container + collector separate process, including telemetry HTTP probe cost',
            maintenance='separate profile process CPU/RSS + step thread CPU/wall + startup/warmup',
            controller='must be separate from generator; thread CPU for local computation; process RSS/CPU separately',
            actuation='API submission, acknowledged spec, observed status, actual cgroups; separate from CPU computation',
            status='not demonstrated by V7A process CPU timer cohosted with generator'),
        failure_policy=dict(infrastructure=['source_or_input_drift','sleep_or_clock_failure',
            'unusable_fixed_bootstrap','lost_required_telemetry_or_output','environment_mismatch'],
            operational=['SLO_violations','OOM','workload_failures','deferred_or_rejected_resize'],
            rule='retain every attempt; operational harms are outcomes, not exclusions; correctness fixes invalidate affected generation',
            implementation_status='continuous collection and operational-failure retention still required'),
        blockers=['real_24h_bootstrap_not_demonstrated','calibration_not_run',
            'operational_margins_unjustified','precision_targets_missing','repetition_cap_and_host_budget_missing',
            'host_reservation_missing','continuous_isolated_runner_and_attribution_not_implemented'])


@dataclass(frozen=True)
class MeasuredBootstrap:
    frame: pd.DataFrame
    start_ns: int
    end_ns: int
    accepted_slots: int
    missing_slots: int
    evidence_sha256: str
    schema_version: str = BOOTSTRAP_SCHEMA


def measured_bootstrap(slot_evidence, start_ns, end_ns, initialization_read_ns, design):
    """Reconstruct from actual raw sample evidence, never from supplied utilization labels.

    Unit fixtures exercise this routine but are not proof of a measured 24h run.
    No shortened interval, replicated rows, future receipt, reset or synthetic role
    is accepted. Missing buckets remain absent under the existing 200/96 gate.
    """
    if any(type(v) is not int for v in (start_ns,end_ns,initialization_read_ns)):
        raise ValueError('integer_clocks_required')
    step = 300 * 10**9
    if start_ns % step or end_ns-start_ns != 86400*10**9 or initialization_read_ns < end_ns:
        raise ValueError('real_fixed_24h_nominal_bootstrap_required')
    rows = {}; normalized = []; instance_ids = set(); counter_bounds = []
    for entry in slot_evidence:
        if set(entry) != {'role','end_ns','samples'} or entry['role'] != 'MEASURED_CGROUP_SAMPLES':
            raise ValueError('measured_raw_sample_evidence_required')
        q = entry['end_ns']
        if type(q) is not int or not start_ns < q <= end_ns or (q-start_ns) % step or q in rows:
            raise ValueError('duplicate_or_outside_bootstrap_slot')
        samples = entry['samples']
        if any(type(s[k]) is not int for s in samples for k in ('sample_time_ns','received_at_ns')):
            raise ValueError('integer_sample_clocks_required')
        if any(not q-step < s['received_at_ns'] <= q or
               s.get('host_admitted_at_ns',initialization_read_ns+1) > initialization_read_ns for s in samples):
            raise ValueError('future_or_outside_bootstrap_measurement')
        if any(not math.isfinite(s[k]) or s[k] < 0 for s in samples
               for k in ('cpu_seconds','memory_working_set_bytes')):
            raise ValueError('nonfinite_or_negative_sample')
        bucket = aggregate_bucket(samples,q-step,q,design)
        ordered = sorted(samples,key=lambda s:s['sample_time_ns'])
        instance_ids.update(s['instance_id'] for s in samples)
        counter_bounds.append((q,ordered[0]['cpu_seconds'],ordered[-1]['cpu_seconds']))
        if bucket['available_at_ns'] > initialization_read_ns:
            raise ValueError('incomplete_bootstrap_invisible')
        rows[q] = [bucket['cpu_percent'], bucket['memory_percent']]
        normalized.append(entry)
    if len(instance_ids)>1:raise ValueError('application_restart_during_bootstrap')
    ordered_bounds=sorted(counter_bounds)
    if any(b[1]<a[2] for a,b in zip(ordered_bounds,ordered_bounds[1:])):
        raise ValueError('counter_reset_between_buckets')
    targets = range(start_ns+step,end_ns+step,step)
    frame = pd.DataFrame([rows.get(q,[np.nan,np.nan]) for q in targets],
        columns=METRICS,index=pd.date_range(pd.Timestamp(start_ns+step,tz='UTC'),periods=HORIZON_STEPS,freq='5min'))
    paired = np.isfinite(frame.to_numpy(dtype=float)).all(axis=1)
    if int(paired.sum()) < MIN_OBSERVATIONS or not paired[-FEATURE_HISTORY_SLOTS:].all():
        raise ValueError('bootstrap_requires_200_paired_and_last_96_complete_slots')
    evidence_hash = fingerprint({'schema':BOOTSTRAP_SCHEMA,'start_ns':start_ns,'end_ns':end_ns,
        'slots':sorted(normalized,key=lambda e:e['end_ns'])})
    return MeasuredBootstrap(frame,start_ns,end_ns,int(paired.sum()),int((~paired).sum()),evidence_hash)


class MeasuredProfileAdapter(ProfileAdapter):
    """Measured initialization through the unchanged production policy factory.

    This is not yet a continuous deployed calibration service/executor.
    """
    def __init__(self,method,bootstrap,design,*,planned_streaming_slots):
        import threading,time
        if method not in design['methods'] or type(planned_streaming_slots) is not int or planned_streaming_slots<1:
            raise ValueError('valid_production_method_and_planned_slots_required')
        self.design=design;self.method_id=method;self.anchor_ns=bootstrap.end_ns;self.lock=threading.Lock()
        self.history=bootstrap.frame.dropna().copy()
        anchor=pd.Timestamp(bootstrap.end_ns,tz='UTC')
        cpu_th=compute_thresholds(self.history,METRICS[0]);mem_th=compute_thresholds(self.history,METRICS[1])
        profile=ProfileInstance(StaticFields('application','measured-system-calibration',None,None,
            pd.Timestamp(bootstrap.start_ns,tz='UTC'),anchor,HORIZON_STEPS+planned_streaming_slots),
            DynamicFields('idle','idle',0.,0.),{k:anchor for k in (
                'cpu_class','memory_class','predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h')})
        self.policy=factory_for(method)(profile,cpu_th,mem_th,
            bootstrap_cpu_series=self.history[METRICS[0]],bootstrap_mem_series=self.history[METRICS[1]])
        self.last_slot=bootstrap.end_ns;self.last_commit_wall_ns=time.time_ns()
        self.step_wall=[];self.step_cpu=[];self.observations=[];self.bootstrap=bootstrap

    def _snapshot(self):
        result=super()._snapshot()
        result.update(scope='MEASURED_BOOTSTRAP_DEVELOPMENT_NOT_CLAIM',bootstrap_evidence_sha256=self.bootstrap.evidence_sha256,
            accepted_bootstrap_slots=self.bootstrap.accepted_slots,missing_bootstrap_slots=self.bootstrap.missing_slots)
        return result


def isolated_trial_plan(spec, repetitions, *, calibration):
    """Plan identities only. Cannot launch a cluster or inspect any outcomes."""
    if type(repetitions) is not int or repetitions<1:
        raise ValueError('positive_explicit_repetition_count_required')
    plan=spec['engineering_plan'];seed=plan['ordering_seed']
    methods=[plan['neutral_method']] if calibration else spec['methods']
    scenarios=plan['calibration_scenarios'] if calibration else list(spec['scenarios'])
    ranked=lambda xs:sorted(xs,key=lambda x:fingerprint({'seed':seed,'identity':x}))
    methods=ranked(methods);scenarios=ranked(scenarios);result=[]
    seconds=plan['cooldown_seconds']+plan['warmup_seconds']+spec['bootstrap']['duration_seconds']+plan['measurement_seconds']
    for block in range(repetitions):
        for scenario in scenarios[block%len(scenarios):]+scenarios[:block%len(scenarios)]:
            order=methods[block%len(methods):]+methods[:block%len(methods)]
            for method in order:
                result.append(dict(block=block,scenario=scenario,method=method,seed=seed,
                    recreate=True,reuse_bootstrap=False,minimum_wall_seconds=seconds))
    return result


def conditional_precision_plan(values,half_width,maximum_n,*,confidence=.95,sd_confidence=.95):
    """Conditional paired-contrast planning; not a power/significance calculation.

    SD upper bound assumes independent normal run-level calibration endpoints.
    Contrast SD <= 2*sigma uses worst-case covariance. It still assumes *both*
    methods' future SDs do not exceed the neutral calibration envelope, which is
    not established by neutral calibration. No auto-freeze is permitted.
    """
    values=[float(v) for v in values]
    if len(values)<3 or not all(math.isfinite(v) for v in values):raise ValueError('three_finite_independent_runs_required')
    if not math.isfinite(half_width) or half_width<=0 or type(maximum_n) is not int or maximum_n<3:
        raise ValueError('positive_justified_precision_target_and_cap_required')
    if not 0<confidence<1 or not 0<sd_confidence<1:raise ValueError('valid_confidence_required')
    sd=statistics.stdev(values)
    if sd==0:return dict(status='BLOCKED_ZERO_VARIANCE_NOT_PRECISION_EVIDENCE',required_n=None,observed_sd=0.)
    df=len(values)-1;upper=sd*math.sqrt(df/float(chi2.ppf(1-sd_confidence,df)))
    for n in range(3,maximum_n+1):
        width=float(student_t.ppf((1+confidence)/2,n-1))*2*upper/math.sqrt(n)
        if width<=half_width:return dict(status='CONDITIONAL_PLANNING_ESTIMATE_NOT_FROZEN',
            required_n=n,observed_sd=sd,sd_upper=upper,projected_half_width=width)
    return dict(status='INFEASIBLE_WITHIN_CAP',required_n=None,observed_sd=sd,sd_upper=upper)


def current_draft(repo):
    spec=read_json(Path(repo)/SPEC)
    if spec!=draft_spec(repo):raise ValueError('draft_source_or_config_mismatch')
    return spec


def preparation_report(repo):
    spec=current_draft(repo);p=spec['engineering_plan']
    plan=isolated_trial_plan(spec,p['calibration_repetitions_per_scenario'],calibration=True)
    return dict(status='V7B_BLOCKED_V8_DISABLED',schema_version=SCHEMA,
        spec_sha256=file_sha256(Path(repo)/SPEC),calibration_plan=plan,
        minimum_serial_hours=sum(r['minimum_wall_seconds'] for r in plan)/3600,
        real_bootstrap_demonstrated=False,calibration_runs_completed=0,
        calibration_variance=None,frozen_repetitions=None,blockers=spec['blockers'])


def write_draft(repo):
    write_json(Path(repo)/SPEC,draft_spec(repo))
