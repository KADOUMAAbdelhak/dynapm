# V2.4F — Predictor-Free Adaptive Trigger Investigation

Development-only, fixed 18 VMs. No confirmatory outcomes, parameter tuning,
additional trigger search, model families, or profile-content changes are
permitted. V2.5/V3 remain blocked pending this investigation and scope review.

## Predefined design

Every method initializes and commits the same paired actual observations from
the exact `(t-24h,t]` nominal grid. A commit requires at least 200 of 288 finite
CPU/memory pairs. Classes use frozen bootstrap thresholds and p95 is the
empirical .95 quantile. No prediction, interpolation, or recursive forecasting
is used.

- **PW-6h:** periodic base only.
- **Reactive:** the existing reactive signal: at least 50 paired finite slots in
  the exact trailing six-hour grid, then trigger if either six-hour mean class
  differs from the trigger's last accepted classes. It has the same 6h periodic base;
  the signal affects timing only and every commit uses the shared 24h content.
  A separate six-hour trigger-state shadow preserves the class-transition
  closure that the legacy policy obtained by storing its six-hour candidate;
  it cannot alter profile content, and periodic 24h commits cannot manufacture
  a six-hour class transition by resetting it.
- **ADWIN-Observation:** independent CPU and memory ADWIN detectors with the
  existing fixed `delta=0.002`. At each paired observed timestamp they consume
  the current CPU and memory values directly. Either detector signaling is one
  trigger opportunity. It has the same 6h periodic base and shared content.
- **BudgetMatched-Reactive:** same base plus exactly Reactive's per-VM number of
  extra commits.
- **BudgetMatched-ADWIN:** same base plus exactly ADWIN-Observation's per-VM
  number of extra commits.

Both controls use `budget-match-uniform-eligible-v2`: midpoint equal-spacing
indices over content-eligible observed timestamps after excluding base commits.
Only count K enters placement—never adaptive timestamps, values, labels, or
outcomes. Periodic commits take precedence over simultaneous signals. Such a
signal is counted and consumed. A signal without eligible 24h content is counted
as ineligible and consumed without refresh or latching.

Evaluation remains `causal-timeline-v3`, `phase-balanced-hourly-v1`, and
`refresh-accounting-v1`, with delayed verified `(t,t+24h]` truth requiring 200
paired finite targets.

## Predefined interpretation

Primary comparisons are Reactive minus BudgetMatched-Reactive and
ADWIN-Observation minus BudgetMatched-ADWIN, paired by VM. Comparisons with
PW-6h are secondary and exploratory. Report CPU/memory class correctness,
p95-profile MAE and bias, profile ages, refresh/trigger accounting, every VM,
and volatility-tier consistency. No p-values, confirmatory inference, or
post-outcome numerical meaningful-effect threshold are permitted.

The disposition must be exactly one of:

1. **PREDICTOR-FREE ADAPTIVE RETAINED:** at least one predefined trigger shows
   consistent advantage over its equal-budget control across both resources
   without material harm.
2. **ADAPTIVE MAINTENANCE NOT JUSTIFIED:** neither trigger shows convincing
   equal-budget benefit; abandon adaptive-refresh novelty rather than searching
   for more triggers.
3. **INCONCLUSIVE:** only for a specific technical-validity failure.

## Execution status

**PASS — ADAPTIVE MAINTENANCE NOT JUSTIFIED.** The corrected fixed run completed
validly, but neither trigger provides convincing equal-budget benefit across
both resources without harm. Do not retain adaptive-refresh novelty or begin
another trigger search.

## Invalid first generation

Source `10cae8cfb77b142fcad8548235c8d21694f6345c`, run
`2026-10-22T092211.896873Z-f4f66f61eb48-deed1373`, is preserved but superseded:
a no-signal periodic commit reset Reactive's six-hour shadow and could
manufacture a later transition; resource-signal aggregates were also omitted.
No findings below use that generation.

## Valid managed generation

- Source commit: `d8b8421226ebd989476323c2f955eb676e2c0d7f` (clean and
  committed before execution).
