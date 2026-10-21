"""Shared causal policy construction and snapshot-and-verify replay.

Each invocation fits CPU/memory predictors once on bootstrap observations only.
Residual predictions are recomputed by the current causal implementation, never
loaded from an unverified cached generation. Observation policies fit no model.
"""
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Callable

import pandas as pd

from dynapm.core.discretization import compute_thresholds
from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.core.ground_truth import derive_ground_truth_at_t_v2
from dynapm.core.temporal import HORIZON, TEMPORAL_PROTOCOL
from dynapm.core.features import build_features
from dynapm.core.predictor import VMPredictor
from dynapm.core.schema import DynamicFields, ProfileInstance, StaticFields
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv
from dynapm.data.provisioning import extract_provisioning
from dynapm.methods.factories import policy_class
from dynapm.methods.baselines_v2 import _BasePolicyV2

CPU_T = "CPU usage [%]"
MEM_T = "Memory usage [%]"
REPO = Path(__file__).resolve().parents[2]
CAUSAL_PROTOCOL = TEMPORAL_PROTOCOL


def require_causal_protocol(frame: pd.DataFrame) -> None:
    """Refuse unversioned measurements rather than relabeling them as causal."""
    if "causal_protocol" not in frame or not frame["causal_protocol"].eq(CAUSAL_PROTOCOL).all():
        raise ValueError("data has no matching causal protocol; create a fresh experimental generation")


@dataclass
class VMReplay:
    method: _BasePolicyV2
    observations: pd.DataFrame
    predictions: pd.DataFrame | None
    ground_truth: pd.DataFrame
    stream_days: float
    snapshots_dropped_unverified: int = 0


@dataclass
class PreparedVM:
    """Read-only per-VM inputs; target models are fit once, never by a policy."""
    frame: pd.DataFrame
    bootstrap: pd.DataFrame
    stream: pd.DataFrame
    info: dict
    profile: ProfileInstance
    cpu_thresholds: dict
    mem_thresholds: dict
    predictors: tuple | None
    observations: pd.DataFrame
    predictions: pd.DataFrame | None
    ground_truth: pd.DataFrame
    stream_days: float


def prepare_vm_inputs(trace, vm_id, *, repo_root=None, predictor_factory=VMPredictor,
                      with_predictors=False, with_residuals=True, bootstrap_fraction=0.30,
                      evaluation_period_hours=12, minimum_ground_truth_slots=200):
    root = REPO if repo_root is None else Path(repo_root)
    df = load_vm_csv(str(root / "data/raw" / trace / f"{vm_id}.csv"))
    boot, stream, info = compute_split(df, bootstrap_fraction)
    cpu_th, mem_th = compute_thresholds(boot, CPU_T), compute_thresholds(boot, MEM_T)
    prov = extract_provisioning(boot)
    b_end = pd.Timestamp(info["bootstrap_end"])
    profile = ProfileInstance(
        static=StaticFields(vm_id=str(vm_id), trace_name=trace,
            provisioned_cpu_cores=prov["provisioned_cpu_cores"],
            provisioned_ram_gb=prov["provisioned_ram_gb"],
            bootstrap_start=pd.Timestamp(info["bootstrap_start"]), bootstrap_end=b_end,
            n_total_timesteps=int(info["n_total"])),
        dynamic=DynamicFields("idle", "idle", float("nan"), float("nan")),
        last_updated={f: b_end for f in ("cpu_class", "memory_class",
            "predicted_cpu_p95_next_24h", "predicted_mem_p95_next_24h")})
    predictors, predictions = None, None
    if with_predictors:
        cpu, mem = predictor_factory(target=CPU_T), predictor_factory(target=MEM_T)
        cpu.fit(boot)
        mem.fit(boot)
        predictors = cpu, mem
    if with_predictors and with_residuals:
        cpu_out, mem_out = cpu.predict_streaming(stream), mem.predict_streaming(stream)
        idx = cpu_out.index.intersection(mem_out.index).sort_values()
        predictions = pd.DataFrame({"cpu": cpu_out.loc[idx, "y_pred"],
                                    "mem": mem_out.loc[idx, "y_pred"]}, index=idx)
    else:
        idx = build_features(stream, CPU_T).index.intersection(
            build_features(stream, MEM_T).index).sort_values()
    observations = stream.loc[idx, [CPU_T, MEM_T]]
    candidates, _ = compute_data_aware_evaluation_timestamps(df, stream.index,
        period_hours=evaluation_period_hours, min_observations_in_window=minimum_ground_truth_slots)
    rows = [{"eval_timestamp": t, **derive_ground_truth_at_t_v2(df, t,
        cpu_thresholds=cpu_th, mem_thresholds=mem_th,
        min_observations_in_window=minimum_ground_truth_slots)} for t in candidates if t in idx]
    gt = pd.DataFrame(rows, columns=["eval_timestamp", "cpu_class", "memory_class",
        "p95_cpu_next_24h", "p95_mem_next_24h"]).set_index("eval_timestamp")
    days = (stream.index[-1]-stream.index[0]).total_seconds()/86400.0
    return PreparedVM(df, boot, stream, info, profile, cpu_th, mem_th,
                      predictors, observations, predictions, gt, days)


