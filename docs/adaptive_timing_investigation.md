# V2.4E — Architecture Simplification & Drift-Signal Justification

Development-only, fixed 18 VMs. No confirmatory outcomes, tuning, model search or
manuscript claims. V2.5/V3 remain blocked until disposition review.

## Predefined design

The candidate architecture uses only paired actual observations in exact
`(t-24h,t]` nominal slots. At least 200/288 finite CPU+memory pairs are required.
All three methods share one content function and initialization from the same
bootstrap trailing window; classes use frozen bootstrap thresholds, p95 is the
empirical .95 quantile. No imputation or extension before t-24h is allowed.

- PW-6h: periodic only; content eligibility does not require RF history.
- Adaptive-Residual: identical 6h periodic base plus current RF one-step residual
  ADWIN triggers (delta .002, existing settings). No RF-generated profile content.
- BudgetMatched: identical base plus exactly K additional eligible refreshes,
  where K is the adaptive drift count only. `budget-match-uniform-eligible-v2`
  distributes extras at midpoint equal-spacing indices across eligible observed
  timestamps excluding base commits. No drift timestamps, residual magnitudes,
  truth, or scores enter placement. This is an analysis-only counterfactual.

The only difference between methods is timing. The periodic grid remains
anchored to the protocol bootstrap/stream anchor. Ineligible ticks remain pending
and coalesce to the latest nominal tick when content becomes eligible. ADWIN
updates require valid exact-grid one-step histories/residuals for both resources;
missing residuals pause rather than reset detectors. A signal with ineligible
content is consumed, counted diagnostically, and not latched; the profile is
unchanged. Periodic wins on coincidence. Initialization is not a refresh.

Evaluation uses shared production replay: `causal-timeline-v3`, nominal
`phase-balanced-hourly-v1` reads (including absent telemetry), post-refresh reads
on coincidence, delayed `(t,t+24h]` truth with >=200 paired targets, and
`refresh-accounting-v1`. Legacy predictor-content policies remain isolated in
their existing modules for development reproducibility and are not the candidate
architecture. The adaptive policy receives scalar one-step predictions only;
its content constructor never receives predictor objects.

## Predefined interpretation

The key contrast is Adaptive minus BudgetMatched, paired per VM; Adaptive minus
PW is secondary. Report class correctness, p95 MAE/bias, age distributions,
counts, VM-level ranges and volatility tiers, without confirmatory inference.
No numerical meaningful-effect margin has been frozen. Do not invent one after
seeing outcomes. A positive retention decision cannot rest on small favorable
pooled averages with inconsistent VM/resource directions. A conservative negative
architectural disposition is possible when consistent equal-budget benefit is
not demonstrated; it is not proof that every possible drift detector is useless.
No parameter, placement or threshold adjustment follows from these results.

## Residual-signal disposition

**B — RESIDUAL SIGNAL NOT JUSTIFIED.** The fixed RF-residual/ADWIN timing does
not show a convincing consistent equal-budget advantage across the two resources
and endpoints. Recommend removing prediction entirely from the final framework:
no learned profile-content forecasting and no retained residual-RF timing
component. Keep the implemented residual control and legacy predictors isolated
for reproducibility/development until a separately authorized removal/refactor.
No alternative model, detector, margin, interval or placement was searched here.

The simplified supported reference is observation-window profile maintenance.
This is not yet a validated novel adaptive algorithm. Neither a few favorable
class averages nor completing an implementation restores a contribution claim.
This conservative architecture decision is limited to development evidence; it
does not prove that all possible drift signals are ineffective.


## Managed generation

