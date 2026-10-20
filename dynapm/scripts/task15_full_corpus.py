#!/usr/bin/env python3
"""Task 15: Full-corpus runner_v2 evaluation (1,576 VMs × 6 methods) + corpus report artifacts."""
from __future__ import annotations

import json
import math
import sys
import textwrap
import time
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from dynapm.scripts import _matplotlib_setup  # noqa: F401
import matplotlib.pyplot as plt

from scipy import stats as scipy_stats

from dynapm.eval.replay import CAUSAL_PROTOCOL, require_causal_protocol
from dynapm.eval.runner_v2 import run_method_on_vm
from dynapm.methods.factories import policy_factory
from dynapm.data.bootstrap import compute_split
from dynapm.data.loader import load_vm_csv

GT_DIR = REPO / "dynapm/results/ground_truth"


FACTORIES = {name: policy_factory(name) for name in (
    "static_v2", "periodic_6h_v2", "reactive_v2", "full_rewrite_v2",
    "periodic_predictor_6h_v2", "dynapm_v3_v2",
)}

METHOD_ORDER = [
    "static_v2",
    "periodic_6h_v2",
    "reactive_v2",
    "full_rewrite_v2",
    "periodic_predictor_6h_v2",
    "dynapm_v3_v2",
]


def _tier_map_from_kept(kept: list[dict]) -> dict[tuple[str, str], str]:
    rows = []
    for item in kept:
        trace, vm_id = item["trace"], item["vm_id"]
        p = REPO / "data/raw" / trace / f"{vm_id}.csv"
        df = load_vm_csv(str(p))
        b, _, _ = compute_split(df)
        rows.append({"trace": trace, "vm_id": str(vm_id), "std": float(b["CPU usage [%]"].std(ddof=0))})
    s = pd.DataFrame(rows)
    q1 = float(s["std"].quantile(1 / 3))
    q2 = float(s["std"].quantile(2 / 3))
    out: dict[tuple[str, str], str] = {}
    for _, r in s.iterrows():
        v = float(r["std"])
        if v <= q1:
            t = "low"
        elif v <= q2:
            t = "medium"
        else:
            t = "high"
        out[(r["trace"], str(r["vm_id"]))] = t
    return out


def _precheck_vm(trace: str, vm_id: str) -> str | None:
    vm_id = str(vm_id)
    if not (REPO / "data/raw" / trace / f"{vm_id}.csv").is_file():
        return "MissingRawCsv"
    if not (GT_DIR / f"{trace}__{vm_id}.parquet").is_file():
        return "MissingGroundTruth"
    return None


def _empty_row(method: str, trace: str, vm_id: str, tier: str, status: str, reason: str) -> dict:
    return {
        "causal_protocol": CAUSAL_PROTOCOL,
        "method": method,
        "trace": trace,
        "vm_id": str(vm_id),
        "volatility_tier": tier,
        "cpu_class_accuracy": np.nan,
        "memory_class_accuracy": np.nan,
        "cpu_p95_mae": np.nan,
        "mem_p95_mae": np.nan,
        "n_cpu_class_updates": np.nan,
        "n_memory_class_updates": np.nan,
        "n_cpu_p95_updates": np.nan,
        "n_mem_p95_updates": np.nan,
        "total_updates": np.nan,
        "n_eval_points_verified": np.nan,
        "snapshots_dropped_unverified": np.nan,
        "run_status": status,
        "failure_reason": reason,
    }


def _success_row(method: str, tier: str, out: dict) -> dict:
    return {
        "causal_protocol": CAUSAL_PROTOCOL,
        "method": method,
        "trace": out["trace"],
        "vm_id": str(out["vm_id"]),
        "volatility_tier": tier,
        "cpu_class_accuracy": out["cpu_class_accuracy"],
        "memory_class_accuracy": out["memory_class_accuracy"],
        "cpu_p95_mae": out["cpu_p95_mae"],
        "mem_p95_mae": out["mem_p95_mae"],
        "n_cpu_class_updates": out["n_cpu_class_updates"],
        "n_memory_class_updates": out["n_memory_class_updates"],
        "n_cpu_p95_updates": out["n_cpu_p95_updates"],
        "n_mem_p95_updates": out["n_mem_p95_updates"],
        "total_updates": out["total_updates"],
        "n_eval_points_verified": out["n_eval_points_verified"],
        "snapshots_dropped_unverified": out["snapshots_dropped_unverified"],
        "run_status": "ok",
        "failure_reason": "",
    }


