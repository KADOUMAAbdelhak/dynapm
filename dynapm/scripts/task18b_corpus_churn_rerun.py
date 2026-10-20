#!/usr/bin/env python3
"""Optional PP/V3 replay and direct aggregation of canonical accounting counters."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import wilcoxon

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from dynapm.core.accounting import ACCOUNTING_SCHEMA, ACCOUNTING_METRICS, require_accounting_metrics
from dynapm.eval.metrics import summarize_accounting
from dynapm.eval.replay import CAUSAL_PROTOCOL
from dynapm.eval.runner_v2 import run_method_on_vm  # noqa: E402
from dynapm.methods.factories import policy_factory  # noqa: E402


PP = "periodic_predictor_6h_v2"
V3 = "dynapm_v3_v2"
FACTORIES = {name: policy_factory(name) for name in (PP, V3)}
OUT_JSON = REPO / "dynapm/results/eval_full_corpus_with_log"
PARQUET_OUT = REPO / "dynapm/data/accounting_corpus.parquet"


def _precheck_vm(trace: str, vm_id: str) -> str | None:
    vm_id = str(vm_id)
    if not (REPO / "data/raw" / trace / f"{vm_id}.csv").is_file():
        return "MissingRawCsv"
    return None


def _run_one(method: str, trace: str, vm_id: str) -> tuple[str, float | None]:
    """Returns cache_hit True as wall 0.0; fresh run CPU seconds; None if skipped/failed."""
    outp = OUT_JSON / f"{method}__{trace}__{vm_id}.json"
    pre = _precheck_vm(trace, vm_id)

    if pre is None and outp.is_file():
        try:
            data = json.loads(outp.read_text(encoding="utf-8"))
            require_accounting_metrics(pd.DataFrame([{**data, "method": method}]))
            cc = data.get("cpu_class_accuracy")
            if (
                data.get("causal_protocol") == CAUSAL_PROTOCOL
                and isinstance(cc, (int, float))
                and math.isfinite(float(cc))
            ):
                return "cached", 0.0
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    if pre is not None:
        row = {"method": method, "trace": trace, "vm_id": str(vm_id), "run_status": "skipped", "failure_reason": pre}
        outp.write_text(json.dumps(row), encoding="utf-8")
        return "skipped", None

    t0 = time.perf_counter()
    try:
        out = run_method_on_vm(trace, vm_id, FACTORIES[method])
        outp.write_text(json.dumps(out, default=str), encoding="utf-8")
        return "ok", time.perf_counter() - t0
    except Exception as e:
        row = {
            "method": method,
            "trace": trace,
            "vm_id": str(vm_id),
            "run_status": "failed",
            "failure_reason": type(e).__name__,
        }
        outp.write_text(json.dumps(row), encoding="utf-8")
        return "failed", None


def run_corpus(n_jobs: int) -> tuple[float, int, int, int]:
    OUT_JSON.mkdir(parents=True, exist_ok=True)
    kept_path = REPO / "dynapm/data/kept_vms.json"
    kept = json.loads(kept_path.read_text(encoding="utf-8"))
    assert len(kept) == 1576, len(kept)

    jobs = [(m, item["trace"], str(item["vm_id"])) for m in (PP, V3) for item in kept]
    assert len(jobs) == 3152

    wall0 = time.perf_counter()
    results = Parallel(n_jobs=n_jobs, backend="loky")(delayed(_run_one)(m, tr, vm) for m, tr, vm in jobs)
    wall = time.perf_counter() - wall0

    n_cached = sum(1 for tag, wt in results if tag == "cached")
    n_ok = sum(1 for tag, wt in results if tag == "ok")
    n_fail = sum(1 for tag, _ in results if tag == "failed")
    return wall, n_ok, n_cached, n_fail


def _bootstrap_ci_delta(delta: np.ndarray, n_boot: int = 1000, seed: int = 18) -> tuple[float, float, float]:
    d = delta[np.isfinite(delta)]
    if len(d) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = len(d)
    means = np.array([float(d[rng.integers(0, n, size=n)].mean()) for _ in range(n_boot)])
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _wilcox(d: np.ndarray) -> float | None:
    d = d[np.isfinite(d)]
    if len(d) < 3 or np.allclose(d, 0):
        return None
    try:
        return float(wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue)
    except ValueError:
        return None


def row_from_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("causal_protocol") != CAUSAL_PROTOCOL:
        return None
    if data.get("run_status") in ("skipped", "failed"):
        return None
    for method in (PP, V3):
        prefix = method + "__"
        if path.stem.startswith(prefix):
            parts = path.stem[len(prefix):].rsplit("__", 1)
            if len(parts) != 2:
                return None
            trace, vm_id = parts
            try:
                require_accounting_metrics(pd.DataFrame([{**data, "method": method}]))
            except (ValueError, TypeError):
                return None
            return {"method": method, "trace": trace, "vm_id": str(vm_id),
                    "causal_protocol": CAUSAL_PROTOCOL, "accounting_schema": ACCOUNTING_SCHEMA,
                    **{k: data[k] for k in ACCOUNTING_METRICS}}
    return None


def aggregate_accounting_records() -> pd.DataFrame:
    rows = []
    for p in sorted(OUT_JSON.glob(f"{PP}__*.json")):
        r = row_from_json(p)
        if r:
            rows.append(r)
    for p in sorted(OUT_JSON.glob(f"{V3}__*.json")):
        r = row_from_json(p)
        if r:
            rows.append(r)

    df = pd.DataFrame(rows)
    PARQUET_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET_OUT, index=False)
    return df


def summarize(df: pd.DataFrame) -> dict:
    require_accounting_metrics(df)
    pp = df[df["method"] == PP].set_index(["trace", "vm_id"]).sort_index()
    v3 = df[df["method"] == V3].set_index(["trace", "vm_id"]).sort_index()
    j = pd.concat(
        [
            pp["n_refresh_events"].rename("pp_n"),
            v3["n_refresh_events"].rename("v3_n"),
            pp["n_periodic_refreshes"].rename("pp_per"),
            v3["n_periodic_refreshes"].rename("v3_per"),
            v3["n_drift_refreshes"].rename("v3_drift"),
        ],
        axis=1,
        join="inner",
    )
    delta = (j["v3_n"].to_numpy(dtype=np.float64) - j["pp_n"].to_numpy(dtype=np.float64)).astype(np.float64)
    m_d, lo, hi = _bootstrap_ci_delta(delta)

    wp = _wilcox(delta)

    accounting = summarize_accounting(df).to_dict(orient="records")
    stats_pp = df[df["method"] == PP]["n_refresh_events"]
    stats_v3 = df[df["method"] == V3]["n_refresh_events"]
    drift_m = float(df[df["method"] == V3]["n_drift_refreshes"].mean())

    return {
        "accounting_by_method": accounting,
        "pp_mean": float(stats_pp.mean()),
        "pp_med": float(stats_pp.median()),
        "pp_mean_periodic": float(df[df["method"] == PP]["n_periodic_refreshes"].mean()),
        "pp_mean_drift": float(df[df["method"] == PP]["n_drift_refreshes"].mean()),
        "v3_mean": float(stats_v3.mean()),
        "v3_med": float(stats_v3.median()),
        "v3_mean_periodic": float(df[df["method"] == V3]["n_periodic_refreshes"].mean()),
        "v3_mean_drift": drift_m,
        "delta_mean": m_d,
        "delta_ci_lo": lo,
        "delta_ci_hi": hi,
        "wilcox_p": wp,
        "n_pairs": int(len(delta)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-jobs", type=int, default=8, help="parallel workers")
    ap.add_argument("--aggregate-only", action="store_true", help="skip runs; rebuild parquet from JSON")
    args = ap.parse_args()

    if not args.aggregate_only:
        wall, n_ok, n_cached, n_fail = run_corpus(args.n_jobs)
        print(json.dumps({"wall_clock_s_total": round(wall, 2), "fresh_ok": n_ok, "cached": n_cached, "failed": n_fail}))

    df = aggregate_accounting_records()
    summ = summarize(df)

    lines = (
        "| method | mean_refresh_events | median | mean_periodic | mean_drift |\n"
        "| ------ | -------------------:| -----: | ------------: | ---------: |\n"
        f"| PP | {summ['pp_mean']:.4f} | {summ['pp_med']:.1f} | {summ['pp_mean_periodic']:.4f} | {summ['pp_mean_drift']:.4f} |\n"
        f"| V3 | {summ['v3_mean']:.4f} | {summ['v3_med']:.1f} | {summ['v3_mean_periodic']:.4f} | {summ['v3_mean_drift']:.4f} |\n"
    )
    print(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
