# Predictor Diagnosis — V2.4

Exploratory development-only diagnosis under `causal-timeline-v3`. No policy, RF, ADWIN, scheduling or accounting parameter changes. No confirmatory entity outcomes or historical archive inputs.

## Frozen diagnostic design

The same eighteen permanent development VMs are loaded from the integrity-validated corrected pilot cohort. For each VM, select eight equal-index-spaced origins from observed, globally verifiable hourly times with complete CPU/memory exact-grid history. Selection uses eligibility/timestamps only, never forecast errors. This bounded sample is not every refresh or a confirmation study.

Fit unchanged bootstrap-only RF CPU/memory models once per VM: 200 trees, depth20, sqrt features, seed42, one model thread. Existing pilot files contain no serialized fitted models; fresh identical fits are necessary. Reuse each fit for every selected origin and diagnostic. No tuning or method selection is executed.

Compare 288-step recursive forecasts with persistence and exact timestamp 24h seasonal-naive. Missing seasonal slots remain unavailable. Report leads 1/12/72/144/288 (5min/1h/6h/12h/24h), error, bias, class-boundary distance, and per-VM variability. Summary lead comparisons use the common target set available to all controls. All available per-method rows remain in Parquet so availability restrictions can be inspected.

A separate `rf_one_step_actual_history_DIAGNOSTIC` uses actual intervening history for each target. It is causal at each target but **not** a deployable fixed-origin forecast. Its comparison with recursion diagnoses feedback accumulation and does not count as a competitor receiving the same information.

Profile diagnostics compute forward mean-based classes (as in production) and p95 error; p95 classes are an auxiliary diagnostic only. Record coverage, bootstrap/stream distribution shift, gap-related origin loss, threshold proximity, and forecast/actual variation. Never interpret p95 classes as the maintained mean-based class endpoint.

## Managed execution

Use `python -m dynapm.scripts.task21_predictor_diagnosis` from a clean committed tree. Run purpose is pilot, never claim. Config fingerprints include sample rule, controls, leads, unchanged model settings and class convention. The driver validates the prior pilot before reading its development cohort; it does not load fitted predictions/results as diagnostic outputs. Full raw hashes may be checked as provenance, but model/data-outcome diagnostics are restricted to the eighteen development entities.

Outputs: `lead_errors.parquet`, `profile_errors.parquet`, `vm_diagnostics.parquet`, `summary.json`, plus standard managed source/config/environment/dataset/cohort/output manifests. No generated scientific result is committed or manually edited.

## Gate

V2.4 completion requires validated managed outputs, lead/resource results and evidence-limited diagnosis, dataset suitability audit, full lightweight tests and source review. V2.5 stays blocked pending review; V3 stays blocked. Model redesign, if supported, is a separate authorized development phase and must precede freezing confirmation. No practical-benefit threshold may be chosen from favorable pilot effects.

## Completed execution — 2026-10-21

**V2.4: PASS (diagnostic/audit completion); REVIEW REQUIRED before V2.5.** No redesign or confirmatory execution is authorized by this record.

- Source commit: `8ad366a0a282c3981d135f26fe9cde34b1cb80ee`.
- Fingerprint: `d62c95d22722a7d42f43a61766bae0e7de1c31fcb8d02337b46f0e066f9dbd13`.
- Run ID: `2026-10-21T144944.993961Z-d62c95d22722-bedfa37c`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Output-manifest SHA-256: `cf8ca8c06b75480319a8dfa8c29ce864572cf1cc59d1e6b9bed2e7f01acdbd88`.
- Location: `results/runs/d62c95d22722a7d42f43a61766bae0e7de1c31fcb8d02337b46f0e066f9dbd13/2026-10-21T144944.993961Z-d62c95d22722-bedfa37c/` (ignored, generated).
- Purpose: pilot; claim eligible: false; source dirty: false.
- 18/18 VMs, eight origins each, 144 VM/origin pairs and 288 resource/origin forecasts. CPU/memory models fitted once each per VM (36 fits); no policy replay.
- 5,752 lead-error rows; 1,148 profile-diagnostic rows; 36 VM/resource metadata rows. Each resource/lead has 144 paired targets except step288, which has 143 because one actual target is missing. All four methods share the available scored lead targets.
- Wall time: 278.76s. This is execution feasibility, not a controlled overhead benchmark; unit tests ran concurrently.
- Full suite: **259 passed, 0 failed, 0 skipped**. All 68 Python files parsed/compiled, production modules imported and CLI/local documentation checks passed.
- Independent raw checks passed for target timestamps, actual target values, persistence values and exact seasonal lookup. All 288 first-step recursive predictions equal the corresponding causal one-step predictions within 1e-10 tolerance.
- Managed cache and all four output files validate. Changed diagnostic config and claim-purpose reuse are rejected. A tampered disposable output copy is rejected; original run revalidates unchanged.
- No failed/invalidated diagnostic attempts. No historical archive inputs, no confirmatory entity model outcomes, no parameter changes and no confirmatory inference. Full-dataset byte hashes were verified for provenance only.

