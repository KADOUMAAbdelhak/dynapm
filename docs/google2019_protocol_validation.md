# Google corpus/cohort protocol validation — V4C

Status: **PENDING full local metadata audit**. No replication authorization.
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
