import numpy as np
import pandas as pd
import pytest
from dynapm.experiments.forecast_design import DirectHorizonRF,direct_training_data
from dynapm.core.predictor import forecast_at_origin
from dynapm.core.features import build_features
from dynapm.eval.replay import CPU_T

@pytest.fixture
def series():
    idx=pd.date_range('2026-01-01',periods=850,freq='5min')
    return pd.Series(3+np.sin(np.arange(850)/10),index=idx,name=CPU_T)

def test_labels_stay_inside_bootstrap(series):
    boot=series.iloc[:600].to_frame();x,y=direct_training_data(boot,CPU_T)
    assert y.shape==(len(x),288)
    np.testing.assert_allclose(y[0],series.reindex(pd.date_range(x.index[0],periods=288,freq='5min')))
    assert x.index[-1]+pd.Timedelta(minutes=287*5)<=boot.index[-1]
    np.testing.assert_allclose(x.iloc[0],build_features(boot,CPU_T).loc[x.index[0]])

def test_gap_labels_not_bridged(series):
    gap=series.index[350];x,y=direct_training_data(series.drop(gap).to_frame(),CPU_T)
    assert all(not (s<=gap<=s+pd.Timedelta(minutes=287*5)) for s in x.index)
    assert np.isfinite(y).all()

def test_direct_future_invariance_and_full_cadence(series):
    model=DirectHorizonRF(CPU_T,n_estimators=3,max_depth=4);model.fit(series.iloc[:600].to_frame())
    origin=series.index[620];a=forecast_at_origin(model,series,origin)
    mutated=series.copy();mutated.loc[mutated.index>origin]=1e9
    b=forecast_at_origin(model,mutated,origin)
    np.testing.assert_array_equal(a,b)
    assert len(a)==288 and a.index[0]==origin+pd.Timedelta(minutes=5)
    assert a.index[-1]==origin+pd.Timedelta(hours=24)
    assert model.last_training_target<=series.index[599]
    with pytest.raises(ValueError):model.predict_causal_horizon(series.loc[:origin].drop(series.index[619]))

def test_insufficient_direct_training(series):
    with pytest.raises(ValueError):direct_training_data(series.iloc[:300].to_frame(),CPU_T)


def test_no_contiguous_bootstrap_support_rejected(series):
    with pytest.raises(ValueError,match='no complete direct bootstrap labels'):
        direct_training_data(series.iloc[:700].drop(series.index[350]).to_frame(),CPU_T)

def test_prediction_feature_parity(series):
    model=DirectHorizonRF(CPU_T,n_estimators=3,max_depth=4);model.fit(series.iloc[:600].to_frame())
    origin=series.index[620]
    expected_x=build_features(series.to_frame(),CPU_T).loc[origin+pd.Timedelta(minutes=5)]
    expected=model.model.predict(expected_x.to_numpy().reshape(1,-1))[0]
    np.testing.assert_allclose(forecast_at_origin(model,series,origin).to_numpy(),expected)