## Error by lead and resource

MAE and signed bias are utilization **percentage points**, not relative percent. Rows are unweighted means of per-VM mean errors on matched available targets; every row includes all eighteen VMs. Eight origins per VM is a bounded diagnostic sample, not a population estimate.

| Resource | Lead / elapsed time | RF recursive MAE | Persistence MAE | Seasonal-naive MAE | RF one-step diagnostic MAE | RF recursive bias | RF target-class error |
|---|---|---:|---:|---:|---:|---:|---:|
| cpu | 1 / 5min | 0.6485 | 1.2612 | 0.6870 | 0.6485 | -0.0549 | 44.44% |
| cpu | 12 / 1h | 0.9550 | 0.7199 | 0.4611 | 0.5501 | +0.6176 | 65.28% |
| cpu | 72 / 6h | 2.2612 | 0.4128 | 0.3705 | 0.5088 | +2.1380 | 79.17% |
| cpu | 144 / 12h | 3.0047 | 0.6217 | 0.3896 | 0.6375 | +2.6809 | 73.61% |
| cpu | 288 / 24h | 3.0869 | 0.5779 | 0.5779 | 0.6858 | +2.5814 | 72.12% |
| memory | 1 / 5min | 1.3622 | 1.6740 | 2.3322 | 1.3622 | +0.1061 | 58.33% |
| memory | 12 / 1h | 1.7262 | 2.5526 | 2.1460 | 1.2597 | +0.1836 | 63.89% |
| memory | 72 / 6h | 3.5682 | 2.2190 | 2.1049 | 1.1309 | +2.3144 | 69.44% |
| memory | 144 / 12h | 4.6551 | 2.6408 | 1.6376 | 0.9950 | +3.3072 | 71.53% |
| memory | 288 / 24h | 4.5719 | 1.9890 | 1.9890 | 0.9590 | +3.2356 | 75.60% |

At step288, recursive MAE is 4.50x the actual-history one-step diagnostic for CPU and 4.77x for memory. Error grows markedly through 6–12h and then largely plateaus; it is not strictly monotonic. Recursive bias changes from near-zero at step1 to +2.581 CPU / +3.236 memory at step288. This is not merely loss of resolution at fixed percentile gates.

## Forward-profile diagnosis

Class errors below classify the **forward arithmetic mean**, matching production. p95 is a separate numerical endpoint. All three fixed-origin methods have identical actual means/p95s and paired-slot counts at each resource/origin in this run. Seasonal and persistence are diagnostic controls, not modifications to DynAPM.

| Resource | Fixed-origin method | p95 MAE | p95 bias | Mean-profile class error | Origins |
|---|---|---:|---:|---:|---:|
| cpu | persistence | 2.7899 | -2.7819 | 65.97% | 144 |
| cpu | rf_recursive | 2.6680 | +0.6349 | 62.50% | 144 |
| cpu | seasonal_naive_24h | 0.4547 | -0.2438 | 25.00% | 144 |
| memory | persistence | 4.6438 | -4.5181 | 75.69% | 144 |
| memory | rf_recursive | 3.7061 | +0.9216 | 71.53% | 144 |
| memory | seasonal_naive_24h | 0.6389 | -0.2405 | 22.22% | 144 |

