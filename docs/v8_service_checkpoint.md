# V8C-R.2 slot checkpoint component (not a qualified executor)

Frozen scientific source: `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`.
Qualified transport ancestor: `b3fd0d1fa095dbaa13c2b035624d6336b24d60ca`.
No frozen scientific file or existing transport implementation is changed by this component.
No claim-launch command is provided or enabled.

## Blocking timing decision

The original `bounded_v8_runtime.episode` waits for T0, dispatches the snapshot
recommendation and calls `actuate` while `stream_requests` independently offers
requests from T0. The resize latency is therefore inside the primary and
first-five-minute transition windows. Resources during that transition are
integrated using observed patch-ack and enforcement timestamps.

The V8C-R.2 instruction also says measured exposure cannot start before target
enforcement is verified. That would require one of: applying the target before
T0 (changing the reference-resource warm-up), delaying the offer schedule after
T0, or redefining T0 after enforcement. Each changes frozen primary timing.
These alternatives must not be selected implicitly. The timing choice was sent
as a required clarification before any live qualification. Until resolved, no
full-lifecycle executor or 75-minute qualification is represented as complete.

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

No start/resume/stop *live* CLI exists yet. Claim execution remains disabled.
A future CLI must call the same primary implementation for diagnostic and claim
scopes, require explicit resume, and apply --max-slots/--stop-after-slot only
after a slot is sealed and independently verified.

## Still required

Resolve T0/enforcement ordering; implement and version primary Service
orchestration; bind generator/Linux T0 and host controller observations without
subtracting unrelated monotonic domains; integrate full amended preflight;
verify target/snapshot and all telemetry; seal/recover node and host results;
certify complete peak storage including Docker growth; run the real 75-minute
non-claim qualification; freeze its evidence separately. No claim execution is
authorized merely by the persistence tests.
