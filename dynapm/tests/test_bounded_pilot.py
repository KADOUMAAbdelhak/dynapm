"""Bounded/synthetic pilot design and wiring tests, never a real corpus pilot."""
from dataclasses import replace
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dynapm.core.accounting import ACCOUNTING_METRICS, ACCOUNTING_SCHEMA, Trigger, require_accounting_metrics
from dynapm.core.provenance import canonical_json, fingerprint, SourceProvenance
from dynapm.core.run_store import RunSession, OutputSpec, check_cache, write_json
from dynapm.core.temporal import forecast_targets
from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.methods.budget_matched import budget_extra_times, periodic_commit_times, BudgetMatchedPredictorPolicy
from dynapm.experiments.pilot_design import (default_config, select_pilot, guard_cohort,
    gap_records, summarize_gaps, TRACES, TIERS, pilot_cohort_manifest)
from dynapm.experiments.pilot_execution import (factory_for, run_vm, assert_counts,
    AuditedPredictor, validate_config)
from dynapm.scripts.task20_bounded_pilot import OUTPUTS, integrity_probes, execute
from dynapm.tests.test_provenance import inputs


@pytest.fixture
def pool():
    return pd.DataFrame([{'trace': trace, 'vm_id': str(i), 'volatility': float(i),
        'observation_count': 5000, 'first_timestamp': '2021-01-01', 'last_timestamp':'2021-02-01'}
        for trace in TRACES for i in range(1,31)])


def test_selection_deterministic_stratified_and_outcome_independent(pool):
    first, meta = select_pilot(pool)
    changed = pool.sample(frac=1, random_state=42).assign(old_accuracy=999, drift_count=999, provisioning='ignored')
    second, meta2 = select_pilot(changed)
    pd.testing.assert_frame_equal(first, second)
    assert meta == meta2
    assert len(first) == 18
    assert first.groupby(['trace','volatility_tier']).size().eq(2).all()
    assert first.selection_hash.str.len().eq(64).all()
    guard_cohort(first)


def test_underpopulated_cell_stops(pool):
    with pytest.raises(ValueError, match='fewer than 2'):
        select_pilot(pool[pool.trace!=TRACES[0]])


@pytest.mark.parametrize('count',[0,17,19,51,1576])
def test_cohort_size_guard(pool,count):
    selected,_ = select_pilot(pool)
    candidate = pd.concat([selected]*100).iloc[:count]
    with pytest.raises(ValueError, match='exactly 18'):
        guard_cohort(candidate)


def test_dedicated_cohort_identity(pool,inputs):
    selected, meta = select_pilot(pool)
    dataset = replace(inputs[2].dataset, dataset_id='materna')
    cohort = pilot_cohort_manifest(dataset,selected,meta)
    assert len(cohort.entities)==18 and cohort.filtering_config['development_pilot']
    assert cohort.sha256 != inputs[2].cohort.sha256
    changed=selected.copy(); changed.loc[0,'selection_hash']='f'*64
    assert pilot_cohort_manifest(dataset,changed,meta).sha256 != cohort.sha256


@pytest.mark.parametrize('hours',[3,6,12])
def test_period_binding_and_pw_pp_actual_schedule_equality(hours,replay_repo,lag_predictor_factory):
    config=default_config()
    prepared=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,
        predictor_factory=lag_predictor_factory,with_predictors=True)
    logs=[]
    for kind in ('pw','pp'):
        policy=next(p for p in config.policies if p.method_id==f'{kind}_{hours}h')
        factory=factory_for(policy)
        assert factory.keywords['period_hours']==hours
        replay=replay_from_inputs(prepared,factory)
        evaluate_replay(replay)
        logs.append([(e.actual_commit_time,e.nominal_scheduled_time) for e in replay.method.accounting.refresh_events])
    assert logs[0]==logs[1]
    assert len(lag_predictor_factory.instances)==2
    assert all(p.fit_index is not None for p in prepared.predictors)


