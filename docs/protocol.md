# Deterministic causal timeline

Protocol: `causal-timeline-v3`. Evaluation design: `phase-balanced-hourly-v1`.
Accounting remains `refresh-accounting-v1`. These semantics create a new scientific
generation. Previous v2 outputs remain immutable and incompatible with current caches.

## Nominal grid and observation visibility

`dynapm/core/temporal.py` owns the five-minute cadence, exact lookups, trailing
windows, presence/validity masks and pending periodic grid. Each entity has one
nominal grid anchored to its first timestamp. Off-grid or duplicate timestamps
are invalid. Missing raw slots stay missing: no forward/back fill or interpolation.
Bootstrap is the first 30% of observed samples, unchanged. All available bootstrap
and earlier streaming observations can support a streaming prediction; there is
no additional arbitrary streaming-only 96-observation warmup.

## Exact causal feature history

For target timestamp s, lags 1,2,3,6,12,24,48 mean exact multiples of five minutes
before s. Shifted rolling windows 6,12,24,48,96 require every nominal source slot;
differences 1/12 are computed on shifted past history. All 96 slots
[s-480min,s-5min] must be finite for that target/resource. Calendar features depend
only on s. Batch shifting/rolling occurs AFTER nominal-grid reindexing; recursive
array indexing operates only on a validated contiguous nominal buffer.

Training uses only bootstrap targets that actually exist and are finite, with
complete causal features. A missing slot invalidates the next 96 target rows;
the 97th target after it can recover. Per-target diagnostics record bootstrap
observations, post-initial-context candidate targets, valid rows, gap-affected
invalid rows and valid fraction. CPU and memory remain separate models.

A one-step residual at t is u_t-yhat(t|t-5min). It is available only with finite
u_t and complete exact prior history. Unavailable residuals pause both detectors
without a reset, imputation or invented update. River's signal belongs only to
the current update: if an exceptional invalid forecast origin prevents a drift
commit, the signal is consumed and counted diagnostically, never latched.

## Refresh origins and observation windows

A predictor-origin t requires the exact 96 actual slots [t-475min,t] for each
resource. Recursive inference then inserts predictions at the next exact nominal
slot, never actual future values. Every horizon is 288 finite targets.

Periodic-Window and Full-Rewrite use (t-24h,t], with at least 200 paired finite
observed slots of 288. Reactive uses (t-6h,t], with at least 50 paired slots of 72
(ceil(72*200/288)). No window reaches further back to replace missing samples.
Initialization separately populates the profile from bootstrap data using the
policy's existing bootstrap estimator; runtime eligibility does not manufacture
bootstrap data or count initialization as a refresh.

PW, PP and V3's periodic component share BOTH conditions: >=200 paired slots in
the exact trailing 24h AND a valid CPU/memory predictor origin. The gate is based
on input availability, including for observation-only PW; it requires no model
construction for PW. Runtime window arguments contain only actual past samples.

## Periodic grid and coalescing

Anchor is the first streaming timestamp from the bootstrap split. Nominal ticks
are anchor+k*period, k>=1. Missing observations or false common eligibility leave
the tick pending. At the first subsequent observed eligible origin, one refresh
commits, representing the latest due nominal tick. Later ticks remain on the
original grid. Gaps longer than 6h can cross many nominal ticks but cannot cause
a burst of stale commits. Nominal ticks due and actual commits are separate counts.
Drift never resets/reanchors the periodic grid. PW and PP therefore commit the
same nominal/actual periodic timestamps for each shared interval and input timeline.

## Single event ordering

The shared replay merges observed timestamps, nominal read clocks and verification
maturity clocks. At t with an observation:

1. Observation u_t becomes visible.
2. Available causal one-step residuals are evaluated.
3. Both ADWIN states update if residuals are available.
4. Eligible periodic/drift triggers resolve; periodic takes precedence.
5. At most one runtime refresh commits.
6. A coincident nominal evaluation reads the resulting profile copy.
7. Pending copies whose future horizons have elapsed receive ground truth.

At t without an observation, there is no residual, detector update or policy step;
the evaluation still reads the latest committed state AT t. Reads are never
shifted to telemetry arrival. Verification is also a clock event, not a delayed
observation event, and occurs only after t+24h within the available trace horizon.

## Hourly phase-balanced evaluation and profile age

Nominal evaluations are anchor+k*1h, including k=0. Over the common 12h
superperiod this covers phases 0..11. On complete data, after the first scheduled
refresh, 3h policies have ages {0,1,2}h, 6h have {0,..,5}h and 12h have {0,..,11}h.
Phase zero is retained but cannot be the only measured phase. Before the first
periodic commit, age is measured from the policy's bootstrap initialization.

Each read stores evaluation_time, last_refresh_actual_commit_time,
profile_age_seconds, profile_age_hours, and last_refresh_trigger. Static age is
from initialization. Same-time commit/read has zero age. A persisted aggregate
is scored as-is; it is never silently recomputed at the read time.

## Forecast and ground-truth alignment

Both nominal target sets are (t,t+24h] = {t+5min,...,t+1440min}, 288 exact slots.
A forecast requires an observed eligible origin; a ground-truth/read origin need
not have an observation. Ground truth uses actual paired finite samples on those
exact targets, >=200/288, and requires the full wall-clock horizon within the trace.
Sparse truth describes the observed subset, not an imputed complete horizon.

The globally verified evaluation set depends only on data and this protocol, not
on policy refresh behavior. Every method reads the same verified nominal times,
thresholds and truth. Evaluation of stale profiles at e uses truth (e,e+24h]; its
stored forecast originally issued at r is not resliced or regenerated at e.