- Fingerprint: `7f855e124a481a40e3449a72e3c045f6ce022246b8cf78171eb83dad23fc8979`.
- Run ID: `2026-10-22T094401.887475Z-7f855e124a48-b40753f6`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Output-manifest SHA-256: `3ffda15c5fc9ab2e2b2b070c10cb0a0c48cd6dbea9aa3e95544511f8b3e430d0`.
- Purpose: pilot/exploratory; exactly the fixed 18 development VMs; 90/90
  method/VM evaluations; wall time 650.204s with two VM workers.
- Predictor fits, prediction calls, and recursive forecast calls: zero.

## Absolute descriptive results

Equal-VM macro averages. Class values are percentages; p95 MAE/bias are
utilization percentage points. Positive bias is overstatement.

| Method | CPU class % | Memory class % | CPU p95 MAE | Memory p95 MAE | CPU bias | Memory bias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 74.9296 | 71.9465 | 0.416812 | 0.719239 | -0.017926 | 0.000639 |
| Reactive | 75.3862 | 72.1916 | 0.410471 | 0.713014 | -0.017154 | 0.006964 |
| BudgetMatched-Reactive | 75.5718 | 72.5098 | 0.409708 | 0.708363 | -0.014370 | 0.003651 |
| ADWIN-Observation | 75.0848 | 72.1667 | 0.413169 | 0.717467 | -0.011569 | 0.006961 |
| BudgetMatched-ADWIN | 75.0419 | 71.8887 | 0.416482 | 0.716186 | -0.016458 | 0.001849 |

## Primary equal-budget effects

Adaptive minus its matched control, paired per VM. Positive class differences
and negative MAE differences are favorable.

| Trigger | Metric | Mean | Median | VM range | Favorable / unfavorable / tie |
| --- | --- | ---: | ---: | ---: | ---: |
| Reactive | CPU class (pp) | -0.1856 | 0.0000 | -2.0654 to 0.8048 | 7 / 6 / 5 |
| Reactive | Memory class (pp) | -0.3183 | -0.1078 | -3.6638 to 1.2048 | 8 / 9 / 1 |
| Reactive | CPU p95 MAE | 0.000762 | -0.000068 | -0.022533 to 0.050644 | 11 / 7 / 0 |
| Reactive | Memory p95 MAE | 0.004651 | 0.003624 | -0.022624 to 0.042185 | 6 / 12 / 0 |
| ADWIN-Observation | CPU class (pp) | 0.0429 | 0.0000 | -1.2072 to 1.2739 | 4 / 4 / 10 |
| ADWIN-Observation | Memory class (pp) | 0.2780 | 0.0901 | -2.0121 to 1.5152 | 9 / 2 / 7 |
| ADWIN-Observation | CPU p95 MAE | -0.003313 | 0.000000 | -0.036443 to 0.005757 | 7 / 7 / 4 |
| ADWIN-Observation | Memory p95 MAE | 0.001281 | 0.000000 | -0.028822 to 0.030609 | 8 / 8 / 2 |

Reactive worsens both average class correctness values and both MAEs; only one
VM improves all four quantities. ADWIN has favorable average class changes and CPU MAE, but
worsens memory MAE, has tied median CPU class/both MAEs, and splits CPU and
memory MAE wins 7/7 and 8/8. Only one VM improves all four. These mixed resource
and VM directions do not satisfy the predefined retention rule.

### Per-VM effects

Class differences are percentage points.

