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
  it cannot alter profile content.
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

Implementation and bounded execution are pending. Factual results, managed run
identity, integrity checks, and architecture disposition will be recorded only
after a clean-source run.
