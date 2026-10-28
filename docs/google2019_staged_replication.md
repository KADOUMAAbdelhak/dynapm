# V4D — Prospective staged Google replication

**Status: design frozen before any Google method outcomes.** Subsequent **V4E
Stage-A e execution PASS** is recorded in [the findings](google2019_stage_a_results.md);
g remains mandatory and unexecuted. The V4D preparation record below implements
and tests the evaluator with synthetic data only. It does not execute Stage A or B.
The versioned design is `configs/google2019_staged_replication_v1.{json,yaml}`;
`configs/google2019_current_protocol.json` is the current status/pointer.

## Prospective amendment and independence

The earlier V4C.1 metadata-only gate required both cells before any V5 execution.
V4D explicitly supersedes that execution prerequisite for **Stage A only**. It
changes neither Google protocol v2 nor V4A's RQs, comparisons, eligibility,
normalization, methods, parameters or statistics. Earlier `v5_requires`,
`replication_authorized=false` and `policy_outcomes_authorized=false` fields in
frozen V4A/V4C.1 records describe those historical gates, not this new stage-specific
readiness. V4C overall remains incomplete; final two-cell readiness is false.

- **Stage A / V5A:** cell e, exactly the existing 1,000 identities. Cohort SHA-256
  `992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c`.
  `configs/google2019_stage_e_binding_v1.json` pins canonical generation, shard
  inventory aggregate, validated clock audit, eligibility table and cohort bytes.
- **Stage B / V5B:** cell g, independently apply the unchanged
  `google2019-v4c-cohort-v1|cell|collection_id|instance_index` identity hash, lowest
  1,000 protocol-eligible entities, or all if fewer. No backfill between cells,
  no replacement cell, no utilization/volatility/outcome selection. The future
  `configs/google2019_stage_g_binding_v1.json` must bind validated g artifacts.
  It is deliberately absent now; the evaluator refuses Stage B.
- Acquire, analyze and report g **regardless of e's direction**, including null,
  negative or mixed results. g is held-out **within-corpus** replication, not a
  third independent corpus. Same-month/provider/workload and shared-collection
  dependence limit independence; report collection overlap as metadata without
  creating post-outcome exclusions.

No method, parameter, statistical or cohort-rule changes after seeing e. A
correctness fix requires a versioned amendment, regression test, invalidation of
affected generations and comparable e/g reruns. Never edit measured outputs or
silently redefine the contract. Failure to acquire g is reported as missing
replication evidence, not grounds to substitute a favorable cell.

## Frozen execution semantics

| Method | Initialization content | Runtime content | Runtime gate / schedule |
|---|---|---|---|
| Static | whole completed bootstrap | none | one initialization, zero refreshes |
| PW-12h | last 12h of bootstrap at last bootstrap observation | trailing 24h | 200 paired slots + 96 complete recent slots; anchored 12h |
| PW-6h | last 6h of bootstrap at last bootstrap observation | trailing 24h | same gates; anchored 6h |
| PW-3h | last 3h of bootstrap at last bootstrap observation | trailing 24h | same gates; anchored 3h |
| Full-Rewrite | last 24h of bootstrap at last bootstrap observation | trailing 24h | 200 paired slots; every eligible observed sample |

These initialization exceptions and the inherited PW 96-slot gate are retained
literally. The 200-slot runtime threshold is not retroactively applied to
initialization. No RF fit, prediction, residual or detector runs in this matrix.
Static initialization is recorded at the first streaming read anchor, while PW
and Full-Rewrite initialize at the last bootstrap observation, matching shared
policy constructors. Each method records that actual initialization time for age.

Google protocol v2 fingerprint:
`88e11c165a05658fe587878a66ee2816f033957efceb883062b0577d4f98a2c1`.
Clock: `google-completed-slot-availability-v1`; shared timeline:
`causal-timeline-v3`; evaluation: `phase-balanced-hourly-v1`; accounting:
`refresh-accounting-v1`.