## Analysis-only budget control

`budget-match-uniform-eligible-v2` changes only candidate eligibility from v1.
K is V3's paired count of committed drift refreshes. Eligible observed predictor
origins excluding shared 6h periodic commits form an ordered candidate sequence.
Midpoint integer equal-spacing chooses K unique timestamps; neither drift times,
residuals nor outcomes enter. Extras are `budget_extra`, never drift. K=0 is PP6.
This is a paired offline counterfactual, not a deployable online policy.

## Refresh Accounting

Accounting schema: `refresh-accounting-v1`, alongside temporal protocol `causal-timeline-v3`. The schema is required on result JSONs and per-VM summary rows. Earlier counter formats must not be relabeled as current measurements.

`dynapm/core/accounting.py` defines frozen `InitializationEvent` and `RefreshEvent` records, a constrained `Trigger` enum, and the single `ProfileCommitter` used by every policy. All dynamic field assignments pass through this helper; policies only decide when to commit and calculate the values.

- **Initialization event:** the initial population of all four dynamic fields from bootstrap data. Exactly one per policy instance, stored in `initialization_log`. It is not a runtime refresh, and its assignments are excluded from runtime write/change counters.
- **Runtime refresh event:** one committed maintenance operation at one processed timestamp. It exists even when all newly assigned values equal the old values. Duplicate or reversed runtime commit timestamps are rejected before any assignment.
- **Trigger:** exactly one of `periodic`, `drift`, `reactive`, or `full_rewrite`. Policies restrict their allowed triggers. V3 selects periodic on coincidence, producing one event and no additional drift event.
- **Nominal scheduled tick:** a grid point from Phase 2A. `nominal_scheduled_time` is the latest due tick represented by a periodic commit, and is null for other triggers.
- **Actual commit time:** the observed timestamp at which the operation writes its profile state. It can be later than the nominal tick.
- **Field write:** one assignment to one dynamic field during a runtime refresh. Every current policy refresh writes all four fields, including assignments of equal values. Assignment timestamps are updated for those writes.
- **Field value change:** a field write whose value differs from the previously committed value. Missing-to-missing is unchanged. `fields_changed` is a unique subset of `fields_written`.
- **Coalesced ticks:** several nominal ticks can become due during a gap, but produce only one periodic commit on resumption. Skipped/coalesced ticks are not refreshes.

The four written fields are CPU class, memory class, CPU p95, and memory p95. One refresh that changes only CPU p95 records one event, four writes, and one value change. One unchanged Full-Rewrite operation records one event, four writes, and zero changes.

Each per-VM policy result exposes:

| Counter | Exact scope |
|---|---|
| `n_initialization_events` | Bootstrap population operations; exactly one |
| `n_refresh_events` | All committed runtime operations; the authoritative refresh metric |
| `n_field_writes` | Runtime assignments; exactly four times runtime refreshes |
| `n_field_value_changes` | Runtime assignments with a changed value |
| `n_periodic_refreshes` | Runtime periodic-trigger events |
| `n_drift_refreshes` | Runtime drift-only events |
| `n_reactive_refreshes` | Runtime Reactive-trigger events |
| `n_full_rewrite_refreshes` | Runtime Full-Rewrite-trigger events |
| `nominal_periodic_ticks_due` | All grid ticks crossed through the last processed observation, including coalesced ticks |
| `periodic_refresh_events_committed` | Actual periodic commits; equals `n_periodic_refreshes` |

Static has zero runtime refreshes, writes, and changes after its one initialization. PW and PP each satisfy total refreshes = periodic refreshes, with exactly equal committed schedules/counts for identical timelines, split, and period even when their predicted content differs. Reactive counts only class-change-triggered commits. Full-Rewrite counts every eligible processed observation. V3 satisfies total refreshes = periodic + drift refreshes.

Example: a six-hour grid crossed at 06:00, 12:00, and 18:00 during a gap has `nominal_periodic_ticks_due=3` on a 20:00 resume, but at most one committed periodic event, associated with 18:00, if content eligibility is true. Otherwise it remains pending until recovery, potentially coalescing further ticks. The next nominal tick remains 24:00. Drift never moves this grid.

`refresh_log` is a serializable trace of canonical runtime events; `initialization_log` is separate. Each runtime event contains `actual_commit_time`, `trigger`, `nominal_scheduled_time`, `fields_written`, and `fields_changed`. ISO timestamps and explicit counters survive ordinary JSON serialization. No event trace is required to compute statistics. A bounded provisioning replay also exposes its per-VM accounting as `DataFrame.attrs["policy_accounting"]`, rather than repeating counters on each verified outcome row.

The ambiguous legacy result names and changed-field-row log are removed. Per-field diagnostics use explicit names such as `n_memory_class_value_changes`. Task 15 retains every canonical counter in its per-VM summary. `summarize_accounting` and table builders read validated counters directly, including means of refreshes, periodic/drift events, writes, and value changes. There is no sample normalization, unique-field-timestamp inference, or cell override. [The accounting audit](accounting-audit.md) classifies the previous references and the remaining uses.

### Analysis-only budget control

Phase 3A adds `budget_extra` and `n_budget_extra_refreshes` as an additive counterfactual category. It uses the same one-commit/four-write rules; the six production policy definitions, initialization exclusion, periodic precedence and grid remain unchanged. The [bounded pilot](bounded_pilot.md) explains the non-adaptive extra placement and why the paired-budget control is not an online algorithm.
