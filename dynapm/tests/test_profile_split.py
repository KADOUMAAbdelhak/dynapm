"""Tests for profile schema, bootstrap split, provisioning, patterns, ground truth."""
from __future__ import annotations


import numpy as np
import pandas as pd

from dynapm.core.ground_truth import derive_ground_truth_at_t, derive_ground_truth_at_t_v2
from dynapm.core.pattern import derive_burst_profile, derive_diurnal_pattern
from dynapm.core.schema import (
    CPU_CLASSES,
    MEMORY_CLASSES,
)
from dynapm.data.bootstrap import LOCKED_BOOTSTRAP_FRACTION, compute_split
from dynapm.core.discretization import classify_value, compute_thresholds
from dynapm.data.provisioning import extract_provisioning

CPU_M = "CPU usage [%]"
MEM_M = "Memory usage [%]"


def test_compute_split_70_30(synthetic_frame):
    df = synthetic_frame
    n_total = len(df)
    df_b, df_s, info = compute_split(df)
    n_boot = info["n_bootstrap"]
    assert n_boot == int(np.floor(n_total * LOCKED_BOOTSTRAP_FRACTION))
    assert abs(n_boot / n_total - 0.30) < (1.0 / n_total) + 1e-9
    assert len(df_b) == n_boot
    assert info["n_streaming"] == len(df_s)
    assert info["bootstrap_end"] == info["streaming_start"]
    bs_idx = set(df_b.index)
    st_idx = set(df_s.index)
    assert bs_idx.isdisjoint(st_idx)
    assert df.index[n_boot] == info["streaming_start"]


def test_provisioning_extraction(synthetic_frame):
    df = synthetic_frame
    prov = extract_provisioning(df)
    assert prov == {"provisioned_cpu_cores": 2, "provisioned_ram_gb": 4.0}


def test_thresholds_monotone():
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 100, size=10_000)
    sdf = pd.DataFrame({CPU_M: x})
    th = compute_thresholds(sdf, CPU_M)
    assert th["p20"] < th["p40"] < th["p60"] < th["p80"] < th["p95"]


def test_classify_boundaries():
    th = {"p20": 20.0, "p40": 40.0, "p60": 60.0, "p80": 80.0, "p95": 95.0}
    assert classify_value(19.9, th) == "idle"
    assert classify_value(20.0, th) == "low"
    assert classify_value(39.9, th) == "low"
    assert classify_value(40.0, th) == "medium"
    assert classify_value(59.9, th) == "medium"
    assert classify_value(60.0, th) == "high"
    assert classify_value(79.9, th) == "high"
    assert classify_value(80.0, th) == "burst"
    assert classify_value(100.0, th) == "burst"


def test_derive_diurnal_synthetic():
    # Fewer than 2017 samples so lag-2016 autocorr is undefined → diurnal via strong lag-288 only
    n = 4 * 288
    idx = pd.date_range("2020-01-01", periods=n, freq="5min", tz=None)
    phase = np.arange(n, dtype=float) * (2 * np.pi / 288.0)
    values = 50.0 + 30.0 * np.sin(phase)
    s = pd.Series(values, index=idx)
    label = derive_diurnal_pattern(s)
    assert label == "diurnal"


def test_derive_burst_profile_thresholds():
    p95 = 50.0
    n = 10_000
    s_none = pd.Series(np.ones(n) * 10.0)
    assert derive_burst_profile(s_none, p95) == "none"

    s_occ = pd.Series(np.ones(n) * 10.0)
    s_occ.iloc[:15] = 60.0
    assert derive_burst_profile(s_occ, p95) == "occasional"

    s_freq = pd.Series(np.concatenate([np.ones(5000) * 10.0, np.ones(5000) * 60.0]))
    assert derive_burst_profile(s_freq, p95) == "frequent"


def test_ground_truth_returns_all_fields(synthetic_frame):
    df = synthetic_frame
    df_b, _, _ = compute_split(df)
    cpu_th = compute_thresholds(df_b, CPU_M)
    mem_th = compute_thresholds(df_b, MEM_M)
    t = pd.Timestamp(df.index[350])
    out = derive_ground_truth_at_t(
        df,
        t,
        window_hours=24,
        cpu_thresholds=cpu_th,
        mem_thresholds=mem_th,
    )
    assert set(out.keys()) == {
        "cpu_class",
        "memory_class",
        "p95_cpu_next_24h",
        "p95_mem_next_24h",
    }
    assert out["cpu_class"] in CPU_CLASSES
    assert out["memory_class"] in MEMORY_CLASSES
    assert np.isfinite(out["p95_cpu_next_24h"])
    assert np.isfinite(out["p95_mem_next_24h"])



def test_derive_ground_truth_v2_returns_4_keys(synthetic_frame):
    df = synthetic_frame
    df_b, _, _ = compute_split(df)
    cpu_th = compute_thresholds(df_b, CPU_M)
    mem_th = compute_thresholds(df_b, MEM_M)
    t = pd.Timestamp(df.index[350])
    out = derive_ground_truth_at_t_v2(
        df,
        t,
        backward_window_hours=1.0,
        forward_window_hours=24,
        cpu_thresholds=cpu_th,
        mem_thresholds=mem_th,
    )
    assert set(out.keys()) == {
        "cpu_class",
        "memory_class",
        "p95_cpu_next_24h",
        "p95_mem_next_24h",
    }


def test_derive_ground_truth_v2_class_matches_forward_window_mean():
    """Class GT must use the same forward horizon as predicted class (not backward 1h)."""
    idx = pd.date_range("2021-01-01", periods=600, freq="5min")
    # Past is idle (10); future is burst (95). Forward-mean class must be burst.
    cpu = np.concatenate([np.full(300, 10.0), np.full(300, 95.0)])
    mem = np.concatenate([np.full(300, 15.0), np.full(300, 90.0)])
    df = pd.DataFrame({CPU_M: cpu, MEM_M: mem}, index=idx)
    th = {"p20": 20.0, "p40": 40.0, "p60": 60.0, "p80": 80.0, "p95": 95.0}
    t = idx[299]
    out_v1 = derive_ground_truth_at_t(df, t, window_hours=24, cpu_thresholds=th, mem_thresholds=th)
    out_v2 = derive_ground_truth_at_t_v2(
        df, t, backward_window_hours=1.0, forward_window_hours=24, cpu_thresholds=th, mem_thresholds=th
    )
    assert out_v1["cpu_class"] == "burst"
    assert out_v2["cpu_class"] == "burst"
    assert out_v2["cpu_class"] == out_v1["cpu_class"]
    assert out_v2["p95_cpu_next_24h"] == out_v1["p95_cpu_next_24h"]
