"""Bounded managed matrix, using the production preparation/replay/aggregation."""
from dataclasses import asdict
from functools import partial
import hashlib
import time

import numpy as np
import pandas as pd

from dynapm.core.accounting import ACCOUNTING_SCHEMA, ACCOUNTING_METRICS, require_accounting_metrics
from dynapm.core.predictor import VMPredictor
from dynapm.core.provenance import canonical_json, fingerprint, ModelConfig, TEMPORAL_PROTOCOL
from dynapm.core.temporal import forecast_targets, forward_observations
from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs, CPU_T, MEM_T
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.methods.baselines_v2 import (StaticPolicyV2, ReactiveThresholdPolicyV2,
    FullRewritePolicyV2, PeriodicPolicyV2, PeriodicPredictorPolicyV2)
from dynapm.methods.dynapm_v3 import DynAPMPolicyV3
from dynapm.methods.budget_matched import (BudgetMatchedPredictorPolicy,
    budget_extra_times, periodic_commit_times, BUDGET_SCHEDULE_VERSION)
from dynapm.experiments.pilot_design import default_config


class AuditedPredictor:
    """One frozen target model and exact in-memory recursive-horizon reuse.

    Keys include origin and all available history bytes/index. No persisted model
    or unmanaged result cache is read. Cached Series are returned as copies.
    """
    def __init__(self, target, config):
        self.target = target
        self.predictor = VMPredictor(target=target, n_estimators=config.n_estimators,
            max_depth=config.max_depth, random_state=config.random_state)
        self.cache = {}
        self.fit_calls = self.horizon_requests = self.generated_horizons = 0
        self.reused_horizons = 0

    def fit(self, frame):
        if self.fit_calls:
            raise ValueError("predictor must be fitted once per VM/target")
        self.predictor.fit(frame)
        self.fit_calls += 1

    def predict_streaming(self, frame):
        out = self.predictor.predict_streaming(frame)
        if not np.isfinite(out.to_numpy(dtype=float)).all():
            raise ValueError("nonfinite one-step/residual stream")
        return out

    def predict_causal_horizon(self, history, n_steps=288):
        if n_steps != 288 or history.empty or not history.index.is_unique:
            raise ValueError("invalid causal horizon request")
        origin = history.index[-1]
        if not history.index.is_monotonic_increasing or (history.index > origin).any():
            raise ValueError("history visibility violation")
        h = hashlib.sha256(history.index.asi8.tobytes()+history.to_numpy(dtype=float).tobytes()).hexdigest()
        key = (origin, h)
        self.horizon_requests += 1
        if key not in self.cache:
            result = self.predictor.predict_causal_horizon(history, n_steps)
            if not result.index.equals(forecast_targets(origin)) or not np.isfinite(result.to_numpy()).all():
                raise ValueError("forecast horizon/numeric invariant failure")
            self.cache[key] = result
            self.generated_horizons += 1
        else:
            self.reused_horizons += 1
        return self.cache[key].copy()

    def diagnostics(self):
        return {"target": self.target, "fit_calls": self.fit_calls,
            "horizon_requests": self.horizon_requests, "generated_horizons": self.generated_horizons,
            "reused_horizons": self.reused_horizons, "horizon_steps": 288,
            "cadence_seconds": 300, "origin_excluded": True}


def validate_config(config):
    """Reject settings not bound by this driver, rather than merely fingerprinting them."""
    frozen = default_config()
    if config.data != frozen.data or config.preprocessing != frozen.preprocessing or config.analysis != frozen.analysis:
        raise ValueError("unsupported data/preprocessing/analysis configuration")
    if canonical_json(config.statistics) != canonical_json(frozen.statistics):
        raise ValueError("pilot allows descriptive statistics only")
    a, b = asdict(config.model), asdict(frozen.model)
    for name in ('n_estimators', 'max_depth', 'random_state'):
        a.pop(name); b.pop(name)
    if canonical_json(a) != canonical_json(b):
        raise ValueError("unsupported model/feature settings")
    if [p.method_id for p in config.policies] != [p.method_id for p in frozen.policies]:
        raise ValueError("exact 11-method matrix required")
    for policy, expected in zip(config.policies, frozen.policies):
        a, b = asdict(policy), asdict(expected)
        for name in ('periodic_interval_hours', 'adwin_delta'):
            a.pop(name); b.pop(name)
        if a != b or policy.reactive_window_hours != 6 or policy.observation_window_steps != 288:
            raise ValueError("unsupported policy settings")
        if policy.periodic_interval_hours != expected.periodic_interval_hours:
            raise ValueError("pilot matrix periods must be exactly 3/6/12h with 6h V3/base budget")
        if policy.adwin_delta != expected.adwin_delta:
            raise ValueError("pilot freezes current ADWIN settings")


