# V2.4C — Task-Aligned Profile Prediction

Status: PASS — completed investigation; seasonal/PW reference preferred, no learned integration. Development-only. `causal-timeline-v3`, `phase-balanced-hourly-v1`, `refresh-accounting-v1`, ADWIN and policy parameters remain unchanged. No production integration.

## Exact required fields

`DynamicFields` contains exactly `cpu_class`, `memory_class`, `predicted_cpu_p95_next_24h`, `predicted_mem_p95_next_24h`. Each class is `classify_value(mean, frozen_bootstrap_thresholds)`, never classification of p95. Thus each resource needs two scalar future quantities: arithmetic mean and empirical p95. The mean is an intermediate value, not another stored profile field. Provisioned resources/static identity, last-update metadata and version are not forecast targets.

`core/forecasting.py` and `_BasePolicyV2._forecast_values` aggregate all forecast values available at refresh time. Canonical ground truth uses paired finite actual samples on exactly `(t,t+24h]` with at least 200/288 slots and a fully elapsed horizon. Missing observations are not filled. Mean classes use bootstrap p20/p40/p60/p80 gates; p95 remains numerical.

## Predefined candidates and labels

- Current recursive RF -> mean/p95/class.
- Joint direct288-output RF -> mean/p95/class.
- Persistence -> mean/p95/class.
- Exact 24h seasonal-naive -> mean/p95/class where enough source history exists.
- **Direct-profile RF:** one two-output regression ensemble per VM/resource predicting future mean and p95; 200 trees, depth20, sqrt features, seed42, one thread, unchanged settings.
- **Direct-profile Ridge:** standardized causal features plus fixed Ridge alpha1.0; no parameter sweep, target transform, clipping, class classifier or calibration.

Learned inputs are the current exact-grid first-target feature row constructed from observations <=origin, with complete 96-slot history. Direct labels require the full 24h clock horizon to lie inside bootstrap; label samples use the same paired-finite >=200/288 rule as canonical truth. Training allows a missing first future sample if sufficient later samples exist. The origin is excluded from all labels. There is no label from streaming or confirmation. Categorical output always derives from predicted mean through the current classifier.

No invented physical constraints are imposed: Ridge may predict negative mean/p95; such predictions are retained, counted and reported rather than clipped, removed or relabelled as unavailable.

## Fixed comparison and origin-time construction

Use the same 18 development VMs and same eight origins per VM from validated V2.4B. All candidates compare against identical canonical ground truth, thresholds and origins. Evaluate task-aligned class correctness, p95 MAE/bias, auxiliary mean error, per-VM wins/losses/ties and volatility tiers. Do not optimize on final policy accuracy or run policies.

An important diagnostic correction: earlier point-design profile summaries aggregated forecasts on the actual observed future target mask for matched point comparisons. That is not an origin-time profile construction rule. This study aggregates **all predictions available at the origin**, without consulting which targets will later be observed. Ground truth separately uses actual paired observations. Differences from old profile summary cells at gappy origins are expected, not production behavior changes. No old result is edited.

The four point strategies are reused only from the valid managed V2.4B raw forecasts. Their producer source paths must remain unchanged, scientific environment must match, and config pins parent fingerprint/run ID/output-manifest SHA and raw-forecast SHA. This is explicit managed input lineage, not stale cache reuse or relabelling old output as newly computed. Old profile metrics are not reused. New direct-profile models fit once per VM/resource and reuse each fit at all eight origins.

## Predefined decision and limits

A direct-profile recommendation must survive comparison against seasonal-naive on **both** class correctness and p95 MAE for both CPU and memory, with a strict majority of per-VM p95-error wins in both resources, finite/physically admissible outputs and practical state/cost. No post-hoc CPU/memory hybrid, tier selector, RF/Ridge tuning or endpoint weighting may manufacture a winner. Mixed tradeoffs yield no adequate universal design. This development screen is not a confirmatory practical-benefit margin. Point-forecast MAE is not the selection target here.

## Timestamp-only seasonal availability

