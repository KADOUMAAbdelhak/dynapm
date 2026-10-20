from __future__ import annotations

import numpy as np
import pandas as pd

from dynapm.core.drift import ADWINDetector, PageHinkleyDetector, run_detector


def test_adwin_no_drift_on_constant():
    rng = np.random.default_rng(42)
    d = ADWINDetector(delta=0.002)
    detected = False
    for x in rng.normal(0.0, 1e-4, size=5000):
        detected = detected or d.update(float(x))
    assert not detected


def test_adwin_drift_on_shift():
    rng = np.random.default_rng(42)
    d = ADWINDetector(delta=0.002)
    events = []
    vals = np.concatenate([rng.normal(0.0, 0.1, size=1000), rng.normal(5.0, 0.1, size=1000)])
    for i, x in enumerate(vals):
        if d.update(float(x)):
            events.append(i)
    assert len(events) >= 1
    assert any(i >= 1000 for i in events)


def test_page_hinkley_drift_on_shift():
    rng = np.random.default_rng(42)
    d = PageHinkleyDetector(threshold=50.0, delta=0.005)
    events = []
    vals = np.concatenate([rng.normal(0.0, 0.1, size=1000), rng.normal(5.0, 0.1, size=1000)])
    for i, x in enumerate(vals):
        if d.update(float(x)):
            events.append(i)
    assert len(events) >= 1
    assert any(i >= 1000 for i in events)


def test_run_detector_returns_timestamps():
    idx = pd.date_range("2021-01-01", periods=2000, freq="5min")
    vals = np.concatenate([np.zeros(1000), np.ones(1000) * 5.0])
    s = pd.Series(vals, index=idx)
    ts = run_detector(s, detector_type="adwin", delta=0.002)
    assert len(ts) >= 1
    assert all(isinstance(t, pd.Timestamp) for t in ts)
    assert all(t >= idx[1000] for t in ts)
