"""Timing-only experiment over shared production replay and paired PW content."""
from dataclasses import replace
from functools import partial
import time
import numpy as np
import pandas as pd
from dynapm.core.provenance import PolicyConfig, fingerprint, canonical_json
from dynapm.core.predictor import VMPredictor
from dynapm.core.temporal import validity_table, forecast_targets, forward_observations
from dynapm.core.accounting import require_accounting_metrics
from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs, CPU_T, MEM_T
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.methods.observation_timing import (WindowPeriodicPolicy, AdaptiveResidualPolicy,
    BudgetMatchedWindowPolicy, paired_content_window, CONTENT_VERSION)
from dynapm.methods.budget_matched import budget_extra_times, periodic_commit_times, BUDGET_SCHEDULE_VERSION

STUDY_VERSION = 'observation-content-adaptive-timing-v1'
METHODS = ('pw_6h', 'adaptive_residual', 'budget_matched')


def study_config(previous):
    return replace(previous, policies=tuple(PolicyConfig(m, periodic_interval_hours=6,
        observation_window_hours=24, adwin_delta=.002) for m in METHODS),
        analysis=dict(study_version=STUDY_VERSION, content=CONTENT_VERSION,
            budget_schedule=BUDGET_SCHEDULE_VERSION, cohort_size=18,
            eligibility='200-of-288-paired-finite-observed-slots',
            drift='valid-one-step-histories-plus-content;consume-ineligible-signal',
            purpose='pilot-descriptive-only', meaningful_margin='not-defined-no-retrospective-threshold',
            decision='conservative-architecture-disposition-no-confirmatory-inference'))


def validate_config(config):
    if config != study_config(config):
        raise ValueError('exact frozen timing-only matrix and analysis required')
    from dynapm.experiments.pilot_design import default_config
    old = default_config()
    if canonical_json((config.data,config.model,config.statistics,config.preprocessing)) != canonical_json((old.data,old.model,old.statistics,old.preprocessing)):
        raise ValueError('no data/model/ADWIN/statistical tuning allowed')


def factory_for(policy, extra_times=()):
    if policy.method_id=='pw_6h':
        return partial(WindowPeriodicPolicy, period_hours=policy.periodic_interval_hours)
    if policy.method_id=='adaptive_residual':
        return partial(AdaptiveResidualPolicy, period_hours=policy.periodic_interval_hours, drift_delta=policy.adwin_delta)
    if policy.method_id=='budget_matched':
        return partial(BudgetMatchedWindowPolicy, period_hours=policy.periodic_interval_hours, extra_times=extra_times)
    raise ValueError('unknown timing policy')


class ResidualOnlyRF(VMPredictor):
    def __init__(self, target, config):
        super().__init__(target, n_estimators=config.n_estimators,
                         max_depth=config.max_depth, random_state=config.random_state)
        self.fit_calls = self.stream_calls = 0

    def fit(self, frame):
        self.fit_calls += 1
        if self.fit_calls != 1:raise ValueError('residual RF refit')
        start=time.perf_counter();super().fit(frame);self.fit_seconds=time.perf_counter()-start

    def predict_streaming(self, frame):
        self.stream_calls += 1
        start=time.perf_counter();out=super().predict_streaming(frame)
        self.stream_seconds=time.perf_counter()-start
        if not np.isfinite(out.to_numpy(dtype=float)).all():raise ValueError('nonfinite residual stream')
        return out

    def predict_causal_horizon(self, *args, **kwargs):
        raise AssertionError('profile-content forecasting prohibited in timing architecture')


def assert_counts(rows, schedules):
    by={r['method_id']:r for r in rows}
    pw,adaptive,budget=(by[m] for m in METHODS)
    assert pw['n_refresh_events']==pw['n_periodic_refreshes']
    assert adaptive['n_refresh_events']==adaptive['n_periodic_refreshes']+adaptive['n_drift_refreshes']
    assert budget['n_refresh_events']==budget['n_periodic_refreshes']+budget['n_budget_extra_refreshes']==adaptive['n_refresh_events']
    assert budget['n_budget_extra_refreshes']==adaptive['n_drift_refreshes']
    assert schedules['pw_6h']==schedules['adaptive_residual']==schedules['budget_matched']
    for row in rows:
        assert row['n_initialization_events']==1
        assert row['n_field_writes']==4*row['n_refresh_events']
    require_accounting_metrics(pd.DataFrame(rows))