def test_mutated_period_is_explicitly_bound_not_hidden(replay_repo,lag_predictor_factory):
    prepared=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    policy=replace(default_config().policies[4],periodic_interval_hours=4)
    replay=replay_from_inputs(prepared,factory_for(policy))
    assert replay.method.periodic_grid.period==pd.Timedelta(hours=4)
    # A non-matrix value cannot silently enter the actual frozen pilot.
    config=default_config()
    with pytest.raises(ValueError,match='periods'):
        validate_config(replace(config,policies=(*config.policies[:4],policy,*config.policies[5:])))


def test_model_config_reaches_predictor(monkeypatch):
    from dynapm.experiments import pilot_execution
    received=[]
    monkeypatch.setattr(pilot_execution,'VMPredictor',lambda **kw:received.append(kw))
    model=replace(default_config().model,n_estimators=17,max_depth=7,random_state=123)
    AuditedPredictor('CPU usage [%]',model)
    assert received==[dict(target='CPU usage [%]',n_estimators=17,max_depth=7,random_state=123)]


@pytest.mark.parametrize('k',[0,1,2,17,100])
def test_budget_schedule_exact_deterministic_unique_without_drift_inputs(k):
    timeline=pd.date_range('2021-01-01',periods=600,freq='5min')
    base=periodic_commit_times(timeline,timeline[0])
    selected=budget_extra_times(timeline,base,k)
    assert len(selected)==k and selected.is_unique and selected.is_monotonic_increasing
    assert not selected.isin(base).any()
    assert selected.equals(budget_extra_times(timeline,base,k))
    assert list(inspect.signature(budget_extra_times).parameters)==['timeline','periodic_commits','k']


def test_budget_k_zero_is_exact_pp6(replay_repo,lag_predictor_factory):
    prepared=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    config=default_config()
    pp=replay_from_inputs(prepared,factory_for(config.policies[7]))
    bm=replay_from_inputs(prepared,factory_for(config.policies[-1],extra_times=[]))
    a=evaluate_replay(pp,include_records=True); b=evaluate_replay(bm,include_records=True)
    assert a==b
    assert len(lag_predictor_factory.instances)==2


def test_budget_no_collision_and_exact_extra_accounting(replay_repo,lag_predictor_factory):
    prepared=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    base=periodic_commit_times(prepared.observations.index,prepared.info['bootstrap_end'])
    extra=budget_extra_times(prepared.observations.index,base,5)
    replay=replay_from_inputs(prepared,factory_for(default_config().policies[-1],extra_times=extra))
    result=evaluate_replay(replay)
    assert result['n_budget_extra_refreshes']==5
    assert result['n_refresh_events']==len(base)+5
    assert len({e.actual_commit_time for e in replay.method.accounting.refresh_events})==len(base)+5
    require_accounting_metrics(pd.DataFrame([result]))


def test_deliberate_collision_is_rejected(replay_repo,lag_predictor_factory):
    prepared=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    base=periodic_commit_times(prepared.observations.index,prepared.info['bootstrap_end'])
    replay=replay_from_inputs(prepared,factory_for(default_config().policies[-1],extra_times=base[:1]))
    with pytest.raises(ValueError,match='collides'):
        evaluate_replay(replay)


def test_horizon_auditor_reuses_only_same_history_and_checks_targets(monkeypatch,synthetic_frame):
    from dynapm.experiments import pilot_execution
    class Fake:
        def __init__(self,**kw): self.calls=0
        def fit(self,frame): pass
        def predict_causal_horizon(self,history,steps):
            self.calls+=1
            return pd.Series(history.iloc[-1], index=forecast_targets(history.index[-1],steps))
    monkeypatch.setattr(pilot_execution,'VMPredictor',Fake)
    audit=AuditedPredictor('CPU usage [%]',default_config().model)
    audit.fit(synthetic_frame)
    history=synthetic_frame['CPU usage [%]'].iloc[:200]
    a=audit.predict_causal_horizon(history); b=audit.predict_causal_horizon(history)
    assert len(a)==288 and a.index.equals(forecast_targets(history.index[-1])) and a.equals(b)
    b.iloc[0]=1e99
    assert audit.predict_causal_horizon(history).iloc[0]!=1e99
    changed=history.copy();changed.iloc[-1]+=1
    audit.predict_causal_horizon(changed)
    assert audit.generated_horizons==2
    with pytest.raises(ValueError,match='once'): audit.fit(synthetic_frame)