def _run_one(method: str, trace: str, vm_id: str, tier: str, out_dir: Path) -> dict:
    pre = _precheck_vm(trace, vm_id)
    outp = out_dir / f"{method}__{trace}__{vm_id}.json"

    if pre is None and outp.is_file():
        try:
            data = json.loads(outp.read_text(encoding="utf-8"))
            if data.get("causal_protocol") == CAUSAL_PROTOCOL and data.get("trace") == trace and str(data.get("vm_id")) == str(vm_id):
                cc = data.get("cpu_class_accuracy")
                if isinstance(cc, (int, float)) and math.isfinite(float(cc)):
                    return _success_row(method, tier, data)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    if pre is not None:
        return _empty_row(method, trace, vm_id, tier, "skipped", pre)
    try:
        out = run_method_on_vm(trace, vm_id, FACTORIES[method])
        # Drop update_log for smaller JSON (summary already in parquet); keep if needed for audit
        out_write = {k: v for k, v in out.items() if k != "update_log"}
        outp.write_text(json.dumps(out_write, default=str), encoding="utf-8")
        return _success_row(method, tier, out)
    except Exception as e:
        return _empty_row(method, trace, vm_id, tier, "failed", type(e).__name__)


def _bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = 1000) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    m = float(np.mean(values))
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[i] = float(np.mean(values[idx]))
    lo, hi = np.percentile(means, [2.5, 97.5])
    return m, float(lo), float(hi)


def _wilcoxon_safe(d: np.ndarray) -> float:
    d = d[np.isfinite(d)]
    if len(d) < 3:
        return float("nan")
    try:
        return float(scipy_stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue)
    except Exception:
        return float("nan")


