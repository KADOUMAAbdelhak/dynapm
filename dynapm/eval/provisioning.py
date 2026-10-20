"""Resource provisioning helpers: forecast-based capacity vs realized p95."""
from __future__ import annotations

from typing import Callable

import math
import pandas as pd

from dynapm.eval.replay import CAUSAL_PROTOCOL, prepare_vm_replay, iter_verified_snapshots

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


def collect_verified_p95_pairs(
    trace: str, vm_id: str, method_factory: Callable, *, repo_root=None,
    lookback_steps: int = 288, predictor_factory=None,
) -> pd.DataFrame:
    """Use the evaluation replay contract and its verified snapshots verbatim."""
    options = {} if predictor_factory is None else {"predictor_factory": predictor_factory}
    replay = prepare_vm_replay(trace, vm_id, method_factory, repo_root=repo_root, **options)
    rows = []
    for ts, snap, gt in iter_verified_snapshots(replay, lookback_steps):
        rows.append({
            "eval_timestamp": ts,
            "snapshot_cpu_p95": float(snap.predicted_cpu_p95_next_24h),
            "snapshot_mem_p95": float(snap.predicted_mem_p95_next_24h),
            "gt_cpu_p95": float(gt["p95_cpu_next_24h"]),
            "gt_mem_p95": float(gt["p95_mem_next_24h"]),
        })
    return pd.DataFrame(rows, columns=["eval_timestamp", "snapshot_cpu_p95",
        "snapshot_mem_p95", "gt_cpu_p95", "gt_mem_p95"])


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
                "causal_protocol": CAUSAL_PROTOCOL,
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
