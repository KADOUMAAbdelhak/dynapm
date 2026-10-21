import numpy as np
import pandas as pd
import pytest
from dynapm.scripts.task21_predictor_diagnosis import choose_origins, diagnostic_controls, LEADS

def test_origins_deterministic_and_bounded():
    idx=pd.date_range('2026-01-01',periods=100,freq='h')
    a=choose_origins(idx)
    assert a.equals(choose_origins(idx)) and len(a)==8 and a.is_unique
    assert a[0]==idx[0] and a[-1]==idx[-1]
    with pytest.raises(ValueError): choose_origins(idx[:7])

def test_controls_causal_exact_time():
    idx=pd.date_range('2026-01-01',periods=1000,freq='5min')
    s=pd.Series(np.arange(1000,dtype=float),index=idx)
    origin=idx[500]
    a=diagnostic_controls(s,origin)
    s.loc[s.index>origin]=1e9
    b=diagnostic_controls(s,origin)
    for name in a:
        assert a[name].equals(b[name]) and len(a[name])==288
    assert a['persistence'].eq(500).all()
    assert a['seasonal_naive_24h'].iloc[0]==213

def test_seasonal_missing_remains_missing():
    idx=pd.date_range('2026-01-01',periods=600,freq='5min')
    s=pd.Series(1.,index=idx).drop(idx[213])
    assert np.isnan(diagnostic_controls(s,idx[500])['seasonal_naive_24h'].iloc[0])
    assert LEADS==(1,12,72,144,288)