Audit all 1,576 retained VMs, reading only Timestamp columns and the existing >=2,000-observation retention rule. Denominator: observed streaming timestamps whose exact preceding 96-slot history, including origin, is present. Report two numerators: complete288/288 seasonal source slots in `(t-24h,t]`, and density-compatible >=200/288 slots for profile-only aggregation. These differ and are never silently substituted. The audit uses no utilization values, model outputs, future classes or confirmatory performance. Timestamp eligibility is an upper bound on eligibility requiring finite resource values. No final cohort/exclusion rule changes.

## Cost and provenance

New RF/Ridge training/inference times and learned numeric state bytes are recorded. State bytes are a lower bound, not peak RSS. Baseline forecast costs/state are explicitly copied as managed parent evidence; current baseline timings measure artifact lookup/profile aggregation only and must not be represented as full forecasting latency. Separate generations are not a controlled timing benchmark. Parent/new environment identities are checked. All outputs remain ignored under managed pilot runs with config/data/cohort/source/environment/output hashes and SUCCESS only after validation. Clean committed source is mandatory.

Required outputs: profile predictions/canonical truth; bootstrap label-boundary/density audit; new costs; explicit parent costs; timestamp-only availability; per-VM and per-tier metrics; summary. V2.5/V3 remain blocked pending review, predictor disposition and any separately authorized integration work.

## Superseded execution (metadata correction)

Source `d36dbc6050bcab142eef0c00fdc022d1d5b64c02`, fingerprint `c172a29d0e79f4b3a20bebe0700d6734ef2ab0237027376f399934f13ce3ad53`, run `2026-10-22T065806.069700Z-c172a29d0e79-6e0afb11` completed and passed numerical/provenance checks. Final review found that its `available_source_slots=288` metadata incorrectly described direct scalar models. It is superseded and must not be treated as the current study generation. Original bytes and SUCCESS remain untouched. Study-v2 separates nullable `point_forecast_slots_available` from `profile_feature_history_slots=96` for scalar models; no scientific/model/policy parameter changed. All direct models are refitted and the complete bounded study/audit rerun from new clean source; no result is manually upgraded. A regression covers the distinction.

Seasonal-naive scalar profiles equal trailing-window PW refresh content because `(t,t+24h] -24h = (t-24h,t]`, and mean/p95/class ignore temporal ordering. This identity is verified synthetically with a gap and on every one of the 288 resource/origin cases from the superseded numerical run. The current generation will be checked independently again. This does not establish equivalence of policy initialization, refresh timing or aged snapshot outcomes.

## Verified current generation — 2026-10-22

**V2.4C PASS: completed investigation. Disposition B: seasonal-naive/trailing-window profile content is the strongest tested reference. No learned replacement is recommended for production integration. V2.5/V3 remain blocked pending review and predictor/claim disposition.**

- Source commit: `d579c46be0691e72db87814fbd86f636b05e7d3b`; clean source at execution.
- Study schema: `direct-profile-mean-p95-v2`; causal protocol/evaluation/accounting unchanged.
- Experiment fingerprint: `807040bbf43c5f0547da249e9e64999a0e2f988b484f52058135da79d4db5b3f`.
- Run ID: `2026-10-22T071114.218486Z-807040bbf43c-322dd54d`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Output-manifest SHA-256: `0ad850620b246ae0f84916d92e2419558496cd1ea8a2b1f94bcc900300dbd997`.
- Location: ignored `results/runs/807040bbf43c5f0547da249e9e64999a0e2f988b484f52058135da79d4db5b3f/2026-10-22T071114.218486Z-807040bbf43c-322dd54d/`.
- Purpose pilot, not claim. Runtime 96.78s; two VM workers. No policy replay, parameter/model tuning, confirmation inference, archive access or post-hoc resource hybrid.
- 18/18 development VMs completed, same eight fixed origins each;144 VM/origin pairs; 1,728 method/resource/origin rows; 72 new model fits and bootstrap-label audit rows; 1,576 timestamp-only audit rows.
- RF/Ridge each fit once per VM/resource; median 2,197 training rows (range 1,537–2,727), label coverage 200–288 paired slots, and every full label horizon ends no later than the last bootstrap observation. No label crosses into streaming.
- All candidates share exactly the same origins, bootstrap thresholds and canonical ground truth. Point baselines have 288 available forecasts at every selected origin. Scalar models have no point-forecast slots (null metadata) and require 96 feature-history slots. All emitted scalar predictions are finite; four negative Ridge memory-p95 values are explicitly retained and counted as physical inadmissibility.
- Parent V2.4B raw forecasts were validated and reused with pinned lineage, matching scientific environment and unchanged producer paths. Its original profile metrics were not reused. The current generation recomputes profiles from all origin-available predictions and never selects profile inputs using future missingness.
- Independent checks PASS: canonical raw truth/classes, exact 24h targets, all parent aggregation values, bootstrap boundaries, corrected availability schema, byte-identical parent costs and output hashes; altered config, claim requests, tampered disposable copies and superseded generation caches rejected. New refits reproduce the superseded numerical profile predictions within 1e-10; no output was edited.

