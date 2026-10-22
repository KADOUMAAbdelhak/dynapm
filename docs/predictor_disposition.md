# Predictor disposition — V2.4D

Development investigation only. No production predictor, residual RF, detector,
policy, protocol or accounting behavior is changed. V2.5 and V3 remain blocked.

## Frozen analysis plan

Candidates are the existing direct-profile RF (200 trees, depth 20, sqrt features,
seed 42, two outputs: future mean and p95) and seasonal-naive profile content.
The latter is exactly trailing `(t-24h,t]` PW content at a shared origin, requiring
200/288 actual nominal slots. Class is derived from the mean using frozen
bootstrap thresholds; future truth is canonical `(t,t+24h]`, >=200 paired slots.

Origins are taken from the validated corrected V2 pilot event artifact, not
selected using accuracy: PP6 periodic and V3 drift commits are reported separately. The all-origin set
is the deduplicated union of PP3/PP6/PP12/V3/BudgetMatched commits, including
non-adaptive budget extras; recorded source methods are retained. PP6 and V3 periodic commit sets must
match. Origins with unelapsed/insufficient truth are logged, never scored.
Native availability is reported separately; comparisons use identical origins
where both candidates are available. No fallback is introduced.

## Predefined bootstrap selector

For each VM, use four evenly indexed eligible origins from a six-hour grid
anchored at bootstrap start +72h. Each validation origin's complete 24h horizon
must lie inside bootstrap; both resources need 96 complete causal history slots
and >=200 trailing seasonal slots. Each prefix must contain at least one fully matured training label for both
resources. Eligibility uses presence and label maturity, not model outcomes.
At each rolling origin, train RF on the prefix ending there: every training
label's horizon has already elapsed. Thresholds are prefix-only for this
prequential validation, shared across candidates. After bootstrap, select RF
only if its four-origin mean class correctness is strictly higher AND its mean
p95 absolute error is strictly lower than seasonal. Every tie chooses seasonal.
The decision is frozen before evaluating streaming origins. Full-bootstrap RF
and thresholds are then used for operational comparisons. Choices are per
VM/resource; this is the explicitly requested selector, not an invented hybrid.

Aggregation is paired-origin within VM, then equal-VM macro averages. Drift-only
summaries include only VMs with verifiable drift origins; coverage denominators
are retained. Neither significance nor performance magnitude is an investigation
completion criterion. No confirmatory VM outcomes are accessed.

## Final disposition

**B — PREDICTOR NOT JUSTIFIED** for predictor-grounded profile generation.
The direct-profile RF has no robust operational-origin advantage over
seasonal/PW-equivalent content. The predefined bootstrap selector also fails to
improve both resource objectives consistently. Recommend removing learned
profile-content forecasting in a separate architecture task; do not integrate
this RF or the selector. This is an engineering disposition on development
evidence, not proof that all possible forecasting methods are ineffective.

Prediction for one-step residual/drift surveillance is a separate role. This
study neither removes nor justifies that RF; its incremental detection value
requires a separate controlled ablation. Production code is unchanged.


## Invalidated attempt

Study-v1 fingerprint `cd4e36aa96f14dc257cf04c3741f83b90b9906f03d47a36c036f4d8908a3cf38`,
run `2026-10-22T073215.297597Z-cd4e36aa96f1-62b49160`, source
`b638e660d3cfd715f5b86be16903d97c0f351be8`, failed on a bootstrap
prefix with no eligible mature training labels after gaps. No comparison tables
were produced or inspected. Study-v2 adds presence-only mature-label eligibility
before selecting rolling validation folds. No score threshold, model setting,
selector rule or streaming origin is changed. The failed run remains untouched.


## Managed execution and integrity

