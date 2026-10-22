from copy import deepcopy
from dataclasses import replace
from functools import partial
import inspect
import numpy as np
import pandas as pd
import pytest
from dynapm.core.schema import ProfileInstance,StaticFields,DynamicFields
from dynapm.core.temporal import trailing_targets
from dynapm.core.accounting import Trigger
from dynapm.methods.observation_timing import (paired_content_window,WindowPeriodicPolicy,
    AdaptiveResidualPolicy,BudgetMatchedWindowPolicy,ReactiveWindowPolicy,
    ADWINObservationPolicy)
from dynapm.methods.budget_matched import budget_extra_times,periodic_commit_times
from dynapm.eval.replay import prepare_vm_replay,prepare_vm_inputs,replay_from_inputs
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.experiments.adaptive_timing import study_config,validate_config,run_vm
from dynapm.experiments.pilot_design import default_config

ANCHOR=pd.Timestamp('2026-01-02')
TH={'p20':10,'p40':30,'p60':50,'p80':70,'p95':90}


def make(cls=WindowPeriodicPolicy,**kwargs):
    index=pd.date_range(end=ANCHOR-pd.Timedelta(minutes=5),periods=288,freq='5min')
    boot=pd.Series(25.,index=index)
    profile=ProfileInstance(StaticFields('1','T',2,4.,index[0],ANCHOR,1000),DynamicFields('idle','idle',0.,0.),{})
    return cls(profile,TH,TH,bootstrap_cpu_series=boot,bootstrap_mem_series=boot.copy(),**kwargs),boot


def feed(policy,history,t):
    kw=dict(cpu_prediction=25.,mem_prediction=25.) if policy.requires_residuals else {}
    policy.step(t,history.loc[:t],history.loc[:t],**kw)


class Signal:
    def __init__(self,signal=False):self.signal=signal;self.calls=0;self.values=[]
    def update(self,value):self.calls+=1;self.values.append(value);return self.signal


def test_paired_content_exact_window_and_joint_finiteness():
    idx=pd.date_range(end=ANCHOR,periods=350,freq='5min')
    cpu=pd.Series(np.arange(350.),index=idx);mem=cpu.copy()
    mem.loc[idx[-88:]]=np.nan
    window=paired_content_window(cpu,mem,ANCHOR)
    assert len(window)==200 and (window.index>ANCHOR-pd.Timedelta(hours=24)).all()
    mem.loc[idx[-89]]=np.nan
    assert len(paired_content_window(cpu,mem,ANCHOR))==199


def test_content_future_invariance():
    _,boot=make();history=pd.concat([boot,pd.Series(1e10,index=pd.date_range(ANCHOR,periods=10,freq='5min'))])
    pd.testing.assert_frame_equal(paired_content_window(boot,boot,boot.index[-1]),
                                 paired_content_window(history,history,boot.index[-1]))


def test_common_content_initialization_and_periodic_precedence():
    policies=[make(WindowPeriodicPolicy)[0],make(AdaptiveResidualPolicy)[0],make(BudgetMatchedWindowPolicy,extra_times=[])[0]]
    _,boot=make();history=pd.concat([boot,pd.Series(25.,index=pd.date_range(ANCHOR,periods=73,freq='5min'))])
    policies[1]._cpu_drift=Signal(True);policies[1]._mem_drift=Signal(True)
    for p in policies:feed(p,history,ANCHOR+pd.Timedelta(hours=6))
    for p in policies:
        event=p.accounting.refresh_events[-1]
        assert event.trigger==Trigger.PERIODIC and len(p.accounting.initialization_events)==1
        assert p.profile.dynamic==policies[0].profile.dynamic
    assert policies[1]._cpu_drift.calls==policies[1]._mem_drift.calls==1


def test_periodic_does_not_require_rf_origin_history():
    p,boot=make();t=ANCHOR+pd.Timedelta(hours=6)
    history=pd.concat([boot,pd.Series(25.,index=pd.date_range(ANCHOR,t,freq='5min'))]).drop(t-pd.Timedelta(minutes=5))
    feed(p,history,t)
    assert p.accounting.counters()['n_periodic_refreshes']==1


def test_missing_residual_history_pauses_both_detectors():
    p,boot=make(AdaptiveResidualPolicy);p._cpu_drift=Signal(True);p._mem_drift=Signal(True)
    t=ANCHOR+pd.Timedelta(hours=1)
    h=pd.concat([boot,pd.Series(25.,index=pd.date_range(ANCHOR,t,freq='5min'))]).drop(t-pd.Timedelta(minutes=10))
    feed(p,h,t)
    assert p._cpu_drift.calls==p._mem_drift.calls==0
    assert p.unavailable_residuals==1 and not p.accounting.refresh_events


