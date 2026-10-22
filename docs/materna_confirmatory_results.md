# V3 — Materna Confirmatory Estimation Results

**V3 STATUS: PASS** (execution completeness; not a practical-superiority claim)

Estimation-first study bound to frozen design fingerprint
`62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296`
(`configs/materna_confirmatory_v1_1`). Profile-level practical significance remains
`NOT_DEFINED_AT_PROFILE_LEVEL`. C3 and C4 remain **UNPROVEN**. C1/C2 remain withdrawn.

## Run identity

| Field | Value |
|---|---|
| Source commit | `5119957df0d66023b2e62f94604f9f6e5234965d` |
| Experiment fingerprint | `9be95e6c23a5b58688b74f57a4a91b0e8003109d3075c5351581f5bbb4163f11` |
| Run ID | `2026-10-22T150748.006454Z-9be95e6c23a5-87fdc2de` |
| Purpose | `claim` |
| Workers | 4 |
| Preparation | 287.0 s |
| Compute wall | 18309.9 s (~5.1 h) |
| Output manifest SHA-256 | `f1da7159691467338d8d759a1830a4118c52713ab8eefa49c3770e6a1a0064be` |
| Invalidated attempts | none |

Managed outputs:
`results/runs/9be95e6c23a5b58688b74f57a4a91b0e8003109d3075c5351581f5bbb4163f11/2026-10-22T150748.006454Z-9be95e6c23a5-87fdc2de/`.

## Cohort

| Quantity | Count |
|---|---|
| Candidate confirmatory VMs | 1,558 |
| Protocol-validity exclusions | **0** |
| Eligible VMs | **1,558** |
| Pilot VMs in results | **0** |
| Method×VM attempted / completed | **7,790 / 7,790** |

Exclusion codes applied only as frozen protocol-validity gates. The 199 gap-audit
review flags were diagnostics only and did not exclude any VM.

## Method macro means (equal-VM averages)

| Method | CPU class | Mem class | CPU MAE | Mem MAE | Refreshes |
|---|---:|---:|---:|---:|---:|
| Static | 0.476 | 0.590 | 2.573 | 2.450 | 0.0 |
| PW-12h | 0.736 | 0.750 | 1.425 | 1.634 | 42.6 |
| PW-6h | 0.747 | 0.757 | 1.366 | 1.571 | 85.4 |
| PW-3h | 0.753 | 0.762 | 1.328 | 1.529 | 170.8 |
| Full-Rewrite | 0.758 | 0.766 | 1.296 | 1.492 | 6187.5 |

## Accounting totals (sum over 1,558 VMs)

| Method | `n_refresh_events` | `n_field_writes` |
|---|---:|---:|
| Static | 0 | 0 |
| PW-12h | 66,321 | 265,284 |
| PW-6h | 133,054 | 532,216 |
| PW-3h | 266,183 | 1,064,732 |
| Full-Rewrite | 9,640,082 | 38,560,328 |

## Inferential settings (frozen)

Paired VM differences; mean & median; bootstrap B=10,000 seed=20251022; Wilcoxon
`zero_method=wilcox`; Holm within each family; practical significance
`NOT_DEFINED_AT_PROFILE_LEVEL`.

## RQ1 — Maintenance vs Static (F1)

All three PW cadences vs Static are statistically distinguishable (Holm < 0.05)
on all four fidelity endpoints and on refresh cost (n=1,558).

Illustrative PW-3h − Static:

| Endpoint | Mean Δ | 95% CI (mean) | Median Δ | Holm *p* |
|---|---:|---:|---:|---:|
| CPU class | +0.277 | [0.260, 0.294] | +0.173 | ~0 |
| Mem class | +0.172 | [0.156, 0.188] | 0.000 | ~0 |
| CPU p95 MAE | −1.245 | [−1.589, −0.947] | −0.015 | ~0 |
| Mem p95 MAE | −0.922 | [−1.137, −0.732] | +0.003 | ~0 |
| Refreshes | +170.8 | [169.5, 172.2] | +171 | ~0 |

Interpretation (estimation only): mean fidelity moves favor PW over Static, with
large mean MAE reductions but often small median MAE shifts; memory class median
Δ is 0. Cost increases with maintenance. This is **not** an operational-superiority
claim.

## RQ2 — Cadence increments (F2)

PW-6h − PW-12h and PW-3h − PW-6h are statistically distinguishable on all four
fidelity endpoints and cost (Holm < 0.05, n=1,558). Effect magnitudes are small
relative to the Static→PW jump (CPU class mean Δ ≈ +0.010 and +0.006; refresh cost
roughly doubles each step).

## RQ3 — Full-Rewrite vs PW-3h (F3)

Full-Rewrite − PW-3h is statistically distinguishable on all four fidelity
endpoints (small mean gains: CPU class +0.0053; CPU MAE −0.033) and on cost
(+6,017 mean refreshes). Strict Pareto label: **tradeoff_no_strict_dominance**
(fidelity gains with large cost increase).

## Pareto / fidelity–cost (R4)

All six frozen ordered pairs are labeled `tradeoff_no_strict_dominance` under the
predefined rule requiring both mean and median fidelity/cost inequalities. Report
trade-offs; do not claim strict dominance.

## RQ4 — Robustness (secondary)

Trace strata (Materna-Trace-1/2/3) and volatility tertiles (low/medium/high) were
summarized descriptively in `robustness_summary.json`. These are **not** independent
primary confirmation. CPU vs memory endpoints remain separate as frozen.

## Verification

- Frozen design hashes matched at execution.
- No pilot VM in results; no performance-based exclusion.
- Identical per-VM evaluation-stamp fingerprints across the five methods.
- No NaN/Inf primary endpoints; accounting schema present; Static refresh count 0.
- Cache probes: exact claim reusable; altered config / tampered copy / pilot purpose rejected.
- Independent reconciliation: 7,790 rows; paired n=1,558 per contrast×endpoint; refresh totals above.
- Lightweight suite: 329 passed.

## Claims

| Claim | Status after V3 |
|---|---|
| Frozen Materna estimation study executed with complete F1–F3 reporting | **Supported** (this gate) |
| Direction/magnitude/uncertainty/statistical distinguishability for frozen contrasts | **Supported** as estimation outputs |
| Profile-level practical / operational superiority | **Not defined / not claimed** |
| C3 cross-corpus generalization | **UNPROVEN** |
| C4 operational benefit | **UNPROVEN** |
| C1 / C2 | **WITHDRAWN** |

## Next gate

**V4 = NEXT — independent production-corpus suitability/acquisition**
