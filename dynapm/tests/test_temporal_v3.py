"""Exact nominal-grid and phase-balanced remediation regressions, synthetic only."""
from dataclasses import replace
from functools import partial
import numpy as np
import pandas as pd
import pytest

from dynapm.core.features import build_features
from dynapm.core.predictor import VMPredictor
from dynapm.core.temporal import (SAMPLE_STEP, HORIZON, TEMPORAL_PROTOCOL, EVALUATION_GRID,
    trailing_observations, history_valid, validity_table, eligibility, PeriodicGrid)
from dynapm.core.run_store import RunSession, OutputSpec, write_json, check_cache
from dynapm.eval.replay import prepare_vm_inputs, replay_from_inputs, iter_verified_snapshots
from dynapm.eval.runner_v2 import evaluate_replay
from dynapm.experiments.gap_eligibility import audit_frame
from dynapm.methods.factories import policy_factory
from dynapm.methods.budget_matched import periodic_commit_times, budget_extra_times
from dynapm.tests.test_provenance import inputs

CPU,MEM='CPU usage [%]','Memory usage [%]'


@pytest.mark.parametrize('missing_offset',[1,12,48,96])
def test_required_exact_slot_missing_invalidates_feature(synthetic_frame,missing_offset):
    t=synthetic_frame.index[350]
    frame=synthetic_frame.drop(t-missing_offset*SAMPLE_STEP)
    assert t not in build_features(frame,CPU).index


def test_lag12_is_exact_hour(synthetic_frame):
    t=synthetic_frame.index[350]
    assert build_features(synthetic_frame,CPU).at[t,'target_lag_12']==synthetic_frame.at[t-pd.Timedelta(hours=1),CPU]


def test_rolling96_and_training_recovery(synthetic_frame):
    missing=synthetic_frame.index[200]
    frame=synthetic_frame.drop(missing)
    features=build_features(frame,CPU)
    assert not features.index.isin(pd.date_range(missing+SAMPLE_STEP,missing+96*SAMPLE_STEP,freq=SAMPLE_STEP)).any()
    assert missing+97*SAMPLE_STEP in features.index
    model=VMPredictor(CPU,n_estimators=2,max_depth=2)
    model.fit(frame)
    assert missing+SAMPLE_STEP not in model.predict_streaming(frame).index


def test_invalid_target_not_used_for_training(synthetic_frame):
    frame=synthetic_frame.copy();frame.loc[frame.index[200],CPU]=np.nan
    model=VMPredictor(CPU,n_estimators=2,max_depth=2);model.fit(frame)
    assert frame.index[200] not in model.predict_streaming(frame).index


@pytest.mark.parametrize('drop_offset',[0,1,95])
def test_recursive_origin_rejected_until_complete(synthetic_frame,drop_offset):
    model=VMPredictor(CPU,n_estimators=2,max_depth=2);model.fit(synthetic_frame.iloc[:200])
    series=synthetic_frame[CPU].iloc[:351].copy()
    if drop_offset==0: series.iloc[-1]=np.nan
    else: series=series.drop(series.index[-1]-drop_offset*SAMPLE_STEP)
    with pytest.raises(ValueError,match='exact-grid history'):
        model.predict_causal_horizon(series)


def test_recursive_recovered_origin_retains_288_exact_targets(synthetic_frame):
    model=VMPredictor(CPU,n_estimators=2,max_depth=2);model.fit(synthetic_frame.iloc[:200])
    history=synthetic_frame[CPU].iloc[:500].drop(synthetic_frame.index[200])
    result=model.predict_causal_horizon(history)
    assert len(result)==288 and result.index[0]==history.index[-1]+SAMPLE_STEP
    assert result.index[-1]==history.index[-1]+HORIZON
    assert (result.index.to_series().diff().dropna()==SAMPLE_STEP).all()


