# Google corpus/cohort protocol validation — V4C

Current status: **V4C.1 AVAILABILITY_CONTRACT_READY for cell e; V4C INCOMPLETE pending g and final two-cell freeze**. No replication authorization.
See the [versioned clock contract and current evidence](google2019_clock_contract.md).
The original unresolved-clock V4C audit below remains historical evidence; it is
superseded for current interpretation by the explicit v2 completed-slot contract.
The corrected v2 canonical generation is the sole data input. Raw and canonical
files are read-only; there are no cloud calls or policy outcomes.

## Fixed inputs and contract

- Protocol fingerprint: `4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226`.
- Corrected generation: `cell-e-unambiguous-v2-85c74588191efa0b`.
- Canonical dataset SHA: `06ec0ce8a599890bc98f5c2adb1bfb01c3858c83b6d0630a1f0a29335b77fdaf`.
- Only cell e exists locally. Cell g must be acquired and independently validated;
  the final two-cell cohort and V5 remain blocked.

`dynapm/experiments/google2019_protocol_validation.py` rejects legacy canonical
schemas, checks corrected output hashes and raw/part/job/ledger preservation,
requires clean committed source, and creates immutable, hashed local audit
outputs under `data/google2019/protocol_validation/`. Audit completion (`SUCCESS`)
is distinct from scientific protocol readiness.

## Literal frozen semantics being tested

The nominal cadence is 300s; missing/nonfinite paired samples remain missing.
No interpolation, clipping or denominator substitution is permitted. CPU/memory
are usage divided by their causally aligned positive requests.

The Google V4A adaptation explicitly defines the first 30% of **nominal time** as
bootstrap, whereas Materna's `compute_split` uses observed-row count. Google
therefore requires a corpus-specific split: with N nominal slots, bootstrap is
the first floor(0.30*N) slots, using only actual paired finite observations before
the cut. The hourly read anchor is the first observed streaming timestamp; reads
continue at anchor+k*1h without requiring an observation at each read.

Presence-only prefix counts test trailing `(t-24h,t]` and forward `(t,t+24h]`,
288 slots, >=200 paired finite observations, and a completely elapsed forward
horizon. PW's inherited 96-complete-slot gate is reported separately from 24h
coverage; this does not fit an RF or change a policy. Full-Rewrite eligibility
requires the 200-slot trailing window. Bootstrap requires >=96 paired samples;
there must be at least one eligible refresh and one globally verifiable read.
Only frozen validity codes exclude entities, never utilization magnitude,
volatility, profile fidelity, or expected effects.

Class gates are entity/resource bootstrap p20/p40/p60/p80; classes label the
window **mean**, with the existing strict/half-open boundaries. Profile p95 is
the linear empirical 0.95 quantile. Bootstrap p95 is also recorded. Synthetic
checks compare these definitions with the existing core helpers; actual streaming
profile/truth values, classes, errors and policy outputs are never computed.

Inherited initialization estimators remain explicit exceptions: Static uses the
whole bootstrap, PW uses its cadence-length trailing bootstrap window, and
Full-Rewrite its trailing 24h bootstrap window. Runtime density gates are not
silently imposed on these existing initialization estimators. The protocol and
frozen config are not edited in this task.

## Causal visibility check

The frozen canonical mapping labels average-usage windows by floor(start_time).
An average over [source_start_time, source_end_time) cannot be available before
source_end_time. A literal existing indexed replay exposes u_t at its label t;
if source_end_time>t it would expose a not-yet-complete aggregate. The frozen
mapping does not define a separate availability clock or delayed read/verification
rule. This audit quantifies that issue without changing timestamps, moving
windows, introducing a fill, or retrospectively declaring a new convention.

If the conflict is confirmed, disposition is `PROTOCOL_REQUIRES_CORRECTION`.
That does not invalidate v2 canonicalization as an implementation of the frozen
start-label mapping. It prevents using those labels directly as causal arrival
times. A reviewed availability/target/maturity contract is required before a
Google replay can be declared ready; no automatic repair is authorized here.

## Outcome-blind cohort rule and resource plan

The predeclared design is `configs/google2019_cohort_design_spec_v1.json`.
Compute the all-eligible two-cell planning projection from e metadata, explicitly
assuming g has e-like lengths/counts. Keep all if conservative output storage
fits 16 GiB and projected four-worker wall time fits 48h. Otherwise retain up to
1,000 entities per cell, ranked by ascending SHA-256 of
`google2019-v4c-cohort-v1|cell|collection_id|instance_index`.
Resolve this branch once using e metadata; apply the identical resolved rule to
g. No utilization/volatility stratification, favorable-effect selection or
cross-cell replacement. If g has fewer than the cap, retain all eligible g
entities and do not fill its shortfall with e.

Runtime is an analytical range, not measured policy performance: 0.1–10ms per
profile/truth operation, 0.01–0.1ms per event dispatch, 1.25x runtime safety;
outputs reserve 256 bytes per evaluation/event row, 1.5x storage safety plus
1 GiB fixed overhead. Refresh counts in this plan are upper bounds from metadata,
not committed policy counts. A new runtime/disk preflight is mandatory before V5;
g acquisition storage is additional and not magically supplied by subsampling.

