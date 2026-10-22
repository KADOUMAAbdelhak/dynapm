# V2.4C — Task-Aligned Profile Prediction

Status: implementation / managed execution pending. Development-only. `causal-timeline-v3`, `phase-balanced-hourly-v1`, `refresh-accounting-v1`, ADWIN and policy parameters remain unchanged. No production integration.

## Exact required fields

`DynamicFields` contains exactly `cpu_class`, `memory_class`, `predicted_cpu_p95_next_24h`, `predicted_mem_p95_next_24h`. Each class is `classify_value(mean, frozen_bootstrap_thresholds)`, never classification of p95. Thus each resource needs two scalar future quantities: arithmetic mean and empirical p95. The mean is an intermediate value, not another stored profile field. Provisioned resources/static identity, last-update metadata and version are not forecast targets.

`core/forecasting.py` and `_BasePolicyV2._forecast_values` aggregate all forecast values available at refresh time. Canonical ground truth uses paired finite actual samples on exactly `(t,t+24h]` with at least200/288 slots and a fully elapsed horizon. Missing observations are not filled. Mean classes use bootstrap p20/p40/p60/p80 gates; p95 remains numerical.

## Predefined candidates and labels

- Current recursive RF -> mean/p95/class.
- Joint direct288-output RF -> mean/p95/class.
- Persistence -> mean/p95/class.
- Exact 24h seasonal-naive -> mean/p95/class where enough source history exists.
- **Direct-profile RF:** one two-output regression ensemble per VM/resource predicting future mean and p95; 200 trees, depth20, sqrt features, seed42, one thread, unchanged settings.
- **Direct-profile Ridge:** standardized causal features plus fixed Ridge alpha1.0; no parameter sweep, target transform, clipping, class classifier or calibration.

Learned inputs are the current exact-grid first-target feature row constructed from observations <=origin, with complete96-slot history. Direct labels require the full 24h clock horizon to lie inside bootstrap; label samples use the same paired-finite >=200/288 rule as canonical truth. Training allows a missing first future sample if sufficient later samples exist. The origin is excluded from all labels. There is no label from streaming or confirmation. Categorical output always derives from predicted mean through the current classifier.

No invented physical constraints are imposed: Ridge may predict negative mean/p95; such predictions are retained, counted and reported rather than clipped, removed or relabelled as unavailable.

## Fixed comparison and origin-time construction

Use the same18 development VMs and same eight origins per VM from validated V2.4B. All candidates compare against identical canonical ground truth, thresholds and origins. Evaluate task-aligned class correctness, p95 MAE/bias, auxiliary mean error, per-VM wins/losses/ties and volatility tiers. Do not optimize on final policy accuracy or run policies.

An important diagnostic correction: earlier point-design profile summaries aggregated forecasts on the actual observed future target mask for matched point comparisons. That is not an origin-time profile construction rule. This study aggregates **all predictions available at the origin**, without consulting which targets will later be observed. Ground truth separately uses actual paired observations. Differences from old profile summary cells at gappy origins are expected, not production behavior changes. No old result is edited.

The four point strategies are reused only from the valid managed V2.4B raw forecasts. Their producer source paths must remain unchanged, scientific environment must match, and config pins parent fingerprint/run ID/output-manifest SHA and raw-forecast SHA. This is explicit managed input lineage, not stale cache reuse or relabelling old output as newly computed. Old profile metrics are not reused. New direct-profile models fit once per VM/resource and reuse each fit at all eight origins.

## Predefined decision and limits

A direct-profile recommendation must survive comparison against seasonal-naive on **both** class correctness and p95 MAE for both CPU and memory, with a strict majority of per-VM p95-error wins in both resources, finite/physically admissible outputs and practical state/cost. No post-hoc CPU/memory hybrid, tier selector, RF/Ridge tuning or endpoint weighting may manufacture a winner. Mixed tradeoffs yield no adequate universal design. This development screen is not a confirmatory practical-benefit margin. Point-forecast MAE is not the selection target here.

## Timestamp-only seasonal availability

Audit all1,576 retained VMs, reading only Timestamp columns and the existing >=2,000-observation retention rule. Denominator: observed streaming timestamps whose exact preceding96-slot history, including origin, is present. Report two numerators: complete288/288 seasonal source slots in `(t-24h,t]`, and density-compatible >=200/288 slots for profile-only aggregation. These differ and are never silently substituted. The audit uses no utilization values, model outputs, future classes or confirmatory performance. Timestamp eligibility is an upper bound on eligibility requiring finite resource values. No final cohort/exclusion rule changes.

## Cost and provenance

New RF/Ridge training/inference times and learned numeric state bytes are recorded. State bytes are a lower bound, not peak RSS. Baseline forecast costs/state are explicitly copied as managed parent evidence; current baseline timings measure artifact lookup/profile aggregation only and must not be represented as full forecasting latency. Separate generations are not a controlled timing benchmark. Parent/new environment identities are checked. All outputs remain ignored under managed pilot runs with config/data/cohort/source/environment/output hashes and SUCCESS only after validation. Clean committed source is mandatory.

Required outputs: profile predictions/canonical truth; bootstrap label-boundary/density audit; new costs; explicit parent costs; timestamp-only availability; per-VM and per-tier metrics; summary. V2.5/V3 remain blocked pending review, predictor disposition and any separately authorized integration work.

## Superseded execution (metadata correction)

Source `d36dbc6050bcab142eef0c00fdc022d1d5b64c02`, fingerprint `c172a29d0e79f4b3a20bebe0700d6734ef2ab0237027376f399934f13ce3ad53`, run `2026-10-22T065806.069700Z-c172a29d0e79-6e0afb11` completed and passed numerical/provenance checks. Final review found that its `available_source_slots=288` metadata incorrectly described direct scalar models. It is superseded and must not be treated as the current study generation. Original bytes and SUCCESS remain untouched. Study-v2 separates nullable `point_forecast_slots_available` from `profile_feature_history_slots=96` for scalar models; no scientific/model/policy parameter changed. All direct models are refitted and the complete bounded study/audit rerun from new clean source; no result is manually upgraded. A regression covers the distinction.

Seasonal-naive scalar profiles equal trailing-window PW refresh content because `(t,t+24h] -24h = (t-24h,t]`, and mean/p95/class ignore temporal ordering. This identity is verified synthetically with a gap and on every one of the 288 resource/origin cases from the superseded numerical run. The current generation will be checked independently again. This does not establish equivalence of policy initialization, refresh timing or aged snapshot outcomes.