@pytest.mark.parametrize('hours,count,minimum',[(24,288,200),(6,72,50)])
def test_exact_trailing_window_coverage_and_boundaries(synthetic_frame,hours,count,minimum):
    t=synthetic_frame.index[400]
    window=trailing_observations(synthetic_frame[CPU],t,hours)
    assert len(window)==count and t-pd.Timedelta(hours=hours) not in window.index
    assert window.index.min()>t-pd.Timedelta(hours=hours)
    frame=synthetic_frame.drop(window.index[:count-minimum])
    table=validity_table(frame)
    assert bool(table.at[t,'window24' if hours==24 else 'window6'])
    frame=frame.drop(window.index[count-minimum])
    assert not bool(validity_table(frame).at[t,'window24' if hours==24 else 'window6'])


def test_pending_ticks_wait_for_eligibility_and_coalesce():
    t=pd.Timestamp('2021-01-01');g=PeriodicGrid(t,6)
    assert g.pop_due(t+pd.Timedelta(hours=6),False) is None
    assert g.pop_due(t+pd.Timedelta(hours=20),False) is None
    assert g.nominal_ticks_due==3
    assert g.pop_due(t+pd.Timedelta(hours=21),True)==t+pd.Timedelta(hours=18)
    assert g.next_tick==t+pd.Timedelta(hours=24)


@pytest.mark.parametrize('hours',[3,6,12])
def test_gap_shared_periodic_actual_commits(hours,replay_repo,lag_predictor_factory):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    gap=inputs.stream.index[60:90]
    inputs.frame=inputs.frame.drop(gap)
    inputs.observations=inputs.observations.drop(gap)
    schedules=[]
    for method in ('periodic_6h_v2','periodic_predictor_6h_v2'):
        replay=replay_from_inputs(inputs,partial(policy_factory(method),period_hours=hours))
        evaluate_replay(replay)
        schedules.append([(e.actual_commit_time,e.nominal_scheduled_time) for e in replay.method.accounting.refresh_events])
    assert schedules[0]==schedules[1]
    assert all(eligibility(inputs.frame[CPU],inputs.frame[MEM],t) for t,n in schedules[0])


@pytest.mark.parametrize('hours',[3,6,12])
@pytest.mark.parametrize('kind',['periodic_6h_v2','periodic_predictor_6h_v2'])
def test_hourly_age_phases_are_not_all_zero(hours,kind,replay_repo,synthetic_frame,lag_predictor_factory):
    raw=replay_repo/'data/raw/TestTrace/1.csv'
    frame=pd.concat([synthetic_frame]*2,ignore_index=True)
    frame.insert(0,'Timestamp',pd.date_range('2021-01-01',periods=len(frame),freq='5min').strftime('%d.%m.%Y %H:%M:%S'))
    frame.to_csv(raw,sep=';',index=False)
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    replay=replay_from_inputs(inputs,partial(policy_factory(kind),period_hours=hours))
    result=evaluate_replay(replay,include_records=True)
    records=pd.DataFrame(result['evaluation_records'])
    # After first scheduled refresh, all superperiod phases are exact integers.
    stable=records[records.eval_timestamp>=inputs.stream.index[0]+pd.Timedelta(hours=hours)]
    assert set(stable.profile_age_hours)==set(range(hours))
    assert records.profile_age_hours.gt(0).any()
    assert {'evaluation_time','last_refresh_actual_commit_time','last_refresh_trigger','profile_age_seconds'}<=set(records)


def test_missing_observation_read_is_not_delayed(replay_repo,lag_predictor_factory):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    origin=inputs.ground_truth.index[2]
    inputs.observations=inputs.observations.drop(origin)
    replay=replay_from_inputs(inputs,policy_factory('periodic_6h_v2'))
    result=evaluate_replay(replay,include_records=True)
    record=next(r for r in result['evaluation_records'] if r['eval_timestamp']==origin)
    assert record['evaluation_time']==origin and record['profile_age_seconds']>0
    assert record['last_refresh_actual_commit_time']<origin
    assert len(result['evaluation_records'])==len(inputs.ground_truth)