def factory_for(policy, *, extra_times=()):
    method = policy.method_id
    if method == 'static': return StaticPolicyV2
    if method == 'reactive': return ReactiveThresholdPolicyV2
    if method == 'full_rewrite': return FullRewritePolicyV2
    if method.startswith('pw_'):
        return partial(PeriodicPolicyV2, period_hours=policy.periodic_interval_hours)
    if method.startswith('pp_'):
        return partial(PeriodicPredictorPolicyV2, period_hours=policy.periodic_interval_hours)
    if method == 'v3':
        return partial(DynAPMPolicyV3, period_hours=policy.periodic_interval_hours, drift_delta=policy.adwin_delta)
    if method == 'budget_matched':
        return partial(BudgetMatchedPredictorPolicy, period_hours=policy.periodic_interval_hours, extra_times=extra_times)
    raise ValueError('unknown bounded method')


def assert_counts(rows):
    by = {r['method_id']: r for r in rows}
    assert len(by) == 11
    assert by['static']['n_refresh_events'] == 0
    for hours in (3, 6, 12):
        pw, pp = (by[f'{kind}_{hours}h'] for kind in ('pw', 'pp'))
        assert pw['n_refresh_events'] == pw['n_periodic_refreshes'] == pp['n_periodic_refreshes'] == pp['n_refresh_events']
    v3, bm, pp6 = by['v3'], by['budget_matched'], by['pp_6h']
    assert v3['n_refresh_events'] == v3['n_periodic_refreshes']+v3['n_drift_refreshes']
    assert bm['n_refresh_events'] == bm['n_periodic_refreshes']+bm['n_budget_extra_refreshes'] == v3['n_refresh_events']
    assert bm['n_periodic_refreshes'] == pp6['n_periodic_refreshes'] == v3['n_periodic_refreshes']
    assert bm['n_budget_extra_refreshes'] == v3['n_drift_refreshes']
    assert by['reactive']['n_refresh_events'] == by['reactive']['n_reactive_refreshes']
    assert by['full_rewrite']['n_refresh_events'] == by['full_rewrite']['n_full_rewrite_refreshes']
    require_accounting_metrics(pd.DataFrame(rows))


