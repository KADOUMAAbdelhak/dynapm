"""Tests for DynAPM v3 policy (periodic predictor + drift augmentation)."""
from __future__ import annotations

import pandas as pd

from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.methods.dynapm_v3 import DynAPMPolicyV3


def _minimal_profile():
    t0 = pd.Timestamp("2021-01-01 00:00:00")
    return ProfileInstance(
        static=StaticFields(
            vm_id="vm",
            trace_name="TestTrace",
            provisioned_cpu_cores=2,
            provisioned_ram_gb=4.0,
            bootstrap_start=t0,
            bootstrap_end=t0,
            n_total_timesteps=500,
        ),
        dynamic=DynamicFields(
            cpu_class="idle",
            memory_class="idle",
            predicted_cpu_p95_next_24h=float("nan"),
            predicted_mem_p95_next_24h=float("nan"),
        ),
        last_updated={
            "cpu_class": t0,
            "memory_class": t0,
            "predicted_cpu_p95_next_24h": t0,
            "predicted_mem_p95_next_24h": t0,
        },
    )


def _thresholds_medium_band():
    return {"p20": 10.0, "p40": 30.0, "p60": 60.0, "p80": 90.0, "p95": 95.0}


def test_dynapm_v3_initializes():
    profile = _minimal_profile()
    th = _thresholds_medium_band()
    idx_boot = pd.date_range("2021-01-01", periods=50, freq="5min")
    boot_cpu = pd.Series([45.0] * 50, index=idx_boot)
    boot_mem = pd.Series([45.0] * 50, index=idx_boot)
    idx_full = pd.date_range("2021-01-02", periods=400, freq="5min")
    pred_cpu = pd.Series([50.0] * 400, index=idx_full)
    pred_mem = pd.Series([50.0] * 400, index=idx_full)

    pol = DynAPMPolicyV3(
        profile,
        th,
        th,
        bootstrap_cpu_series=boot_cpu,
        bootstrap_mem_series=boot_mem,
        cpu_pred_full=pred_cpu,
        mem_pred_full=pred_mem,
        period_hours=6.0,
        drift_delta=0.002,
    )
    assert pol.profile.dynamic.cpu_class == "medium"
    assert pol.profile.dynamic.memory_class == "medium"
    assert not pd.isna(pol.profile.dynamic.predicted_cpu_p95_next_24h)
    assert not pd.isna(pol.profile.dynamic.predicted_mem_p95_next_24h)


def test_dynapm_v3_periodic_only():
    profile = _minimal_profile()
    th = _thresholds_medium_band()
    idx_boot = pd.date_range("2021-01-01", periods=20, freq="5min")
    boot_cpu = pd.Series([25.0] * 20, index=idx_boot)
    boot_mem = pd.Series([25.0] * 20, index=idx_boot)
    idx_full = pd.date_range("2021-01-02", periods=2000, freq="5min")
    pred_cpu = pd.Series([25.0] * len(idx_full), index=idx_full)
    pred_mem = pred_cpu.copy()

    pol = DynAPMPolicyV3(
        profile,
        th,
        th,
        bootstrap_cpu_series=boot_cpu,
        bootstrap_mem_series=boot_mem,
        cpu_pred_full=pred_cpu,
        mem_pred_full=pred_mem,
        period_hours=1.0,
        drift_delta=0.002,
    )

    for ts in idx_full:
        y = 25.0
        obs = pd.Series([y], index=[ts])
        pc = pd.Series([float(pred_cpu.loc[ts])], index=[ts])
        pm = pd.Series([float(pred_mem.loc[ts])], index=[ts])
        pol.step(ts, obs, obs, pc, pm)

    assert len(pol.update_log) > 0
    reasons = {r.get("reason") for r in pol.update_log}
    assert reasons == {"periodic"}, reasons


def test_dynapm_v3_drift_adds_extra_refreshes():
    profile = _minimal_profile()
    th = _thresholds_medium_band()
    idx_boot = pd.date_range("2021-01-01", periods=20, freq="5min")
    boot_cpu = pd.Series([20.0] * 20, index=idx_boot)
    boot_mem = pd.Series([20.0] * 20, index=idx_boot)
    idx_full = pd.date_range("2021-01-02", periods=1500, freq="5min")
    pred_cpu = pd.Series([10.0] * len(idx_full), index=idx_full)
    pred_mem = pred_cpu.copy()

    pol = DynAPMPolicyV3(
        profile,
        th,
        th,
        bootstrap_cpu_series=boot_cpu,
        bootstrap_mem_series=boot_mem,
        cpu_pred_full=pred_cpu,
        mem_pred_full=pred_mem,
        period_hours=5000.0,
        drift_delta=0.002,
    )

    for i, ts in enumerate(idx_full):
        if i < 400:
            y = 10.0
        else:
            y = 95.0
        obs = pd.Series([y], index=[ts])
        pc = pd.Series([float(pred_cpu.loc[ts])], index=[ts])
        pm = pd.Series([float(pred_mem.loc[ts])], index=[ts])
        pol.step(ts, obs, obs, pc, pm)

    reasons = [r.get("reason") for r in pol.update_log]
    assert "drift" in reasons, reasons
