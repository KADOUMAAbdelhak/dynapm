"""Resource provisioning helpers: forecast-based capacity vs realized p95."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable

import math
import pandas as pd

from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv
from dynapm.eval.runner import _thresholds

SAFETY_FACTOR = 1.2
OVER_THRESHOLD = 1.5


def evaluate_provisioning(
    forecast_p95: float,
    actual_p95: float,
    safety_factor: float = SAFETY_FACTOR,
    over_threshold: float = OVER_THRESHOLD,
) -> dict:
    """
    Evaluates a single (forecast, actual) pair.

    Returns keys:
      ``recommendation`` (forecast * safety_factor),
      ``actual``,
      ``error`` (recommendation - actual),
      ``under_provisioned`` (0/1 or NaN if inputs invalid),
      ``over_provisioned``,
      ``well_provisioned``.
    """
    if not math.isfinite(forecast_p95) or not math.isfinite(actual_p95):
        nan = float("nan")
        return {
            "recommendation": nan,
            "actual": nan,
            "error": nan,
            "under_provisioned": nan,
            "over_provisioned": nan,
            "well_provisioned": nan,
        }
    rec = forecast_p95 * safety_factor
    under = actual_p95 > rec
    over = rec > actual_p95 * over_threshold
    well = not under and not over
    return {
        "recommendation": rec,
        "actual": actual_p95,
        "error": rec - actual_p95,
        "under_provisioned": int(under),
        "over_provisioned": int(over),
        "well_provisioned": int(well),
    }


def _series_window(series: pd.Series, pos: int, lookback_steps: int) -> pd.Series:
    start = max(0, pos - lookback_steps + 1)
    return series.iloc[start : pos + 1]


def collect_verified_p95_pairs(
    trace: str,
    vm_id: str,
    method_factory: Callable,
    *,
    repo_root=None,
    lookback_steps: int = 288,
) -> pd.DataFrame:
    """
    Replays the runner_v2 stream and emits one row per **verified** eval point with
    snapshot p95 predictors and matching GT forward-window p95.
    Mirrors runner_v2 without mutating runner code.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    RESID_FULL = repo_root / "dynapm/results/residuals_full"
    GT_DIR = repo_root / "dynapm/results/ground_truth"

    path = repo_root / "data/raw" / trace / f"{vm_id}.csv"
    df = load_vm_csv(str(path))
    df_boot, _, info = compute_split(df)

    cpu_th, mem_th, prov = _thresholds(trace, vm_id)
    b_end = pd.Timestamp(info["bootstrap_end"])

    profile = ProfileInstance(
        static=StaticFields(
            vm_id=str(vm_id),
            trace_name=trace,
            provisioned_cpu_cores=prov["provisioned_cpu_cores"],
            provisioned_ram_gb=prov["provisioned_ram_gb"],
            bootstrap_start=pd.Timestamp(info["bootstrap_start"]),
            bootstrap_end=b_end,
            n_total_timesteps=int(info["n_total"]),
        ),
        dynamic=DynamicFields(
            cpu_class="idle",
            memory_class="idle",
            predicted_cpu_p95_next_24h=float("nan"),
            predicted_mem_p95_next_24h=float("nan"),
        ),
        last_updated={
            "cpu_class": b_end,
            "memory_class": b_end,
            "predicted_cpu_p95_next_24h": b_end,
            "predicted_mem_p95_next_24h": b_end,
        },
    )

    cpu_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__cpu.parquet")
    mem_resid = pd.read_parquet(RESID_FULL / f"{trace}__{vm_id}__mem.parquet")
    cpu_resid.index = pd.to_datetime(cpu_resid.index)
    mem_resid.index = pd.to_datetime(mem_resid.index)

    gt = pd.read_parquet(GT_DIR / f"{trace}__{vm_id}.parquet")
    gt["eval_timestamp"] = pd.to_datetime(gt["eval_timestamp"])
    gt_map = gt.set_index("eval_timestamp").sort_index()

    common_idx = cpu_resid.index.intersection(mem_resid.index).sort_values()
    cpu_resid = cpu_resid.loc[common_idx]
    mem_resid = mem_resid.loc[common_idx]

    cpu_obs_s = cpu_resid["y_true"]
    mem_obs_s = mem_resid["y_true"]
    cpu_pred_s = cpu_resid["y_pred"]
    mem_pred_s = mem_resid["y_pred"]

    method = method_factory(
        profile,
        cpu_th,
        mem_th,
        bootstrap_cpu_series=df_boot["CPU usage [%]"],
        bootstrap_mem_series=df_boot["Memory usage [%]"],
        cpu_pred_full=cpu_pred_s,
        mem_pred_full=mem_pred_s,
    )

    eval_set = set(gt_map.index)
    snapshot_queue = []
    records: list[dict] = []

    for pos, t in enumerate(common_idx):
        cpu_obs_window = _series_window(cpu_obs_s, pos, lookback_steps)
        mem_obs_window = _series_window(mem_obs_s, pos, lookback_steps)
        cpu_pred_window = _series_window(cpu_pred_s, pos, lookback_steps)
        mem_pred_window = _series_window(mem_pred_s, pos, lookback_steps)

        method.step(
            t=t,
            cpu_obs_window=cpu_obs_window,
            mem_obs_window=mem_obs_window,
            cpu_pred_window=cpu_pred_window,
            mem_pred_window=mem_pred_window,
        )

        if t in eval_set:
            snapshot_queue.append(
                {
                    "eval_timestamp": pd.Timestamp(t),
                    "snapshot": deepcopy(profile.dynamic),
                }
            )

        now_t = pd.Timestamp(t)
        keep = []
        for row in snapshot_queue:
            verify_t = pd.Timestamp(row["eval_timestamp"]) + pd.Timedelta(hours=24)
            if now_t < verify_t:
                keep.append(row)
                continue
            ts = pd.Timestamp(row["eval_timestamp"])
            if ts not in gt_map.index:
                continue
            g = gt_map.loc[ts]
            snap = row["snapshot"]
            records.append(
                {
                    "eval_timestamp": ts,
                    "snapshot_cpu_p95": float(snap.predicted_cpu_p95_next_24h),
                    "snapshot_mem_p95": float(snap.predicted_mem_p95_next_24h),
                    "gt_cpu_p95": float(g["p95_cpu_next_24h"]),
                    "gt_mem_p95": float(g["p95_mem_next_24h"]),
                }
            )
        snapshot_queue = keep

    return pd.DataFrame(records)


