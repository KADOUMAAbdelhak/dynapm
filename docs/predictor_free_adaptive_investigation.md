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

**BLOCKED — first managed generation invalidated; corrected rerun pending.**
Review found that a no-signal periodic 24h commit reset Reactive's six-hour
trigger shadow, manufacturing a class transition at the next observation.
Reactive resource-signal aggregates were also omitted from per-VM rows despite
being present in timestamped events. Source after the first run removes the
periodic reset and populates both counters. No architecture disposition may use
the first generation.

## Superseded managed generation

The tables below preserve the invalid generation for audit only. They are not
scientific findings and do not satisfy V2.4F.

- Source commit: `10cae8cfb77b142fcad8548235c8d21694f6345c` (clean and
  committed before execution).
- Fingerprint: `f4f66f61eb48180766568c7b6aebf2403abcff1566435d617554df257421996a`.
- Run ID: `2026-10-22T092211.896873Z-f4f66f61eb48-deed1373`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Output-manifest SHA-256: `9981408bbd2c8db119f61d545c81340aaaf5ee45ce45beab2345ae613490a30f`.
- Purpose: pilot/exploratory; exactly the fixed 18 development VMs; 90/90
  method/VM evaluations; wall time 660.375s with two VM workers.
- Predictor fits, prediction calls, and recursive forecast calls: zero.

## Absolute descriptive results

Equal-VM macro averages. Class values are percentages; p95 MAE/bias are
utilization percentage points. Positive bias is overstatement.

| Method | CPU class % | Memory class % | CPU p95 MAE | Memory p95 MAE | CPU bias | Memory bias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 74.9296 | 71.9465 | 0.416812 | 0.719239 | -0.017926 | 0.000639 |
| Reactive | 75.5194 | 72.2315 | 0.410235 | 0.712521 | -0.017091 | 0.007036 |
| BudgetMatched-Reactive | 75.4266 | 72.5862 | 0.407480 | 0.705834 | -0.012616 | 0.003466 |
| ADWIN-Observation | 75.0848 | 72.1667 | 0.413169 | 0.717467 | -0.011569 | 0.006961 |
| BudgetMatched-ADWIN | 75.0419 | 71.8887 | 0.416482 | 0.716186 | -0.016458 | 0.001849 |

## Primary equal-budget effects

Adaptive minus its matched control, paired per VM. Positive class differences
and negative MAE differences are favorable.

| Trigger | Metric | Mean | Median | VM range | Favorable / unfavorable / tie |
| --- | --- | ---: | ---: | ---: | ---: |
| Reactive | CPU class (pp) | 0.0928 | 0.0000 | -2.2375 to 1.2739 | 7 / 7 / 4 |
| Reactive | Memory class (pp) | -0.3548 | -0.4172 | -1.7241 to 0.6885 | 6 / 10 / 2 |
| Reactive | CPU p95 MAE | 0.002755 | 0.000179 | -0.009592 to 0.052466 | 8 / 9 / 1 |
| Reactive | Memory p95 MAE | 0.006687 | 0.004492 | -0.007142 to 0.033643 | 5 / 13 / 0 |
| ADWIN-Observation | CPU class (pp) | 0.0429 | 0.0000 | -1.2072 to 1.2739 | 4 / 4 / 10 |
| ADWIN-Observation | Memory class (pp) | 0.2780 | 0.0901 | -2.0121 to 1.5152 | 9 / 2 / 7 |
| ADWIN-Observation | CPU p95 MAE | -0.003313 | 0.000000 | -0.036443 to 0.005757 | 7 / 7 / 4 |
| ADWIN-Observation | Memory p95 MAE | 0.001281 | 0.000000 | -0.028822 to 0.030609 | 8 / 8 / 2 |

Reactive worsens average memory correctness and both MAEs; no VM improves all
four quantities. ADWIN has favorable average class changes and CPU MAE, but
worsens memory MAE, has tied median CPU class/both MAEs, and splits CPU and
memory MAE wins 7/7 and 8/8. Only one VM improves all four. These mixed resource
and VM directions do not satisfy the predefined retention rule.

### Per-VM effects

Class differences are percentage points.