| Trigger | Trace/VM | Tier | CPU class | Memory class | CPU MAE | Memory MAE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Reactive | T1/143 | high | -1.0776 | 0.2155 | -0.003894 | 0.006075 |
| Reactive | T1/213 | low | 0.0000 | -3.6638 | 0.000036 | -0.004568 |
| Reactive | T1/374 | low | -0.2155 | -0.2155 | 0.001170 | 0.042185 |
| Reactive | T1/64 | medium | -1.7677 | -0.7576 | -0.000096 | 0.006418 |
| Reactive | T1/76 | high | -0.2155 | 0.2155 | -0.004791 | 0.002938 |
| Reactive | T1/96 | medium | -1.0776 | -0.8621 | -0.022533 | -0.003481 |
| Reactive | T2/11 | high | 0.0000 | -0.4320 | 0.012814 | 0.014521 |
| Reactive | T2/207 | low | 0.0000 | -1.6097 | -0.000066 | -0.002066 |
| Reactive | T2/388 | medium | 0.8048 | 0.6036 | 0.000783 | 0.009827 |
| Reactive | T2/396 | low | 0.6036 | 0.6036 | 0.000408 | 0.000661 |
| Reactive | T2/398 | medium | 0.2288 | 0.0000 | -0.000069 | 0.000048 |
| Reactive | T2/516 | high | 0.2123 | -0.8493 | -0.011535 | -0.022624 |
| Reactive | T3/127 | high | 0.5164 | -0.3442 | 0.050644 | 0.015416 |
| Reactive | T3/133 | medium | 0.5405 | 0.3604 | -0.001153 | 0.005817 |
| Reactive | T3/151 | low | 0.0000 | 0.1721 | 0.000409 | 0.012133 |
| Reactive | T3/212 | low | 0.1721 | 0.5164 | -0.000033 | -0.003663 |
| Reactive | T3/224 | high | -2.0654 | 1.2048 | -0.002110 | -0.000224 |
| Reactive | T3/83 | medium | 0.0000 | -0.8865 | -0.006258 | 0.004311 |
| ADWIN | T1/143 | high | -0.8621 | 0.6466 | -0.006635 | 0.004545 |
| ADWIN | T1/213 | low | 0.0000 | 0.0000 | 0.000000 | 0.000000 |
| ADWIN | T1/374 | low | 0.6466 | 0.6466 | -0.000384 | -0.028822 |
| ADWIN | T1/64 | medium | -0.2525 | 1.5152 | -0.000261 | -0.000987 |
| ADWIN | T1/76 | high | 0.0000 | 0.0000 | 0.000086 | 0.001485 |
| ADWIN | T1/96 | medium | 0.8621 | 0.6466 | -0.010150 | 0.001319 |
| ADWIN | T2/11 | high | 0.0000 | 0.0000 | 0.005757 | 0.030609 |
| ADWIN | T2/207 | low | 0.0000 | 0.0000 | 0.000000 | 0.000000 |
| ADWIN | T2/388 | medium | 0.0000 | 0.0000 | 0.000093 | -0.000416 |
| ADWIN | T2/396 | low | -1.2072 | -2.0121 | 0.000557 | -0.001956 |
| ADWIN | T2/398 | medium | 0.0000 | 0.0000 | 0.000000 | 0.000144 |
| ADWIN | T2/516 | high | 1.2739 | 1.2739 | -0.036443 | 0.022167 |
| ADWIN | T3/127 | high | 0.0000 | 0.5164 | -0.019159 | -0.000329 |
| ADWIN | T3/133 | medium | -0.7207 | 0.1802 | -0.000105 | -0.004614 |
| ADWIN | T3/151 | low | 0.0000 | 0.0000 | 0.000057 | -0.000811 |
| ADWIN | T3/212 | low | 0.0000 | 0.3442 | 0.000000 | 0.000241 |
| ADWIN | T3/224 | high | 1.0327 | -0.1721 | 0.005071 | 0.000906 |
| ADWIN | T3/83 | medium | 0.0000 | 1.4184 | 0.001880 | -0.000426 |

### Volatility tiers

| Trigger | Tier | CPU class pp | Memory class pp | CPU MAE | Memory MAE |
| --- | --- | ---: | ---: | ---: | ---: |
| Reactive | high | -0.4383 | 0.0017 | 0.006855 | 0.002684 |
| Reactive | low | 0.0934 | -0.6995 | 0.000321 | 0.007447 |
| Reactive | medium | -0.2118 | -0.2570 | -0.004888 | 0.003823 |
| ADWIN | high | 0.2408 | 0.3774 | -0.008554 | 0.009897 |
| ADWIN | low | -0.0934 | -0.1702 | 0.000038 | -0.005225 |
| ADWIN | medium | -0.0185 | 0.6267 | -0.001424 | -0.000830 |