- Source commit: `11131f64b8f4ce69ebf22ba8d3fc5a8d756623f2` (clean, committed before execution).
- Fingerprint: `4fd1541d4a309fa6c09d4ad098c9446d57ce632988f115847f2cd39877dd352a`.
- Run ID: `2026-10-22T080121.494735Z-4fd1541d4a30-1e730315`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Output-manifest SHA-256: `79e2b27d342ed7d7e0b123c1ffb922896758a468e859be3154b0a2d6d0060fe8`.
- Outputs: `results/runs/4fd1541d4a309fa6c09d4ad098c9446d57ce632988f115847f2cd39877dd352a/2026-10-22T080121.494735Z-4fd1541d4a30-1e730315/outputs/` (ignored).
- Purpose: pilot/exploratory. Exactly 18 original development VMs; 54/54 completed.
- Wall time: 244.014s with two VM workers. No invalidated scientific attempts in V2.4E.
- Versions: `causal-timeline-v3`, `phase-balanced-hourly-v1`, `refresh-accounting-v1`, `paired-observation-window-24h-v1`, `budget-match-uniform-eligible-v2`.
- Models: 36 target-specific bootstrap RF fits, once per VM/resource; one-step streams only. Recursive forecasting calls: zero. ADWIN delta .002 and all RF parameters unchanged.

## Absolute descriptive results

Equal-VM macro averages; class in percent, p95 MAE/bias in utilization percentage
points. Positive bias means overstatement, not necessarily worse absolute error.

| Method | CPU class % | Memory class % | CPU p95 MAE | Memory p95 MAE | CPU bias | Memory bias |
| --- | --- | --- | --- | --- | --- | --- |
| adaptive_residual | 74.8804 | 72.0175 | 0.416065 | 0.720755 | -0.013609 | 0.003614 |
| budget_matched | 74.8487 | 71.8185 | 0.415333 | 0.718278 | -0.017394 | -0.000159 |
| pw_6h | 74.9296 | 71.9465 | 0.416812 | 0.719239 | -0.017926 | 0.000639 |

## Paired effects: Adaptive minus control

These are per-VM paired differences, then equal-VM descriptive summaries. For
class correctness positive is favorable; for MAE negative is favorable. Bias is
signed descriptive only. No p-values, confirmatory inference, practical-margin
calibration or retrospective thresholding is performed.

| Control | Metric | Mean delta | Median delta | VM range | Favorable VMs | Unfavorable VMs | Ties |
| --- | --- | --- | --- | --- | --- | --- | --- |
| budget_matched | cpu_class_accuracy (pp) | 0.031632 | 0.000000 | -1.061571 to 0.862069 | 3 | 1 | 14 |
| budget_matched | memory_class_accuracy (pp) | 0.198997 | 0.000000 | -0.172117 to 2.155172 | 5 | 2 | 11 |
| budget_matched | cpu_p95_mae | 0.000732 | 0.000015 | -0.012064 to 0.017216 | 3 | 9 | 6 |
| budget_matched | mem_p95_mae | 0.002477 | 0.000209 | -0.010085 to 0.042316 | 6 | 10 | 2 |
| pw_6h | cpu_class_accuracy (pp) | -0.049236 | 0.000000 | -1.273885 to 0.215517 | 2 | 1 | 15 |
| pw_6h | memory_class_accuracy (pp) | 0.071018 | 0.000000 | -0.402414 to 1.508621 | 2 | 1 | 15 |
| pw_6h | cpu_p95_mae | -0.000747 | 0.000000 | -0.016997 to 0.007972 | 5 | 7 | 6 |
| pw_6h | mem_p95_mae | 0.001516 | 0.000279 | -0.003017 to 0.022618 | 4 | 11 | 3 |

At equal budget, CPU class gains average +0.0316pp and memory +0.1990pp, while
CPU p95 MAE worsens +0.000732 and memory +0.002477. Both class medians are zero;
both MAE medians are positive (worse). CPU MAE improves on 3 VMs and worsens on
9; memory MAE improves on 6 and worsens on 10. Only Trace1/96 strictly improves
all four primary quantities. This is not consistent evidence of adaptive benefit.
No numerical meaningful-effect threshold is invented to turn those class gains
into a retention claim. Equal-budget mixed directions, rather than a new chosen
margin, motivate the conservative negative decision.