Raw measurement `[start,end)` remains stored at b=floor(start/300s)*300s.
Analysis uses closing label q=b+300s, admitted only when **end<=read and q<=read**.
The adapter checks unique contained, non-overlapping intervals before replay.
No incomplete aggregate enters thresholds or a profile. Bootstrap consists of
first floor(0.30*N) nominal closing slots, not 30% of observed rows; thresholds
are resource-specific bootstrap p20/p40/p60/p80 and p95, frozen at the first
streaming q. No interpolation, duration weighting, clipping or capacity inference.
Utilization above one remains above one. Unknown Google capacities are null.

Runtime content at read r is `(r-24h,r]`: exactly 288 nominal closing slots,
using >=200 paired finite observations. PW additionally requires the most recent
96 complete closing slots. Periodic ticks remain anchored to first streaming q;
unavailable ticks stay pending and coalesce to the latest due nominal tick at
first eligible observation, preserving the grid. Hourly evaluation reads retain
nominal time even without an observed sample. Observations/commits precede a
same-time read. Every method has identical verified read times and thresholds.
Forward truth `(r,r+24h]` contains the next 288 closing slots, >=200 paired
observations; verification occurs only after r+24h. Missing slots stay absent.
Partial physical intervals count as actual partial samples, not invented complete
five-minute duration measurements. See [clock contract](google2019_clock_contract.md).

## Frozen analysis and reporting

Unit: **entity**, with paired treatment-minus-control effects. Report CPU/memory
class correctness and CPU/memory p95-profile MAE separately; primary maintenance
cost is `n_refresh_events`. Secondary diagnostics: bias, age distributions,
initializations, writes, value changes, trigger/tick counts, exposure and delay.
Field rows are never refresh counts. No profile-level practical margins exist;
statistical distinguishability does not establish practical or operational benefit.

- F1: PW-12h / PW-6h / PW-3h minus Static.
- F2: PW-6h minus PW-12h; PW-3h minus PW-6h.
- F3: Full-Rewrite minus PW-3h.

For each cell independently: paired mean and median, percentile bootstrap 95% CI,
B=10,000, seed=20251022; two-sided Wilcoxon with `zero_method=wilcox` (zero
pairs excluded from signed ranks; all ties => p=1). Standardized effect is
undefined for zero paired SD and remains null/NaN in the table, never invented.
Holm adjustment separately within F1/F2/F3 across all declared contrasts x
four fidelity endpoints plus refresh cost: **15 / 10 / 5 tests** per cell.
These confidence intervals are marginal; Holm adjusts p-values, not CI coverage.
No additional confirmatory tests for descriptive bootstrap CPU-volatility tiers:
population std(ddof=0), tertiles within each fixed selected cell cohort; <=q1 low,
<=q2 medium, else high. These values never affect selection.

Report e first and g separately using the identical script/configuration. After
both stages, show all predeclared contrast/endpoint estimates and CIs side by side.
Predefined synthesis categories use paired **mean-effect signs**: same_positive,
same_negative, same_zero, discordant_or_one_zero. Report g-minus-e mean/median
point effects as descriptive heterogeneity. This is not a global superiority
rule, pooled p-value or pooled confidence interval. Preserve endpoint direction
(higher correctness / lower MAE / lower cost). Never select the favorable cell.
Absolute Google request-ratio errors must not be pooled with or described as
Materna provisioned-capacity percentage errors. Offline evidence supports no
operational or edge claim.

## Managed evaluator and execution boundary

`dynapm.experiments.google_replication` prepares the Google clock/split and calls
the existing `PreparedVM`, five method factories, snapshot verifier, metrics,
accounting and paired statistics. It does not fork policy logic or the event loop.
The explicit config is checked against frozen settings before dispatch; each
factory's period is checked. Metadata-verified read counts must match execution.
Runtime source hashes in the design detect changes requiring an amendment.
Both cells use the same entry point; g configuration has no e-result input.

Safe input-only check (creates no outcome/run files):

```sh
python -m dynapm.scripts.task30_google_replication --cell e \
  --cohort-manifest data/google2019/protocol_validation/v4c1-e-91887b860ee5e549/provisional_e_cohort.json
```