def rows_to_provisioning_df(
    method: str,
    trace: str,
    vm_id: str,
    volatility_tier: str,
    pairs: pd.DataFrame,
    *,
    safety_factor: float,
    over_threshold: float = OVER_THRESHOLD,
) -> pd.DataFrame:
    """Flatten evaluate_provisioning outputs to task schema."""
    rows = []
    for _, r in pairs.iterrows():
        cpu = evaluate_provisioning(
            r["snapshot_cpu_p95"], r["gt_cpu_p95"], safety_factor, over_threshold
        )
        mem = evaluate_provisioning(
            r["snapshot_mem_p95"], r["gt_mem_p95"], safety_factor, over_threshold
        )
        rows.append(
            {
                "method": method,
                "trace": trace,
                "vm_id": str(vm_id),
                "eval_timestamp": pd.Timestamp(r["eval_timestamp"]),
                "volatility_tier": volatility_tier,
                "cpu_forecast_p95": r["snapshot_cpu_p95"],
                "cpu_actual_p95": r["gt_cpu_p95"],
                "cpu_recommendation": cpu["recommendation"],
                "cpu_error": cpu["error"],
                "cpu_under": cpu["under_provisioned"],
                "cpu_over": cpu["over_provisioned"],
                "cpu_well": cpu["well_provisioned"],
                "mem_forecast_p95": r["snapshot_mem_p95"],
                "mem_actual_p95": r["gt_mem_p95"],
                "mem_recommendation": mem["recommendation"],
                "mem_error": mem["error"],
                "mem_under": mem["under_provisioned"],
                "mem_over": mem["over_provisioned"],
                "mem_well": mem["well_provisioned"],
            }
        )
    return pd.DataFrame(rows)