The actual-history one-step diagnostic has p95 MAE 0.877 CPU / 1.184 memory on 142 eligible origins per resource, versus recursive 2.668 / 3.706 on 144. Its profile masks differ around gaps, so this auxiliary aggregate is not an exact paired fixed-origin comparison; the matched lead table is the cleaner feedback diagnostic.

## Evidenced causes and limits

1. **Recursive feedback is the strongest evidenced mechanism.** RF is competitive at step1 on aggregate, but feeding predicted history back increases both MAE and positive bias at longer leads. At 24h it beats persistence on only 1/18 CPU VMs and 4/18 memory VMs; it beats seasonal-naive on 1/18 and 4/18 respectively. A short one-step task is not evidence of a good 288-step profile predictor. Actual-history one-step inference is not an oracle forecast that an online origin can use.
2. **Horizon amplifies the current model's weakness; 24h unpredictability is not established.** Seasonal-naive has much lower forward-profile p95 errors than recursion, and long-lead error grows while the one-step comparator remains lower. Do not shorten horizons or select a replacement based only on these pilot results. At exactly 24h seasonal-naive equals persistence algebraically; this endpoint is not independent evidence for daily seasonality. Its advantage at other leads and for the whole profile is more informative.
3. **Threshold sensitivity contributes but is not the sole cause.** Five CPU VMs and one memory VM have p20–p80 spread <=0.1 percentage points. Two CPU VMs and one memory VM have repeated class gates; Trace2/398 memory has all four gates at zero (degenerate classes under the unchanged classifier). 63.19% of CPU forward means and 31.94% of memory means fall within 0.1pp of a gate. RF mean-class error is 64.84% near / 58.49% farther from gates for CPU, and 65.22% / 74.49% for memory. The tolerance is descriptive, not a new threshold or exclusion. Large numeric errors and far-boundary errors persist. No classifier/threshold behavior was changed.
4. **Gaps reduce availability but do not explain the general failure.** Of 9,021 globally verifiable observed-or-clock opportunities, 8,942 are eligible observed predictor origins; the 79 excluded include missing origin observations and incomplete history. Six VMs lose origins. Five VMs lose 672 bootstrap target rows per resource, retaining 46,265 valid training rows per resource. Only 3/144 sampled forward windows contain missing actual targets. RF p95 MAE on fully observed windows is still 2.620 CPU / 3.631 memory (141 origins each). Those three gappy windows have higher error, but the subgroup is too small/confounded for a causal gap-effect claim.
5. **Distribution shift and bootstrap support affect particular VMs.** Trace2/11 has 88.28% of streaming CPU values outside its bootstrap min/max and a large downward mean shift; a frozen RF cannot extrapolate below training target support. Yet across VMs the median outside-range fraction is only 0.025% CPU / 0.031% memory, so this cannot be asserted as the universal cause. Per-VM data are retained; no model updating was introduced.
6. **Substantial VM variability rules out a single universal attribution.** Step288 per-VM RF MAE ranges 0.0154–15.3732 CPU and 0.0858–16.1471 memory. CPU RF p95 MAE ranges 0.0096–13.1090 across VM means; memory 0.0881–14.7145. Median forecast/actual within-horizon standard-deviation ratio is 0.833 CPU / 0.491 memory. This supports memory variation compression on median, but RF p95 bias has both signs; do not describe every VM as simple underprediction or variance collapse. Numeric positive long-lead bias and tail/mean-class mismatch both matter.

## Recommendation before V2.5

**Recommend a separately authorized predictor-design investigation before freezing confirmation.** The current recursive RF is not yet a convincing predictor-grounded profile-content baseline. Preserve this diagnosis and the existing model unchanged. A future design study should predefine diagnostic criteria, compare simple controls seriously, inspect target/feature alignment and recursive stability, and evaluate full profile mean/p95 behavior without selecting a method solely for favorable development effects. Any redesign requires regression tests, clean managed re-execution and explicit review before V2.5. No new model, shortened horizon, RF/ADWIN tuning or policy change was implemented here.

Causality tests and first-step equality establish interface/temporal consistency, not that the current predictor is scientifically adequate. Eight evenly spaced origins cannot fully decompose predictor architecture, training-distribution shift, horizon difficulty and threshold artifacts; conclusions are evidence-ranked hypotheses, not a confirmatory causal decomposition.
