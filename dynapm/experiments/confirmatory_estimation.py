"""Frozen F1/F2/F3 estimation analysis for the Materna confirmatory study.

Bootstrap B=10000, seed=20251022. No practical-significance thresholds.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from dynapm.experiments.confirmatory_design import (
    COMPARISON_FAMILIES,
    PRIMARY_FIDELITY_ENDPOINTS,
    PRIMARY_COST_ENDPOINT,
)
from dynapm.experiments.confirmatory_execution import ENDPOINT_COLUMNS

BOOTSTRAP_B = 10000
BOOTSTRAP_SEED = 20251022
CI_LEVEL = 0.95

FIDELITY_HIGHER_BETTER = {
    "cpu_class_correctness",
    "memory_class_correctness",
}
FIDELITY_LOWER_BETTER = {
    "cpu_p95_profile_mae",
    "memory_p95_profile_mae",
}


def holm_adjust(pvalues: list[float | None]) -> list[float | None]:
    """Holm step-down adjustment; None/non-finite stays None."""
    out: list[float | None] = [None] * len(pvalues)
    defined = [(i, float(p)) for i, p in enumerate(pvalues) if p is not None and np.isfinite(p)]
    if not defined:
        return out
    defined.sort(key=lambda t: t[1])
    m = len(defined)
    # Raw Holm factors in increasing-p order, then enforce non-decreasing adjusted p.
    raw_adj = [(i, min(1.0, (m - rank) * p)) for rank, (i, p) in enumerate(defined)]
    running = 0.0
    for i, adj in raw_adj:
        running = max(running, adj)
        out[i] = float(running)
    return out


def paired_bootstrap_cis(delta: np.ndarray, *, repetitions: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED):
    delta = np.asarray(delta, dtype=float)
    delta = delta[np.isfinite(delta)]
    n = len(delta)
    if n == 0:
        nan = float("nan")
        return {
            "mean": nan,
            "mean_ci_low": nan,
            "mean_ci_high": nan,
            "median": nan,
            "median_ci_low": nan,
            "median_ci_high": nan,
            "n": 0,
        }
    rng = np.random.default_rng(seed)
    mean_boot = np.empty(repetitions, dtype=float)
    median_boot = np.empty(repetitions, dtype=float)
    for b in range(repetitions):
        sample = delta[rng.integers(0, n, size=n)]
        mean_boot[b] = sample.mean()
        median_boot[b] = np.median(sample)
    alpha = (1.0 - CI_LEVEL) / 2.0
    lo, hi = 100 * alpha, 100 * (1.0 - alpha)
    return {
        "mean": float(delta.mean()),
        "mean_ci_low": float(np.percentile(mean_boot, lo)),
        "mean_ci_high": float(np.percentile(mean_boot, hi)),
        "median": float(np.median(delta)),
        "median_ci_low": float(np.percentile(median_boot, lo)),
        "median_ci_high": float(np.percentile(median_boot, hi)),
        "n": int(n),
    }


def wilcoxon_report(delta: np.ndarray) -> dict[str, Any]:
    delta = np.asarray(delta, dtype=float)
    delta = delta[np.isfinite(delta)]
    n = len(delta)
    nonzero = delta[delta != 0]
    if n == 0:
        return {"pvalue": 1.0, "n": 0, "n_nonzero": 0, "all_ties": True}
    if len(nonzero) == 0:
        return {"pvalue": 1.0, "n": n, "n_nonzero": 0, "all_ties": True}
    try:
        result = wilcoxon(delta, zero_method="wilcox", alternative="two-sided")
        p = float(result.pvalue)
    except ValueError:
        p = 1.0
    return {"pvalue": p, "n": n, "n_nonzero": int(len(nonzero)), "all_ties": False}


def effect_sizes(delta: np.ndarray) -> dict[str, float]:
    delta = np.asarray(delta, dtype=float)
    delta = delta[np.isfinite(delta)]
    if len(delta) == 0:
        return {"paired_median": float("nan"), "standardized_mean": float("nan")}
    sd = float(delta.std(ddof=1)) if len(delta) > 1 else 0.0
    standardized = float("nan") if sd == 0.0 else float(delta.mean() / sd)
    return {"paired_median": float(np.median(delta)), "standardized_mean": standardized}


def contrast_deltas(frame: pd.DataFrame, treatment: str, control: str, column: str) -> pd.Series:
    wide = frame.pivot_table(index=["trace", "vm_id"], columns="method_id", values=column, aggfunc="first")
    if treatment not in wide.columns or control not in wide.columns:
        raise ValueError(f"missing methods for contrast {treatment} vs {control}")
    paired = wide[[treatment, control]].dropna()
    return paired[treatment] - paired[control]


def analyze_families(per_vm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Return paired rows, inference table, and summary JSON-serializable dict."""
    ok = per_vm[per_vm.run_status == "ok"].copy()
    paired_rows = []
    inference_rows = []
    for family, contrasts in COMPARISON_FAMILIES.items():
        family_p = []
        family_meta = []
        endpoints = list(PRIMARY_FIDELITY_ENDPOINTS) + [PRIMARY_COST_ENDPOINT]
        for treatment, control in contrasts:
            for endpoint in endpoints:
                column = ENDPOINT_COLUMNS.get(endpoint, endpoint)
                if endpoint == PRIMARY_COST_ENDPOINT:
                    column = "n_refresh_events"
                deltas = contrast_deltas(ok, treatment, control, column)
                for (trace, vm_id), value in deltas.items():
                    paired_rows.append(
                        {
                            "family": family,
                            "treatment": treatment,
                            "control": control,
                            "endpoint": endpoint,
                            "trace": trace,
                            "vm_id": str(vm_id),
                            "delta": float(value),
                        }
                    )
                arr = deltas.to_numpy(dtype=float)
                cis = paired_bootstrap_cis(arr)
                wil = wilcoxon_report(arr)
                effects = effect_sizes(arr)
                row = {
                    "family": family,
                    "treatment": treatment,
                    "control": control,
                    "endpoint": endpoint,
                    **cis,
                    **{f"effect_{k}": v for k, v in effects.items()},
                    "wilcoxon_p": wil["pvalue"],
                    "n_pairs": wil["n"],
                    "n_nonzero": wil["n_nonzero"],
                    "all_ties": wil["all_ties"],
                    "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
                }
                inference_rows.append(row)
                family_p.append(wil["pvalue"])
                family_meta.append(len(inference_rows) - 1)
        adjusted = holm_adjust(family_p)
        for idx, adj in zip(family_meta, adjusted):
            inference_rows[idx]["holm_p"] = adj
            raw = inference_rows[idx]["wilcoxon_p"]
            inference_rows[idx]["statistically_distinguishable"] = bool(
                adj is not None and np.isfinite(adj) and adj < 0.05
            )
            inference_rows[idx]["raw_p"] = raw

    paired = pd.DataFrame(paired_rows)
    inference = pd.DataFrame(inference_rows)
    summary = {
        "bootstrap_repetitions": BOOTSTRAP_B,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "ci_level": CI_LEVEL,
        "practical_significance": "NOT_DEFINED_AT_PROFILE_LEVEL",
        "n_inference_rows": int(len(inference)),
        "families": {
            family: inference[inference.family == family][
                [
                    "treatment",
                    "control",
                    "endpoint",
                    "mean",
                    "mean_ci_low",
                    "mean_ci_high",
                    "median",
                    "median_ci_low",
                    "median_ci_high",
                    "wilcoxon_p",
                    "holm_p",
                    "statistically_distinguishable",
                    "n_pairs",
                ]
            ].to_dict("records")
            for family in COMPARISON_FAMILIES
        },
    }
    return paired, inference, summary