## Candidate results

All values are descriptive development results: equally weighted per-VM means over eight origins. p95 MAE is error in the **future profile's p95 value**, not the p95 of pointwise errors. Bias is predicted minus actual. Units are utilization percentage points. Mean MAE concerns the scalar used to derive class; class correctness is not pointwise class accuracy or an aged policy-snapshot score.

| Resource | Candidate | Class correct | p95 MAE | p95 bias | Mean MAE | Mean bias |
|---|---|---:|---:|---:|---:|---:|
| cpu | rf_recursive | 37.50% | 2.6680 | +0.6348 | 2.1442 | +2.0352 |
| cpu | rf_direct_joint | 47.22% | 1.4248 | -0.6330 | 0.4740 | +0.0699 |
| cpu | persistence | 34.03% | 2.7899 | -2.7819 | 0.7007 | -0.4013 |
| cpu | seasonal_naive_24h | 75.00% | 0.4547 | -0.2438 | 0.1836 | -0.0845 |
| cpu | rf_profile | 50.69% | 0.9963 | +0.1240 | 0.4836 | +0.0335 |
| cpu | ridge_profile | 55.56% | 1.7724 | +0.9434 | 0.4145 | +0.1503 |
| memory | rf_recursive | 28.47% | 3.7061 | +0.9216 | 3.1075 | +2.5494 |
| memory | rf_direct_joint | 63.89% | 2.0753 | -1.9068 | 0.5535 | -0.1120 |
| memory | persistence | 24.31% | 4.6438 | -4.5181 | 2.2644 | -0.8423 |
| memory | seasonal_naive_24h | 77.78% | 0.6390 | -0.2405 | 0.4500 | -0.0814 |
| memory | rf_profile | 61.11% | 0.8873 | -0.1493 | 0.5473 | -0.1567 |
| memory | ridge_profile | 61.81% | 0.9164 | -0.1767 | 0.6139 | -0.1465 |

Direct-profile RF improves p95 error over recursive RF and the 288-output RF on both resources. Its class result is mixed versus 288-output RF (CPU improves 47.22%->50.69%; memory falls 63.89%->61.11%). The change combines task-aligned scalar loss, much smaller output state, and somewhat more valid training support (profile labels allow 200 slots, joint 288-output labels require complete horizons). This is not an isolated proof that changing output dimensionality alone causes the benefit.

Seasonal/PW content remains best on both aggregate primary quantities for both resources. Neither learned profile model passes the predefined seasonal comparison. Ridge has four negative memory-p95 forecasts (4/144, 2.78%, all Trace2/398; approximately -0.0023 to -0.0360pp). None were clipped or excluded. No predictions exceeded 100.

## Per-VM and volatility robustness

Wins/losses/ties are paired per-VM comparisons versus seasonal-naive. p95 wins mean lower MAE; class wins mean higher correctness. Tolerance 1e-12 defines numerical ties only, not a practical-benefit threshold.