No trigger is favorable on all four quantities in every tier. Reactive memory
MAE worsens in all tiers and no tier improves both classes. ADWIN's high tier worsens memory MAE; its low tier
worsens both class averages and CPU MAE; its medium tier slightly worsens CPU
class correctness.

## Secondary PW comparison

Against PW, Reactive averages +0.457/+0.245pp class correctness and
-0.006341/-0.006225 CPU/memory MAE; ADWIN averages +0.155/+0.220pp and
-0.003643/-0.001772. These are secondary, unequal-budget contrasts. The matched
controls show that extra opportunities or their nonadaptive placement explain
the apparent gains at least as well as trigger adaptivity, so PW comparisons do
not support retention.

## Accounting, triggers, and profile age

| Method | Periodic | Extra | Total refreshes | Trigger signals | Ineligible | Periodic-coincident |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 1,562 | 0 | 1,562 | 0 | 0 | 0 |
| Reactive | 1,562 | 3,866 | 5,428 | 3,925 | 7 | 52 |
| BudgetMatched-Reactive | 1,562 | 3,866 | 5,428 | 0 | 0 | 0 |
| ADWIN-Observation | 1,562 | 340 | 1,902 | 343 | 3 | 0 |
| BudgetMatched-ADWIN | 1,562 | 340 | 1,902 | 0 | 0 | 0 |

Reactive has 1,438 CPU and 2,611 memory resource signals; ADWIN has 182 CPU and
201 memory signals. Resource counts can overlap at one union trigger. Every
ineligible/coincident signal is timestamped in `trigger_events.parquet`.

| Method | Mean age h | Median h | p95 h | Max h | Age zero % |
| --- | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 2.6658 | 3.0000 | 5.0 | 46.0000 | 16.439 |
| Reactive | 1.8548 | 1.0833 | 5.0 | 46.0000 | 19.277 |
| BudgetMatched-Reactive | 1.2087 | 0.9167 | 3.0 | 42.1667 | 19.166 |
| ADWIN-Observation | 2.4850 | 2.0000 | 5.0 | 46.0000 | 16.484 |
| BudgetMatched-ADWIN | 2.4799 | 2.0000 | 5.0 | 45.0000 | 16.650 |

Equal budgets do not imply equal ages because placement is the treatment.

## Integrity

- 312 tests passed, zero failed/skipped; 84 Python files parse; imports and CLI
  help pass.
- Independent reconstruction from only the 18 raw inputs verified every commit
  content hash, actual/nominal periodic pair, evaluation timestamp and forward
  truth. Both budgets are exact for 18/18 VMs.
- 45,105 finite evaluation records, 16,222 refresh events, and 4,268 timestamped
  trigger events validate without collisions or causal failures.
- All 12 managed outputs pass size/SHA checks. Exact pilot reuse succeeds;
  changed configuration, claim-purpose reuse, and a tampered byte-copy fail with
  the expected cache reasons. The canonical run remains unchanged.

Outputs: `cohort.parquet`, `per_vm_results.parquet`, `refresh_events.parquet`,
`evaluation_records.parquet`, `budget_schedule.parquet`,
`trigger_events.parquet`, `paired_effects.parquet`, `effect_summary.parquet`,
`tier_metrics.parquet`, `tier_effects.parquet`, `diagnostics.json`,
`summary.json`.

## Architecture consequences

**ADAPTIVE MAINTENANCE NOT JUSTIFIED.** Predictor-generated profile content,
RF-residual timing, Reactive timing, and direct-observation ADWIN timing all lack
the required development evidence. Stop adaptive-trigger search. The remaining
supported implementation is deterministic observation-window maintenance; it
is a reference, not an established novel adaptive contribution.

V2.5 should **not** proceed as an adaptive-method confirmation freeze. It remains
blocked until a human scope review either accepts a non-adaptive research
question with defensible contribution and predefined margins or changes the
project objective outside this trigger-search sequence. V3 remains blocked.
Practical margins, independent confirmation, cross-corpus effects, systems cost,
and operational benefit remain unresolved; this study does not estimate them.
