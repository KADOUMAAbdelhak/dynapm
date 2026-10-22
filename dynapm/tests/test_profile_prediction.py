import numpy as np,pandas as pd,pytest
from dynapm.core.ground_truth import derive_ground_truth_at_t
from dynapm.core.discretization import compute_thresholds,classify_value
from dynapm.core.temporal import forecast_targets,FEATURE_HISTORY_SLOTS
from dynapm.experiments.profile_prediction import DirectProfile,profile_training_data,timestamp_availability
from dynapm.eval.replay import CPU_T,MEM_T

@pytest.fixture
def frame():
    idx=pd.date_range('2026-01-01',periods=1000,freq='5min')
    return pd.DataFrame({CPU_T:3+np.sin(np.arange(1000)/17),MEM_T:5+np.cos(np.arange(1000)/9)},index=idx)

def test_labels_equal_canonical_sparse_ground_truth(frame):
    sparse=frame.copy();sparse.loc[frame.index[410:420],MEM_T]=np.nan
    x,y,count=profile_training_data(sparse,CPU_T)
    target=frame.index[400];i=x.index.get_loc(target);origin=target-pd.Timedelta(minutes=5)
    th=compute_thresholds(frame,CPU_T);mt=compute_thresholds(frame,MEM_T)
    truth=derive_ground_truth_at_t(sparse,origin,cpu_thresholds=th,mem_thresholds=mt)
    assert count[i]==278
    assert y[i,1]==pytest.approx(truth['p95_cpu_next_24h'])
    assert classify_value(y[i,0],th)==truth['cpu_class']
    assert y[i,0]==pytest.approx(sparse.loc[forecast_targets(origin)].dropna()[CPU_T].mean())

def test_missing_first_label_allowed_but_missing_history_not(frame):
    gap=frame.index[350];x,y,n=profile_training_data(frame.drop(gap),CPU_T)
    assert gap in x.index and n[x.index.get_loc(gap)]==287
    assert frame.index[351] not in x.index
    assert frame.index[447] in x.index
    assert x.index[-1]+pd.Timedelta(minutes=287*5)<=frame.index[-1]

@pytest.mark.parametrize('method',['rf_profile','ridge_profile'])
def test_future_invariance_and_class_from_mean(frame,method):
    m=DirectProfile(CPU_T,method,n_estimators=3,max_depth=4);boot=frame.iloc[:700];m.fit(boot)
    t=frame.index[730];th=compute_thresholds(boot,CPU_T)
    first=m.predict_profile(frame[CPU_T],t,th)
    changed=frame[CPU_T].copy();changed.loc[changed.index>t]=1e9
    assert m.predict_profile(changed,t,th)==first
    assert first['class']==classify_value(first['mean'],th)
    assert m.last_training_target<=boot.index[-1] and m.state_bytes()>0
    with pytest.raises(ValueError):m.predict_profile(frame[CPU_T].drop(frame.index[729]),t,th)

def test_profile_history_is_nominal_and_origin_excluded(frame):
    x,y,n=profile_training_data(frame,CPU_T)
    i=0;origin=x.index[i]-pd.Timedelta(minutes=5)
    assert origin not in forecast_targets(origin)
    assert forecast_targets(origin)[-1]==origin+pd.Timedelta(hours=24)
    assert y[i,0]==pytest.approx(frame.loc[forecast_targets(origin),CPU_T].mean())
    assert n[i]==288

def test_profile_no_full_elapsed_bootstrap_horizon(frame):
    with pytest.raises(ValueError):profile_training_data(frame.iloc[:300],CPU_T)

def test_timestamp_seasonal_availability_and_gap(frame):
    idx=frame.index
    complete=timestamp_availability(idx,'trace','vm')
    assert complete['predictor_eligible_origins']==700
    assert complete['seasonal_complete_288']==700
    # Gap predates stream; 96-slot recovery completed, 288-slot recovery not yet.
    gapped=timestamp_availability(idx.delete(200),'trace','vm')
    assert gapped['seasonal_complete_288']<gapped['predictor_eligible_origins']
    assert gapped['seasonal_density_200']==gapped['predictor_eligible_origins']
    assert gapped['seasonal_incomplete_but_200']>0


def test_seasonal_profile_equals_periodic_window_even_with_gap(frame):
    from dynapm.scripts.task21_predictor_diagnosis import diagnostic_controls
    from dynapm.core.forecasting import forecast_class_from_window,forecast_p95_from_window
    from dynapm.core.temporal import trailing_observations,history_valid
    origin=frame.index[730]
    for target in (CPU_T,MEM_T):
        history=frame[target].drop(frame.index[600])
        assert history_valid(history,origin)
        seasonal=diagnostic_controls(history,origin)['seasonal_naive_24h'].dropna().to_numpy()
        window=trailing_observations(history,origin,24).to_numpy()
        threshold=compute_thresholds(frame.iloc[:500],target)
        np.testing.assert_array_equal(seasonal,window)
        assert len(window)==287
        assert forecast_class_from_window(seasonal,threshold)==forecast_class_from_window(window,threshold)
        assert forecast_p95_from_window(seasonal)==forecast_p95_from_window(window)


def test_scalar_profile_availability_is_not_288_point_predictions():
    from dynapm.experiments.profile_prediction import availability_metadata
    scalar=availability_metadata(True)
    assert scalar['profile_available']
    assert scalar['profile_feature_history_slots']==96
    assert scalar['point_forecast_slots_available'] is None
    points=availability_metadata(False,287)
    assert points['point_forecast_slots_available']==287
    assert points['profile_feature_history_slots'] is None
    with pytest.raises(ValueError):availability_metadata(False,199)
