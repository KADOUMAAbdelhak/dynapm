#!/usr/bin/env python3
"""Result tables/figures from validated per-VM metrics; no count normalization."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent

from dynapm.core.accounting import ACCOUNTING_METRICS, require_accounting_metrics
from dynapm.eval.metrics import cohen_d_paired
from dynapm.eval.replay import require_causal_protocol  # noqa: E402
from dynapm.scripts.task17b_provisioning import (  # noqa: E402
    SAFETY_FACTOR,
    bootstrap_mean_ci,
    method_metrics_table,
    per_vm_metric,
    safe_wilcoxon,
    tier_table as prov_tier_table,
)

CORPUS_SUMMARY = REPO / "dynapm/data/eval_full_corpus_summary.parquet"
PROV_RECORDS = REPO / "dynapm/data/provisioning_eval_records.parquet"
PAPER = REPO / "dynapm/reports/paper"

PP = "periodic_predictor_6h_v2"
PW = "periodic_6h_v2"
V3 = "dynapm_v3_v2"

TIER_ORDER = ["low", "medium", "high"]
TIER_COL = {"low": "#009E73", "medium": "#0072B2", "high": "#D55E00"}
CB6 = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]


def _setup_pub_style() -> None:
    mpl.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
            "figure.dpi": 300,
        }
    )


def _save_fig(path_stem: Path) -> None:
    for ext in (".png", ".pdf"):
        plt.savefig(path_stem.with_suffix(ext), dpi=300, bbox_inches="tight")
    plt.close()


def bootstrap_vm_mean_ci(values: np.ndarray, n_boot: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = len(v)
    means = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        ix = rng.integers(0, n, size=n)
        means[i] = float(np.mean(v[ix]))
    return float(np.mean(v)), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_vectors_eval(summary: pd.DataFrame, ma: str, mb: str, col: str) -> tuple[np.ndarray, np.ndarray, int]:
    ok = summary[summary["run_status"] == "ok"]
    da = ok[ok["method"] == ma][["trace", "vm_id", col]].rename(columns={col: "va"})
    db = ok[ok["method"] == mb][["trace", "vm_id", col]].rename(columns={col: "vb"})
    j = da.merge(db, on=["trace", "vm_id"], how="inner")
    xa = j["va"].to_numpy(dtype=np.float64)
    xb = j["vb"].to_numpy(dtype=np.float64)
    return xa, xb, len(j)


def paired_eval_delta(summary: pd.DataFrame, ma: str, mb: str, col: str) -> tuple[np.ndarray, int]:
    xa, xb, n = paired_vectors_eval(summary, ma, mb, col)
    return xa - xb, n


def provisioning_vectors(prov: pd.DataFrame, ma: str, mb: str, col: str) -> tuple[np.ndarray, np.ndarray, int]:
    sa = per_vm_metric(prov, ma, SAFETY_FACTOR, col)
    sb = per_vm_metric(prov, mb, SAFETY_FACTOR, col)
    j = pd.concat([sa.rename("va"), sb.rename("vb")], axis=1, join="inner")
    return (
        j["va"].to_numpy(dtype=np.float64),
        j["vb"].to_numpy(dtype=np.float64),
        len(j),
    )


def headline_effect_sizes(summary: pd.DataFrame, prov: pd.DataFrame) -> list[tuple[str, str, float]]:
    xa, xb, _ = paired_vectors_eval(summary, PP, PW, "cpu_class_accuracy")
    m_acc = np.isfinite(xa) & np.isfinite(xb)
    d_cpu_acc_pp_pw = cohen_d_paired(xa[m_acc], xb[m_acc])
    xa2, xb2, _ = paired_vectors_eval(summary, V3, PP, "cpu_class_accuracy")
    m2 = np.isfinite(xa2) & np.isfinite(xb2)
    d_cpu_acc_v3_pp = cohen_d_paired(xa2[m2], xb2[m2])
    ua, ub, _ = provisioning_vectors(prov, PP, PW, "cpu_under")
    um = np.isfinite(ua) & np.isfinite(ub)
    d_under_pp_pw = cohen_d_paired(ua[um], ub[um])
    return [
        ("PP vs Periodic-window", "cpu_class_accuracy (Cohen d, paired)", d_cpu_acc_pp_pw),
        ("DynAPM-V3 vs Periodic-Predictor", "cpu_class_accuracy (Cohen d, paired)", d_cpu_acc_v3_pp),
        ("PP vs Periodic-window", "cpu_under_rate VM-means (Cohen d)", d_under_pp_pw),
    ]


def _fmt_wilcoxon(p: float | None) -> str:
    if p is None:
        return "nan"
    return f"{p:.6g}"


def table_pairwise_append(
    rows: list[dict],
    comparison: str,
    metric: str,
    xa_raw: np.ndarray,
    xb_raw: np.ndarray,
    seed_shift: int,
) -> None:
    m = np.isfinite(xa_raw) & np.isfinite(xb_raw)
    xa, xb = xa_raw[m], xb_raw[m]
    delta = xa - xb
    if len(delta) == 0:
        rows.append(
            {
                "comparison": comparison,
                "metric": metric,
                "mean_delta": "",
                "ci_low": "",
                "ci_high": "",
                "wilcoxon_p": "",
                "cohen_d": "",
                "n_pairs": 0,
            }
        )
        return
    mean_d, lo, hi = bootstrap_mean_ci(delta, n_boot=1000, seed=42 + seed_shift)
    wp = safe_wilcoxon(delta)
    cd = cohen_d_paired(xa, xb)
    rows.append(
        {
            "comparison": comparison,
            "metric": metric,
            "mean_delta": round(float(mean_d), 8),
            "ci_low": round(float(lo), 8) if np.isfinite(lo) else "",
            "ci_high": round(float(hi), 8) if np.isfinite(hi) else "",
            "wilcoxon_p": _fmt_wilcoxon(wp),
            "cohen_d": round(float(cd), 6) if np.isfinite(cd) else "",
            "n_pairs": int(len(delta)),
        }
    )


def build_table_pairwise(summary: pd.DataFrame, prov: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    specs_eval = [
        ("Periodic-Predictor vs Periodic-window", PP, PW, "cpu_class_accuracy", "cpu_acc"),
        ("Periodic-Predictor vs Periodic-window", PP, PW, "memory_class_accuracy", "mem_acc"),
        ("Periodic-Predictor vs Periodic-window", PP, PW, "cpu_p95_mae", "cpu_p95_mae"),
        ("Periodic-Predictor vs Periodic-window", PP, PW, "mem_p95_mae", "mem_p95_mae"),
        ("DynAPM-V3 vs Periodic-Predictor", V3, PP, "cpu_class_accuracy", "cpu_acc"),
        ("DynAPM-V3 vs Periodic-Predictor", V3, PP, "memory_class_accuracy", "mem_acc"),
        ("DynAPM-V3 vs Periodic-Predictor", V3, PP, "cpu_p95_mae", "cpu_p95_mae"),
        ("DynAPM-V3 vs Periodic-Predictor", V3, PP, "mem_p95_mae", "mem_p95_mae"),
    ]
    for i, (label, ma, mb, col, mshort) in enumerate(specs_eval):
        xa, xb, _ = paired_vectors_eval(summary, ma, mb, col)
        table_pairwise_append(rows, label, mshort, xa, xb, seed_shift=101 + i)

    u_pp, u_pw, _ = provisioning_vectors(prov, PP, PW, "cpu_under")
    table_pairwise_append(rows, "Periodic-Predictor vs Periodic-window", "cpu_under_rate", u_pp, u_pw, seed_shift=210)
    mu_pp, mu_pw, _ = provisioning_vectors(prov, PP, PW, "mem_under")
    table_pairwise_append(rows, "Periodic-Predictor vs Periodic-window", "mem_under_rate", mu_pp, mu_pw, seed_shift=211)
    u_v3, u_pp2, _ = provisioning_vectors(prov, V3, PP, "cpu_under")
    table_pairwise_append(rows, "DynAPM-V3 vs Periodic-Predictor", "cpu_under_rate", u_v3, u_pp2, seed_shift=220)
    o_v3, o_pp, _ = provisioning_vectors(prov, V3, PP, "cpu_over")
    table_pairwise_append(rows, "DynAPM-V3 vs Periodic-Predictor", "cpu_over_rate", o_v3, o_pp, seed_shift=221)
    return pd.DataFrame(rows)


def figure_method_progression(summary: pd.DataFrame, path_stem: Path) -> None:
    ok = summary[summary["run_status"] == "ok"].copy()
    means: list[float] = []
    los: list[float] = []
    his: list[float] = []
    methods_list: list[str] = []
    for m in ok["method"].unique():
        sub = ok[ok["method"] == m]
        vals = sub["cpu_class_accuracy"].astype(float).values
        mu, lo, hi = bootstrap_vm_mean_ci(vals, seed=11 + hash(m) % 1000)
        means.append(mu)
        los.append(lo)
        his.append(hi)
        methods_list.append(m)
    ord_ix = np.argsort(means)
    methods_ord = [methods_list[i] for i in ord_ix]
    means_o = [means[i] for i in ord_ix]
    los_o = [los[i] for i in ord_ix]
    his_o = [his[i] for i in ord_ix]
    err_lo = [means_o[j] - los_o[j] for j in range(len(means_o))]
    err_hi = [his_o[j] - means_o[j] for j in range(len(means_o))]
    fig_w = 8.0 if len(means_o) <= 8 else 16.0
    _setup_pub_style()
    _, ax = plt.subplots(figsize=(fig_w, 4.25))
    xpos = np.arange(len(methods_ord))
    cols = CB6[: len(methods_ord)]
    ax.bar(
        xpos,
        means_o,
        color=cols,
        edgecolor="#333333",
        linewidth=0.4,
        yerr=[err_lo, err_hi],
        capsize=4,
        error_kw=dict(lw=1),
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(methods_ord, rotation=22, ha="right")
    ax.set_ylabel("Mean CPU class accuracy")
    ax.set_title("Fig. 1: Method progression (95% bootstrap CI across VMs)")
    ax.set_ylim(0.0, 1.05)
    plt.tight_layout()
    _save_fig(path_stem)


def figure_pp_lift_histogram(summary: pd.DataFrame, path_stem: Path) -> None:
    d, _ = paired_eval_delta(summary, PP, PW, "cpu_class_accuracy")
    d = d[np.isfinite(d)]
    _setup_pub_style()
    fig, ax = plt.subplots(figsize=(16.0 / 2, 4.5))
    ax.hist(d, bins=40, color="#0072B2", alpha=0.85, edgecolor="white")
    ax.axvline(float(np.mean(d)), color="#D55E00", lw=2, ls="--", label=f"mean = {np.mean(d):.4f}")
    ax.axvline(float(np.median(d)), color="#009E73", lw=2, ls=":", label=f"median = {np.median(d):.4f}")
    ax.set_xlabel("Per-VM Δ CPU accuracy (Periodic-Predictor − Periodic-window)")
    ax.set_ylabel("Count (VMs)")
    ax.legend(loc="upper right")
    ax.set_title("Fig. 2: Predictor-source lift distribution (paired VMs)")
    plt.tight_layout()
    _save_fig(path_stem)


def figure_provisioning_stacked(path_stem: Path, prov: pd.DataFrame) -> None:
    tab = method_metrics_table(prov, SAFETY_FACTOR).sort_values("mean_cpu_under_rate", ascending=True)
    methods = tab["method"].tolist()
    und = tab["mean_cpu_under_rate"].to_numpy()
    wel = tab["mean_cpu_well_rate"].to_numpy()
    ovr = tab["mean_cpu_over_rate"].to_numpy()
    _setup_pub_style()
    fig, ax = plt.subplots(figsize=(8.0, 4.25))
    x = np.arange(len(methods))
    ax.bar(x, und, color="#c62828", edgecolor="#333333", linewidth=0.3, label="under")
    ax.bar(x, wel, bottom=und, color="#2e7d32", edgecolor="#333333", linewidth=0.3, label="well")
    ax.bar(x, ovr, bottom=und + wel, color="#f9a825", edgecolor="#333333", linewidth=0.3, label="over")
    ax.set_xticks(x)
    ax.set_xticklabels(methods, rotation=22, ha="right")
    ax.set_ylabel("Fraction (two-stage VM mean)")
    ax.set_title("Fig. 4: CPU provisioning outcomes (safety factor 1.2)")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 1.0)
    plt.tight_layout()
    _save_fig(path_stem)


def figure_per_tier_under(path_stem: Path, prov: pd.DataFrame) -> None:
    tt = prov_tier_table(prov, SAFETY_FACTOR)
    methods_sorted = sorted(tt["method"].unique())
    _setup_pub_style()
    fig, ax = plt.subplots(figsize=(16.0, 4.75))
    n_m = len(methods_sorted)
    n_t = len(TIER_ORDER)
    width = min(0.22, 0.8 / (n_t + 1))
    x = np.arange(n_m)
    for ti, tier in enumerate(TIER_ORDER):
        offs = width * (ti - (n_t - 1) / 2)
        vals = []
        for m in methods_sorted:
            sub = tt[(tt["method"] == m) & (tt["volatility_tier"].astype(str) == tier)]
            vals.append(float(sub["mean_cpu_under_rate"].iloc[0]) if len(sub) else float("nan"))
        ax.bar(
            x + offs,
            vals,
            width,
            label=str(tier),
            color=TIER_COL.get(str(tier), "#333333"),
            edgecolor="#333333",
            linewidth=0.3,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(methods_sorted, rotation=22, ha="right")
    ax.set_ylabel("Mean CPU under-provision rate")
    ax.legend(title="tier", fontsize=10)
    ax.set_title("Fig. 3: Under-provisioning by volatility tier")
    plt.tight_layout()
    _save_fig(path_stem)


def figure_v3_vs_pp_scatter(summary: pd.DataFrame, path_stem: Path) -> None:
    xa, xb, _ = paired_vectors_eval(summary, PP, V3, "cpu_class_accuracy")
    m = np.isfinite(xa) & np.isfinite(xb)
    xa, xb = xa[m], xb[m]
    above = xb > xa
    _setup_pub_style()
    fig, ax = plt.subplots(figsize=(8.0, 7.75))
    lo = float(min(np.min(xa), np.min(xb)))
    hi = float(max(np.max(xa), np.max(xb)))
    ax.plot([lo, hi], [lo, hi], color="#777777", ls="--", lw=1, label="y = x")
    ax.scatter(xa[~above], xb[~above], s=8, alpha=0.65, color=CB6[0], label="V3 ≤ PP accuracy")
    ax.scatter(xa[above], xb[above], s=10, alpha=0.85, color=CB6[3], label="V3 > PP accuracy")
    ax.set_xlabel("Periodic-Predictor CPU class accuracy")
    ax.set_ylabel("DynAPM-V3 CPU class accuracy")
    ax.set_title("Fig. 5: Corpus per-VM CPU accuracy (paired)")
    ax.legend(loc="lower right", fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    _save_fig(path_stem)


def build_table1(summary: pd.DataFrame, prov: pd.DataFrame) -> pd.DataFrame:
    require_accounting_metrics(summary)
    prov_tab = method_metrics_table(prov, SAFETY_FACTOR).set_index("method")
    ok = summary[summary["run_status"] == "ok"]
    out_rows = []
    for method in sorted(ok["method"].unique()):
        sub = ok[ok["method"] == method]
        n_vms = len(sub)
        ca, cla, cha = bootstrap_vm_mean_ci(sub["cpu_class_accuracy"].astype(float).values, seed=301)
        ma, mla, mha = bootstrap_vm_mean_ci(sub["memory_class_accuracy"].astype(float).values, seed=302)
        cma, cmla, cmha = bootstrap_vm_mean_ci(sub["cpu_p95_mae"].astype(float).values, seed=303)
        mma, mmla, mmha = bootstrap_vm_mean_ci(sub["mem_p95_mae"].astype(float).values, seed=304)
        med_ref = float(sub["n_refresh_events"].astype(float).median())
        under = float(prov_tab.loc[method, "mean_cpu_under_rate"]) if method in prov_tab.index else float("nan")
        out_rows.append(
            {
                "method": method,
                "n_vms": n_vms,
                "mean_cpu_class_acc": round(ca, 4),
                "ci_low_cpu_acc": round(cla, 4),
                "ci_high_cpu_acc": round(cha, 4),
                "mean_mem_class_acc": round(ma, 4),
                "ci_low_mem_acc": round(mla, 4),
                "ci_high_mem_acc": round(mha, 4),
                "mean_cpu_p95_mae": round(cma, 3),
                "ci_low_cpu_mae": round(cmla, 3),
                "ci_high_cpu_mae": round(cmha, 3),
                "mean_mem_p95_mae": round(mma, 3),
                "ci_low_mem_mae": round(mmla, 3),
                "ci_high_mem_mae": round(mmha, 3),
                **{f"mean_{metric}": float(sub[metric].mean()) for metric in ACCOUNTING_METRICS},
                "median_n_refresh_events": float(med_ref),
                "mean_cpu_under_rate": round(under, 4),
            }
        )
    return pd.DataFrame(out_rows)


def build_table3(summary: pd.DataFrame, prov: pd.DataFrame) -> pd.DataFrame:
    ok = summary[summary["run_status"] == "ok"].copy()
    ok["volatility_tier"] = ok["volatility_tier"].astype(str)
    tt = prov_tier_table(prov, SAFETY_FACTOR)
    rows = []
    for _, r in tt.iterrows():
        method = str(r["method"])
        tier = str(r["volatility_tier"])
        g = ok[(ok["method"].astype(str) == method) & (ok["volatility_tier"] == tier)]
        if len(g) == 0:
            continue
        rows.append(
            {
                "volatility_tier": tier,
                "method": method,
                "mean_cpu_class_acc": round(float(g["cpu_class_accuracy"].astype(float).mean()), 4),
                "mean_cpu_under_rate": round(float(r["mean_cpu_under_rate"]), 4),
            }
        )
    out = pd.DataFrame(rows).sort_values(["volatility_tier", "method"])
    return out


def main() -> int:
    PAPER.mkdir(parents=True, exist_ok=True)

    summary = pd.read_parquet(CORPUS_SUMMARY)
    require_causal_protocol(summary)
    require_accounting_metrics(summary)
    summary["vm_id"] = summary["vm_id"].astype(str)
    prov = pd.read_parquet(PROV_RECORDS)
    prov["vm_id"] = prov["vm_id"].astype(str)

    effects = headline_effect_sizes(summary, prov)

    t1 = build_table1(summary, prov)
    t1.to_csv(PAPER / "table1_method_comparison.csv", index=False)

    t2 = build_table_pairwise(summary, prov)
    t2.to_csv(PAPER / "table2_pairwise_deltas.csv", index=False)

    t3 = build_table3(summary, prov)
    t3.to_csv(PAPER / "table3_per_tier.csv", index=False)

    figure_method_progression(summary, PAPER / "figure1_method_progression")
    figure_pp_lift_histogram(summary, PAPER / "figure2_predictor_lift_distribution")
    figure_per_tier_under(PAPER / "figure3_per_tier_under_rate", prov)
    figure_provisioning_stacked(PAPER / "figure4_provisioning_outcomes", prov)
    figure_v3_vs_pp_scatter(summary, PAPER / "figure5_v3_vs_pp_per_vm_corpus")

    print(
        json.dumps(
            {
                "paper_dir": str(PAPER),
                "headline_cohen_d": [(a, b, float(c) if np.isfinite(c) else None) for a, b, c in effects],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
