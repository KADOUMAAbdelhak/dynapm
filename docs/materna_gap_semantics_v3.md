# Materna exact-grid eligibility — causal-timeline-v3

This is a metadata-only audit, not model evaluation or a final cohort freeze.
The managed corrected pilot writes `materna_gap_eligibility_v3.parquet/json` for
all 1,576 retained entities, alongside the timestamp-only gap audit.

Training candidates are observed bootstrap targets after the initial 96 nominal
slots. Valid rows require finite paired history for all exact prior 96 slots
and an observed finite target. Each target-specific model also records its own
training validity. Gap-affected invalid rows exclude initial history warmup.

Streaming validity uses all available earlier bootstrap/stream observations.
Missing residual history pauses ADWIN, without reset. Long recovery periods
are contiguous invalid-origin runs of at least 96 nominal slots. Observation
windows are exact (t-24h,t] >=200 paired slots, and (t-6h,t] >=50 slots.
Hourly read opportunities are verifiable with >=200 exact forward slots and an
elapsed horizon, regardless of an observation at the read origin.

Per-period metadata maps each nominal tick to the first subsequent observed
common-eligible timestamp; ticks mapping to the same actual timestamp coalesce
to the latest nominal tick. It records immediate ticks, delayed commits, maximum
delay (latest represented tick), maximum wait of any due tick (including coalesced ticks) and unresolved ticks, without instantiating policies or predictors.

Diagnostic review flags identify zero training/evaluation opportunities or <95%
training/streaming/evaluation validity. This flag is NOT an exclusion rule and
changes no cohort. V2.5 must separately predefine final scientific eligibility.
Verified counts follow below; the corrected pilot identity is linked in the bounded record.

## Verified all-retained metadata counts

Managed source/run/output identity is recorded in [bounded pilot](bounded_pilot.md).
All **1,576** retained VMs were audited, with **641**
affected by gap validity and **199** diagnostic
review flags. There are **zero** entities with no valid training rows or no verified
hourly evaluations. No VM was removed. The review flag is not a final exclusion.

Nominal hourly opportunities: **783,753**; verifiable:
**777,185**. Gap rarity does not justify bridging; exact
invalidation and eligibility are now enforced. **GAP SEMANTICS: ACCEPTABLE FOR V3**
means the gap-handling defect is corrected, not that a full run is authorized.
V2.5 still freezes cohort/exclusions and confirmatory design first.

| Quantity | Count |
|---|---:|
| bootstrap_observations | 4,195,390 |
| candidate_training_targets | 4,044,931 |
| valid_feature_rows | 4,004,156 |
| invalid_gap_affected_rows | 40,775 |
| streaming_observations | 9,791,587 |
| streaming_valid_one_step | 9,727,350 |
| long_recovery_periods | 651 |
| window24_eligible | 9,753,257 |
| window6_eligible | 9,782,242 |

| Period | Nominal ticks | Immediate eligible | Commits | Delayed commits | Max latest-tick delay (s) | Max any-tick wait (s) | Unresolved ticks |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3h | 272,739 | 268,649 | 269,305 | 656 | 10,500 | 1,006,500 | 0 |
| 6h | 135,864 | 133,958 | 134,615 | 657 | 21,300 | 995,700 | 0 |
| 12h | 67,615 | 66,510 | 67,097 | 587 | 42,900 | 974,100 | 0 |

Complete machine-readable per-VM records remain in managed outputs, not tracked result tables. Gaps and missing values are never filled. Source inputs and retained cohort are unchanged.
