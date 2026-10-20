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
CAUSAL_PROTOCOL = "causal-policy-v1"


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


def prepare_vm_replay(
    trace: str, vm_id: str, method_factory: Callable, *, repo_root=None,
    predictor_factory: Callable = VMPredictor,
) -> VMReplay:
    """Construct a policy through the same contract for evaluation and provisioning.

    Factories are policy classes or functools.partial of them. Predictor policies
    require two fitted target-specific predictors and the two observation series.
    No constructor receives a future prediction stream. The replay grid retains
    the streaming-only feature warmup used by one-step residual generation.
    """
    cls = policy_class(method_factory)
    root = REPO if repo_root is None else Path(repo_root)
    df = load_vm_csv(str(root / "data/raw" / trace / f"{vm_id}.csv"))
    boot, stream, info = compute_split(df)
    cpu_th = compute_thresholds(boot, CPU_T)
    mem_th = compute_thresholds(boot, MEM_T)
    prov = extract_provisioning(boot)
    b_end = pd.Timestamp(info["bootstrap_end"])
    profile = ProfileInstance(
        static=StaticFields(
            vm_id=str(vm_id), trace_name=trace,
            provisioned_cpu_cores=prov["provisioned_cpu_cores"],
            provisioned_ram_gb=prov["provisioned_ram_gb"],
            bootstrap_start=pd.Timestamp(info["bootstrap_start"]),
            bootstrap_end=b_end, n_total_timesteps=int(info["n_total"]),
        ),
        dynamic=DynamicFields("idle", "idle", float("nan"), float("nan")),
        last_updated={f: b_end for f in (
            "cpu_class", "memory_class", "predicted_cpu_p95_next_24h",
            "predicted_mem_p95_next_24h",
        )},
    )
    dependencies = dict(bootstrap_cpu_series=boot[CPU_T], bootstrap_mem_series=boot[MEM_T])
    predictors = None
    if cls.requires_predictors:
        cpu = predictor_factory(target=CPU_T)
        mem = predictor_factory(target=MEM_T)
        cpu.fit(boot)
        mem.fit(boot)
        predictors = (cpu, mem)
        dependencies.update(cpu_predictor=cpu, mem_predictor=mem,
                            cpu_obs_full=df[CPU_T], mem_obs_full=df[MEM_T])
    method = method_factory(profile, cpu_th, mem_th, **dependencies)

    predictions = None
    if cls.requires_residuals:
        cpu_out = predictors[0].predict_streaming(stream)
        mem_out = predictors[1].predict_streaming(stream)
        idx = cpu_out.index.intersection(mem_out.index).sort_values()
        predictions = pd.DataFrame({"cpu": cpu_out.loc[idx, "y_pred"],
                                    "mem": mem_out.loc[idx, "y_pred"]}, index=idx)
    else:
        idx = build_features(stream, CPU_T).index.intersection(
            build_features(stream, MEM_T).index).sort_values()
    observations = stream.loc[idx, [CPU_T, MEM_T]]
    gt = pd.read_parquet(root / "dynapm/results/ground_truth" / f"{trace}__{vm_id}.parquet")
    gt["eval_timestamp"] = pd.to_datetime(gt["eval_timestamp"])
    gt = gt.set_index("eval_timestamp").sort_index()
    if not gt.index.is_unique:
        raise ValueError("ground-truth evaluation timestamps must be unique")
    stream_days = (stream.index[-1] - stream.index[0]).total_seconds() / 86400.0
    return VMReplay(method, observations, predictions, gt, stream_days)


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
        window = obs.iloc[max(0, pos - lookback_steps + 1):pos + 1]
        residual_inputs = {}
        if replay.method.requires_residuals:
            residual_inputs = dict(cpu_prediction=float(replay.predictions.at[t, "cpu"]),
                                   mem_prediction=float(replay.predictions.at[t, "mem"]))
        replay.method.step(t=t, cpu_obs_window=window[CPU_T],
                           mem_obs_window=window[MEM_T], **residual_inputs)
        if t in replay.ground_truth.index:
            pending.append((pd.Timestamp(t), deepcopy(replay.method.profile.dynamic)))
        keep = []
        for origin, snapshot in pending:
            if t < origin + pd.Timedelta(hours=24):
                keep.append((origin, snapshot))
            else:
                yield origin, snapshot, replay.ground_truth.loc[origin]
        pending = keep
    replay.snapshots_dropped_unverified = len(pending)