def fidelity_better(endpoint: str, delta: float) -> bool:
    """Whether treatment-minus-control delta favors treatment on this endpoint."""
    if endpoint in FIDELITY_HIGHER_BETTER:
        return delta > 0
    if endpoint in FIDELITY_LOWER_BETTER:
        return delta < 0
    raise ValueError(endpoint)


def fidelity_worse(endpoint: str, delta: float) -> bool:
    if endpoint in FIDELITY_HIGHER_BETTER:
        return delta < 0
    if endpoint in FIDELITY_LOWER_BETTER:
        return delta > 0
    raise ValueError(endpoint)


def pareto_relations(inference: pd.DataFrame) -> list[dict[str, Any]]:
    """Strict Pareto dominance per R4 using both mean and median paired effects."""
    results = []
    # Candidate ordered pairs among primary methods (report for frozen F contrasts + neighbors).
    pairs = [
        ("pw_12h", "static"),
        ("pw_6h", "static"),
        ("pw_3h", "static"),
        ("pw_6h", "pw_12h"),
        ("pw_3h", "pw_6h"),
        ("full_rewrite", "pw_3h"),
    ]
    for treatment, control in pairs:
        mean_map = {}
        median_map = {}
        for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
            sub = inference[
                (inference.treatment == treatment)
                & (inference.control == control)
                & (inference.endpoint == endpoint)
            ]
            if len(sub) != 1:
                mean_map[endpoint] = float("nan")
                median_map[endpoint] = float("nan")
            else:
                mean_map[endpoint] = float(sub.iloc[0]["mean"])
                median_map[endpoint] = float(sub.iloc[0]["median"])
        cost = inference[
            (inference.treatment == treatment)
            & (inference.control == control)
            & (inference.endpoint == PRIMARY_COST_ENDPOINT)
        ]
        cost_mean = float(cost.iloc[0]["mean"]) if len(cost) == 1 else float("nan")
        cost_median = float(cost.iloc[0]["median"]) if len(cost) == 1 else float("nan")

        def dominates(mean_effects, cost_effect):
            # treatment dominates control if nowhere worse on fidelity+cost and strictly better somewhere.
            if any(fidelity_worse(ep, mean_effects[ep]) for ep in PRIMARY_FIDELITY_ENDPOINTS):
                return False
            # cost: lower is better; treatment-control negative is better for treatment
            if cost_effect > 0:
                return False
            strict_fid = any(fidelity_better(ep, mean_effects[ep]) for ep in PRIMARY_FIDELITY_ENDPOINTS)
            strict_cost = cost_effect < 0
            return strict_fid or strict_cost

        treat_dom_mean = dominates(mean_map, cost_mean)
        treat_dom_median = dominates(median_map, cost_median)
        # Reverse: control dominates treatment using negated deltas
        rev_mean = {ep: -mean_map[ep] for ep in PRIMARY_FIDELITY_ENDPOINTS}
        rev_median = {ep: -median_map[ep] for ep in PRIMARY_FIDELITY_ENDPOINTS}
        ctrl_dom_mean = dominates(rev_mean, -cost_mean)
        ctrl_dom_median = dominates(rev_median, -cost_median)

        if treat_dom_mean and treat_dom_median:
            label = f"{treatment}_strictly_dominates_{control}"
        elif ctrl_dom_mean and ctrl_dom_median:
            label = f"{control}_strictly_dominates_{treatment}"
        else:
            label = "tradeoff_no_strict_dominance"
        results.append(
            {
                "treatment": treatment,
                "control": control,
                "label": label,
                "mean_fidelity_deltas": mean_map,
                "median_fidelity_deltas": median_map,
                "mean_cost_delta": cost_mean,
                "median_cost_delta": cost_median,
            }
        )
    return results


