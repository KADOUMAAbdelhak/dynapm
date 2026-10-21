# Deterministic causal timeline

Protocol identifier: `causal-timeline-v2`. This changes scheduling and label semantics; earlier causal-protocol outputs are not interchangeable. No existing result files are rewritten by these definitions.

## Audit of the preceding implementation

At commit `07fe9efd4b62bea9de9f4c4b849759a8212e4c62`:

- `PeriodicPolicyV2.step` and `PeriodicPredictorPolicyV2.step` in `dynapm/methods/baselines_v2.py` tested elapsed time from the previous actual refresh. Their anchors were the final bootstrap observation, and delayed commits shifted later ticks.
- `DynAPMPolicyV3.step` in `dynapm/methods/dynapm_v3.py` refreshed immediately at its first processed observation, then tested elapsed time from the last periodic commit. Drift already did not reset that timer. Both ADWIN detectors already ran before periodic/drift selection, and periodic already took precedence.
- `iter_verified_snapshots` in `dynapm/eval/replay.py` already updated the policy before copying an evaluation snapshot and attached labels only after 24 elapsed hours. These correct orderings are retained and tested centrally.
- `VMPredictor.predict_causal_horizon` targeted steps 1 through 288 after the origin. It inferred cadence from the first two history timestamps, so a gap there could turn 288 steps into more than 24 hours.
- Both ground-truth functions and the density clock used `[t, t+24h)`: on a complete five-minute series they included the origin and excluded the final forecast target. The documented claim of alignment was incorrect.

## Event ordering and observation visibility

The authoritative replay is `iter_verified_snapshots` in `dynapm/eval/replay.py`. Evaluation, provisioning, and the compatibility runner all use it. At each processed timestamp `t`:

1. The current observation `u_t` becomes visible, along with earlier observations. Future actual utilization remains unavailable to policy inference.
2. V3 compares `u_t` with its frozen one-step prediction `yhat(t | observations strictly before t)`, producing `r_t`. CPU and memory are separate.
3. Both ADWIN detectors consume their current residuals.
4. The policy checks the shared periodic grid and the drift flags.
5. At most one logical refresh commits: periodic wins if both triggers are true.
6. An evaluation at `t` copies the resulting dynamic profile. It sees the post-refresh state; a later refresh cannot mutate this copy.
7. Pending snapshots are paired with forward labels only once the current replay time is at least their origin plus 24 hours.

One-step predictions and labels may be computed in an offline batch during preparation. The one-step feature row for target `t` uses utilization at timestamps strictly before `t`, never `u_t`. Calendar information for `t` is deterministic. Preparation does not expose labels to the policy; replay reads them for verification only after the horizon. It never passes a future one-step prediction array to a refresh policy.

Refresh inference uses `forecast_at_origin` in `dynapm/core/predictor.py`: the history is filtered to timestamps `<= t`, and `t` must have an observation. Recursive steps append only predictions after `t`.

## Periodic grid and anchor

`PeriodicGrid` in `dynapm/core/temporal.py` is shared by Periodic-Window, Periodic-Predictor, and V3. The anchor is `profile.static.bootstrap_end`, which `compute_split` defines as the first streaming observation timestamp. It is a per-VM wall-clock anchor, not a global midnight anchor.

Bootstrap initialization is not a periodic refresh. For period `P > 0`, nominal refreshes are:

```
anchor + k * P,  k = 1, 2, 3, ...
```

All three policies receive the same nominal grid for the same timeline and period. Their initial bootstrap estimators remain method-specific. Policy processing retains the common streaming feature warmup of 96 observed rows. If this warmup crosses scheduled ticks, the same missed-tick rule applies to all three methods; the grid does not restart at the first usable feature row.

## Missing observations and long gaps

A tick becomes due at its nominal time. If that time has no processed observation, delivery waits for the first subsequent processed observation. The commit uses history through this actual observation time, not a retrospective forecast at the missed tick.

When several ticks become due during a gap, exactly one refresh executes, associated with the latest due nominal tick. Earlier crossed ticks are coalesced. Subsequent ticks stay on the original grid.

Example with a six-hour period and anchor 00:00: observations stop before 06:00 and resume at 20:00. One refresh at 20:00 records nominal 18:00; the next nominal tick remains 24:00. There are no duplicate catch-up refreshes for 06:00 or 12:00.

Missing observations are neither fabricated nor backfilled. Feature lags and rolling windows retain their existing observed-row interpretation across gaps; this phase does not introduce resampling or a new missing-data model. Future target cadence is nevertheless always five minutes.

## Coincident periodic and drift triggers