- Clean source: `0ada9c14ead1621039830ade86963193ba8a446a`.
- Experiment fingerprint: `77f3f60abcd1f2dfdb1f6ad0e7ffedc1ccbccec1b2a317e369286f6e74c0a519`.
- Run ID: `2026-10-22T073824.175800Z-77f3f60abcd1-ef449ae2`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f` (the same fixed 18 development VMs).
- Output-manifest SHA-256: `2a007d5b28228ab00845d9f29a4ce63e3946cba27765afe78513522d40dc0c26`.
- Location: `results/runs/77f3f60abcd1f2dfdb1f6ad0e7ffedc1ccbccec1b2a317e369286f6e74c0a519/2026-10-22T073824.175800Z-77f3f60abcd1-ef449ae2/outputs/` (ignored).
- Wall time: 135.860 seconds with two workers. No confirmatory outcomes, policy tuning, ADWIN tuning or historical target inputs.
- Versions remain `causal-timeline-v3`, `phase-balanced-hourly-v1`, `refresh-accounting-v1`. This is an origin-content study, not a policy replay or phase-balanced snapshot rerun.
- 3,362 distinct recorded origins: 1,561 PP6 periodic, 122 V3 drift, and 1,679 other predictor-policy commits. These are inherited origins, not newly optimized schedules.
- 36 fixed selector choices; 288 resource/method validation rows; 19,158 operational resource/method rows before paired-availability filtering. Four prequential validation origins per VM/resource; no selection from streaming outcomes.

## Operational-origin results

Equal-VM macro averages on common available origins; p95 errors/bias are in
utilization percentage points. Class correctness is percent. Positive bias
means overprediction. Drift summaries cover 15 VMs; periodic/all cover 18.
The all-origin set is not a time-weighted deployment average and includes
non-adaptive matched-budget opportunities from the previous pilot.

| Origins | Resource | Content | VMs | Paired origins | Class % | p95 MAE | p95 bias |
| --- | --- | --- | --- | --- | --- | --- | --- |
| periodic_6h | cpu | rf_profile | 18 | 1485 | 49.45 | 0.9016 | 0.2549 |
| periodic_6h | cpu | seasonal | 18 | 1485 | 76.01 | 0.3906 | -0.0206 |
| periodic_6h | cpu | selector | 18 | 1485 | 75.14 | 0.3745 | -0.0361 |
| periodic_6h | memory | rf_profile | 18 | 1485 | 60.08 | 0.8176 | -0.0374 |
| periodic_6h | memory | seasonal | 18 | 1485 | 72.55 | 0.6847 | 0.0033 |
| periodic_6h | memory | selector | 18 | 1485 | 71.00 | 0.7102 | -0.0653 |
| v3_drift | cpu | rf_profile | 15 | 110 | 45.34 | 1.1136 | -0.0449 |
| v3_drift | cpu | seasonal | 15 | 110 | 69.98 | 0.7418 | 0.2743 |
| v3_drift | cpu | selector | 15 | 110 | 69.15 | 0.6879 | 0.2140 |
| v3_drift | memory | rf_profile | 15 | 110 | 52.97 | 0.9097 | -0.0070 |
| v3_drift | memory | seasonal | 15 | 110 | 71.47 | 0.8925 | 0.4420 |
| v3_drift | memory | selector | 15 | 110 | 70.36 | 0.9613 | 0.3132 |
| all | cpu | rf_profile | 18 | 3192 | 49.71 | 0.8981 | 0.2268 |
| all | cpu | seasonal | 18 | 3192 | 75.92 | 0.4075 | -0.0153 |
| all | cpu | selector | 18 | 3192 | 74.63 | 0.3908 | -0.0319 |
| all | memory | rf_profile | 18 | 3192 | 59.90 | 0.8208 | -0.0386 |
| all | memory | seasonal | 18 | 3192 | 72.71 | 0.6908 | 0.0165 |
| all | memory | selector | 18 | 3192 | 70.81 | 0.7214 | -0.0555 |

RF underperformance persists at actual drift origins; it is not explained away
by the earlier use of hourly snapshot origins. Near-zero aggregate drift bias
for RF does not imply low absolute error: opposite errors can cancel. No
confirmatory p-values or practical-benefit thresholds were estimated here.

### Per-VM robustness

Wins/losses/ties versus seasonal; ties use reporting tolerance 1e-12. Selector
selection itself uses strict comparisons with no fitted margin.

| Origins | Resource | Method | Metric | Wins | Losses | Ties | VMs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | cpu | rf_profile | class_correct | 2 | 15 | 1 | 18 |
| all | cpu | rf_profile | p95_absolute_error | 6 | 12 | 0 | 18 |
| all | cpu | selector | class_correct | 1 | 1 | 16 | 18 |
| all | cpu | selector | p95_absolute_error | 1 | 1 | 16 | 18 |
| all | memory | rf_profile | class_correct | 5 | 12 | 1 | 18 |
| all | memory | rf_profile | p95_absolute_error | 8 | 10 | 0 | 18 |
| all | memory | selector | class_correct | 2 | 1 | 15 | 18 |
| all | memory | selector | p95_absolute_error | 0 | 3 | 15 | 18 |
| periodic_6h | cpu | rf_profile | class_correct | 2 | 15 | 1 | 18 |
| periodic_6h | cpu | rf_profile | p95_absolute_error | 6 | 12 | 0 | 18 |
| periodic_6h | cpu | selector | class_correct | 1 | 1 | 16 | 18 |
| periodic_6h | cpu | selector | p95_absolute_error | 1 | 1 | 16 | 18 |
| periodic_6h | memory | rf_profile | class_correct | 5 | 12 | 1 | 18 |
| periodic_6h | memory | rf_profile | p95_absolute_error | 8 | 10 | 0 | 18 |
| periodic_6h | memory | selector | class_correct | 2 | 1 | 15 | 18 |
| periodic_6h | memory | selector | p95_absolute_error | 0 | 3 | 15 | 18 |
| v3_drift | cpu | rf_profile | class_correct | 4 | 9 | 2 | 15 |
| v3_drift | cpu | rf_profile | p95_absolute_error | 6 | 8 | 1 | 15 |
| v3_drift | cpu | selector | class_correct | 0 | 1 | 14 | 15 |
| v3_drift | cpu | selector | p95_absolute_error | 1 | 0 | 14 | 15 |
| v3_drift | memory | rf_profile | class_correct | 5 | 8 | 2 | 15 |
| v3_drift | memory | rf_profile | p95_absolute_error | 7 | 8 | 0 | 15 |
| v3_drift | memory | selector | class_correct | 2 | 1 | 12 | 15 |
| v3_drift | memory | selector | p95_absolute_error | 1 | 2 | 12 | 15 |

### Volatility tiers (all origins)

Six VMs per bootstrap CPU-volatility tier. The full origin-group breakdown is
in `tier_metrics.parquet`; no tier-specific model or selector was invented.

| Resource | Tier | Content | Class % | p95 MAE | p95 bias |
| --- | --- | --- | --- | --- | --- |
| cpu | high | rf_profile | 40.84 | 2.1626 | 0.9456 |
| cpu | low | rf_profile | 62.81 | 0.0436 | -0.0281 |
| cpu | medium | rf_profile | 45.48 | 0.4882 | -0.2373 |
| cpu | high | seasonal | 66.55 | 0.6798 | -0.0568 |
| cpu | low | seasonal | 88.51 | 0.0240 | -0.0004 |
| cpu | medium | seasonal | 72.70 | 0.5186 | 0.0113 |
| cpu | high | selector | 67.03 | 0.6292 | -0.1002 |
| cpu | low | selector | 88.51 | 0.0240 | -0.0004 |
| cpu | medium | selector | 68.36 | 0.5190 | 0.0050 |
| memory | high | rf_profile | 64.10 | 1.4158 | 0.2118 |
| memory | low | rf_profile | 55.15 | 0.3373 | -0.1399 |
| memory | medium | rf_profile | 60.45 | 0.7093 | -0.1878 |
| memory | high | seasonal | 74.19 | 0.9771 | 0.0551 |
| memory | low | seasonal | 72.56 | 0.3998 | -0.0233 |
| memory | medium | seasonal | 71.38 | 0.6955 | 0.0178 |
| memory | high | selector | 75.64 | 1.0174 | -0.0817 |
| memory | low | selector | 72.56 | 0.3998 | -0.0233 |
| memory | medium | selector | 64.21 | 0.7472 | -0.0614 |

CPU RF loses class correctness in every tier. Its medium-tier p95 improvement
comes with much worse class accuracy, and high/low-tier p95 errors worsen.
Memory RF loses class correctness in every tier; low-tier p95 MAE improves
while medium/high-tier p95 MAE worsens. Selector CPU gains
are concentrated in one high-tier VM; medium-tier class performance worsens.
Memory selector improves high-tier class accuracy but worsens its p95 MAE;
medium-tier performance worsens on both. These findings do not support a
post-hoc tier/resource hybrid or revised selector rule.

## Bootstrap choices and streaming generalization

Every choice below is made using four prefix-trained bootstrap validation
origins. Class columns are RF/seasonal percentages; MAE columns are RF/seasonal.
Rolling thresholds are prefix-only, rather than using later bootstrap values.
Streaming comparisons use the common full-bootstrap thresholds.

| Trace | VM | Resource | Choice | Bootstrap class % RF/S | Bootstrap p95 MAE RF/S |
| --- | --- | --- | --- | --- | --- |
| Materna-Trace-1 | 143 | cpu | seasonal | 50.00/75.00 | 0.2846/0.3784 |
| Materna-Trace-1 | 143 | memory | seasonal | 50.00/75.00 | 0.4802/0.2114 |
| Materna-Trace-1 | 213 | cpu | seasonal | 75.00/75.00 | 0.0191/0.0084 |
| Materna-Trace-1 | 213 | memory | seasonal | 75.00/75.00 | 0.2116/0.1991 |
| Materna-Trace-1 | 374 | cpu | seasonal | 0.00/25.00 | 0.0726/0.0134 |
| Materna-Trace-1 | 374 | memory | seasonal | 75.00/100.00 | 1.6573/0.4500 |
| Materna-Trace-1 | 64 | cpu | seasonal | 25.00/25.00 | 0.0953/0.0591 |
| Materna-Trace-1 | 64 | memory | rf_profile | 50.00/25.00 | 0.2069/0.2946 |
| Materna-Trace-1 | 76 | cpu | seasonal | 25.00/75.00 | 2.6348/2.0870 |
| Materna-Trace-1 | 76 | memory | seasonal | 75.00/75.00 | 1.1651/0.7702 |
| Materna-Trace-1 | 96 | cpu | seasonal | 100.00/100.00 | 0.6945/0.7491 |
| Materna-Trace-1 | 96 | memory | seasonal | 50.00/50.00 | 1.0130/0.7183 |
| Materna-Trace-2 | 11 | cpu | seasonal | 50.00/25.00 | 3.9242/3.7029 |
| Materna-Trace-2 | 11 | memory | seasonal | 75.00/100.00 | 2.1711/2.1014 |
| Materna-Trace-2 | 207 | cpu | seasonal | 75.00/50.00 | 0.0000/0.0000 |
| Materna-Trace-2 | 207 | memory | seasonal | 50.00/50.00 | 0.1681/0.2166 |
| Materna-Trace-2 | 388 | cpu | rf_profile | 50.00/25.00 | 0.0073/0.0141 |
| Materna-Trace-2 | 388 | memory | seasonal | 25.00/50.00 | 0.3064/0.3286 |
| Materna-Trace-2 | 396 | cpu | seasonal | 50.00/50.00 | 0.0140/0.0291 |
| Materna-Trace-2 | 396 | memory | seasonal | 100.00/100.00 | 0.1085/0.0911 |
| Materna-Trace-2 | 398 | cpu | seasonal | 25.00/100.00 | 0.0276/0.0000 |
| Materna-Trace-2 | 398 | memory | seasonal | 100.00/100.00 | 0.0471/0.0361 |
| Materna-Trace-2 | 516 | cpu | seasonal | 100.00/50.00 | 0.8596/0.5811 |
| Materna-Trace-2 | 516 | memory | rf_profile | 100.00/75.00 | 0.4002/0.9284 |
| Materna-Trace-3 | 127 | cpu | seasonal | 25.00/100.00 | 5.6757/5.4560 |
| Materna-Trace-3 | 127 | memory | seasonal | 75.00/100.00 | 1.4412/1.0020 |
| Materna-Trace-3 | 133 | cpu | seasonal | 25.00/75.00 | 0.0737/0.0706 |
| Materna-Trace-3 | 133 | memory | seasonal | 75.00/75.00 | 2.0936/2.0641 |
| Materna-Trace-3 | 151 | cpu | seasonal | 100.00/100.00 | 0.0104/0.0091 |
| Materna-Trace-3 | 151 | memory | seasonal | 75.00/75.00 | 0.2733/0.1939 |
| Materna-Trace-3 | 212 | cpu | seasonal | 75.00/75.00 | 0.0021/0.0000 |
| Materna-Trace-3 | 212 | memory | seasonal | 75.00/75.00 | 0.1569/0.0914 |
| Materna-Trace-3 | 224 | cpu | rf_profile | 50.00/25.00 | 0.5031/0.6304 |
| Materna-Trace-3 | 224 | memory | seasonal | 50.00/50.00 | 1.7524/1.4009 |
| Materna-Trace-3 | 83 | cpu | seasonal | 75.00/75.00 | 0.0381/0.0275 |
| Materna-Trace-3 | 83 | memory | rf_profile | 75.00/50.00 | 0.1675/0.3427 |

RF is selected for CPU Trace2/388 and Trace3/224, and memory Trace1/64,
Trace2/516 and Trace3/83. The other 31 resource choices select seasonal.
Among these five selected resource models, only CPU Trace3/224 improves both
streaming objectives against seasonal. CPU Trace2/388 worsens both. Memory
Trace1/64 and Trace2/516 improve class correctness but worsen p95 MAE;
Trace3/83 worsens both. Therefore bootstrap strict-both selection does not
generalize convincingly.

Across all origins, selector versus seasonal changes CPU correctness by
-1.2913 percentage points and p95 MAE by -0.01670; memory correctness by
-1.9060 points and p95 MAE by +0.03063. CPU p95 improvement alone cannot pass
the requested two-objective, two-resource robustness criterion. Four validation
origins are a coarse development estimate, not a stable universal selector;
no extra folds, margins, weights or new search were selected after the results.

## Availability and no-fallback rule

Truth requires a fully elapsed horizon and >=200 paired finite nominal targets.
Coverage below is per resource (identical CPU/memory counts). Comparisons drop
the same unavailable origins for all three candidates, with native rows retained.

| Origin group | Recorded | Verifiable truth | RF available | Seasonal available | Selector available |
| --- | --- | --- | --- | --- | --- |
| other_predictor_refresh | 1679 | 1597 | 1597 | 1597 | 1597 |
| periodic_6h | 1561 | 1485 | 1485 | 1485 | 1485 |
| v3_drift | 122 | 111 | 111 | 110 | 110 |

All-origin totals: 3,193/3,362 have verifiable truth; 169 are excluded identically
(157 unelapsed horizons and 12 insufficient paired-target windows). RF is
available at all 3,193 verifiable origins. Seasonal and selector are available
at 3,192/3,193 (99.9687%); paired comparison uses exactly 3,192 origins per
resource. The one missing seasonal origin is Trace3/133 at
`2016-02-03 11:55:00`, a V3 drift commit after a gap. It has enough 96-slot RF
history but fewer than 200 trailing seasonal observations. No fallback or
imputation is used. A future PW-content V3 needs an explicit drift-content
eligibility rule, with retain/skip/defer behavior predefined and regression-tested;
this task does not choose or implement that behavior. One extra RF-available
origin is not evidence of robust fidelity benefit.

## Cost context

Per-resource final RF bootstrap training, averaged across VMs, was

- cpu: 1.183s training, 37.82 MiB learned-array state lower bound, 8.234ms median / 11.299ms p95 inference; 45.125s summed extra bootstrap-selector training across 72 folds.

- memory: 1.297s training, 40.23 MiB learned-array state lower bound, 8.243ms median / 11.301ms p95 inference; 49.046s summed extra bootstrap-selector training across 72 folds.

These are bounded diagnostic timings from the recorded environment with two
workers, not dedicated maintenance benchmarks or peak RSS. No extra seasonal
inference benchmark is inferred from RF measurements. The cost does not buy a
robust content advantage in this cohort.

## Architectural consequences (recommended; not integrated)

1. **C1:** withdraw predictor-grounded content superiority as an intended current
   contribution. The evidence does not justify it; independent confirmation is
   not a license to search for favorable results. Future fidelity tests may
   still falsify revised timing claims.
2. **Periodic-Predictor:** retain current code only as a development/negative
   control until a separate implementation change. Seasonal-profile PP is
   mathematically PW content at the same origin, so it must not be presented as
   a distinct strong forecasting baseline or novel component.
3. **DynAPM-V3:** propose observation-window content plus adaptive maintenance
   timing in a separate architecture task. One-step RF residual/drift detection
   remains conceptually separate and requires independent incremental-value
   evidence. Do not describe rejection of content RF as validation of residual RF.
4. **Matched budget:** future timing tests should compare adaptive versus
   non-adaptive extra refresh placement with the SAME observation-window
   content, same eligibility and exact refresh budgets. The old predictor-grounded
   matched-budget experiment is not automatically transferable. Revalidate
   candidate availability, common schedules and counters after any code change.
5. **Framing:** adaptive profile-maintenance timing, measured cost and operational
   benefit are candidate questions, not established contributions. Remove
   unsupported learned 24h-profile-forecast superiority/novelty. Cross-corpus and
   systems/edge claims still require their planned evidence.

## Verification and next gate

- 288 tests passed, zero failed/skipped; all 77 tracked Python files parse;
  diagnostic imports and CLI help pass. New tests cover origin union, paired
  truth, strict two-metric/tie rule, rolling label maturity, future-data
  invariance for both content candidates, missing seasonal availability and
  frozen selector application.
- Independent checks reproduce all 36 choices and confirm every training label
  ends <= its validation origin and every validation horizon ends <= bootstrap
  end. Selected predictions match the frozen candidate exactly. All candidate
  scores use identical origins/truth; finite available predictions throughout.
- Managed cache accepts the exact pilot; altered config rejects with
  `config_mismatch` / `experiment_fingerprint_mismatch`; claim reuse rejects
  with `run_purpose_mismatch` / `noncanonical_run`; tampered temporary output
  copy rejects with `output_hash_mismatch`. Canonical outputs were not edited.
- All ten declared output files pass manifest size/SHA checks. No confirmatory
  outcomes, historical targets or archive content were consumed. The full raw
  dataset manifest was integrity-hashed, not evaluated outside the 18 VMs.
- **V2.4D = PASS (investigation complete, disposition B). V2.5 and V3 remain
  BLOCKED** pending architecture review/follow-up and bounded revalidation.
  No production integration or new scientific run follows automatically.

Machine-readable outputs: `operational_origins.parquet`, `predictions.parquet`,
`bootstrap_validation.parquet`, `selector_choices.parquet`,
`availability.parquet`, `costs.parquet`, `vm_metrics.parquet`,
`macro_metrics.parquet`, `tier_metrics.parquet`, and `summary.json`.