Against PW, the 121 extra refreshes (7.7465% above the base total) do not produce
a consistent two-resource improvement: CPU class -0.0492pp, memory +0.0710pp,
CPU p95 MAE -0.000747, memory +0.001516. More updates alone do not establish
useful drift timing. RF detection overhead has not received a dedicated systems
benchmark; these findings cannot establish a favorable cost/benefit tradeoff.

### Every VM: Adaptive minus BudgetMatched

Accuracy deltas are percentage points. All original VMs are retained; none were
excluded based on accuracy, volatility effects, detector behavior or missingness.

| Trace | VM | Tier | CPU class delta pp | Memory class delta pp | CPU p95 MAE delta | Memory p95 MAE delta |
| --- | --- | --- | --- | --- | --- | --- |
| Materna-Trace-1 | 143 | high | 0.000000 | 0.000000 | -0.001077 | -0.001607 |
| Materna-Trace-1 | 213 | low | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Materna-Trace-1 | 374 | low | 0.000000 | 0.000000 | 0.000000 | -0.001955 |
| Materna-Trace-1 | 64 | medium | 0.252525 | 0.000000 | 0.000438 | 0.002527 |
| Materna-Trace-1 | 76 | high | 0.000000 | 0.000000 | 0.001278 | 0.002775 |
| Materna-Trace-1 | 96 | medium | 0.862069 | 2.155172 | -0.012064 | -0.010085 |
| Materna-Trace-2 | 11 | high | 0.000000 | 0.000000 | 0.017216 | 0.042316 |
| Materna-Trace-2 | 207 | low | 0.000000 | 0.000000 | 0.000000 | 0.000275 |
| Materna-Trace-2 | 388 | medium | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| Materna-Trace-2 | 396 | low | 0.000000 | 0.201207 | 0.000069 | -0.002536 |
| Materna-Trace-2 | 398 | medium | 0.000000 | 0.000000 | 0.000000 | 0.000144 |
| Materna-Trace-2 | 516 | high | -1.061571 | 0.000000 | -0.011141 | 0.003487 |
| Materna-Trace-3 | 127 | high | 0.000000 | 0.344234 | 0.002352 | 0.003256 |
| Materna-Trace-3 | 133 | medium | 0.000000 | 0.000000 | 0.001309 | 0.006373 |
| Materna-Trace-3 | 151 | low | 0.000000 | -0.172117 | 0.000030 | -0.000111 |
| Materna-Trace-3 | 212 | low | 0.000000 | -0.172117 | 0.000000 | 0.000687 |
| Materna-Trace-3 | 224 | high | 0.516351 | 0.516351 | 0.007575 | -0.001355 |
| Materna-Trace-3 | 83 | medium | 0.000000 | 0.709220 | 0.007186 | 0.000392 |

### Volatility tiers

Each tier has six VMs. The following are Adaptive minus control averages;
reporting a tier does not authorize a tier-specific detector or post-hoc hybrid.

| Control | Tier | CPU class delta pp | Memory class delta pp | CPU p95 MAE delta | Memory p95 MAE delta |
| --- | --- | --- | --- | --- | --- |
| budget_matched | high | -0.090870 | 0.143431 | 0.002701 | 0.008145 |
| budget_matched | low | 0.000000 | -0.023838 | 0.000017 | -0.000607 |
| budget_matched | medium | 0.185766 | 0.477399 | -0.000522 | -0.000108 |
| pw_6h | high | -0.183628 | 0.028686 | -0.001158 | 0.004375 |
| pw_6h | low | 0.000000 | -0.067069 | -0.000068 | -0.000177 |
| pw_6h | medium | 0.035920 | 0.251437 | -0.001016 | 0.000351 |

The medium tier has favorable equal-budget averages on all four endpoints, but
one VM (Trace1/96) contributes the largest class and MAE improvements. Other
tiers are mixed: high-tier CPU correctness and both MAEs worsen; low-tier CPU
correctness ties, memory correctness worsens and memory MAE improves. There is
no consistent tier/resource pattern supporting blanket retention.