def robustness_summaries(per_vm: pd.DataFrame, paired: pd.DataFrame) -> dict[str, Any]:
    """Secondary RQ4 strata — descriptive only."""
    ok = per_vm[per_vm.run_status == "ok"]
    out: dict[str, Any] = {"primary": False, "note": "secondary robustness only"}
    for stratum, col in (("trace", "trace"), ("volatility_tier", "volatility_tier")):
        rows = []
        for key, g in ok.groupby(col):
            for method, mg in g.groupby("method_id"):
                rows.append(
                    {
                        "stratum": stratum,
                        "level": str(key),
                        "method_id": method,
                        "n_vms": int(mg.vm_id.nunique()),
                        "cpu_class_accuracy_mean": float(mg.cpu_class_accuracy.mean()),
                        "memory_class_accuracy_mean": float(mg.memory_class_accuracy.mean()),
                        "cpu_p95_mae_mean": float(mg.cpu_p95_mae.mean()),
                        "mem_p95_mae_mean": float(mg.mem_p95_mae.mean()),
                        "n_refresh_events_mean": float(mg.n_refresh_events.mean()),
                    }
                )
        out[stratum] = rows
    # Resource-specific contrast medians for F1 pw_3h vs static
    resource = []
    for endpoint in PRIMARY_FIDELITY_ENDPOINTS:
        sub = paired[
            (paired.family == "F1_maintenance_vs_none")
            & (paired.treatment == "pw_3h")
            & (paired.control == "static")
            & (paired.endpoint == endpoint)
        ]
        resource.append(
            {
                "endpoint": endpoint,
                "contrast": "pw_3h_minus_static",
                "median_delta": float(sub.delta.median()) if len(sub) else float("nan"),
                "mean_delta": float(sub.delta.mean()) if len(sub) else float("nan"),
                "n": int(len(sub)),
            }
        )
    out["resource_pw3_vs_static"] = resource
    return out