def test_invalid_residual_pauses_without_detector_reset(replay_repo,lag_predictor_factory):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    t=inputs.stream.index[100]
    inputs.predictions=inputs.predictions.drop(t)
    replay=replay_from_inputs(inputs,policy_factory('dynapm_v3_v2'))
    class Counter:
        calls=0
        def update(self,x):self.calls+=1;return False
    cpu=replay.method._cpu_drift=Counter();mem=replay.method._mem_drift=Counter()
    evaluate_replay(replay)
    assert cpu.calls==mem.calls==len(inputs.observations)-1
    assert replay.method.unavailable_residuals==1


def test_consumed_drift_signal_cannot_manufacture_forecast(replay_repo,lag_predictor_factory,monkeypatch):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    replay=replay_from_inputs(inputs,policy_factory('dynapm_v3_v2'))
    class Fire:
        def update(self,x):return True
    replay.method._cpu_drift=Fire();replay.method._mem_drift=Fire()
    t=inputs.stream.index[0]
    cpu=inputs.frame.loc[:t,CPU].copy()
    mem=inputs.frame.loc[:t,MEM].copy()
    # Defensive exceptional-origin branch: normal finite one-step eligibility
    # implies next-origin eligibility; simulate its rejection without NaN input.
    monkeypatch.setattr('dynapm.methods.dynapm_v3.history_valid',lambda series,origin: origin!=t)
    replay.method.step(t,cpu,mem,cpu_prediction=25.,mem_prediction=25.)
    assert replay.method.ineligible_drift_signals==1
    assert not replay.method.accounting.refresh_events


def test_budget_candidates_are_origin_eligible(replay_repo,lag_predictor_factory):
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo,predictor_factory=lag_predictor_factory,with_predictors=True)
    frame=inputs.frame.drop(inputs.stream.index[70:90]);mask=validity_table(frame)
    observed=frame.index.intersection(inputs.stream.index)
    base=periodic_commit_times(observed,inputs.stream.index[0],6,mask.periodic)
    eligible=observed[mask.predictor_origin.reindex(observed).to_numpy()]
    extra=budget_extra_times(eligible,base,7)
    assert len(extra)==7 and extra.is_unique and not extra.isin(base).any()
    assert mask.predictor_origin.reindex(extra).all()


def test_old_protocol_cache_cannot_satisfy_v3(inputs,tmp_path):
    repo,raw,exp,env=inputs
    assert TEMPORAL_PROTOCOL=='causal-timeline-v3' and EVALUATION_GRID=='phase-balanced-hourly-v1'
    old=replace(exp,protocol_version='causal-timeline-v2')
    assert old.fingerprint!=exp.fingerprint
    with RunSession(tmp_path/'runs',exp,env,repo=repo,dataset_root=raw,purpose='pilot',required_outputs=[OutputSpec('outputs/x.json','fixture')]) as run:
        write_json(run.path/'outputs/x.json',{'x':1});run.complete()
    assert 'protocol_mismatch' in check_cache(run.path,old,'pilot').reasons
    # Simulate an independently stored old-generation manifest, without upgrading
    # any old scientific output. The current protocol must refuse its cache.
    import json
    from dynapm.core.provenance import read_json
    stored=read_json(run.path/'manifest.json')
    stored['experiment']['protocol_version']='causal-timeline-v2'
    with pytest.MonkeyPatch.context() as patch:
        import dynapm.core.run_store as store
        original=store.read_json
        patch.setattr(store,'read_json',lambda p:stored if p==run.path/'manifest.json' else original(p))
        rejected=check_cache(run.path,exp,'pilot')
        assert not rejected.reusable
        assert 'protocol_mismatch' in rejected.reasons or 'manifest_identity_mismatch' in rejected.reasons or 'unsupported_manifest_schema' in rejected.reasons
    assert check_cache(run.path,exp,'pilot').reusable