Only a separately authorized Stage-A task adds `--execute`. Clean committed
source is mandatory. `--workers` accepts 1..4. No entity limit/override/all-entity
option exists. Exactly the bound cohort executes; any missing entity, malformed
input, nonfinite committed profile, accounting/read-set mismatch or exception
fails the run. Do not drop failures or backfill after outcomes. g requires its
validated binding/cohort before any run can start.

Runs use purpose `claim` in the existing provenance lifecycle, meaning a
prospectively frozen replication generation, **not** validation of an empirical
claim. Scientific identities include cell/stage, source/environment, design,
configuration, canonical shards, input binding and exact cohort. The dataset
manifest's `canonical_usage` trace is a physical shard inventory group; the
cohort's logical trace is e or g. Paths are relative; resource units are ratios
throughout (legacy internal CPU column names ending `[%]` are compatibility
aliases only). Source/input/environment and ignored parent/audit/cohort manifests
are rechecked before SUCCESS. Smoke/pilot/unversioned/changed-generation outputs
cannot satisfy claim cache reuse. `--reuse-run` uses the one authoritative
`check_cache`, never existence-only reuse.

Outputs under ignored `results/runs/<fingerprint>/<run-id>/`:

- per-entity method summaries, common-truth evaluation records, refresh events;
- entity wall-time/threshold diagnostics (not isolated overhead measurements);
- cost/accounting means, paired effects, family inference JSON/Parquet;
- descriptive robustness/age/bias summaries, design/input binding and diagnostics;
- config/environment/dataset/cohort/run/output manifests, hashes, SUCCESS or FAILED.

No generated results are committed. Canonical inputs are read-only. The evaluator
has no acquisition/query calls. This gate runs only synthetic fixtures and metadata
integrity checks, never real Google policy outcomes.

## Remaining gates and optional corpus

V4D readiness permits a separately authorized **V5A — cell-e replication**.
V5B remains blocked by g acquisition under zero-spend/monthly/disk safeguards,
corrected canonicalization, availability validation and its independent cohort
binding. Full V4C/two-cell completion is not asserted here.

Alibaba 2026 MaaS remains a **conditional third-corpus** hypothesis, not a
replacement for g. Licence/redistribution permission and one-week protocol fit
remain unresolved. No new download, experiment or corpus commitment is made.


## V4D verification record

`configs/google2019_v4d_validation_record.json` records 459 passed, zero failed,
one skipped; 28 new staged-evaluator tests pass. The skip is the pre-existing
access-blocker test on a machine with local dry-run credentials; it issues no query.
All 121 Python files parse and the new modules/CLI import. Synthetic runs exercise
the production managed path and common replay, complete output inventories, exact
cache reuse, configuration/purpose rejection, superseded input rejection and
tampered-copy rejection. Real e input-only preflight verifies all canonical
artifact hashes, clock audit/eligibility/cohort lineage and exactly 1,000 frozen
identities; g preflight refuses its absent validated binding. Ledger/e cohort
hashes remain unchanged. No actual e/g method outcomes, acquisition/cloud queries
or Materna scientific result modifications occur.


## V4F — collection-aware secondary supplement before Stage B

[The secondary collection contract](google2019_collection_robustness.md) and
`configs/google2019_collection_robustness_v1.{json,yaml}` freeze a separate
collection sensitivity procedure. The primary staged JSON/YAML, cohort/methods,
entity-level F1/F2/F3 analysis, Wilcoxon/Holm and no-practical-margin framing remain
unchanged. This authorized supplement does not substitute for primary statistics
or retrospectively preregister e. Any real e collection analysis is **post-hoc**;
the identical procedure is **prospective secondary robustness for g**.

Always report original primary entity estimates beside cluster-adjusted
entity-mean uncertainty and the distinct equal-collection mean/median-of-means
estimates. Whole clusters are resampled with all selected members/multiplicity,
B=10,000, seed=20251022, nominal 95% percentile CIs. Retain every singleton and
large collection. No new secondary p-values/Holm family, practical margin,
cohort weighting/selection or favorable-estimand choice. Both cells remain
separate first; descriptive magnitude/direction/heterogeneity only, no pooled
entities or favorable-cell selection. Stage B remains mandatory. V4F itself
audits e identities and synthetic tests only; no real secondary outcomes run.