| Resource | Candidate | p95 wins/losses/ties | Class wins/losses/ties |
|---|---|---:|---:|
| cpu | rf_recursive | 0/18/0 | 1/13/4 |
| cpu | rf_direct_joint | 1/17/0 | 3/12/3 |
| cpu | persistence | 1/17/0 | 1/15/2 |
| cpu | rf_profile | 2/15/1 | 2/11/5 |
| cpu | ridge_profile | 3/14/1 | 3/11/4 |
| memory | rf_recursive | 1/17/0 | 1/13/4 |
| memory | rf_direct_joint | 1/17/0 | 4/10/4 |
| memory | persistence | 1/17/0 | 0/17/1 |
| memory | rf_profile | 6/12/0 | 3/10/5 |
| memory | ridge_profile | 7/11/0 | 4/13/1 |

Tiers are the frozen bootstrap **CPU-volatility** tiers, used unchanged for both resources, six VMs per tier. They are not memory-specific tiers. Complete six-candidate tier data are in `tier_metrics.parquet`; focused comparisons follow. No significance inference.

| Resource | Tier | Candidate | Class correct | p95 MAE |
|---|---|---|---:|---:|
| cpu | low | seasonal_naive_24h | 81.25% | 0.0254 |
| cpu | low | rf_profile | 62.50% | 0.0473 |
| cpu | low | ridge_profile | 54.17% | 0.0509 |
| cpu | medium | seasonal_naive_24h | 79.17% | 0.4090 |
| cpu | medium | rf_profile | 52.08% | 0.5536 |
| cpu | medium | ridge_profile | 68.75% | 0.4565 |
| cpu | high | seasonal_naive_24h | 64.58% | 0.9298 |
| cpu | high | rf_profile | 37.50% | 2.3880 |
| cpu | high | ridge_profile | 43.75% | 4.8097 |
| memory | low | seasonal_naive_24h | 81.25% | 0.3726 |
| memory | low | rf_profile | 56.25% | 0.2877 |
| memory | low | ridge_profile | 58.33% | 0.4250 |
| memory | medium | seasonal_naive_24h | 85.42% | 0.6201 |
| memory | medium | rf_profile | 66.67% | 0.8317 |
| memory | medium | ridge_profile | 60.42% | 0.8007 |
| memory | high | seasonal_naive_24h | 66.67% | 0.9242 |
| memory | high | rf_profile | 60.42% | 1.5424 |
| memory | high | ridge_profile | 66.67% | 1.5236 |

Seasonal/PW wins both aggregate metrics in every CPU tier. Direct-profile RF has lower p95 error in low-tier memory (0.288 vs seasonal 0.373) but much lower class correctness (56.25% vs 81.25%); seasonal has lower p95 error in medium/high memory. Ridge ties seasonal high-tier memory class correctness but loses p95 error. These tradeoffs do not justify selecting models by tier or resource after observing outcomes.

## Seasonal availability — timestamp audit only

Denominator is 9,728,006 timestamp-eligible predictor origins among 9,791,587 observed streaming timestamps. Every one of 1,576 retained VMs was audited using Timestamp columns only.

| Source-history condition | Eligible origins | Fraction of predictor-eligible origins |
|---|---:|---:|
| Complete288/288 | 9,602,349 | 98.708296% |
| At least200/288, profile-density rule | 9,707,935 | 99.793678% |
| Incomplete but at least 200 | 105,586 | 1.085382% |
| Below200/288 | 20,071 | 0.206322% |

Strict completeness fails at some otherwise eligible origins in **526 VMs**; the 200-slot criterion fails in **183 VMs**. No utilization values, future labels or confirmatory model outcomes were inspected for this audit. These are timestamp-presence rates, an upper bound on finite-value eligibility. No new exclusion rule is applied.

The distinction matters: predicting a complete 288-point seasonal trajectory needs 288 source observations; constructing only scalar profiles can use the same >=200 coverage principle as existing window policies. Existing V3 drift eligibility requires only 96 history slots, so seasonal/profile source eligibility cannot silently be assumed at every drift signal. Handling unavailable source windows, pending/consumed signals, shared periodic comparison eligibility, initialization and the residual-model contract require separate review. No fallback or detector change was implemented.

## Seasonal/PW identity and scientific interpretation