Both detectors are updated even if one reports drift. If a periodic tick is also due, one refresh commits with `trigger="periodic"`. Otherwise a drift event commits with `trigger="drift"`. Drift never changes the grid anchor or next nominal periodic tick.

Canonical events carry an explicit trigger and separate written/changed field lists. See [Refresh Accounting](#refresh-accounting) for the complete schema and counter definitions.

## Forecast and ground-truth targets

The canonical origin `t` is an available observation timestamp. Both nominal target definitions are:

```
(t, t+24h] = {t+5min, t+10min, ..., t+1440min}
```

There are exactly 288 targets. `forecast_targets` in `dynapm/core/temporal.py` supplies this index. Recursive inference uses it regardless of gaps in earlier observations; a ten-minute inferred cadence is not allowed.

`forward_observations` selects actual observations on exactly these target timestamps. Both class and p95 ground-truth functions use this selection. They exclude `u_t` and include the observation at `t+24h` when present. The compatibility function name delegates to the same implementation.

For a complete series, the forecast index equals the ground-truth observation index exactly. For a sparse series, the nominal target grid is still identical, but ground truth uses only its available paired CPU/memory observations. Missing actual utilization is not imputed, and future missingness is not used to reshape the profile forecast. Sparse labels therefore estimate the full-window quantities from an observed subset; they are not equivalent to fully observed labels.

A persisted profile is read as the current estimate at each evaluation time. Between refreshes, its aggregate fields can be stale: evaluation at `e` scores the retained estimate against `(e, e+24h]`. The original forecast was issued at the last refresh `r`; it is not secretly regenerated or resliced at `e`. At a coincident refresh/evaluation (`r=e`), both use exactly the same target set. With the standard six-hour periodic and twelve-hour evaluation grids, complete observed evaluation ticks coincide with periodic ticks. Other period settings must retain this staleness distinction.

## Eligibility and evaluation clocks

The existing density threshold remains **at least 200 observed target slots out of 288**, with paired non-null CPU/memory values. The origin is not one of those slots. Duplicate timestamps are invalid; off-grid rows cannot inflate the count. A dense but truncated window is ineligible: the dataset must extend to at least `t+24h`.

Evaluation candidates are anchored to the first streaming timestamp at twelve-hour intervals, including the anchor itself. They must have an observed origin, sufficient forward density, and an elapsed full horizon within the trace. Candidates before feature warmup are excluded from replay. An evaluation origin missing from the observation timeline is dropped, not deferred; later evaluation candidates remain on their original grid.

Verification occurs at the first processed observation at or after `t+24h`. If the endpoint is missing, a later observation can release the pending snapshot. If replay stops before the horizon, the snapshot remains unverified and is counted as dropped, never scored early.

Replays derive labels in memory from these shared clock/window functions, using bootstrap-only thresholds. They do not consume old cached ground-truth Parquets. The standalone ground-truth producer uses the same functions and stamps the new protocol when explicitly run. No corpus generation is part of this phase.

## Refresh Accounting

Accounting schema: `refresh-accounting-v1`, alongside the unchanged temporal protocol `causal-timeline-v2`. The schema is required on result JSONs and per-VM summary rows. Earlier counter formats must not be relabeled as current measurements.

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

Example: a six-hour grid crossed at 06:00, 12:00, and 18:00 during a gap has `nominal_periodic_ticks_due=3` on a 20:00 resume, but only one committed periodic event, associated with 18:00. The next tick remains 24:00. Drift never moves this grid.

`refresh_log` is a serializable trace of canonical runtime events; `initialization_log` is separate. Each runtime event contains `actual_commit_time`, `trigger`, `nominal_scheduled_time`, `fields_written`, and `fields_changed`. ISO timestamps and explicit counters survive ordinary JSON serialization. No event trace is required to compute statistics. A bounded provisioning replay also exposes its per-VM accounting as `DataFrame.attrs["policy_accounting"]`, rather than repeating counters on each verified outcome row.

The ambiguous legacy result names and changed-field-row log are removed. Per-field diagnostics use explicit names such as `n_memory_class_value_changes`. Task 15 retains every canonical counter in its per-VM summary. `summarize_accounting` and table builders read validated counters directly, including means of refreshes, periodic/drift events, writes, and value changes. There is no sample normalization, unique-field-timestamp inference, or cell override. [The accounting audit](accounting-audit.md) classifies the previous references and the remaining uses.

### Analysis-only budget control

Phase 3A adds `budget_extra` and `n_budget_extra_refreshes` as an additive counterfactual category. It uses the same one-commit/four-write rules; the six production policy definitions, initialization exclusion, periodic precedence and grid remain unchanged. The [bounded pilot](bounded_pilot.md) explains the non-adaptive extra placement and why the paired-budget control is not an online algorithm.