def test_all_eleven_methods_share_evaluation_alignment_and_frozen_models(replay_repo,lag_predictor_factory,monkeypatch):
    from dynapm.methods import dynapm_v3
    class Fire:
        def __init__(self,**kw): self.n=0
        def update(self,value): self.n+=1; return self.n in (3,101,205)
    monkeypatch.setattr(dynapm_v3,'ADWINDetector',Fire)
    class Cheap(lag_predictor_factory):
        def __init__(self,target,config): super().__init__(target); self.fit_calls=0
        def fit(self,frame): super().fit(frame); self.fit_calls+=1
        def diagnostics(self): return {'target':self.target,'fit_calls':self.fit_calls}
    out=run_vm({'trace':'TestTrace','vm_id':'1','volatility_tier':'low'},default_config(),replay_repo,predictor_class=Cheap)
    rows=out['rows']; assert len(rows)==11
    assert_counts(rows)
    assert out['diagnostics']['budget_total_equal'] and out['diagnostics']['common_evaluation_points']==18
    assert all(r['n_initialization_events']==1 for r in rows)
    assert all('total_updates' not in r for r in rows)
    assert all(set(ACCOUNTING_METRICS)<=set(r) for r in rows)
    assert len({r['policy_config_sha256'] for r in rows})==11
    by={r['method_id']:r for r in rows}
    assert by['v3']['n_drift_refreshes']>0
    assert by['v3']['n_refresh_events']==by['budget_matched']['n_refresh_events']
    assert len(out['extras'])==by['v3']['n_drift_refreshes']
    evals=pd.DataFrame(out['evaluations'])
    assert evals.groupby('eval_timestamp').observed_target_sha256.nunique().eq(1).all()
    # The counterfactual's K=0 path is checked separately against PP6 exactly.


def test_invariant_violation_blocks():
    with pytest.raises(AssertionError): assert_counts([])


def test_gap_audit_percentages_and_preconfirmation_decision():
    index=pd.to_datetime(['2021-01-01 00:00','2021-01-01 00:05','2021-01-01 00:15','2021-01-01 02:15'])
    rows=gap_records(index,'Trace','1',2)
    summary=summarize_gaps(pd.DataFrame(rows))
    assert summary['phases']['all']['total_intervals']==3
    assert summary['phases']['all']['exact_5m']['fraction']==1/3
    assert summary['phases']['all']['gt_1h']['n_vms']==1
    assert summary['phases']['all']['max_gap_seconds']==7200
    assert summary['decision']=='EXACT-GRID ELIGIBILITY REQUIRED'
    assert summary['protocol']=='causal-timeline-v3'


def test_output_roles_and_managed_provenance_cache_probes(inputs,tmp_path):
    repo,raw,exp,env=inputs
    exp=replace(exp,config=replace(exp.config,analysis={'purpose':'pilot'}))
    with RunSession(tmp_path/'results',exp,env,repo=repo,dataset_root=raw,purpose='pilot',
        required_outputs=[OutputSpec('outputs/pilot_summary.json','descriptive-only')]) as run:
        write_json(run.path/'outputs/pilot_summary.json',{'label':'PILOT / EXPLORATORY'})
        run.complete()
    probes=integrity_probes(run.path,exp)
    assert probes['exact_pilot']
    assert 'output_hash_mismatch' in probes['tampered_copy']
    assert not check_cache(run.path,exp,'claim').reusable
    assert check_cache(run.path,exp,'pilot').reusable
    assert {'per_vm_results.parquet','refresh_events.parquet','matched_budget_schedule.parquet',
        'materna_gap_audit.json','pilot_cohort.json','pilot_diagnostics.json'}<=OUTPUTS.keys()


def test_no_dirty_scientific_pilot(inputs):
    repo,_,_,_=inputs
    (repo/'dynapm/model.py').write_text('changed = 2\n')
    with pytest.raises(ValueError,match='clean committed'):
        execute(repo,default_config())


def test_driver_does_not_use_ambiguous_counter():
    for relative in ['experiments/pilot_execution.py','scripts/task20_bounded_pilot.py']:
        source=(Path(__file__).resolve().parents[1]/relative).read_text()
        assert 'total_updates' not in source
        assert 'ttest' not in source and 'wilcoxon' not in source