The e selection is provisional and conditional on resolving any global protocol
issue. A corrected availability convention may change eligibility; in that case
regenerate the cohort under the same outcome-blind selection rule before outcomes.
Neither e alone nor an audit-integrity marker freezes the final two-cell cohort.

## Cross-corpus comparison limits

RQ1–RQ4, five methods, F1–F3, paired estimation, temporal density requirements,
class/p95 definitions and accounting identities remain frozen. Refresh counts
need exposure normalization when trace lengths differ; counts/writes/ages and
within-corpus paired effects answer the same kinds of questions.

Materna values are provisioned-capacity percentages; Google values are ratios to
changing **requests**, not physical capacities or percentages. Google >1 values
are valid and are never clipped. A request change can change the normalized
series without an underlying usage change. Absolute p95/MAE levels cannot be
pooled or read as equivalent capacity error. Classes use resource/entity-specific
bootstrap quantiles: equal labels/correctness do not establish equal physical
loads or operational utility. Borg instances and VMs have different entity and
dependence structures; many instances may share a collection. Cell-stratified
reporting and limits on generalization remain necessary. No latency, cost,
provisioning or heterogeneous-edge benefit follows from this metadata audit.

## Original V4C evidence — unresolved start-label clock (historical)

The audit completed without policy execution. Integrity completion is not a
protocol PASS. The complete metadata artifact inventories all canonical entities;
selection is restricted to the acquisition pool and metadata validity rules.

- Clean audit producer: `73f57129d9da2e4f27fcd5eefff289decc62e722`.
- Local artifact directory: `data/google2019/protocol_validation/v4c-e-3c40f8395c60540a`.
- [Tracked audit record](../configs/google2019_v4c_validation_record.json).
- [Independent verification](../configs/google2019_v4c_validation_evidence.json).
- [Provisional cohort authority/config](../configs/google2019_replication_cohort_v1.json).
- Audit manifest SHA: `4a05b07f95c5cc89f52017ec14c74ce4c27d83dadee261a409768de971c77824`.
- Eligibility Parquet SHA: `e99de363baec35e46523ce79a9c5c25cd961cbf5deb84f6db425c88729b55554`.
- Provisional e cohort SHA: `10f90eb7f3b03cd6c4b40d3eb4c967febb4fd90d55b0d28880d94fb9fc4115e2`.
- Resolved selection rule SHA: `b8016d94b3c633d5d73abf7dde8085325b2ebe7630309e3f114a1febd1fa624c`.

| Metadata denominator / count | Result |
|---|---:|
| Canonical rows | 462,821,691 |
| Canonical entities | 157,259 |
| Acquisition candidates | 62,451 |
| Nominal-time protocol-eligible candidates | 62,444 |
| Unique excluded acquisition candidates | 7 |
| Provisional selected e entities | 1,000 |
| Bootstrap paired observations (62,451 acquisition candidates) | 135,927,515 |
| Bootstrap valid exact-history rows (62,451 acquisition candidates) | 126,277,913 |
| 200-slot trailing-window opportunities (62,451 acquisition candidates) | 317,572,992 |
| PW opportunities including the inherited 96-slot gate (62,451 acquisition candidates) | 309,116,408 |
| Nominal hourly evaluation origins (62,451 acquisition candidates) | 25,030,381 |
| Globally verifiable nominal evaluation origins (62,451 acquisition candidates) | 24,998,548 |
| Verified read origins without an observed sample (62,451 acquisition candidates) | 10,049 |
| Missing paired nominal slots (62,451 acquisition candidates) | 920,312 |
| Intervals longer than 300s (62,451 acquisition candidates) | 130,363 |

These opportunity counts are not executed/committed policy refresh counts. All retained resources are finite; CPU and memory nonfinite counts are zero. Every nominally eligible entity has finite bootstrap thresholds. Bootstrap values from after the cut/stream anchor were not used (both source-window end violation counts are zero). No profile correctness, p95 error, policy outputs, treatment effects or significance tests were computed.

### Exclusions (overlapping reasons; seven unique entities)

| Entity (collection, instance) | Bootstrap paired slots | PW opportunities | Verified reads | Frozen reason(s) |
|---|---:|---:|---:|---|
| (22146209788, 260) | 2,121 | 123 | 0 | insufficient_globally_verifiable_evaluation_origins |
| (22146209788, 261) | 1,850 | 0 | 0 | insufficient_exact_grid_feature_or_window_validity; insufficient_globally_verifiable_evaluation_origins |
| (22146639972, 4863) | 89 | 2,146 | 182 | insufficient_bootstrap_history |
| (22146639972, 4865) | 77 | 2,193 | 180 | insufficient_bootstrap_history |
| (28763138846, 262) | 1 | 2,308 | 225 | insufficient_bootstrap_history |
| (28763138846, 263) | 1 | 1,645 | 137 | insufficient_bootstrap_history |
| (28763138846, 265) | 1 | 1,499 | 137 | insufficient_bootstrap_history |