For exact five-minute slots, `forecast_targets(t)-24h == trailing_targets(t,288)`. Seasonal-naive copies the same multiset of actual values used by the trailing 24h observation window. Aggregation order does not affect mean or empirical p95; applying the same frozen gates also produces identical classes. Missing source values remain missing on either side. Therefore **seasonal-naive -> scalar profile equals PW refresh content at the same origin/window**. This is a mathematical identity, checked with a synthetic gap regression and independently on all 288 resource/origin cases in the current run.

This does not make complete policies equivalent: refresh decisions, initialization, delayed eligibility, drift timing and aged snapshot reads can differ. It does mean that seasonal's strong scalar scores cannot be presented as learned prediction or evidence of predictor-grounded content outperforming PW. The earlier actual-future-mask diagnostic convention could obscure this identity around gaps; current origin-time construction makes it explicit.

## Cost/state observations

New timings include history lookup, feature construction, inference and class derivation. Same generation/hardware, two VM processes. Baseline costs are separately labelled parent-generation evidence; current baseline aggregation/lookup costs exclude forecast generation. Do not compare them as full end-to-end inference. One bounded run is not a warm-up/repeated-trial deployment overhead benchmark and does not pass V5.

| Resource | Direct model | Mean training s | Median profile inference ms | p95 inference ms | Median learned state lower bound |
|---|---|---:|---:|---:|---:|
| cpu | rf_profile | 1.316 | 9.743 | 13.264 | 37.20 MiB |
| cpu | ridge_profile | 0.105 | 1.725 | 2.600 | 1.50 KiB |
| memory | rf_profile | 1.422 | 9.638 | 13.748 | 40.23 MiB |
| memory | ridge_profile | 0.104 | 1.686 | 2.581 | 1.50 KiB |

Direct-profile RF state is about 37/40 MiB CPU/memory, versus parent joint 288-output RF about 1046/948 MiB. Ridge's scaler/coefficient/intercept arrays total 1,536 bytes per resource. These exclude Python overhead/peak RSS and are not serialized deployment sizes. Seasonal/persistence have no trained model; seasonal needs observed source-window state. All baseline training/inference/tree arrays remain recorded in byte-identical `parent_costs.parquet` with pinned parent provenance; they were not refitted or retimed as new costs.

## Recommendation and remaining gates

**Evidence supports B as the preferred tested profile-content reference; it does not support A as a superior learned replacement.** At these quantities B is existing trailing-window content, not a distinct predictive contribution. Direct-profile RF is a far more efficient and task-aligned learned candidate than 288-output RF, but still loses the seasonal/PW comparison. Ridge is cheap but not accurate/physically robust enough without a separately justified new design.

**No learned production predictor integration should follow this task.** There is no new seasonal profile-content algorithm to claim: PW already provides this content at matching refresh origins. A separate review must decide whether the research should study adaptive timing with window content, pursue another predeclared learned predictor, or narrow the intended claims. Any eventual integration must freeze availability/initialization/residual contracts and revalidate all policies; no CPU/memory hybrid, alpha/tree tuning, clipping or schedule change is introduced here. V2.5/V3 remain blocked until that disposition is reviewed. Eighteen development VMs/eight origins are not confirmatory evidence or generalization validation.

## Verification and files

**274 passed, 0 failed, 0 skipped**. Nine added tests cover canonical sparse labels, first-target missingness, exact-grid history, bootstrap/full-horizon boundaries, RF/Ridge future-data invariance, class derivation, timestamp availability, seasonal/PW identity and scalar-versus-point availability metadata. Parse/compile/import/CLI/document checks pass. No production core/policy change. The superseded metadata generation was preserved unchanged; the complete study was rerun, not manually upgraded. Model scores reproduce; timings belong to the current generation.

Current `outputs/`: `profile_predictions.parquet`, `training_labels_audit.parquet`, `costs.parquet`, `parent_costs.parquet`, `seasonal_availability.parquet`, `vm_metrics.parquet`, `tier_metrics.parquet`, `summary.json`, plus standard managed manifests/SUCCESS. Generated results remain ignored/uncommitted. V2.4C PASS is investigation completion, not authorization for production integration, confirmatory execution or manuscript claims.
