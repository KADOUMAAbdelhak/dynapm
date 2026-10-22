import numpy as np
import pandas as pd
import pytest
from dynapm.core.temporal import HORIZON, METRICS
from dynapm.core.discretization import compute_thresholds
from dynapm.experiments.predictor_disposition import (bootstrap_origins, choose_content,
    operational_origins, seasonal_profile)
from dynapm.experiments.profile_prediction import DirectProfile
from dynapm.scripts.task24_predictor_disposition import run_vm, summarize


@pytest.fixture
def frame():
    idx=pd.date_range('2026-01-01',periods=3100,freq='5min')
    return pd.DataFrame({METRICS[0]:5+np.sin(np.arange(len(idx))/20),
                         METRICS[1]:7+np.cos(np.arange(len(idx))/30)},index=idx)


@pytest.mark.parametrize('a,b,c,d,expected',[
    (.8,.7,1,2,'rf_profile'),(.7,.7,1,2,'seasonal'),(.8,.7,2,2,'seasonal'),
    (.8,.7,3,2,'seasonal'),(.6,.7,1,2,'seasonal')])
def test_strict_both_selector(a,b,c,d,expected):
    assert choose_content(a,b,c,d)==expected


def test_selector_rejects_missing_evidence():
    with pytest.raises(ValueError):choose_content(np.nan,.5,1,2)


def test_bootstrap_rolling_origins_are_deterministic_and_elapsed(frame):
    boot=frame.iloc[:2600]
    origins=bootstrap_origins(boot)
    assert len(origins)==4 and origins.equals(bootstrap_origins(boot))
    assert origins.min()>=boot.index[0]+pd.Timedelta(hours=72)
    assert origins.max()+HORIZON<=boot.index[-1]
    changed=frame.copy();changed.loc[changed.index>boot.index[-1]]=1e12
    assert origins.equals(bootstrap_origins(changed.iloc[:2600]))
    for origin in origins:
        model=DirectProfile(METRICS[0],n_estimators=2,max_depth=3)
        model.fit(boot.loc[:origin])
        assert model.last_training_target<=origin


def test_insufficient_bootstrap_refuses_selection(frame):
    with pytest.raises(ValueError):bootstrap_origins(frame.iloc[:500])


def test_content_future_invariance_both_resources(frame):
    origin=frame.index[2700]
    changed=frame.copy();changed.loc[changed.index>origin]=1e12
    for resource in METRICS:
        threshold=compute_thresholds(frame.iloc[:2600],resource)
        model=DirectProfile(resource,n_estimators=2,max_depth=3);model.fit(frame.iloc[:2600])
        assert model.predict_profile(frame[resource],origin,threshold)==model.predict_profile(changed[resource],origin,threshold)
        assert seasonal_profile(frame[resource],origin,threshold)==seasonal_profile(changed[resource],origin,threshold)


def test_seasonal_missing_history_no_hidden_fallback(frame):
    origin=frame.index[2700]
    sparse=frame[METRICS[0]].drop(frame.index[2500:2600])
    assert seasonal_profile(sparse,origin,compute_thresholds(frame,METRICS[0])) is None


def events_fixture():
    t=pd.Timestamp('2026-02-01')
    return pd.DataFrame([dict(trace='trace',vm_id='1',method_id=m,trigger=kind,actual_commit_time=t+pd.Timedelta(hours=h))
        for m,kind,h in [('pp_6h','periodic',0),('v3','periodic',0),('v3','drift',1),('pp_3h','periodic',3)]])


def test_actual_origin_union_includes_all_predictor_policies():
    selected=operational_origins(events_fixture())
    assert len(selected)==3
    assert set(selected.origin_group)=={'periodic_6h','v3_drift','other_predictor_refresh'}
    assert selected.source_methods.iloc[0]=='pp_6h|v3'
    changed=events_fixture().assign(irrelevant_outcome=np.arange(4))
    pd.testing.assert_frame_equal(selected,operational_origins(changed))


def test_origin_mismatch_and_collision_refused():
    events=events_fixture()
    with pytest.raises(ValueError):operational_origins(events[events.method_id.ne('pp_6h')])
    events.loc[events.trigger.eq('drift'),'actual_commit_time']=events.actual_commit_time.iloc[0]
    with pytest.raises(ValueError):operational_origins(events)


def test_production_diagnostic_path_bootstrap_freeze_and_common_truth(frame,monkeypatch):
    from types import SimpleNamespace
    import dynapm.scripts.task24_predictor_disposition as driver
    inputs=SimpleNamespace(frame=frame,bootstrap=frame.iloc[:2600],
        cpu_thresholds=compute_thresholds(frame.iloc[:2600],METRICS[0]),
        mem_thresholds=compute_thresholds(frame.iloc[:2600],METRICS[1]))
    monkeypatch.setattr(driver,'prepare_vm_inputs',lambda *a,**k:inputs)
    class FakeModel:
        def __init__(self,*a,**k):pass
        def fit(self,boot):self.last_training_target=boot.index[-1];self.training_rows=10
        def state_bytes(self):return 1
        def predict_profile(self,series,origin,thresholds):return seasonal_profile(series,origin,thresholds)
    monkeypatch.setattr(driver,'DirectProfile',FakeModel)
    origins=pd.DataFrame({'origin':frame.index[[2700,2750]],'origin_group':['periodic_6h','v3_drift']})
    rows,validation,choices,availability,costs=run_vm((None,{'trace':'trace','vm_id':'1','volatility_tier':'low'},origins))
    assert len(rows)==12 and len(validation)==16 and len(choices)==2
    assert all(c['selected_method']=='seasonal' for c in choices)
    assert all(v['last_training_target']<=v['origin'] and v['validation_horizon_end']<=v['bootstrap_end'] for v in validation)
    assert all(c['selection_cutoff']<origins.origin.min() for c in choices)
    vm,macro,tiers,wins=summarize(pd.DataFrame(rows))
    assert macro.groupby(['origin_group','resource']).class_correct.nunique().eq(1).all()
    assert all(w['losses']==0 and w['wins']==0 for w in wins)
