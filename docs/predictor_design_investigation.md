# V2.4B — Predictor Design Investigation

Status: PASS — completed investigation; no universal replacement selected. Development-only, not confirmation. Protocol remains `causal-timeline-v3`, evaluation `phase-balanced-hourly-v1`, accounting `refresh-accounting-v1`.

## Architecture audit and hypothesis

Production `VMPredictor` fits a one-step target-specific RF on bootstrap-only actual-history features. `predict_causal_horizon` repeatedly appends each predicted value, reconstructing all 96-slot causal rolling/lag/difference features, and predicts again. Calendar features remain deterministic. No future observation is read. CPU and memory models are independent.

This is temporally correct but creates a training/inference mismatch: every training feature uses actual utilization history, whereas recursive features increasingly contain model output. Trees return averages of observed training targets; rare spikes influence those averages, and altered rolling means/extrema/variance can lead subsequent predictions into different leaves. There is no stability or unbiasedness guarantee when this mapping is iterated 288 times. Frozen training support also prevents extrapolation to new regimes. Positive bias and reduced variation in V2.4 are evidence of this mechanism, not proof that every VM follows the same dynamics. We test removal of feedback, rather than assuming leakage or changing policy parameters.

## Predefined candidates — no search

1. Current RF recursion: 200 trees, depth20, sqrt features, seed42, one model thread; unchanged source.
2. Persistence: latest actual observation repeated for 288 slots.
3. Seasonal-naive 24h: exact actual value 288 nominal slots before each target, when available. Missing history remains unavailable; no fill or silent fallback.
4. Joint direct multi-output RF: same 200/depth20/sqrt/42 settings and first-target features, one tree ensemble per VM/resource with a 288-value response vector. Each output is predicted directly from the origin feature state, without feeding any prediction back. Shared splits capture cross-output dependence but do not guarantee a smooth path. No additional model family is justified in this bounded comparison.

Direct training uses complete exact-grid input history and all 288 finite labels within bootstrap. No training target crosses the bootstrap boundary; no gap bridging. Fewer direct training rows than one-step RF are expected and recorded; this is a deployment/data-cost property, not an invitation to use streaming labels. No training or inference on confirmatory entities. The investigation module is separate from production predictor/policy classes.

## Frozen execution and evaluation

Use the same 18 permanent development VMs and the same eight origins per VM as the provenance-validated V2.4 diagnosis. No new origin selection based on accuracy. Models fit once per resource/VM, then reuse their fit at all eight origins. All methods emit the same nominal `(t,t+24h]` target index; comparisons use identical observed finite target slots available to all four methods. Record incomplete seasonal forecasts explicitly. All 288 leads are retained, with selected summaries at 1/12/72/144/288.

Primary diagnostic endpoints are direct forecast MAE, signed bias, p95 of absolute point error, pointwise class correctness under frozen bootstrap thresholds, full error-vs-lead curves and per-VM heterogeneity. Mean-class/profile-p95 errors are supplementary diagnostics, not final profile-policy accuracy and not the selection target. Track adjacent predicted jumps relative to observed jumps as a descriptive consistency measure; smoothness alone is not forecast quality. No confirmatory tests or significance claims.

A new learned design cannot be recommended just for beating recursion: before seeing this run, require lower macro-VM full-horizon MAE than seasonal-naive for both CPU and memory, a strict majority of VM MAE wins in both resources, no worse absolute aggregate bias, causal/finite complete horizons and feasible costs. This is an exploratory design-screening rule, not a confirmatory practical-effect threshold. If it fails, do not tune/retry candidates to force a winner. A seasonal recommendation must also acknowledge required exact 24h source-history availability and unresolved deployment recovery behavior.

## Cost and provenance

Record bootstrap training time, each 288-target inference time, training-row count and tree node/value array bytes (a lower bound on model memory, not process peak RSS). Same machine/environment, at most two VM processes, one model thread each, no cross-run timing comparisons. Single measurements have no warm-up/repeat-controlled service benchmark claim. Simple controls need no fitting. All outputs are managed pilot-purpose artifacts under ignored `results/runs/`, with source/config/data/cohort/environment identities and hashed completion. Start only from a clean committed tree.