Five fail bootstrap history, one lacks eligible profile windows, and two have zero verifiable read origins; one entity has both latter failures. No entity is excluded for low coverage percentages alone, utilization magnitude, volatility, or method behavior.

### Causal-visibility disposition

All **462,821,691 rows** across **157,259 entities** have `source_end_time_us > timestamp_us`; the maximum difference is **300 seconds**. `timestamp_us` is a start label, not proof of aggregate availability. The existing direct-index replay would read that aggregate before its source window completes if labels were treated as physical event times.

This is an unresolved **clock/adapter contract**, not evidence of bad method outcomes (none exist) or invalid request normalization. A consistently completed-bucket logical clock may be a possible clarification, but no such mapping is silently imposed here. Physical availability, target labels and verification maturity must be defined and tested together. V4C cannot certify causality by checking ordered labels alone. The current v2 canonical files remain VERIFIED as a faithful implementation of the frozen start-label mapping; no data or V4A files are rewritten. Disposition: **PROTOCOL_REQUIRES_CORRECTION**.

### Outcome-blind provisional cohort and V5 planning

The 16-GiB/48h resource rule selects the bounded hash branch. The e cohort contains exactly 1,000 of 62,444 nominally eligible entities. Rank uses identity only; independent reimplementation reproduced all selections, and changing threshold/value/fake-outcome columns leaves selection unchanged. Apply the same salt, cap and eligibility rules to g; at most 2,000 entities / 10,000 method×entity runs. The final two-cell cohort is not frozen. Any availability correction requires a new eligibility/cohort validation before outcomes.

| Planning scope | Entities | Method×entity runs | Verified origins | Evaluation records (five methods) | Output reservation GiB | Four-worker wall range, h |
|---|---:|---:|---:|---:|---:|---:|
| All nominally eligible e | 62,444 | 312,220 | 24,997,687 | 124,988,435 | 164.76 | 4.49–324.75 |
| Provisional selected e | 1,000 | 5,000 | 396,569 | 1,982,845 | 3.60 | 0.07–5.15 |
| e+g planning projection | 2,000 | 10,000 | 793,138 | 3,965,690 | 6.20 | 0.14–10.31 |

These are assumptions-based bounds for audited row-preserving outputs, not observed policy runtimes or benchmark results. All-eligible e needs a conservative 164.76-GiB output reservation, beyond the declared 16-GiB budget and current free disk. The selected-output projection is locally practical under the declared planning assumptions; g input/staging storage is additional, g length/counts are unknown, and both costs and disk must be reassessed before V5. This audit is not authorization to execute 10,000 method runs.

### Independent verification and exact next task

All corrected output hashes and the canonical dataset aggregate SHA were reverified. Raw events/merged usage SHA values remain pinned; raw/part/job/ledger identities were checked unchanged before/after. Legacy canonical input is rejected. Independent core-helper checks reproduce bootstrap thresholds, trailing eligibility and nominal read sets for 16 actual entities, including all seven exclusions, without evaluating a policy. Synthetic/future-value-invariance, hash selection and tampering checks pass. Tests: **404 passed, 0 failed, 1 skipped**; focused tests: **16 passed**. Python parsing/imports and safe CLI help pass. Audit metadata computation took 83.45s; this is not a V5 runtime measurement.

Next scientifically valid task: **V4C.1 — review/freeze the Google availability-clock interpretation and validate a causal adapter, without outcomes**. Preserve the canonical mapping or explicitly version any approved scientific amendment; validate bootstrap visibility, refresh/read ordering, target intervals and maturity together, then regenerate metadata/cohorts as required. Separately acquire and validate g under its authorized budget/disk guards. **V5 remains blocked until corrected V4C readiness, g validation, and a final two-cell cohort freeze.** No BigQuery query bytes, billing action, Static/PW/Full-Rewrite execution, V3 rerun, or method-performance inspection occurred.


## V4C.1 — current availability-aware result

The explicit derived closing label q=b+300s and visibility gate end<=read AND
q<=read resolve the earlier availability ambiguity without modifying canonical
start labels. The 288 trailing and 288 forward slot sets are mapped explicitly
in [the contract](google2019_clock_contract.md); no target count, imputation,
policy parameter or scientific comparison changes. All intervals were audited
and independently checked: zero crossing/overlap/ambiguous retained intervals.

Cell-e disposition is **AVAILABILITY_CONTRACT_READY**. Eligible counts remain
62,444/62,451, with the same seven exclusions and the identical 1,000 selected
members. Bootstrap thresholds and all refresh/read opportunity counts are equal
per entity; physical cut/read anchors are explicitly +300s. Current authority is
`configs/google2019_current_protocol.json`, protocol v2, and cohort config v2;
v1 configs/blocked artifacts remain historical and are not current inputs.

**V4C remains incomplete until g is acquired/validated under the same contract
and the final two-cell cohort is frozen. V5 stays blocked; no policy outcomes
or BigQuery queries were run.**