| Trigger | Trace/VM | Tier | CPU class | Memory class | CPU MAE | Memory MAE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Reactive | T1/143 | high | -0.4310 | 0.4310 | -0.002482 | 0.010475 |
| Reactive | T1/213 | low | 0.0000 | -1.7241 | 0.000000 | -0.007142 |
| Reactive | T1/374 | low | -0.4310 | -0.6466 | 0.001162 | 0.028980 |
| Reactive | T1/64 | medium | -0.2525 | -1.2626 | 0.000357 | 0.006304 |
| Reactive | T1/76 | high | -0.2155 | 0.2155 | -0.009592 | 0.001678 |
| Reactive | T1/96 | medium | 0.6466 | -0.6466 | -0.002983 | 0.007998 |
| Reactive | T2/11 | high | 0.2160 | -0.4320 | 0.009203 | 0.033643 |
| Reactive | T2/207 | low | 0.0000 | -0.8048 | -0.000085 | 0.002383 |
| Reactive | T2/388 | medium | -0.2012 | -1.6097 | 0.000763 | 0.010461 |
| Reactive | T2/396 | low | 1.2072 | -0.4024 | 0.000877 | -0.001065 |
| Reactive | T2/398 | medium | 0.6865 | 0.0000 | -0.000092 | -0.000096 |
| Reactive | T2/516 | high | 1.2739 | -1.0616 | 0.005920 | 0.000454 |
| Reactive | T3/127 | high | 0.8606 | 0.5164 | 0.052466 | 0.014731 |
| Reactive | T3/133 | medium | 0.7207 | 0.5405 | 0.000417 | 0.005850 |
| Reactive | T3/151 | low | 0.0000 | 0.0000 | 0.000402 | 0.009628 |
| Reactive | T3/212 | low | -0.1721 | 0.3442 | -0.000073 | -0.006269 |
| Reactive | T3/224 | high | -2.2375 | 0.6885 | -0.001576 | -0.000776 |
| Reactive | T3/83 | medium | 0.0000 | -0.5319 | -0.005100 | 0.003134 |
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
| Reactive | high | -0.0889 | 0.0596 | 0.008990 | 0.010034 |
| Reactive | low | 0.1007 | -0.5389 | 0.000381 | 0.004419 |
| Reactive | medium | 0.2667 | -0.5850 | -0.001106 | 0.005608 |
| ADWIN | high | 0.2408 | 0.3774 | -0.008554 | 0.009897 |
| ADWIN | low | -0.0934 | -0.1702 | 0.000038 | -0.005225 |
| ADWIN | medium | -0.0185 | 0.6267 | -0.001424 | -0.000830 |

No trigger is favorable on all four quantities in every tier. Reactive memory
MAE worsens in all tiers. ADWIN's high tier worsens memory MAE; its low tier
worsens both class averages and CPU MAE; its medium tier slightly worsens CPU
class correctness.

## Secondary PW comparison

Against PW, Reactive averages +0.590/+0.285pp class correctness and
-0.006577/-0.006718 CPU/memory MAE; ADWIN averages +0.155/+0.220pp and
-0.003643/-0.001772. These are secondary, unequal-budget contrasts. The matched
controls show that extra opportunities or their nonadaptive placement explain
the apparent gains at least as well as trigger adaptivity, so PW comparisons do
not support retention.

## Accounting, triggers, and profile age

| Method | Periodic | Extra | Total refreshes | Trigger signals | Ineligible | Periodic-coincident |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 1,562 | 0 | 1,562 | 0 | 0 | 0 |
| Reactive | 1,562 | 4,547 | 6,109 | 4,606 | 7 | 52 |
| BudgetMatched-Reactive | 1,562 | 4,547 | 6,109 | 0 | 0 | 0 |
| ADWIN-Observation | 1,562 | 340 | 1,902 | 343 | 3 | 0 |
| BudgetMatched-ADWIN | 1,562 | 340 | 1,902 | 0 | 0 | 0 |

Reactive has 1,861 CPU and 3,106 memory resource signals; ADWIN has 182 CPU and
201 memory signals. Resource counts can overlap at one union trigger. Every
ineligible/coincident signal is timestamped in `trigger_events.parquet`.

| Method | Mean age h | Median h | p95 h | Max h | Age zero % |
| --- | ---: | ---: | ---: | ---: | ---: |
| PW-6h | 2.6658 | 3.0000 | 5.0 | 46.0000 | 16.439 |
| Reactive | 1.8433 | 1.0833 | 5.0 | 46.0000 | 19.277 |
| BudgetMatched-Reactive | 1.0923 | 0.7500 | 3.0 | 41.3333 | 19.743 |
| ADWIN-Observation | 2.4850 | 2.0000 | 5.0 | 46.0000 | 16.484 |
| BudgetMatched-ADWIN | 2.4799 | 2.0000 | 5.0 | 45.0000 | 16.650 |

Equal budgets do not imply equal ages because placement is the treatment.

## Integrity

- 311 tests passed, zero failed/skipped; 84 Python files parse; imports and CLI
  help pass.
- Independent reconstruction from only the 18 raw inputs verified every commit
  content hash, actual/nominal periodic pair, evaluation timestamp and forward
  truth. Both budgets are exact for 18/18 VMs.
- 45,105 finite evaluation records, 17,584 refresh events, and 4,949 timestamped
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

**No disposition from this generation.** The specific Reactive validity defect
requires a corrected clean-source bounded rerun. V2.5 and V3 remain blocked.
