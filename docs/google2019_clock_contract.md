# Google measurement, availability and read clocks — V4C.1

Contract: `google-completed-slot-availability-v1`. Protocol configuration:
`configs/google_clusterdata_2019_replication_protocol_v2.{json,yaml}`.
Cell-e interval validation is PENDING the committed metadata-only audit. No
policy outcomes or replication authorization. The old V4A v1 files and all
Materna/V3 artifacts remain untouched.

## Three clocks and the explicit analysis view

For a canonical row, let s and e be exact source start/end times and δ=300s.

| Concept | Definition |
|---|---|
| Actual measurement | `[s,e)`; the source's observed average over that interval |
| Stored canonical label | `b=floor(s/δ)*δ`, unchanged in the v2 canonical files |
| Availability | `a=e`; the average cannot be visible before completion |
| Derived analysis label/admission | `q=b+δ`, the closing point of its nominal bin |
| Policy/evaluation read | Physical trace-relative read clock r, on the nominal grid |
| Visibility | Both `a<=r` and `q<=r` |

Require `b<=s<e<=b+δ` and exactly one retained row per entity/bin. Retained
cross-bin, nonpositive, overlapping or duplicate intervals block the contract;
no silent splitting, discarding or retiming of ambiguous measurements is allowed.
A partial interval ending before q is available at e but admitted conservatively
at q. It is not expanded, interpolated, clipped, rescaled, or duration-weighted.
One actual paired finite partial observation counts as one nominal observed slot,
as allowed by V4A; 288 slots must not be described as 288 full-duration intervals.

Example: `[10:01,10:05)` retains canonical b=10:00, is available at 10:05, and
enters the q=10:05 slot. A read at 10:00 cannot use it. If a partial interval
ends at 10:03 within that bin, q stays 10:05. No intermediate early-admission
policy event is created.

`dynapm/data/google2019_clock.py` creates this derived view and owns visibility,
bootstrap, trailing/forward extraction and refresh-eligibility checks. Canonical
columns/files remain byte-identical. Values remain request-normalized ratios;
pandas epoch conversion is only a trace-relative indexing bridge, not an
assertion of a real calendar date or a conversion to Materna percentages.

## Bootstrap and thresholds

For N nominal closing slots from first q through last q, bootstrap comprises
the first floor(0.30*N) slots. Use actual paired finite rows with q<cut.
Streaming anchor is the first actual streaming q. Bootstrap thresholds freeze
only at that anchor, from measurements completed by it; thresholds never use
streaming/future values. p20/p40/p60/p80/p95 and mean-class boundaries retain
the frozen definitions. Minimum bootstrap count remains 96 paired samples.

This is the explicit Google nominal-time split, not Materna's observed-row
helper. The old-to-new analysis cut and anchor are translated by +δ; data row
identities and nominal-slot counts are not silently changed.

Inherited bootstrap profile estimators remain as previously specified: Static
whole bootstrap; PW cadence-length trailing bootstrap window; Full-Rewrite
trailing 24h bootstrap window. Runtime 200-slot eligibility is not retroactively
imposed on initialization. No policies are instantiated in this audit.

## Trailing content, future truth and 288-slot equivalence

At read r:

- Profile inputs: closing slots `(r-24h,r]`, exactly
  `{r-287δ,...,r}`; their nominal measurement bins cover `[r-24h,r)`.
- Future targets: closing slots `(r,r+24h]`, exactly
  `{r+δ,...,r+288δ}`; bins cover `[r,r+24h)`.
- Both require >=200/288 actual paired finite slots; absent/nonfinite slots
  remain missing. No window reaches farther back to compensate for a gap.
- Class remains the class of the window mean; p95 remains the linear empirical
  quantile. No streaming profile/truth values or class accuracy are computed here.

This is an explicit **analysis-label** translation, not a modification of
canonical start labels. For an old stored-label origin b, new r=b+δ. Old stored
trailing rows `{b-287δ,...,b}` map to the new trailing closing slots; old future
rows `{b+δ,...,b+288δ}` map to the new future closing slots. Exact target count,
row identities, relative phases and physical 24h windows are preserved when the
containment audit passes. Reads/verification have explicit physical times;
start labels are never used as instantaneous availability claims.

## Reads, events and verification

Hourly evaluations remain anchor+k*1h, including missing-observation reads.
On a coincident completed observation/read: admit observation, update any
permitted residual/state, resolve eligibility/trigger, commit at most once,
then read the snapshot. With no observation at r: no observation/state/refresh
step; read the most recent committed profile at r.

Verification waits until at least r+24h, even if partial rows finish earlier.
The full closing-slot horizon must fit within the observed entity timeline.
All attached truth observations must have a<=verification read and belong to
the exact target set; no future target can leak into an earlier snapshot.

No residual algorithm is introduced: any future consumer must use admitted q
history only. A one-step prediction of the interval closing at q is constructed
from admitted history through q-δ; the target aggregate enters residual/state
only at q. Frozen Google primary policies do not require residual predictors.

## Periodic eligibility and gaps

Periodic anchor is the first streaming q. Nominal 3h/6h/12h ticks remain anchored;
missing/ineligible ticks stay pending and coalesce to the latest due tick at
resumption. Only an actual admitted observation can cause a refresh. PW retains
both >=200 paired trailing slots and its inherited 96-complete-slot history
gate; Full-Rewrite eligibility retains the >=200-slot window gate. No new
predictor or detector dependency is introduced. Periodic/read clocks do not
shift in response to a late partial interval or telemetry gap.

## Versioning and gates

The v2 Google protocol adds this clock contract while keeping V4A scientific
questions, inherited methods, endpoints, comparison families, class definitions,
statistics and unit limitations unchanged. Core `causal-timeline-v3`,
`phase-balanced-hourly-v1` and `refresh-accounting-v1` are unchanged. The new
protocol fingerprint invalidates use of the old unresolved-clock generation.

Recompute metadata/cohort wrappers with the same identity-hash selection rule;
compare member identities separately from protocol-bound manifest hashes.
A ready e contract does not complete V4C: g must be acquired and validated under
the same contract, and the final two-cell cohort must be frozen before V5.