def test_metadata_audit_matches_feature_validity(synthetic_frame):
    frame=synthetic_frame.drop(synthetic_frame.index[150])
    row=audit_frame(frame,'fixture','1')
    n_boot=int(len(frame)*.3)
    # compute_split uses floor, same explicit bootstrap boundary.
    expected=build_features(frame.iloc[:n_boot],CPU)
    assert row['valid_feature_rows']==len(expected)
    assert row['gap_validity_affected'] and row['invalid_gap_affected_rows']>0


def test_gapped_eleven_policy_matrix_keeps_counts_and_common_reads(replay_repo,lag_predictor_factory,monkeypatch):
    from dynapm.experiments.pilot_execution import run_vm
    from dynapm.experiments.pilot_design import default_config
    class Cheap(lag_predictor_factory):
        def __init__(self,target,config):super().__init__(target);self.fit_calls=0
        def fit(self,frame):super().fit(frame);self.fit_calls+=1
        def diagnostics(self):return {'target':self.target,'fit_calls':self.fit_calls}
    class Detector:
        def __init__(self,**kw):self.n=0
        def update(self,r):self.n+=1;return self.n in (2,200)
    monkeypatch.setattr('dynapm.methods.dynapm_v3.ADWINDetector',Detector)
    raw=replay_repo/'data/raw/TestTrace/1.csv'
    frame=pd.read_csv(raw,sep=';').drop(index=range(300,315))
    frame.to_csv(raw,sep=';',index=False)
    answer=run_vm({'trace':'TestTrace','vm_id':'1','volatility_tier':'low'},default_config(),replay_repo,predictor_class=Cheap)
    assert len(answer['rows'])==11 and answer['diagnostics']['budget_total_equal']
    assert answer['diagnostics']['unavailable_residual_timestamps']>0
    evals=pd.DataFrame(answer['evaluations'])
    assert evals.groupby('eval_timestamp').method_id.nunique().eq(11).all()
    assert not evals[evals.method_id.str.startswith(('pw_','pp_'))].profile_age_seconds.eq(0).all()


def test_missing_raw_hourly_origin_keeps_nominal_truth_and_read(replay_repo,lag_predictor_factory):
    raw=replay_repo/'data/raw/TestTrace/1.csv'
    original=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo)
    # Remove a streaming origin while preserving the bootstrap split boundary:
    # remove one bootstrap sample too so floor(718*.3)=215 and original anchor
    # at old index216 stays at new observed index215.
    frame=pd.read_csv(raw,sep=';')
    missing=original.ground_truth.index[2]
    stamp=missing.strftime('%d.%m.%Y %H:%M:%S')
    frame=frame.drop(index=0)
    frame=frame[frame.Timestamp!=stamp]
    frame.to_csv(raw,sep=';',index=False)
    inputs=prepare_vm_inputs('TestTrace','1',repo_root=replay_repo)
    assert inputs.stream.index[0]==original.stream.index[0]
    assert missing not in inputs.observations.index and missing in inputs.ground_truth.index
    replay=replay_from_inputs(inputs,policy_factory('static_v2'))
    result=evaluate_replay(replay,include_records=True)
    record=next(r for r in result['evaluation_records'] if r['evaluation_time']==missing)
    assert record['profile_age_seconds']>0
    pd.testing.assert_series_equal(inputs.ground_truth.loc[missing],original.ground_truth.loc[missing])


def test_metadata_distinguishes_coalesced_tick_wait_from_commit_delay(synthetic_frame):
    frame=pd.concat([synthetic_frame]*3,ignore_index=True)
    frame.index=pd.date_range('2021-01-01',periods=len(frame),freq='5min')
    frame=frame.drop(frame.index[1000:1240])
    row=audit_frame(frame,'fixture','1')
    assert row['p3_max_tick_wait_seconds']>3*3600
    assert row['p3_max_delay_seconds']<3*3600
    assert row['p3_delayed_commits']>0
