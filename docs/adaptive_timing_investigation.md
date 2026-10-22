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

## Execution

Pending clean-source managed run. Completion of this investigation does not
authorize V2.5 or confirmation without review.