def run_vm(selected, config, repo_root, predictor_class=AuditedPredictor):
    started = time.perf_counter()
    validate_config(config)
    trace, vm_id = selected['trace'], str(selected['vm_id'])
    inputs = prepare_vm_inputs(trace, vm_id, repo_root=repo_root,
        predictor_factory=partial(predictor_class, config=config.model), with_predictors=True,
        bootstrap_fraction=config.data.bootstrap_fraction,
        evaluation_period_hours=config.data.evaluation_cadence_seconds/3600,
        minimum_ground_truth_slots=config.data.minimum_ground_truth_paired_slots)
    if inputs.observations.empty or inputs.ground_truth.empty:
        raise ValueError('no eligible processed/evaluation timestamps')
    if not np.isfinite(inputs.frame[[CPU_T, MEM_T]].to_numpy()).all():
        raise ValueError('raw utilization contains NaN/Inf')
    if inputs.predictors[0] is inputs.predictors[1] or tuple(p.target for p in inputs.predictors) != (CPU_T, MEM_T):
        raise ValueError('target-specific independence violated')
    frozen_inputs = fingerprint({'cpu_thresholds': inputs.cpu_thresholds, 'mem_thresholds': inputs.mem_thresholds,
        'ground_truth': inputs.ground_truth.reset_index().assign(eval_timestamp=lambda f:f.eval_timestamp.astype(str)).to_dict('records')})
    rows, events, evaluations, extras = [], [], [], []
    evaluated_index, v3_result = None, None
    periodic = periodic_commit_times(inputs.observations.index, inputs.info['bootstrap_end'], 6)
    for policy in config.policies:
        tick = time.perf_counter()
        extra = ()
        if policy.method_id == 'budget_matched':
            # Only K crosses this boundary. Drift event locations/residuals never do.
            extra = budget_extra_times(inputs.observations.index, periodic, int(v3_result['n_drift_refreshes']))
            extras += [{'trace': trace, 'vm_id': vm_id, 'timestamp': t,
                'schedule_version': BUDGET_SCHEDULE_VERSION, 'k': len(extra), 'ordinal': i,
                'candidate_count': len(inputs.observations)-len(periodic)} for i, t in enumerate(extra)]
        replay = replay_from_inputs(inputs, factory_for(policy, extra_times=extra))
        original_commit = replay.method.accounting.commit
        def checked_commit(t, values, **kwargs):
            if not all(np.isfinite(values[f]) for f in ('predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h')):
                raise ValueError('nonfinite profile commit')
            return original_commit(t, values, **kwargs)
        replay.method.accounting.commit = checked_commit
        if not all(np.isfinite(getattr(replay.method.profile.dynamic, f)) for f in ('predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h')):
            raise ValueError('nonfinite initialized profile')
        result = evaluate_replay(replay, lookback_steps=policy.observation_window_steps, include_records=True)
        records = result.pop('evaluation_records')
        timestamps = pd.DatetimeIndex([r['eval_timestamp'] for r in records])
        if not len(timestamps): raise ValueError('no verified evaluation points')
        if evaluated_index is None: evaluated_index = timestamps
        if not evaluated_index.equals(timestamps): raise ValueError('evaluation alignment mismatch')
        for record in records:
            origin = record['eval_timestamp']
            observed = forward_observations(inputs.frame, origin)
            target_sha = hashlib.sha256(forecast_targets(origin).asi8.tobytes()).hexdigest()
            observed_sha = hashlib.sha256(observed.index.asi8.tobytes()+observed[[CPU_T, MEM_T]].to_numpy(dtype=float).tobytes()).hexdigest()
            truth = inputs.ground_truth.loc[origin]
            evaluations.append({'trace': trace, 'vm_id': vm_id, 'method_id': policy.method_id,
                **record, 'forecast_target_sha256': target_sha, 'observed_target_sha256': observed_sha,
                'ground_truth_cpu_class': truth['cpu_class'], 'ground_truth_memory_class': truth['memory_class'],
                'ground_truth_cpu_p95': truth['p95_cpu_next_24h'], 'ground_truth_memory_p95': truth['p95_mem_next_24h'],
                'input_threshold_label_sha256': frozen_inputs})
        values = np.array([result[k] for k in ('cpu_class_accuracy','memory_class_accuracy','cpu_p95_mae','mem_p95_mae')])
        if not np.isfinite(values).all(): raise ValueError('nonfinite scored result')
        for event in replay.method.accounting.refresh_events:
            for field in ('predicted_cpu_p95_next_24h','predicted_mem_p95_next_24h'):
                if not np.isfinite(getattr(replay.method.profile.dynamic, field)): raise ValueError('nonfinite committed profile')
            events.append({'trace': trace, 'vm_id': vm_id, 'method_id': policy.method_id, **event.as_record()})
        row = {k:v for k,v in result.items() if k not in ('refresh_log','initialization_log','decision_head_stats')}
        row.update(method_id=policy.method_id, volatility_tier=selected['volatility_tier'],
            policy_configuration=canonical_json(policy), policy_config_sha256=fingerprint(policy),
            run_status='ok', input_threshold_label_sha256=frozen_inputs,
            wall_seconds=time.perf_counter()-tick)
        rows.append(row)
        print(canonical_json({'trace': trace, 'vm_id': vm_id, 'method_completed': policy.method_id, 'refreshes': row['n_refresh_events'], 'wall_seconds': row['wall_seconds']}), flush=True)
        if policy.method_id == 'v3': v3_result = result
    assert_counts(rows)
    periodic_by_method = {p.method_id: [(e['actual_commit_time'], e['nominal_scheduled_time'])
        for e in events if e['method_id'] == p.method_id and e['trigger'] == 'periodic']
        for p in config.policies}
    for hours in (3, 6, 12):
        assert periodic_by_method[f'pw_{hours}h'] == periodic_by_method[f'pp_{hours}h']
    assert periodic_by_method['v3'] == periodic_by_method['budget_matched'] == periodic_by_method['pp_6h']
    frame = pd.DataFrame(evaluations)
    for _, group in frame.groupby('eval_timestamp'):
        assert len(group) == 11
        for col in ('forecast_target_sha256','observed_target_sha256','ground_truth_cpu_class',
                    'ground_truth_memory_class','ground_truth_cpu_p95','ground_truth_memory_p95','input_threshold_label_sha256'):
            assert group[col].nunique() == 1, col
    assert all(p.fit_calls == 1 for p in inputs.predictors)
    return {'rows': rows, 'events': events, 'evaluations': evaluations, 'extras': extras,
        'diagnostics': {'trace': trace, 'vm_id': vm_id, 'attempted': 11, 'completed': 11,
            'common_evaluation_points': len(evaluated_index), 'accounting_invariants': True,
            'budget_total_equal': True, 'budget_collisions': 0, 'causal_numeric_failures': 0,
            'predictors': [p.diagnostics() for p in inputs.predictors],
            'wall_seconds': time.perf_counter()-started}}