Machine-readable outputs: all forecast values/errors, per-origin metrics, per-VM metrics, all-lead curves, per-model/per-origin costs and summary JSON. The earlier diagnosis supplies only verified cohort/origin metadata, not forecasts reused as current output. Existing fitted models were not persisted; unchanged recursive RF models are refitted once per VM/resource.

## Gates

V2.4B must complete and be reviewed before V2.5. V2.5 and V3 remain blocked. No production integration occurs in this task, even if one candidate meets the screening rule. Integration, history-availability behavior, causal residual interfaces and policy revalidation require a separate task. No archive inputs, confirmatory outcomes, parameter tuning or model search are authorized.

## Completed investigation — 2026-10-22

**V2.4B PASS: investigation complete, with no single adequate two-resource replacement selected. Production integration is not recommended yet. V2.5/V3 remain blocked.** This is an exploratory negative/mixed finding, not evidence that forecasting is impossible.

- Source: `ff7388ab3ec122d3f528e45216adc5882cacbc13` (clean committed tree).
- Experiment fingerprint: `62f5727e20e29e0d0cbb620b9391c6d2909dd978549120dddd09bd7b3e470948`.
- Run ID: `2026-10-22T004212.427895Z-62f5727e20e2-905e675d`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f` (same 18 development entities).
- Output-manifest SHA-256: `c55b505bf87a0a3ba27520cbc2e00b955a9a8ebcb904140e907956f9ea50c21c`.
- Ignored run location: `results/runs/62f5727e20e29e0d0cbb620b9391c6d2909dd978549120dddd09bd7b3e470948/2026-10-22T004212.427895Z-62f5727e20e2-905e675d/`.
- Purpose pilot, never claim. Wall time 316.73s with two VM workers. No tuning, model search, policy replay, confirmatory inference or historical archive inputs. Existing full input-manifest bytes were rehashed for provenance; no confirmatory entity outcomes were evaluated.
- 18/18 VM executions; 144 VM/origin pairs; 288 resource/origin cases; 1,152 method/resource/origin comparisons; 331,776 forecast rows; 2,304 all-lead curve rows. All methods forecast all 288 slots at these selected origins, including seasonal-naive. Actual missing target slots are excluded through one common mask per origin/resource, giving identical targets for every method. Leads 1/12/72/144 have 144 actual pairs per resource; lead288 has 143.
- 36 unchanged one-step RF fits and 36 joint direct RF fits; each reused across all eight origins. Median valid training rows: recursive 2,483, direct 2,122. Complete direct labels legitimately reduce training support; no labels cross bootstrap.
- Independent reconciliation passed: target cadence, original eight origins, exact raw actual/persistence/seasonal values, finite complete learned forecasts and deterministic reproduction of prior recursive predictions at every available previously recorded lead. Four-candidate aligned origin/target counts and all output hashes passed. Changed config, claim reuse and tampered disposable output copies were rejected; original outputs revalidate unchanged.

## Lead-wise forecast quality

MAE in utilization percentage points. Unweighted macro-VM means of per-VM origin means; all eighteen VMs represented. No p-values or confirmatory confidence intervals. All 288 leads and signed bias/class correctness are in `lead_curves.parquet`.

| Resource | Lead | Recursive RF MAE | Direct RF MAE | Persistence MAE | Seasonal-naive MAE |
|---|---:|---:|---:|---:|---:|
| cpu | 1 | 0.6485 | 0.8886 | 1.2612 | 0.6870 |
| cpu | 12 | 0.9550 | 0.6395 | 0.7199 | 0.4611 |
| cpu | 72 | 2.2612 | 0.5032 | 0.4128 | 0.3705 |
| cpu | 144 | 3.0047 | 0.9510 | 0.6217 | 0.3896 |
| cpu | 288 | 3.0869 | 0.9152 | 0.5779 | 0.5779 |
| memory | 1 | 1.3622 | 1.5159 | 1.6740 | 2.3322 |
| memory | 12 | 1.7262 | 1.7981 | 2.5526 | 2.1460 |
| memory | 72 | 3.5682 | 1.4093 | 2.2190 | 2.1049 |
| memory | 144 | 4.6551 | 1.7725 | 2.6408 | 1.6376 |
| memory | 288 | 4.5719 | 1.5673 | 1.9890 | 1.9890 |

## Full-horizon forecast quality

MAE/bias/p95 AE below average per-origin statistics within VM, then average VMs equally. **p95 AE is the 95th percentile of pointwise absolute forecast errors**, not error of the forecast's p95 statistic. Point-class correctness applies frozen bootstrap gates to each target, not policy snapshot accuracy. Auxiliary mean-class and profile-p95 errors are retained in machine-readable outputs but did not select a method.

| Resource | Method | MAE | Bias | p95 absolute error | Point-class correctness |
|---|---|---:|---:|---:|---:|
| cpu | persistence | 0.8328 | -0.4013 | 3.0200 | 41.82% |
| cpu | rf_direct_joint | 0.8270 | +0.0700 | 2.1658 | 32.75% |
| cpu | rf_recursive | 2.4503 | +2.0351 | 3.8446 | 33.40% |
| cpu | seasonal_naive_24h | 0.4897 | -0.0844 | 1.5554 | 59.62% |
| memory | persistence | 2.8089 | -0.8423 | 6.2396 | 29.63% |
| memory | rf_direct_joint | 1.7196 | -0.1120 | 4.4888 | 30.35% |
| memory | rf_recursive | 3.9954 | +2.5491 | 6.8737 | 28.10% |
| memory | seasonal_naive_24h | 2.0076 | -0.0812 | 5.2872 | 35.56% |

## Robustness and error mechanisms

- **Recursive accumulation:** late-lead CPU bias grows to +2.581 and memory +3.236 at step288; direct RF has -0.273 / -0.088 at that lead. Full-horizon bias falls from +2.035/+2.549 recursively to +0.070/-0.112 directly. Direct RF beats recursion on 16/18 VMs in each resource. This strongly supports feedback-distribution mismatch as a practical weakness. Direct training also changes objective and row support, so this is not a perfect isolated causal ablation of feedback alone.
- **CPU versus memory:** direct RF improves aggregate memory MAE versus seasonal (1.720 vs2.008) and wins 14/18 VMs, but loses CPU (0.827 vs0.490) and wins only 4/18. Its memory absolute aggregate bias is slightly worse than seasonal (0.112 vs0.081). It fails the predefined two-resource screening rule, even though it is much better than recursion. No rule was relaxed after seeing results.
- **Cross-horizon consistency:** direct RF's lead errors remain relatively flat instead of blowing up with lead, but its first-step MAE is worse than recursive RF. Joint outputs share tree partitions and avoid feedback; this does not guarantee low level error or preserve variability. Mean adjacent predicted jumps are CPU 0.250 / memory 0.463, versus observed 0.542/1.555; recursion 0.133/0.378; seasonal 0.500/1.546. Direct paths remain substantially smoother than real telemetry, especially memory. Smoothness is not a success criterion by itself.
- **Threshold sensitivity:** direct RF can reduce numeric error without improving class correctness comparably. CPU point correctness remains 32.75%, versus seasonal 59.62%; memory 30.35% versus 35.56%. The frozen threshold behavior/degenerate gates identified in V2.4 remain unchanged. This is a forecast classification diagnostic, not a policy-selection objective.
- **Heterogeneity:** per-VM full-horizon direct MAE ranges 0.022–3.267 CPU /0.022–7.542 memory, versus seasonal 0.004–2.127 /0.024–10.871. Recursive ranges 0.015–12.254 /0.075–12.850. A favorable aggregate on one resource does not justify a universal method or per-VM selector.
- **Seasonality and gaps:** all selected eight-origin cases have complete seasonal source histories, but that does not establish availability at every live refresh or after telemetry gaps. No missing-history imputation/fallback was introduced. At lead288 seasonal equals persistence algebraically; its CPU advantage over intermediate leads and the whole horizon is more informative than this single endpoint.

Per-VM full-horizon MAE wins/losses/ties against seasonal-naive:

| Resource | Method | Wins | Losses | Ties |
|---|---|---:|---:|---:|
| cpu | persistence | 3 | 15 | 0 |
| cpu | rf_direct_joint | 4 | 14 | 0 |
| cpu | rf_recursive | 0 | 18 | 0 |
| cpu | seasonal_naive_24h | 0 | 0 | 18 |
| memory | persistence | 9 | 9 | 0 |
| memory | rf_direct_joint | 14 | 4 | 0 |
| memory | rf_recursive | 7 | 11 | 0 |
| memory | seasonal_naive_24h | 0 | 0 | 18 |

## Cost observations

Apple M3, arm64, eight logical/physical cores, 24 GiB RAM, two concurrent VM workers; package/hardware inventory in the managed environment manifest. No concurrent unit suite during this run. Same-environment descriptive timings, not controlled deployment/service benchmarks: no dedicated warm-up/repeated-trial study, no RSS/energy/SLA claim.

| Resource | Method | Mean training seconds | Median 288-target inference ms | p95 inference ms | Median tree arrays MiB |
|---|---|---:|---:|---:|---:|
| cpu | rf_recursive | 0.790 | 1143.141 | 1231.047 | 28.8 |
| cpu | rf_direct_joint | 6.408 | 5.058 | 5.458 | 1046.3 |
| cpu | persistence | none | 0.146 | 0.191 | no trees |
| cpu | seasonal_naive_24h | none | 0.201 | 0.247 | no trees |
| memory | rf_recursive | 0.894 | 1142.599 | 1244.246 | 33.1 |
| memory | rf_direct_joint | 6.810 | 5.166 | 5.696 | 948.4 |
| memory | persistence | none | 0.150 | 0.190 | no trees |
| memory | seasonal_naive_24h | none | 0.202 | 0.248 | no trees |

Direct RF reduces refresh-time inference by predicting a vector in one ensemble call instead of 288 calls, but requires roughly 1GiB tree arrays per resource, versus 29–33MiB for one-step RF. These are lower bounds on model state, not process RSS. Multi-output values exist at tree nodes, so retaining 200 full vector-output trees is costly. Reducing trees/depth, compression or horizon segmentation would be a new candidate study; none was tried. Controls need no model fitting, but seasonal requires a day of exact source observations.

## Recommendation and disposition

**No single candidate currently earns a robust deployable two-resource recommendation for confirmation. Do not integrate a replacement into production yet.** The recursive RF remains unsuitable as the sole strong predictor control; the direct RF fixes much of the instability and is promising for memory, but fails CPU comparisons against seasonal-naive and has substantial model-state cost. Seasonal-naive is the strongest low-cost CPU control and must remain an explicit comparator, but it is not the best memory forecaster here and its all-refresh missing-history/recovery contract has not been validated.

There is no declared winner and therefore no proposed production code replacement in this task. A future narrowly scoped investigation may assess target-specific design and storage-efficient nonrecursive prediction, but **an untested CPU-seasonal/memory-direct hybrid is not a candidate evaluated here**. Do not turn these outcomes into an automatic hybrid/VM selector, tune trees/ADWIN, shorten the horizon, or inspect confirmation. Any further candidate requires a predefined development-only plan, new provenance and separate integration validation. V2.5 must wait for review and explicit predictor disposition.

## Verification and artifacts

Full lightweight suite: **265 passed, 0 failed, 0 skipped**. Six new regression tests cover bootstrap-bounded labels, gap-safe support, insufficient support, first-target feature parity, complete 288-step cadence and direct future-data invariance. Existing tests cover recursive, persistence and seasonal causality. Production core/method files are unchanged. Parse/compile, import and safe CLI checks pass. No failed scientific attempts or manual output edits occurred.

Artifacts in `outputs/`: `forecasts.parquet`, `origin_metrics.parquet`, `vm_metrics.parquet`, `lead_curves.parquet`, `costs.parquet`, `summary.json`, plus standard manifests/SUCCESS. Generated outputs are ignored/uncommitted. The cohort/origins remain permanent development observations; none of this is independent confirmation. V2.4B PASS denotes investigation completion and an evidence-limited no-adequate-candidate conclusion, not forecasting readiness. V2.5/V3 remain blocked.