def test_ineligible_drift_signal_consumed_not_latched():
    p,boot=make(AdaptiveResidualPolicy);p._cpu_drift=Signal(True);p._mem_drift=Signal(False)
    t=ANCHOR+pd.Timedelta(hours=40)
    h=pd.concat([boot,pd.Series(25.,index=pd.date_range(end=t,periods=100,freq='5min'))])
    feed(p,h,t)
    assert p.ineligible_drift_signals==1 and not p.accounting.refresh_events
    p._cpu_drift.signal=False
    later=t+pd.Timedelta(minutes=5);h.loc[later]=25.;feed(p,h,later)
    assert not p.accounting.refresh_events and p._cpu_drift.calls==2


def test_reactive_trigger_uses_six_hours_but_commits_shared_window():
    p,boot=make(ReactiveWindowPolicy)
    t=ANCHOR+pd.Timedelta(hours=1)
    stream=pd.Series(95.,index=pd.date_range(ANCHOR,t,freq='5min'))
    history=pd.concat([boot,stream])
    feed(p,history,t)
    assert p.total_trigger_signals==1 and p.accounting_metrics()['n_reactive_refreshes']==1
    window=paired_content_window(history,history,t)
    assert p.profile.dynamic.predicted_cpu_p95_next_24h==np.quantile(window.cpu,.95)
    later=t+pd.Timedelta(minutes=5);history.loc[later]=95.;feed(p,history,later)
    assert p.total_trigger_signals==1
    assert p.accounting_metrics()['n_reactive_refreshes']==1
    assert p.trigger_events[0]['disposition']=='committed'


def test_reactive_ineligible_trigger_is_consumed():
    p,boot=make(ReactiveWindowPolicy)
    t=ANCHOR+pd.Timedelta(hours=40)
    history=pd.concat([boot,pd.Series(95.,index=pd.date_range(end=t,periods=72,freq='5min'))])
    feed(p,history,t)
    assert p.total_trigger_signals==p.ineligible_trigger_signals==1
    assert not p.accounting.refresh_events
    later=t+pd.Timedelta(minutes=5);history.loc[later]=95.;feed(p,history,later)
    assert p.total_trigger_signals==1


def test_periodic_content_does_not_manufacture_reactive_transition():
    p,boot=make(ReactiveWindowPolicy)
    index=pd.date_range(ANCHOR,ANCHOR+pd.Timedelta(hours=6,minutes=5),freq='5min')
    history=pd.concat([boot,pd.Series(95.,index=index)])
    feed(p,history,ANCHOR+pd.Timedelta(hours=5,minutes=55))
    assert p.total_trigger_signals==1
    feed(p,history,ANCHOR+pd.Timedelta(hours=6))
    assert p.accounting_metrics()['n_periodic_refreshes']==1
    feed(p,history,ANCHOR+pd.Timedelta(hours=6,minutes=5))
    assert p.total_trigger_signals==1
    assert p.cpu_trigger_signals==p.mem_trigger_signals==1


def test_adwin_observation_consumes_direct_values_and_periodic_precedes():
    p,boot=make(ADWINObservationPolicy)
    p._cpu_drift=Signal(True);p._mem_drift=Signal(True)
    t=ANCHOR+pd.Timedelta(hours=6)
    history=pd.concat([boot,pd.Series(37.,index=pd.date_range(ANCHOR,t,freq='5min'))])
    feed(p,history,t)
    assert p._cpu_drift.values==p._mem_drift.values==[37.]
    assert p.total_trigger_signals==p.periodic_coincident_trigger_signals==1
    assert p.cpu_trigger_signals==p.mem_trigger_signals==1
    assert p.accounting.refresh_events[-1].trigger==Trigger.PERIODIC


def test_predictor_free_policies_declare_no_prediction_dependencies():
    assert not ReactiveWindowPolicy.requires_predictors
    assert not ReactiveWindowPolicy.requires_residuals
    assert not ADWINObservationPolicy.requires_predictors
    assert not ADWINObservationPolicy.requires_residuals


def test_gap_delayed_coalesced_periodic_base_equal():
    index=pd.date_range(ANCHOR,ANCHOR+pd.Timedelta(hours=60),freq='5min')
    index=index[~((index>ANCHOR+pd.Timedelta(hours=1))&(index<ANCHOR+pd.Timedelta(hours=30)))]
    policies=[make(WindowPeriodicPolicy)[0],make(AdaptiveResidualPolicy)[0],make(BudgetMatchedWindowPolicy,extra_times=[])[0]]
    _,boot=make();h=pd.concat([boot,pd.Series(25.,index=index)])
    schedules=[]
    for p in policies:
        for t in index:feed(p,h,t)
        schedules.append([(e.actual_commit_time,e.nominal_scheduled_time) for e in p.accounting.refresh_events])
    assert schedules[0]==schedules[1]==schedules[2]
    actual,nominal=schedules[0][0]
    assert actual>ANCHOR+pd.Timedelta(hours=30)
    assert nominal==ANCHOR+pd.Timedelta(hours=42)
    assert len([a for a,n in schedules[0] if a==actual])==1
    assert schedules[0][1][1]==ANCHOR+pd.Timedelta(hours=48)


