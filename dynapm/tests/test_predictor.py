"""Unit tests for feature engineering and VM predictor pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from dynapm.core.features import LAGS, ROLL_WINDOWS, build_features
from dynapm.core.predictor import VMPredictor
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv

REPO = Path(__file__).resolve().parents[2]
TRACE1_501 = str(REPO / "data/raw/Materna-Trace-1/501.csv")
CPU_T = "CPU usage [%]"
MEM_T = "Memory usage [%]"


def _assert_feature_set(df_feat: pd.DataFrame, n_input: int) -> None:
    for lag in LAGS:
        assert f"target_lag_{lag}" in df_feat.columns
    for w in ROLL_WINDOWS:
        assert f"target_roll_mean_{w}" in df_feat.columns
        assert f"target_roll_std_{w}" in df_feat.columns
        assert f"target_roll_min_{w}" in df_feat.columns
        assert f"target_roll_max_{w}" in df_feat.columns
        assert f"target_roll_range_{w}" in df_feat.columns
    for c in ("hour_sin", "hour_cos", "dow_sin", "dow_cos", "target_diff_1", "target_diff_12"):
        assert c in df_feat.columns
    assert not df_feat.isna().any().any()
    assert len(df_feat) == (n_input - 96)


def test_features_cpu_target():
    df = load_vm_csv(TRACE1_501)
    feat = build_features(df, CPU_T)
    _assert_feature_set(feat, len(df))


def test_features_memory_target():
    df = load_vm_csv(TRACE1_501)
    feat = build_features(df, MEM_T)
    _assert_feature_set(feat, len(df))


def test_predictor_fits_and_predicts():
    df = load_vm_csv(TRACE1_501)
    df_b, df_s, _ = compute_split(df)
    p = VMPredictor(target=CPU_T)
    p.fit(df_b)
    out = p.predict_streaming(df_s)
    assert list(out.columns) == ["y_true", "y_pred", "residual"]
    assert len(out) > 0


def test_predictor_residuals_finite():
    df = load_vm_csv(TRACE1_501)
    df_b, df_s, _ = compute_split(df)
    p = VMPredictor(target=MEM_T)
    p.fit(df_b)
    out = p.predict_streaming(df_s)
    vals = out["residual"].to_numpy(dtype=float)
    assert np.isfinite(vals).all()


def test_predictor_train_test_separation():
    df = load_vm_csv(TRACE1_501)
    df_b, df_s, info = compute_split(df)
    p = VMPredictor(target=CPU_T)
    p.fit(df_b)
    out = p.predict_streaming(df_s)
    assert len(out) > 0
    assert out.index.min() >= info["streaming_start"]
