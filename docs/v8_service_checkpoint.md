# V8C-R.2 slot checkpoint component (not a qualified executor)

Frozen scientific source: `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`.
Qualified transport ancestor: `b3fd0d1fa095dbaa13c2b035624d6336b24d60ca`.
No frozen scientific file or existing transport implementation is changed by this component.
Claim execution additionally requires a separately sealed passing primary-executor qualification.

## Timing decision

The user explicitly chose to preserve frozen T0: target dispatch and measured
offers begin at T0; enforcement latency remains in the transition. A causal
source marker and host receipt link the two domains. No enforcement gate delays
the measured offer schedule. See `v8_service_primary.md` for the executor and
clock limitations. The earlier checkpoint-only commit did not qualify a live
executor.

## Persistence implemented

`service_checkpoint.py` is an offline, runtime-independent persistence component:

- Exact ordered 18-cell matrix from the frozen `cells()` function.
- Campaign identity hash binds caller-supplied source/config/snapshot/amendment
  identities and scope. Host-session identity is separate from campaign identity.
- Each slot records cell, status, treatment ID, manifest path/hash, request hash,
  endpoint hash, continuity hash, start/end timestamps and session binding.
- States: PENDING, RUNNING, SEALED_VALID, SEALED_INVALID, INTERRUPTED.
- Exclusive advisory campaign lock must span execution and checkpoint publication.
- Same-directory atomic rename, file fsync and directory fsync.
- Checkpoint writes enforce 20 GiB reserve; this does not substitute for guards
  on future generator/telemetry/Docker writes.
- Every sealed manifest and inventoried output is rehashed on verification.
  Request, endpoint and continuity files must be included explicitly.
- Exact contiguous prefix; no gaps, duplicate treatment IDs or skipped slots.
- No automatic rerun of valid slots. Invalid/interrupted slots require review.
- On launcher restart, a surviving RUNNING record becomes INTERRUPTED and the
  next-slot operation refuses to proceed. Partial evidence is retained.
- Scope-bound identity prevents diagnostic/claim mixing.
- Stop-limit predicate is evaluated only by a future executor after sealing.
  It does not interrupt a treatment.

The component verifies the supplied manifest and identity; it does not itself
certify completeness of telemetry, physical enforcement, clocks or host
preflight. Those remain required responsibilities of the integrated executor.
Hash verification detects alteration relative to the trusted checkpoint; it is
not a cryptographic signature against an adversary rewriting all local evidence.

## Offline verification

Tests exercise two sealed fixture slots followed by resume at slot 3, new host
session binding, exact order, explicit resume, manifest/payload tampering,
noncontiguous prefixes, interruption review, invalid-slot stop, concurrent lock
ownership, atomic reserve failure, stop limits and all 18 frozen offer schedules.
Fixtures are synthetic and are not physical cluster recreation or host
qualification proof.

The versioned live CLI and qualification requirements are documented in
`v8_service_primary.md`. Persistence fixtures remain synthetic and do not replace
the required full physical qualification.
