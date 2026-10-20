"""Residual-stream drift detector wrappers and execution helper."""
from __future__ import annotations

from typing import List

import pandas as pd


class ADWINDetector:
    def __init__(self, delta: float = 0.002):
        from river.drift import ADWIN

        self._d = ADWIN(delta=delta)
        self._delta = delta

    def update(self, residual: float) -> bool:
        self._d.update(residual)
        return bool(self._d.drift_detected)


class PageHinkleyDetector:
    def __init__(self, threshold: float = 50.0, delta: float = 0.005):
        from river.drift import PageHinkley

        self._d = PageHinkley(threshold=threshold, delta=delta)

    def update(self, residual: float) -> bool:
        self._d.update(residual)
        return bool(self._d.drift_detected)


def run_detector(
    residual_series: pd.Series,
    detector_type: str = "adwin",
    **kwargs,
) -> List[pd.Timestamp]:
    """Run detector over residual series; return drift event timestamps."""
    s = pd.Series(residual_series).dropna()
    if not isinstance(s.index, pd.DatetimeIndex):
        raise ValueError("residual_series must have a DatetimeIndex")

    det_type = detector_type.lower().strip()
    if det_type == "adwin":
        detector = ADWINDetector(**kwargs)
    elif det_type in {"pagehinkley", "page_hinkley", "ph"}:
        detector = PageHinkleyDetector(**kwargs)
    else:
        raise ValueError(f"unknown detector_type {detector_type!r}")

    out: List[pd.Timestamp] = []
    for ts, val in s.items():
        if detector.update(float(val)):
            out.append(pd.Timestamp(ts))
    return out