@pytest.mark.parametrize('k',[0,3,10])
def test_budget_exact_unique_no_drift_information(k):
    index=pd.date_range(ANCHOR,periods=145,freq='5min');base=periodic_commit_times(index,ANCHOR,6)
    extras=budget_extra_times(index,base,k)
    assert len(extras)==k and extras.is_unique and not extras.isin(base).any()
    assert list(inspect.signature(budget_extra_times).parameters)==['timeline','periodic_commits','k']
    adaptive,boot=make(AdaptiveResidualPolicy)
    budget,_=make(BudgetMatchedWindowPolicy,extra_times=extras)
    history=pd.concat([boot,pd.Series(25.,index=index)])
    for t in index:feed(budget,history,t)
    counts=budget.accounting_metrics()
    assert counts['n_budget_extra_refreshes']==k
    assert counts['n_refresh_events']==counts['n_periodic_refreshes']+k
    if k==0:
        pw,_=make()
        for t in index:feed(pw,history,t)
        assert pw.profile.dynamic==budget.profile.dynamic
        assert pw.refresh_log==budget.refresh_log


def test_budget_collision_and_ineligible_extra_fail():
    t=ANCHOR+pd.Timedelta(hours=6);p,boot=make(BudgetMatchedWindowPolicy,extra_times=[t])
    h=pd.concat([boot,pd.Series(25.,index=pd.date_range(ANCHOR,t,freq='5min'))])
    with pytest.raises(ValueError,match='collides'):feed(p,h,t)
    p,boot=make(BudgetMatchedWindowPolicy,extra_times=[t+pd.Timedelta(days=3)])
    h=pd.concat([boot,pd.Series(25.,index=[t+pd.Timedelta(days=3)])])
    with pytest.raises(ValueError,match='ineligible'):feed(p,h,t+pd.Timedelta(days=3))


def test_residual_only_replay_prepares_models_without_content_dependencies(replay_repo,lag_predictor_factory):
    class NoHorizon(lag_predictor_factory):
        def predict_causal_horizon(self,*a,**k):raise AssertionError('content forecasting forbidden')
    replay=prepare_vm_replay('TestTrace','1',AdaptiveResidualPolicy,repo_root=replay_repo,predictor_factory=NoHorizon)
    result=evaluate_replay(replay,include_records=True)
    assert result['n_eval_points_verified']>0
    records=pd.DataFrame(result['evaluation_records'])
    assert records.profile_age_hours.gt(0).any()
    assert {'cpu_p95_bias','profile_cpu_p95'}.issubset(records)
    assert not replay.method.requires_predictors and replay.method.requires_residuals


def test_config_frozen_and_binding():
    config=study_config(default_config());validate_config(config)
    with pytest.raises(ValueError):validate_config(replace(config,policies=(replace(config.policies[0],periodic_interval_hours=3),*config.policies[1:])))
    with pytest.raises(ValueError):validate_config(replace(config,model=replace(config.model,n_estimators=3)))


def test_full_bounded_execution_path_synthetic(replay_repo,lag_predictor_factory,monkeypatch):
    import dynapm.experiments.adaptive_timing as execution
    class Fake(lag_predictor_factory):
        def __init__(self,target,config):super().__init__(target);self.fit_calls=self.stream_calls=0
        def fit(self,frame):super().fit(frame);self.fit_calls+=1;self.fit_seconds=0.
        def predict_streaming(self,frame):self.stream_calls+=1;self.stream_seconds=0.;return super().predict_streaming(frame)
        def predict_causal_horizon(self,*a,**k):raise AssertionError('no horizon content')
    monkeypatch.setattr(execution,'ResidualOnlyRF',Fake)
    rows,events,records,extras,diagnostic=run_vm((replay_repo,dict(trace='TestTrace',vm_id='1',volatility_tier='low'),study_config(default_config())))
    assert len(rows)==3 and diagnostic['equal_total_budget']
    rec=pd.DataFrame(records)
    assert rec.groupby('eval_timestamp').method_id.nunique().eq(3).all()
    assert rec.groupby('eval_timestamp').observed_truth_sha256.nunique().eq(1).all()
    assert diagnostic['recursive_forecast_calls']==0


def test_new_policies_read_nominal_clock_without_observation(replay_repo,lag_predictor_factory):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    origin=inputs.ground_truth.index[1]
    inputs.observations=inputs.observations.drop(origin)
    for factory in [WindowPeriodicPolicy,AdaptiveResidualPolicy,partial(BudgetMatchedWindowPolicy,extra_times=[])]:
        replay=replay_from_inputs(inputs,factory)
        result=evaluate_replay(replay,include_records=True)
        record=next(r for r in result['evaluation_records'] if r['evaluation_time']==origin)
        assert record['profile_age_seconds']>0
        assert record['eval_timestamp']==origin
        assert record['cpu_p95_bias']==record['profile_cpu_p95']-inputs.ground_truth.loc[origin,'p95_cpu_next_24h']


def test_deserialized_frozen_configuration_is_accepted():
    import json
    from dynapm.core.provenance import canonical_json,config_from_dict
    restored=config_from_dict(json.loads(canonical_json(default_config())))
    validate_config(study_config(restored))