## Accounting and exact budgets

Initialization: one event per method/VM, excluded from runtime refreshes.
Each runtime commit writes all four fields, even if unchanged. All methods share
exactly 1,562 actual and nominal periodic commits. Adaptive and BudgetMatched
have 1,683 runtime refreshes each, with 121 drift/budget extras respectively.
PW has 1,562. No duplicate or colliding commits. The previous development
predictor-content run had a different eligibility gate; its counts are not reused.

| Trace | VM | Periodic base | Adaptive drift K | Adaptive total | Budget total |
| --- | --- | --- | --- | --- | --- |
| Materna-Trace-1 | 143 | 81 | 7 | 88 | 88 |
| Materna-Trace-1 | 213 | 81 | 0 | 81 | 81 |
| Materna-Trace-1 | 374 | 81 | 2 | 83 | 83 |
| Materna-Trace-1 | 64 | 69 | 4 | 73 | 73 |
| Materna-Trace-1 | 76 | 81 | 3 | 84 | 84 |
| Materna-Trace-1 | 96 | 81 | 18 | 99 | 99 |
| Materna-Trace-2 | 11 | 81 | 10 | 91 | 91 |
| Materna-Trace-2 | 207 | 86 | 1 | 87 | 87 |
| Materna-Trace-2 | 388 | 86 | 0 | 86 | 86 |
| Materna-Trace-2 | 396 | 86 | 18 | 104 | 104 |
| Materna-Trace-2 | 398 | 76 | 1 | 77 | 77 |
| Materna-Trace-2 | 516 | 81 | 7 | 88 | 88 |
| Materna-Trace-3 | 127 | 100 | 16 | 116 | 116 |
| Materna-Trace-3 | 133 | 95 | 5 | 100 | 100 |
| Materna-Trace-3 | 151 | 100 | 3 | 103 | 103 |
| Materna-Trace-3 | 212 | 100 | 5 | 105 | 105 |
| Materna-Trace-3 | 224 | 100 | 10 | 110 | 110 |
| Materna-Trace-3 | 83 | 97 | 11 | 108 | 108 |

There are 4,928 refresh events and 19,712 field writes across the three methods;
54 separate initialization events are excluded. Two VMs have K=0; their extra
schedule is empty and all three methods reduce to the same base/content behavior.
The nonadaptive scheduler receives only eligible timestamps, base commits and K;
independent reconstruction reproduced every extra timestamp. No drift timestamp,
residual magnitude, score or target value enters it. This K-based control remains
analysis-only and is not claimed to be deployable online.

## Profile age and evaluation alignment

Exactly 9,021 common VM/evaluation-time points, 27,063 method snapshot records.
Every method uses the same nominal hourly times, thresholds and verified forward
`(t,t+24h]` targets per VM. Reads during missing telemetry occur at their nominal
clock time and do not wait for the next observation. All reported values are
finite. Profile age is recorded at the read; it is not reconstructed from field
change rows.

The table below pools scored snapshots, so its means differ slightly from the
equal-VM age means in `per_vm_results.parquet`/summary. p95 is a pooled percentile,
not the mean of per-VM p95s.

| Method | Mean age h | Median h | p95 h | Max h | Age zero % |
| --- | --- | --- | --- | --- | --- |
| adaptive_residual | 2.604368 | 2.000000 | 5.000000 | 46.000000 | 16.505931 |
| budget_matched | 2.602058 | 2.000000 | 5.000000 | 46.000000 | 16.472675 |
| pw_6h | 2.665826 | 3.000000 | 5.000000 | 46.000000 | 16.439419 |

No periodic method has all-zero-age scoring. Most complete-data PW evaluations
cover ages 0,1,2,3,4,5h; early initialized profiles have an additional 5-minute
offset. All three methods retain old state through telemetry gaps. The maximum
46h age is preserved stale state during gaps, not a scheduler re-anchor or
imputation. Equal budgets do not imply equal age distributions: placement is the
experimental treatment. Adaptive minus BudgetMatched equal-VM mean age is
+0.001809h, with range -0.124204 to +0.028829h; an age change is not itself a
fidelity improvement.