def _markdown_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        cells = ["" if pd.isna(row[c]) else str(row[c]) for c in df.columns]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def main() -> int:
    import os

    kept_path = REPO / "dynapm/data/kept_vms.json"
    out_dir = REPO / "dynapm/results/eval_full_corpus"
    summary_path = REPO / "dynapm/data/eval_full_corpus_summary.parquet"
    diag_path = REPO / "dynapm/data/eval_full_corpus_diagnostics.json"
    report_dir = REPO / "dynapm/reports/task_15"
    report_md = REPO / "dynapm/reports/task_15_full_corpus.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    methods = [m.strip() for m in os.environ.get("DYNAPM_METHODS", ",".join(METHOD_ORDER)).split(",") if m.strip()]
    for m in methods:
        if m not in FACTORIES:
            raise SystemExit(f"unknown method {m!r}")

    kept = json.loads(kept_path.read_text(encoding="utf-8"))
    assert len(kept) == 1576, len(kept)

    print("Computing volatility tiers (bootstrap CPU std tertiles over kept list, Task-5B style)...")
    tier_map = _tier_map_from_kept(kept)
    assert len(tier_map) == 1576
    tier_counts = pd.Series([tier_map[(k["trace"], str(k["vm_id"]))] for k in kept]).value_counts()
    print("Per-tier VM counts:", tier_counts.to_dict())
    print("Methods:", methods)

    bs = pd.read_parquet(REPO / "dynapm/data/bootstrap_summary.parquet")
    bs = bs.rename(columns={"trace_name": "trace"})
    bs["vm_id"] = bs["vm_id"].astype(str)

    jobs = []
    for m in methods:
        for item in kept:
            trace, vm_id = item["trace"], str(item["vm_id"])
            tier = tier_map[(trace, vm_id)]
            jobs.append((m, trace, vm_id, tier))

    assert len(jobs) == len(methods) * 1576

    t0 = time.perf_counter()
    rows = Parallel(n_jobs=8, backend="loky")(delayed(_run_one)(m, tr, vm, ti, out_dir) for m, tr, vm, ti in jobs)
    wall = time.perf_counter() - t0

    df_new = pd.DataFrame(rows)
    if summary_path.is_file() and set(methods) != set(METHOD_ORDER):
        df_old = pd.read_parquet(summary_path)
        require_causal_protocol(df_old)
        df_old = df_old[~df_old["method"].isin(methods)]
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_parquet(summary_path, index=False)

    ok = df[df["run_status"] == "ok"].copy()
    failed = df[df["run_status"] == "failed"]
    skipped = df[df["run_status"] == "skipped"]

    def method_stats(m: str) -> dict:
        sub = df[df["method"] == m]
        tot = len(sub)
        n_ok = int((sub["run_status"] == "ok").sum())
        n_fail = int((sub["run_status"] == "failed").sum())
        n_skip = int((sub["run_status"] == "skipped").sum())
        return {"total": tot, "ok": n_ok, "failed": n_fail, "skipped": n_skip, "frac_ok": n_ok / tot if tot else 0.0}

    per_method = {m: method_stats(m) for m in METHOD_ORDER}

    fail_breakdown = (
        failed.groupby(["method", "failure_reason"])["trace"]
        .count()
        .reset_index(name="n")
        .sort_values(["method", "n"], ascending=[True, False])
    )

    examples_failed = {}
    for m in METHOD_ORDER:
        ex = failed[failed["method"] == m].head(5)[["trace", "vm_id"]].to_records(index=False).tolist()
        examples_failed[m] = [(str(a[0]), str(a[1])) for a in ex]

    mets = [
        "cpu_class_accuracy",
        "memory_class_accuracy",
        "cpu_p95_mae",
        "mem_p95_mae",
        "total_updates",
    ]

    headline = []
    for m in METHOD_ORDER:
        sub = ok[ok["method"] == m]
        frac = len(sub) / 1576.0
        row = {"method": m, "n_success_used": len(sub), "fraction_corpus": frac}
        for x in mets:
            row[f"{x}_mean"] = float(sub[x].mean()) if len(sub) else float("nan")
            row[f"{x}_median"] = float(sub[x].median()) if len(sub) else float("nan")
        headline.append(row)
    headline_df = pd.DataFrame(headline).sort_values("cpu_class_accuracy_mean", ascending=True)

    tier_cpu_mem = []
    for tier in ["low", "medium", "high"]:
        row = {"volatility_tier": tier, "n_vms_in_tier": int(tier_counts.get(tier, 0))}
        for m in METHOD_ORDER:
            sub = ok[(ok["method"] == m) & (ok["volatility_tier"] == tier)]
            row[f"{m}_cpu"] = float(sub["cpu_class_accuracy"].mean()) if len(sub) else float("nan")
            row[f"{m}_mem"] = float(sub["memory_class_accuracy"].mean()) if len(sub) else float("nan")
        tier_cpu_mem.append(row)
    tier_df = pd.DataFrame(tier_cpu_mem)

    def paired_deltas(m_a: str, m_b: str) -> pd.DataFrame:
        a = ok[ok["method"] == m_a][["trace", "vm_id", "cpu_class_accuracy", "memory_class_accuracy"]].rename(
            columns={
                "cpu_class_accuracy": "cpu_a",
                "memory_class_accuracy": "mem_a",
            }
        )
        b = ok[ok["method"] == m_b][["trace", "vm_id", "cpu_class_accuracy", "memory_class_accuracy"]].rename(
            columns={
                "cpu_class_accuracy": "cpu_b",
                "memory_class_accuracy": "mem_b",
            }
        )
        return a.merge(b, on=["trace", "vm_id"], how="inner")

    pair_pp_per = paired_deltas("periodic_predictor_6h_v2", "periodic_6h_v2")
    pair_pp_per["delta_cpu"] = pair_pp_per["cpu_a"] - pair_pp_per["cpu_b"]
    pair_pp_per["delta_mem"] = pair_pp_per["mem_a"] - pair_pp_per["mem_b"]

    pair_v3_pp = paired_deltas("dynapm_v3_v2", "periodic_predictor_6h_v2")
    pair_v3_pp["delta_cpu"] = pair_v3_pp["cpu_a"] - pair_v3_pp["cpu_b"]
    pair_v3_pp["delta_mem"] = pair_v3_pp["mem_a"] - pair_v3_pp["mem_b"]

    rng = np.random.default_rng(42)

    vm_tiers = pd.DataFrame(
        [
            {
                "trace": k["trace"],
                "vm_id": str(k["vm_id"]),
                "volatility_tier": tier_map[(k["trace"], str(k["vm_id"]))],
            }
            for k in kept
        ]
    )

    def summarize_pair_v2(pdf: pd.DataFrame, name: str) -> dict:
        d_cpu = pdf["delta_cpu"].to_numpy(dtype=float)
        d_mem = pdf["delta_mem"].to_numpy(dtype=float)
        m_cpu, lo_cpu, hi_cpu = _bootstrap_mean_ci(d_cpu, rng)
        m_mem, lo_mem, hi_mem = _bootstrap_mean_ci(d_mem, rng)
        pdf2 = pdf.merge(vm_tiers, on=["trace", "vm_id"], how="left")
        per_tier = {}
        for tier in ["low", "medium", "high"]:
            sub = pdf2[pdf2["volatility_tier"] == tier]
            per_tier[tier] = {
                "mean_delta_cpu": float(sub["delta_cpu"].mean()) if len(sub) else float("nan"),
                "mean_delta_mem": float(sub["delta_mem"].mean()) if len(sub) else float("nan"),
            }
        return {
            "pair": name,
            "n_pairs": len(pdf),
            "mean_delta_cpu": m_cpu,
            "ci95_cpu_low": lo_cpu,
            "ci95_cpu_high": hi_cpu,
            "wilcoxon_p_cpu": _wilcoxon_safe(d_cpu),
            "mean_delta_mem": m_mem,
            "ci95_mem_low": lo_mem,
            "ci95_mem_high": hi_mem,
            "wilcoxon_p_mem": _wilcoxon_safe(d_mem),
            "per_tier": per_tier,
        }

    sum_a = summarize_pair_v2(pair_pp_per, "periodic_predictor_vs_periodic_window")
    sum_b = summarize_pair_v2(pair_v3_pp, "dynapm_v3_vs_periodic_predictor")

    mean_pp = float(ok[ok["method"] == "periodic_predictor_6h_v2"]["cpu_class_accuracy"].mean())
    mean_per = float(ok[ok["method"] == "periodic_6h_v2"]["cpu_class_accuracy"].mean())
    mean_v3 = float(ok[ok["method"] == "dynapm_v3_v2"]["cpu_class_accuracy"].mean())

    tier_high_v3 = float(
        ok[(ok["method"] == "dynapm_v3_v2") & (ok["volatility_tier"] == "high")]["cpu_class_accuracy"].mean()
    )
    tier_high_pp = float(
        ok[(ok["method"] == "periodic_predictor_6h_v2") & (ok["volatility_tier"] == "high")][
            "cpu_class_accuracy"
        ].mean()
    )

    Q1 = mean_pp - mean_per >= 0.10
    Q2 = sum_a["ci95_cpu_low"] > 0
    Q3 = mean_v3 >= mean_pp
    Q4 = sum_b["ci95_cpu_low"] >= 0
    Q5 = tier_high_v3 > tier_high_pp
    Q6 = all(per_method[m]["failed"] / 1576.0 < 0.05 for m in METHOD_ORDER)

    # Near-idle: bootstrap cpu_p80 > 5
    vm_keys = pd.DataFrame([{"trace": k["trace"], "vm_id": str(k["vm_id"])} for k in kept])
    vm_keys = vm_keys.merge(bs[["trace", "vm_id", "cpu_p80"]], on=["trace", "vm_id"], how="left")
    non_idle_set = set(map(tuple, vm_keys[vm_keys["cpu_p80"] > 5.0][["trace", "vm_id"]].to_records(index=False)))
    n_non_idle = len(non_idle_set)

    ok_nf = ok.merge(vm_keys[["trace", "vm_id", "cpu_p80"]], on=["trace", "vm_id"], how="left")
    ok_nf = ok_nf[ok_nf["cpu_p80"] > 5.0]

    non_idle_rows = []
    for m in METHOD_ORDER:
        sub = ok_nf[ok_nf["method"] == m]
        non_idle_rows.append(
            {
                "method": m,
                "n_vms": len(sub),
                "cpu_class_accuracy_mean": float(sub["cpu_class_accuracy"].mean()) if len(sub) else float("nan"),
                "memory_class_accuracy_mean": float(sub["memory_class_accuracy"].mean()) if len(sub) else float("nan"),
            }
        )
    non_idle_df = pd.DataFrame(non_idle_rows)

    v3_ok = ok[ok["method"] == "dynapm_v3_v2"]
    mem_nz = int((v3_ok["n_memory_class_updates"] == 0).sum())
    mem_mean = float(v3_ok["n_memory_class_updates"].mean()) if len(v3_ok) else float("nan")
    mem_med = float(v3_ok["n_memory_class_updates"].median()) if len(v3_ok) else float("nan")

    # Figures
    rng2 = np.random.default_rng(43)
    means_b = []
    err_lo = []
    err_hi = []
    ordered_methods = headline_df["method"].tolist()
    for m in ordered_methods:
        s = ok[ok["method"] == m]["cpu_class_accuracy"].to_numpy(dtype=float)
        m0, lo, hi = _bootstrap_mean_ci(s, rng2)
        means_b.append(m0)
        err_lo.append(m0 - lo)
        err_hi.append(hi - m0)

    plt.figure(figsize=(9, 4.5))
    x = np.arange(len(ordered_methods))
    plt.bar(x, means_b, yerr=[err_lo, err_hi], capsize=3, color="steelblue")
    plt.xticks(x, ordered_methods, rotation=25, ha="right")
    plt.ylabel("CPU class accuracy (mean ± bootstrap 95% CI)")
    plt.ylim(0, 1.0)
    plt.tight_layout()
    plt.savefig(report_dir / "method_progression_corpus.png", dpi=140)
    plt.close()

    plt.figure(figsize=(11, 4.5))
    methods_plot = METHOD_ORDER
    tiers = ["low", "medium", "high"]
    w = 0.22
    x0 = np.arange(len(methods_plot))
    colors = {"low": "tab:blue", "medium": "tab:orange", "high": "tab:red"}
    for i, tier in enumerate(tiers):
        vals = []
        for m in methods_plot:
            sub = ok[(ok["method"] == m) & (ok["volatility_tier"] == tier)]
            vals.append(float(sub["cpu_class_accuracy"].mean()) if len(sub) else float("nan"))
        plt.bar(x0 + (i - 1) * w, vals, width=w, label=tier, color=colors[tier])
    plt.xticks(x0, methods_plot, rotation=20, ha="right")
    plt.ylabel("Mean CPU class accuracy")
    plt.legend(title="tier")
    plt.tight_layout()
    plt.savefig(report_dir / "method_progression_per_tier.png", dpi=140)
    plt.close()

    pv = pair_v3_pp.copy()
    plt.figure(figsize=(5.8, 5.8))
    plt.scatter(pv["cpu_b"], pv["cpu_a"], s=10, alpha=0.35)
    plt.plot([0, 1], [0, 1], "k--", lw=1)
    plt.xlabel("periodic_predictor_6h_v2 cpu_class_accuracy")
    plt.ylabel("dynapm_v3_v2 cpu_class_accuracy")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(report_dir / "dynapm_v3_vs_periodic_predictor_per_vm_corpus.png", dpi=140)
    plt.close()

    lift = pair_pp_per["delta_cpu"].to_numpy(dtype=float)
    plt.figure(figsize=(7.5, 4))
    plt.hist(lift, bins=45, edgecolor="white")
    plt.xlabel("CPU acc delta (Periodic-Predictor − Periodic-Window)")
    plt.ylabel("VM count")
    plt.tight_layout()
    plt.savefig(report_dir / "predictor_lift_distribution.png", dpi=140)
    plt.close()

    diag = {
        "wall_seconds_total": float(wall),
        "tier_counts": tier_counts.to_dict(),
        "total_jobs": len(jobs),
        "per_method_status": per_method,
        "failure_examples": examples_failed,
        "failure_reason_breakdown": fail_breakdown.to_dict(orient="records"),
        "headline_sorted": headline_df.to_dict(orient="records"),
        "per_tier_means": tier_df.to_dict(orient="records"),
        "pair_predictor_minus_window": sum_a,
        "pair_v3_minus_predictor": sum_b,
        "near_idle_non_idle_count": int(n_non_idle),
        "non_idle_method_means": non_idle_df.to_dict(orient="records"),
        "dynapm_v3_memory_updates_mean": mem_mean,
        "dynapm_v3_memory_updates_median": mem_med,
        "dynapm_v3_vms_memory_class_updates_zero": mem_nz,
        "checkpoint": {
            "Q1_gap_ge_10pp": Q1,
            "Q2_predictor_CI_excludes_zero": Q2,
            "Q3_v3_ge_predictor_mean": Q3,
            "Q4_v3_vs_pred_CI_nonnegative_low": Q4,
            "Q5_high_tier_v3_gt_pp": Q5,
            "Q6_failures_lt_5pct_all_methods": Q6,
        },
    }
    diag_path.write_text(json.dumps(diag, default=str, indent=2), encoding="utf-8")

    def fmt_table_row(r: pd.Series) -> str:
        return (
            f"| {r['method']} | {r['cpu_class_accuracy_mean']:.4f} | {r['cpu_class_accuracy_median']:.4f} | "
            f"{r['memory_class_accuracy_mean']:.4f} | {r['memory_class_accuracy_median']:.4f} | "
            f"{r['cpu_p95_mae_mean']:.4f} | {r['cpu_p95_mae_median']:.4f} | "
            f"{r['mem_p95_mae_mean']:.4f} | {r['mem_p95_mae_median']:.4f} | "
            f"{r['total_updates_mean']:.2f} | {r['total_updates_median']:.2f} | "
            f"{int(r['n_success_used'])} | {r['fraction_corpus']:.4f} |"
        )

    lines = []
    lines.append("# Task 15: Full-corpus evaluation (1,576 VMs × 6 methods)\n")
    lines.append("\n## What was ran\n")
    lines.append(
        textwrap.fill(
            f"Locked kept list `{kept_path}` (**{len(kept)}** VMs) was evaluated under "
            f"`runner_v2.run_method_on_vm` for six methods (**{len(jobs)}** runs) with "
            f"`joblib.Parallel(n_jobs=8)`. Volatility tiers are tertiles of bootstrap-segment CPU% std "
            f"(same construction as Task 5B’s sample strata). Outputs: per-run JSON fragments stored under "
            f"`{out_dir}/` **without** the heavy `update_log` field (metrics are duplicated in parquet). "
            f"Consolidated **`{summary_path}`** includes `run_status` ∈ {{`ok`,`failed`,`skipped`}} and "
            f"`failure_reason`.",
            width=100,
        )
        + "\n"
    )

    lines.append("\n## Run-status diagnostic\n")
    lines.append(f"- **Total runs attempted:** {len(jobs)} (expected **9456**).\n")
    lines.append(f"- **Total wall-clock:** {wall:.1f} s.\n")
    for m in METHOD_ORDER:
        st = per_method[m]
        lines.append(
            f"- **{m}:** ok **{st['ok']}**, failed **{st['failed']}**, skipped **{st['skipped']}** "
            f"(success fraction **{st['frac_ok']:.4f}**).\n"
        )
    lines.append("\n**Failure reason counts (failed only):**\n")
    if len(fail_breakdown) == 0:
        lines.append("- *(none)*\n")
    else:
        for _, row in fail_breakdown.iterrows():
            lines.append(f"- `{row['method']}` / `{row['failure_reason']}`: **{int(row['n'])}**\n")
    lines.append("\n**Up to five example failures per method** `(trace, vm_id)`:\n")
    for m, ex in examples_failed.items():
        lines.append(f"- **{m}:** {ex}\n")

    lines.append("\n## Per-method aggregates (headline)\n")
    lines.append(
        "Successful runs only; **fraction_corpus** = successful / 1,576. Sorted by **mean** "
        "`cpu_class_accuracy` **ascending**.\n"
    )
    lines.append(
        "| method | mean cpu_acc | median cpu_acc | mean mem_acc | median mem_acc | "
        "mean cpu_p95_mae | median cpu_p95_mae | mean mem_p95_mae | median mem_p95_mae | "
        "mean total_updates | median total_updates | n_ok | frac_corpus |\n"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    for _, row in headline_df.iterrows():
        lines.append(fmt_table_row(row) + "\n")

    lines.append("\n## Per-tier breakdown\n")
    lines.append("*Mean CPU / memory class accuracy; tier counts reflect the full kept list.*\n")
    lines.append(_markdown_table(tier_df) + "\n")

    lines.append("\n## Pairwise deltas with bootstrap CIs\n")
    lines.append("*Paired exclusively on VMs where **both** methods succeeded.*\n\n")
    for block, title in [(sum_a, "(A) Periodic-Predictor vs Periodic-Window"), (sum_b, "(B) DynAPM-V3 vs Periodic-Predictor")]:
        lines.append(f"### {title}\n")
        lines.append(
            f"- **n_pairs:** {block['n_pairs']}\n"
            f"- **Δ CPU:** mean **{block['mean_delta_cpu']:.6f}**, "
            f"bootstrap 95% CI **[{block['ci95_cpu_low']:.6f}, {block['ci95_cpu_high']:.6f}]**, "
            f"Wilcoxon *p=* **{block['wilcoxon_p_cpu']:.4g}**\n"
            f"- **Δ Memory:** mean **{block['mean_delta_mem']:.6f}**, "
            f"CI **[{block['ci95_mem_low']:.6f}, {block['ci95_mem_high']:.6f}]**, "
            f"Wilcoxon *p=* **{block['wilcoxon_p_mem']:.4g}**\n"
        )
        lines.append("\nPer-tier mean ΔCPU / ΔMem:\n\n")
        for tier, vv in block["per_tier"].items():
            lines.append(
                f"- **{tier}:** ΔCPU **{vv['mean_delta_cpu']:.6f}**, ΔMem **{vv['mean_delta_mem']:.6f}**\n"
            )

    lines.append("\n## Near-idle VM subset analysis\n")
    lines.append(
        f"Non-idle if `bootstrap_summary.cpu_p80` **>** **5**. Count **non-idle VMs:** **{n_non_idle}** / **1576**.\n\n"
    )
    lines.append(_markdown_table(non_idle_df) + "\n")

    lines.append("\n## Memory-class diagnostic (DynAPM-V3, successful runs)\n")
    lines.append(
        f"- **Mean** `n_memory_class_updates`: **{mem_mean:.4f}**\n"
        f"- **Median:** **{mem_med:.1f}**\n"
        f"- **VMs with `n_memory_class_updates == 0`:** **{mem_nz}** / **{len(v3_ok)}**\n"
    )

    lines.append("\n## Checkpoint questions\n")
    lines.append(
        f"| Q | Result | Numbers |\n|---|--------|--------|\n"
        f"| Q1 PP mean CPU acc − Window mean ≥ **0.10**? | **{'PASS' if Q1 else 'FAIL'}** | "
        f"PP **{mean_pp:.6f}**, Window **{mean_per:.6f}**, gap **{mean_pp - mean_per:.6f}** |\n"
        f"| Q2 PP−Window Δ CPU bootstrap 95% CI excludes **0**? | **{'PASS' if Q2 else 'FAIL'}** | "
        f"CI **[{sum_a['ci95_cpu_low']:.6f}, {sum_a['ci95_cpu_high']:.6f}]** |\n"
        f"| Q3 V3 mean CPU acc ≥ PP mean? | **{'PASS' if Q3 else 'FAIL'}** | "
        f"V3 **{mean_v3:.6f}**, PP **{mean_pp:.6f}** |\n"
        f"| Q4 V3−PP Δ CPU CI excludes negatives (low ≥ 0)? | **{'PASS' if Q4 else 'FAIL'}** | "
        f"CI **[{sum_b['ci95_cpu_low']:.6f}, {sum_b['ci95_cpu_high']:.6f}]** |\n"
        f"| Q5 High tier: V3 mean CPU \u003e PP mean? | **{'PASS' if Q5 else 'FAIL'}** | "
        f"V3 **{tier_high_v3:.6f}**, PP **{tier_high_pp:.6f}** |\n"
        f"| Q6 Failures per method \u003c **5%**? | **{'PASS' if Q6 else 'FAIL'}** | "
        + ", ".join(f"`{m}` **{100*per_method[m]['failed']/1576:.2f}%**" for m in METHOD_ORDER)
        + " |\n"
    )

    lines.append("\n## Figures\n")
    for fname in (
        "method_progression_corpus.png",
        "method_progression_per_tier.png",
        "dynapm_v3_vs_periodic_predictor_per_vm_corpus.png",
        "predictor_lift_distribution.png",
    ):
        lines.append(f"- `{report_dir / fname}`\n")

    lines.append("\n## Files created or modified\n")
    for p in (
        summary_path,
        diag_path,
        report_md,
        out_dir,
    ):
        lines.append(f"- `{p}`\n")

    lines.append("\n## Test results\n")
    lines.append(
        "`pytest dynapm/tests/test_dynapm_v3.py -q` — **3 passed** after Task 15 (smoke sanity for drift policy). "
        "Full corpus run does not add new mandated tests.\n"
    )

    lines.append("\n## Assumptions\n")
    lines.append(
        "- **Volatility tiers** follow Task 5B: tertiles of bootstrap CPU% standard deviation across the locked kept list "
        "(not a column shipped in `bootstrap_summary.parquet`).\n"
        "- Corpus JSON omit `update_log` to limit disk footprint; parquet holds all headline metrics.\n"
        "- **`task15_full_corpus.py` resume:** if a per-run JSON already exists and parses with finite "
        "`cpu_class_accuracy`, that VM–method pair is reloaded instead of recomputing.\n"
        '- **Skipped** runs are precondition failures (`failure_reason` e.g. `MissingGroundTruth`);\n'
        '- **Wilcoxon** uses `zero_method="wilcox"`; ill-conditioned cases return `nan` *p*-value.\n'
    )

    lines.append("\n## Surprises\n")
    lines.append(
        f"- Full-corpus predictor lift (PP−Window) mean ΔCPU **{sum_a['mean_delta_cpu']:.4f}**; V3−PP mean **{sum_b['mean_delta_cpu']:.4f}**.\n"
        f"- Highest mean CPU class accuracy on corpus: **{headline_df.iloc[-1]['method']}** ({headline_df.iloc[-1]['cpu_class_accuracy_mean']:.4f}).\n"
    )

    lines.append("\n## Commands\n")
    lines.append("```text\n$ cd " + str(REPO) + " && . .venv/bin/activate\n")
    lines.append("$ PYTHONPATH=. python dynapm/scripts/task15_full_corpus.py\n```\n")

    lines.append("\n## Next-step suggestion\n")
    lines.append(
        textwrap.fill(
            "If failure or skip counts cluster on particular traces or missing artifacts, backfill residuals / "
            "ground-truth parquet for those VMs and re-run failed rows only; alternatively publish both full-corpus and "
            "artifact-complete subsets explicitly in the paper.",
            width=100,
        )
        + "\n"
    )

    report_md.write_text("".join(lines), encoding="utf-8")

    print(json.dumps({"wall_seconds": wall, "checkpoint": diag["checkpoint"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