def replay_from_inputs(inputs, method_factory):
    """Construct independent policy state over identical observations and labels."""
    cls = policy_class(method_factory)
    deps = dict(bootstrap_cpu_series=inputs.bootstrap[CPU_T],
                bootstrap_mem_series=inputs.bootstrap[MEM_T])
    if cls.requires_predictors:
        if inputs.predictors is None:
            raise ValueError("predictor-grounded replay requires prepared target models")
        deps.update(cpu_predictor=inputs.predictors[0], mem_predictor=inputs.predictors[1],
                    cpu_obs_full=inputs.frame[CPU_T], mem_obs_full=inputs.frame[MEM_T])
    method = method_factory(deepcopy(inputs.profile), inputs.cpu_thresholds, inputs.mem_thresholds, **deps)
    return VMReplay(method, inputs.observations,
                    inputs.predictions if cls.requires_residuals else None,
                    inputs.ground_truth, inputs.stream_days)


def prepare_vm_replay(trace, vm_id, method_factory, *, repo_root=None,
                      predictor_factory=VMPredictor):
    """Standalone compatibility path; managed matrices use shared PreparedVM."""
    inputs = prepare_vm_inputs(trace, vm_id, repo_root=repo_root,
        predictor_factory=predictor_factory, with_predictors=policy_class(method_factory).requires_predictors,
        with_residuals=policy_class(method_factory).requires_residuals)
    return replay_from_inputs(inputs, method_factory)


def iter_verified_snapshots(replay: VMReplay, lookback_steps: int = 288):
    """Yield (origin, copied snapshot, ground truth) only after the 24h horizon.

    Policies see current/past observations and, for V3 only, current causal
    one-step predictions. Forward ground truth is used solely for verification.
    """
    if lookback_steps <= 0:
        raise ValueError("lookback_steps must be positive")
    obs = replay.observations
    pending = []
    for pos, t in enumerate(obs.index):
        # Prepared yhat(t|past) uses no u_t; the observation is now visible.
        # step consumes r_t, updates drift, resolves triggers, then commits once.
        window = obs.iloc[max(0, pos - lookback_steps + 1):pos + 1]
        residual_inputs = {}
        if replay.method.requires_residuals:
            residual_inputs = dict(cpu_prediction=float(replay.predictions.at[t, "cpu"]),
                                   mem_prediction=float(replay.predictions.at[t, "mem"]))
        replay.method.step(t=t, cpu_obs_window=window[CPU_T],
                           mem_obs_window=window[MEM_T], **residual_inputs)
        # Refresh-before-read: a coincident evaluation sees the committed state.
        if t in replay.ground_truth.index:
            pending.append((pd.Timestamp(t), deepcopy(replay.method.profile.dynamic)))
        keep = []
        for origin, snapshot in pending:
            if t < origin + HORIZON:
                keep.append((origin, snapshot))
            else:
                yield origin, snapshot, replay.ground_truth.loc[origin]
        pending = keep
    replay.snapshots_dropped_unverified = len(pending)