def run_vm(task):
    repo,entity,config=task
    validate_config(config);start=time.perf_counter()
    trace,vm=entity['trace'],str(entity['vm_id'])
    inputs=prepare_vm_inputs(trace,vm,repo_root=repo,with_predictors=True,
        predictor_factory=partial(ResidualOnlyRF,config=config.model),
        bootstrap_fraction=config.data.bootstrap_fraction,
        evaluation_period_hours=config.data.evaluation_cadence_seconds/3600,
        minimum_ground_truth_slots=config.data.minimum_ground_truth_paired_slots)
    threshold_sha=fingerprint(dict(cpu=inputs.cpu_thresholds,memory=inputs.mem_thresholds))
    valid=validity_table(inputs.frame)
    eligible=inputs.observations.index[valid.window24.reindex(inputs.observations.index).to_numpy()]
    periodic=periodic_commit_times(inputs.observations.index,inputs.info['bootstrap_end'],6,valid.window24)
    rows,events,evaluations,extra_rows=[],[],[],[]
    schedules={};initials=[];common_index=None;adaptive_count=None
    for policy in config.policies:
        extras=()
        if policy.method_id=='budget_matched':
            # Interface carries only K; no adaptive timestamps/residuals/outcomes.
            extras=budget_extra_times(eligible,periodic,adaptive_count)
            extra_rows=[dict(trace=trace,vm_id=vm,timestamp=t,k=adaptive_count,
                candidate_count=len(eligible)-len(periodic),schedule_version=BUDGET_SCHEDULE_VERSION)
                for t in extras]
        replay=replay_from_inputs(inputs,factory_for(policy,extras))
        initial=replay.method.profile.dynamic
        initials.append((initial.cpu_class,initial.memory_class,initial.predicted_cpu_p95_next_24h,initial.predicted_mem_p95_next_24h))
        hashes={};original=replay.method.accounting.commit
        def checked(t,values,**kwargs):
            w=paired_content_window(inputs.frame[CPU_T],inputs.frame[MEM_T],t)
            expected=replay.method._forecast_values(w.cpu,w.memory)
            if len(w)<200 or values!=expected:raise ValueError('shared content/eligibility mismatch')
            if not np.isfinite([values['predicted_cpu_p95_next_24h'],values['predicted_mem_p95_next_24h']]).all():
                raise ValueError('nonfinite commit')
            hashes[pd.Timestamp(t)]=fingerprint(values)
            return original(t,values,**kwargs)
        replay.method.accounting.commit=checked
        result=evaluate_replay(replay,include_records=True)
        records=result.pop('evaluation_records')
        index=pd.DatetimeIndex([r['eval_timestamp'] for r in records])
        if common_index is None:common_index=index
        if not len(index) or not common_index.equals(index):raise ValueError('unequal evaluation grid')
        for record in records:
            t=record['eval_timestamp'];truth=inputs.ground_truth.loc[t]
            targets=forward_observations(inputs.frame,t)
            evaluations.append(dict(trace=trace,vm_id=vm,tier=entity['volatility_tier'],method_id=policy.method_id,
                **record,thresholds_sha256=threshold_sha,ground_truth_cpu_class=truth.cpu_class,ground_truth_memory_class=truth.memory_class,
                ground_truth_cpu_p95=truth.p95_cpu_next_24h,ground_truth_memory_p95=truth.p95_mem_next_24h,
                target_grid_sha256=fingerprint([str(x) for x in forecast_targets(t)]),
                observed_truth_sha256=fingerprint(targets.reset_index().astype(str).to_dict('records'))))
        ev=replay.method.accounting.refresh_events
        schedules[policy.method_id]=[(e.actual_commit_time,e.nominal_scheduled_time) for e in ev if e.trigger.value=='periodic']
        assert pd.DatetimeIndex([e.actual_commit_time for e in ev]).is_unique
        events += [dict(trace=trace,vm_id=vm,method_id=policy.method_id,**e.as_record(),
                        content_sha256=hashes[e.actual_commit_time]) for e in ev]
        row={k:v for k,v in result.items() if k not in ('refresh_log','initialization_log')}
        row.update(method_id=policy.method_id,tier=entity['volatility_tier'],policy_config_sha256=fingerprint(policy),
            thresholds_sha256=threshold_sha,
            cpu_p95_bias=float(np.mean([r['cpu_p95_bias'] for r in records])),
            mem_p95_bias=float(np.mean([r['mem_p95_bias'] for r in records])),
            profile_age_mean_hours=float(np.mean([r['profile_age_hours'] for r in records])),
            profile_age_p95_hours=float(np.quantile([r['profile_age_hours'] for r in records],.95)),
            unavailable_residuals=getattr(replay.method,'unavailable_residuals',0),
            ineligible_drift_signals=getattr(replay.method,'ineligible_drift_signals',0))
        rows.append(row)
        if policy.method_id=='adaptive_residual':adaptive_count=int(row['n_drift_refreshes'])
    assert len(set(initials))==1
    assert_counts(rows,schedules)
    assert [t for t,n in schedules['pw_6h']]==list(periodic)
    record_frame=pd.DataFrame(evaluations)
    for t,g in record_frame.groupby('eval_timestamp'):
        assert len(g)==3
        for col in ['target_grid_sha256','observed_truth_sha256','ground_truth_cpu_class',
                    'ground_truth_memory_class','ground_truth_cpu_p95','ground_truth_memory_p95']:
            assert g[col].nunique()==1
    for method,g in record_frame.groupby('method_id'):
        assert g.profile_age_seconds.gt(0).any(), 'all-zero-age aliasing'
    for t,g in pd.DataFrame(events).groupby('actual_commit_time'):
        assert g.content_sha256.nunique()==1
    assert all(p.fit_calls==1 and p.stream_calls==1 for p in inputs.predictors)
    assert np.isfinite(record_frame[['cpu_p95_abs_err','mem_p95_abs_err','cpu_p95_bias','mem_p95_bias']].to_numpy()).all()
    diagnostics=dict(trace=trace,vm_id=vm,completed=3,common_evaluation_points=len(common_index),
        content_identical=True,periodic_commits_identical=True,equal_total_budget=True,
        collision_count=0,causal_numeric_failures=0,observed_steps=len(inputs.observations),
        unavailable_one_step_slots=int((~valid.one_step.reindex(inputs.observations.index)).sum()),
        content_ineligible_slots=int((~valid.window24.reindex(inputs.observations.index)).sum()),
        maximum_gap_seconds=float(inputs.frame.index.to_series().diff().dt.total_seconds().max()),
        model_training_seconds=sum(p.fit_seconds for p in inputs.predictors),
        one_step_inference_seconds=sum(p.stream_seconds for p in inputs.predictors),
        recursive_forecast_calls=0,wall_seconds=time.perf_counter()-start)
    print(canonical_json(diagnostics),flush=True)
    return rows,events,evaluations,extra_rows,diagnostics