## Gap eligibility and residual behavior

Within the 18 VMs, 6 have unavailable exact-grid one-step slots
(768 processed timestamps
in total). 2 have ineligible content windows
(398 processed timestamps).
Maximum observed gap is 86700s
(24h 5min). No rolling/lag history bridges a missing nominal slot; detector updates
pause where either one-step history/prediction is unavailable.

One actual ADWIN signal at Trace3/133 has insufficient content and is consumed,
counted as `ineligible_drift_signals=1`, without a refresh. No signal is latched.
Periodic pending ticks wait for 200 paired content slots, coalesce after long
gaps and preserve their nominal anchor. They are not gated by RF origin history.
The runtime/independent checks confirm all actual commits are observed and content
eligible; every drift commit also has valid one-step history. No full-corpus
policy, forecasting or new full-corpus metadata experiment was run.

## Integrity and tests

- 304 tests passed, zero failed/skipped. All 81 Python files parse; new modules
  import and CLI help works. Synthetic checks include K=0, budget collisions,
  gap recovery/coalescing, joint finite masks, missing-observation clock reads,
  same-time refresh precedence, future-content invariance, and a horizon-raising
  predictor proving no profile forecasting is used.
- Clean committed source was verified before managed execution. Nine required
  artifacts pass size/SHA manifest checks. Independent verification reconstructed
  all commit contents, base/extra schedules and forward truths from only the same
  18 raw VM inputs, without fitting models. Budget equality is exact for 18/18.
- Exact pilot cache accepted; mutated period rejected with `config_mismatch` and
  `experiment_fingerprint_mismatch`; claim reuse rejected with
  `run_purpose_mismatch` / `noncanonical_run`; a tampered byte-copy rejected with
  `output_hash_mismatch`. The canonical run is unchanged.
- No confirmatory forecasting/policy outcomes were accessed. Dataset integrity
  hashing covers the input manifest. Existing unit CSV-loader checks read three
  other raw fixtures for schema/dtype/row-count checks only; no forecasts,
  profile scores, detector decisions or confirmatory outcomes are computed there.
- This gate is investigation completion, not validation of a positive contribution.
  No significance tests or practical margins were estimated from the pilot.

## Architecture and next-gate consequences

1. Remove predictor-generated profile content from the candidate (implemented
   in the new shared-window policies). Legacy PP/V3 modules remain isolated,
   not reintroduced as accepted candidates.
2. The residual RF/ADWIN component is also not justified by equal-budget timing
   evidence. Recommend omitting prediction entirely from the final architecture.
   Current residual-only policies remain experimental controls, not a retained
   contribution. No automatic destructive removal of reproducibility code.
3. C1 remains withdrawn. C2's residual-driven timing benefit is unsupported;
   do not pre-register a superiority claim as if it had passed. Equal-budget
   controls remain necessary for any later timing claim, with shared content.
4. The remaining supported reference is observation-window maintenance with
   deterministic scheduling/accounting. This does not by itself establish a novel
   adaptive method or strong systems contribution. Review the research scope and
   actual candidate contribution before a confirmatory freeze.
5. **V2.4E = PASS. V2.5 remains BLOCKED until review; V3 remains BLOCKED.**
   After review accepts a final architecture and falsifiable question, V2.5 can
   begin freezing the cohort/endpoints/margins/comparisons. It cannot automatically
   begin as a plan to rescue unsupported C1/C2. No new algorithm or model search
   is proposed by this task.

Outputs: `cohort.parquet`, `per_vm_results.parquet`, `refresh_events.parquet`,
`evaluation_records.parquet`, `budget_schedule.parquet`, `paired_effects.parquet`,
`tier_metrics.parquet`, `diagnostics.json`, `summary.json`.
