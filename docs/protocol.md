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

Both detectors are updated even if one reports drift. If a periodic tick is also due, one refresh commits with `reason="periodic"`. Otherwise a drift event commits with `reason="drift"`. Drift never changes the grid anchor or next nominal periodic tick.

Each policy exposes `refresh_log`, with one record per logical refresh:

- `nominal_scheduled_time`: latest due periodic tick, or `None` for a non-periodic refresh;
- `actual_commit_time`: actual observation/commit timestamp;
- `timestamp`: compatibility alias for actual commit time;
- `reason`: periodic, drift, reactive, or full_rewrite.

`update_log` remains a field-mutation log. A logical refresh can write several fields or leave values unchanged, so field rows must not be counted as distinct refresh events. Runner `n_refresh_events` and periodic/drift counters use `refresh_log`. `total_updates` continues to count field rows, not logical refreshes. Task 15 preserves these distinct counters in its summary.

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
