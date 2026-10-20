from __future__ import annotations

import math

from dynapm.core.forecasting import forecast_class_from_window, forecast_p95_from_window


def test_forecast_class_simple():
    thresholds = {"p20": 20.0, "p40": 40.0, "p60": 60.0, "p80": 80.0, "p95": 95.0}
    values = [45.0, 50.0, 55.0]
    assert forecast_class_from_window(values, thresholds) == "medium"


def test_forecast_class_empty():
    thresholds = {"p20": 20.0, "p40": 40.0, "p60": 60.0, "p80": 80.0, "p95": 95.0}
    assert forecast_class_from_window([], thresholds) == "idle"


def test_forecast_p95_known():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert abs(forecast_p95_from_window(values) - 4.8) < 1e-9


def test_forecast_p95_empty():
    out = forecast_p95_from_window([])
    assert math.isnan(out)
