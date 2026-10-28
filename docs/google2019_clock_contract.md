# Google measurement, availability and read clocks — V4C.1

Contract: `google-completed-slot-availability-v1`. Protocol configuration:
`configs/google_clusterdata_2019_replication_protocol_v2.{json,yaml}`.
Cell-e interval validation: **AVAILABILITY_CONTRACT_READY** (2026-10-28).
V4C remains incomplete pending g validation/final two-cell freeze. No policy
outcomes or replication authorization. The old V4A v1 files and all
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

## Verified cell-e audit (2026-10-28)

Clean producer: `5867341972aea1e316e0a9291c0193e39ffe69e0`. Local immutable audit: `data/google2019/protocol_validation/v4c1-e-91887b860ee5e549`.
[Execution record](../configs/google2019_v4c1_validation_record.json), [independent evidence](../configs/google2019_v4c1_validation_evidence.json), [current protocol pointer](../configs/google2019_current_protocol.json), and [v2 cohort authority](../configs/google2019_replication_cohort_v2.json) pin all inputs/outputs.

| Timing quantity — retained canonical rows | Count / value |
|---|---:|
| Retained rows | 462,821,691 |
| Exact 300s intervals | 461,835,716 (99.78696439%) |
| Shorter positive intervals | 985,975 (0.21303561%) |
| Off-grid source ends | 103,998 (0.02247042%) |
| Off-grid source starts | 982,229 |
| Cross-bin/invalid duration/ambiguous rows | 0 / 0 / 0 |
| Retained overlapping pairs / duplicate slots | 0 / 0 |
| Contiguous actual interval pairs | 461,807,851 |
| Positive actual interval gaps | 856,581 |
| Gaps despite consecutive nominal bins | 724,183 |
| Gaps across missing nominal bins | 132,398 |
| Maximum actual interval gap (seconds) | 1,903,739 |

Actual durations range 1–300s; mean 299.64914995s; p50/p95/p99 all 300s. Stored-label→availability delay ranges 1–300s, mean 299.96578898s. Availability→grid-admission hold ranges 0–299s, mean 0.03421102s (p50/p95/p99 zero). All ends lie at/before their own bin close. Full frequency histograms are in `timing_histograms.json`.

The corrected generation already rejected 1,012,660 surplus same-bin rows. Among request-valid pre-dedup interval candidates, 11,123 are exact interval surplus copies across 11,123 groups; others are distinct intervals in a shared bin. Frozen max-end/min-source-SHA selection is not changed. No rejected candidate is admitted, and retained canonical observations have unique intervals/slots.

| Availability-aware metadata | Before V4C.1 | After V4C.1 |
|---|---:|---:|
| Acquisition candidates | 62,451 | 62,451 |
| Eligible entities | 62,444 | 62,444 |
| Excluded acquisition candidates | 7 | 7 |
| Bootstrap paired observations | 135,927,515 | 135,927,515 |
| Valid bootstrap exact-history rows | 126,277,913 | 126,277,913 |
| 200-slot trailing refresh opportunities | 317,572,992 | 317,572,992 |
| PW opportunities including inherited 96-slot gate | 309,116,408 | 309,116,408 |
| Nominal hourly reads | 25,030,381 | 25,030,381 |
| Verifiable hourly reads | 24,998,548 | 24,998,548 |
| Read origins without observation | 10,049 | 10,049 |

Among acquisition candidates, 62,446 meet the >=96 paired-bootstrap threshold requirement; 62,444 have >=200 actual samples in the initializer's last 24h bootstrap window (a diagnostic, not a new initialization exclusion). There are 62,450 entities with a trailing-window refresh opportunity and 62,449 with a verifiable hourly origin.

The seven unique exclusions and overlapping reasons are unchanged: five insufficient bootstrap history, one insufficient exact-window eligibility, and two zero-verifiable-origin cases. All counts, nominal periodic ticks and bootstrap thresholds match per entity. All bootstrap source intervals finish by the cut/stream anchor. An independent all-entity comparison verifies first/last/cut/anchor timestamps are exactly +300s, with identical nominal-slot counts. This is the declared closing-label projection, not an unreported row/window shift.

The existing 1,000-member e cohort has **zero additions/removals**. Member-record SHA is `72509e63e07504d905e78d7c9ace6f70b66b9b6a0c4309a29d0c175471b00b6d`. Its new wrapper SHA `992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c` changes because it binds the new protocol/clock identity, not because members or selection changed. Keep the same identity-hash salt/cap/eligibility rule for g; the final two-cell cohort remains unfrozen.

| Pinned current identity | SHA-256 |
|---|---|
| Protocol v2 fingerprint / JSON | `88e11c165a05658fe587878a66ee2816f033957efceb883062b0577d4f98a2c1` |
| Protocol v2 YAML | `c971148f289df76514b88fadf1361f515802bd99c39f9dbfdc618c010ad431ad` |
| Clock contract | `1917007869550d23fff697e508d73911a01a96e24044936b18378669341e5e94` |
| Audit manifest | `ea3a4ced23c774bf49b5a12bfa8c8b19b9720d959dae3c10b0be318696ac4863` |
| Eligibility Parquet | `2587ee8ef6975c4152a6e6bd009d6245b983c09279e47b3ef6d32ace8215ece9` |
| Provisional e cohort | `992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c` |

All corrected-generation artifacts were rehashed unchanged before/after execution. The stored start-labelled data, original V4A configs, prior blocked audit/cohort, Materna/V3 artifacts and historical logs remain untouched. RQs/methods/endpoints/F1–F3/statistics are identical to V4A; only Google clock/config identity is versioned. Zero cloud queries/bytes; billing untouched; no g acquisition and no policy outcomes.

Independent verification rescanned all retained intervals and checked completed visibility, bootstrap thresholds, read grids and verification maturity on 16 actual entities, including all seven exclusions. Full lightweight suite: **431 passed, 0 failed, 1 skipped**; **27 focused tests passed**; Python parsing/imports and CLI help passed. No incomplete aggregate passed the visibility/maturity gates.

Availability here models source-interval completion, not measured telemetry ingestion/network delay; the trace provides no delivery timestamps. No operational delivery guarantee or system benefit is inferred. **V4C.1 PASS / AVAILABILITY_CONTRACT_READY for e. V4C is incomplete and V5 is blocked until g acquisition/validation under this same contract and the final two-cell cohort freeze.** New g staging/disk/budget preflight remains necessary.
