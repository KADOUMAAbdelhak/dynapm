"""V7B estimation-first amendment. No practical margins and no comparative executor."""
from copy import deepcopy
from pathlib import Path
from dynapm.core.provenance import fingerprint,read_json,file_sha256
from dynapm.core.run_store import write_json
from dynapm.system_validation.clock_observations import SCHEMA as CLOCK_SCHEMA,MAX_CLOCK_DELTA_NS
from dynapm.system_validation.design import frozen_design
from dynapm.system_validation.trial_preparation import draft_spec,isolated_trial_plan,PRIMARY

SPEC='configs/system_trials_v8_estimation_v2.json'
SCHEMA='system-estimation-design-v2'
RUNTIME=('dynapm/system_validation/estimation_design.py','dynapm/system_validation/system_estimation.py',
 'dynapm/system_validation/calibration_workers.py','dynapm/system_validation/calibration_runner.py',
 'dynapm/scripts/task34_system_calibration.py','dynapm/system_validation/trial_preparation.py',
 'dynapm/system_validation/application_instrumented.py','dynapm/system_validation/clock_observations.py',
 'harness/system/Calibration.Dockerfile')


def specification(repo):
    d=deepcopy(draft_spec(repo));base=frozen_design(repo)
    d['telemetry']=deepcopy(base['telemetry']);d['slo']=deepcopy(base['slo'])
    d.update(schema_version=SCHEMA,status='CALIBRATION_REQUIRED',frozen=False,
        calibration_execution_enabled=True,comparative_execution_enabled=False,
        study_framing='ESTIMATION_FIRST',framing_frozen=True,calibration_protocol_frozen=True,confirmatory_count_frozen=False,operationally_meaningful_benefit='NOT_DEFINED')
    d['operational_contract']['required_for_estimation']=False
    d['operational_contract']['practical_superiority_claims_enabled']=False
    d['engineering_plan']['calibration_count_status']='predeclared neutral-method calibration: 3 runs per scenario, 6 maximum'
    d['engineering_plan']['approval']='execution authorized; reserved host not asserted'
    d['hardware']['calibration_context']='research workstation; background interference monitored, no reservation assertion'
    d['hardware']['isolated_docker_engine_required']=True
    d['hardware']['calibration_requires_dedicated_host']=False
    d['hardware']['dedicated_host_required']=False
    d['hardware']['comparative_dedicated_host_required']=True
    d['hardware']['confirmatory_control']='freeze matched controlled hardware before comparative execution'
    d['kubernetes']['application_image']='dynapm-system-workload:v7b-instrumented'
    d['kubernetes']['cluster']='dynapm-v7b-calibration'
    d['kubernetes']['namespace']='dynapm-v7b-calibration'
    d['kubernetes']['context']='kind-dynapm-v7b-calibration'
    d['primary_allocation_companions']=['mean_cpu_allocated_cores','mean_memory_allocated_bytes']
    d['estimation']=dict(unit='independent run/scenario',separate_scenarios=True,
        paired_unit='predeclared randomized/counterbalanced block; identical offered trace and seed',
        effects='method minus control; arithmetic mean and median of paired run differences',
        confidence_level=.95,bootstrap_repetitions=10000,bootstrap_seed=20251022,
        ci_method='paired-block percentile bootstrap, pointwise 95%; no familywise or practical superiority claim',
        comparisons=[['pw_12h','static'],['pw_6h','static'],['pw_3h','static'],
            ['pw_6h','pw_12h'],['pw_3h','pw_6h'],['full_rewrite','pw_3h']],
        pvalue_recommendations=False,distinguishability_does_not_imply_practical_superiority=True,negative_and_null_findings_retained=True,
        cross_scenario_pooling=False,
        pareto_dimensions=['mean_cpu_requested_cores','mean_memory_requested_bytes','mean_cpu_allocated_cores','mean_memory_allocated_bytes','slo_violation_rate','successful_latency_p95_seconds'],
        dominance='all six minimization dimensions no better, at least one strictly worse; equality is not strict dominance',
        dominance_scope='point-estimate ordering only; uncertainty reported jointly; not population dominance or practical superiority',
        otherwise='report resource-SLO/latency trade-off without choosing a winner',
        churn_and_overhead='always reported alongside fidelity/performance/resource estimates')
    d['precision']['targets_status']='NOT_DEFINED; do not infer precision goals from favorable effects'
    d['precision']['rule']='report neutral-run variance and precision-versus-N curves; freeze N only for a prospective justified precision target, never significance'
    d['precision']['no_target_disposition']='report limitation and leave comparative execution disabled; practical margins are not required'
    d['attribution']['status']='separate worker processes required; no shared generator/controller CPU attribution'
    d['blockers']=[x for x in d['blockers'] if x not in ('operational_margins_unjustified','continuous_isolated_runner_and_attribution_not_implemented','host_reservation_missing')]
    d['blockers'].append('continuous_runner_validation_and_hardware_control_pending')
    d['clock_observations']=dict(schema=CLOCK_SCHEMA,source_ahead_tolerance_ns=0,
        maximum_source_receipt_delta_ns=MAX_CLOCK_DELTA_NS,receipt_boundary='complete HTTP body read before JSON decoding',
        rejection='fail closed; isolated raw body + context/hash; never scientific telemetry')
    d['scientific_runtime_sha256']={p:file_sha256(Path(repo)/p) for p in RUNTIME}
    return d


def frozen_spec(repo):
    d=read_json(Path(repo)/SPEC)
    if d!=specification(repo):raise ValueError('system_estimation_config_or_source_mismatch')
    if d['comparative_execution_enabled'] or d['operationally_meaningful_benefit']!='NOT_DEFINED':
        raise ValueError('comparative_or_practical_claim_gate_closed')
    return d


def calibration_plan(repo):
    d=frozen_spec(repo)
    return isolated_trial_plan(d,d['engineering_plan']['calibration_repetitions_per_scenario'],calibration=True)


def write_spec(repo):write_json(Path(repo)/SPEC,specification(repo))
