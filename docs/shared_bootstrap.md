# Shared measured-bootstrap implementation contract

V7C.4 decouples reusable measured initialization from a72h anchor. A genuine
bootstrap-only acquisition is sufficient; a48h measurement phase is not required.
The ordinary path requires a completed genuine24h acquisition. V7C.8
separately supports verified derivation from a boundary-failed acquisition. Unit
fixtures and failed warm-up samples are not production evidence. Synthetic unit parents require an explicit
test-only creation path, remain labelled UNIT_TEST_ONLY, and are refused by
production creation and all pilot/claim block/treatment initialization paths. No collection was run in this phase.

## Frozen inputs and immutable artifacts

`configs/system_shared_bootstrap_v1.json` pins the implementation contract.
Artifact schema `shared-measured-bootstrap-v2` requires a clean managed pilot
acquisition SUCCESS and valid output hashes, measured-bootstrap provenance,
24h acquisition within the parent's real execution interval, source Pod/app IDs,
hardware/image identities, fixed reference resources, actual source/receipt clocks,
and supported host-continuity provenance. It reconstructs all288nominal slots,
requires>=200paired slots and final96complete, and permits no filling or counter
reset. The raw samples retain original bytes. Integrity establishes consistency
with recorded producer provenance, not cryptographic attestation of physical
hardware: producer code and execution evidence remain auditable.

The content-addressed directory stores raw bootstrap plus parent manifest,
SUCCESS/output-manifest and bootstrap/plan/host metadata snapshots. It copies no
measurement-phase requests/results, no initialized profile and no controller state.
Every file has a recorded size/hash. Creation never overwrites an existing
artifact. COMPLETE is written last; loads require an explicitly trusted expected
artifact hash, exact inventory, canonical completion marker, file/lineage hashes,
supported schema and raw reconstruction. Symlinks, incomplete artifacts, changed
bytes, synthetic/incomplete parents and stale contracts are rejected. Relocation
does not alter identity. Generated artifacts belong under ignored results paths.

```sh
# Preparation only; requires a future completed genuine acquisition.
python -m dynapm.scripts.task36_shared_bootstrap freeze \
  --acquisition-run <managed-bootstrap-acquisition> --artifact-store results/shared_bootstrap
python -m dynapm.scripts.task36_shared_bootstrap validate \
  --artifact <artifact-directory> --expected-sha256 <frozen-artifact-sha>
```

Future guarded collection has an explicit `task34 --collect-bootstrap-only`
mode, requiring compatible endurance evidence. It retains cooldown/warm-up,
collects24real hours at fixed resources, validates bootstrap and source Pod
continuity, and finishes with zero policy initializations or measurement phase.
It has no automatic calibration continuation. **Do not launch it without a
separate collection instruction and approved host conditions.**

## Blocks and treatment isolation

`freeze_blocks` creates outcome-blind identity-hash/cyclic method orders with the
existing seed20251022, not a precision-derived repetition count. Each independent
block must have a distinct independently collected artifact/run/source instance;
serial acquisition intervals cannot overlap. All five treatments in a block share
that artifact. Common stable prehistory across scenarios is explicit in the
estimand. No measurement outcome participates in block design.

Only the initialization VIEW is mapped to a treatment's logical origin; original
raw acquisition clocks and availability remain unchanged. The artifact must have
been available before that origin. This is reused measured prehistory, not a claim
that old samples were collected from the new Pod or represent continuous live
telemetry immediately before it.

`TreatmentRegistry.initialize` validates startup/reset identities, allocates fresh
copied history and a fresh policy through unchanged production factories. Static
keeps whole-bootstrap initialization, PW keeps its cadence-length initialization,
and Full-Rewrite keeps trailing24h initialization. Shared raw input does not mean
silently replacing method-specific initialization rules. Mutation in one policy
cannot affect another. Reused treatment IDs, Pod/app/controller/profile/telemetry
IDs, duplicate matrix entries or nonzero initial runtime state are rejected.
The real runner must obtain these identities/reset evidence from fresh deployments;
the library does not claim that synthetic unit tests demonstrate physical resets.

Initialization including load/validation is timed; initialization and initial
resource actuation remain inside each treatment's measured interval. The library
performs no pre-actuation. It reuses no measurement outcomes or mutable snapshots.
A future five-method system executor still needs separately authorized deployment
and runtime integration validation. No comparative trial is enabled by this API.

V7C.6 uses [separate cluster/host clocks](system_clock_domains.md): host-receipt
slot membership, validated cluster source causality and host admission before use.
Failed parents cannot enter the ordinary SUCCESS-parent artifact path. V7C.8 adds the explicitly labelled, independently validated derivation path below.


## V7C.8 receipt-boundary correctness repair

The V7C.7 collector sampled `now` before polling, received and admitted a complete
response, then appended it to the current pending buffer. When the pre-request
clock reached the scheduled `next_q`, aggregation filtered that buffer but durable
`bootstrap_samples.jsonl` stored the entire unfiltered buffer. A just-late receipt
therefore entered the earlier bucket's persisted evidence and stayed buffered for
the next bucket too. The defect was buffer persistence, not an invalid source or
host clock. Final strict validation correctly refused the original evidence.

The corrected selector uses actual accepted `received_at_ns` in `[start,end)` for
both aggregation and persistence. Receipts before bootstrap start or at/after its
end are excluded. Boundary receipts enter the following bucket, once. Elapsed
buckets close after complete-response receipt, independently of poll scheduling.
Sample source, receipt, admission, indices and raw envelope/source bytes never
change. The measured evidence hash schema is now `measured-system-bootstrap-v3`.
Per-bucket >=50 samples and >=270 seconds, paired >=200 and final96 complete,
resources, age/causal checks and policy-specific initialization windows stay fixed.

`receipt_derivation.create_generation` requires an independently trusted complete
parent-file hash inventory and the specific final bucket-validation failure from
a clean pilot bootstrap-only acquisition. It snapshots the failed parent unchanged,
verifies accepted records against exact source/envelope bytes and clock manifests,
reconstructs chronological host assertions/power/boot/policy and Pod/resource
continuity, reconciles requests and zero controller changes, then partitions raw
accepted telemetry. All288 corrected buckets must pass; no filling, extension,
replay, tolerance, source-time reassignment or pulling a terminal receipt backward
is supported. Failed coverage yields a BLOCKED generation and cannot make an artifact.
The original parent always remains FAILED, including its unfinished controller
completion flag after cleanup. This path does not synthesize a parent SUCCESS.

The immutable `receipt-rebucket-generation-v1` binds original run/source/config and
all parent files, corrected implementation commit/file hashes, derivation config
and exact corrected-file bytes. Independent load reconstructs the generation.
`create_derived_artifact` then creates a new `shared-measured-bootstrap-derived-v1`
artifact, labelled `MEASURED_24H_DERIVED_FROM_FAILED_ACQUISITION`, retaining that
complete lineage. `load_artifact` supports this separate schema with an externally
trusted expected SHA. Artifact availability is the actual derivation/artifact
creation time, never backdated to the raw acquisition. Samples retain their
original availability/admission clocks. Synthetic fixtures require explicit test
creation and remain UNIT_TEST_ONLY, forbidden in pilot/claim treatments.

This is an explicitly documented correctness fix before comparative outcomes.
A valid derived scientific prehistory does not qualify the current boot or erase
the authorized battery-drain deviation: claim disposition remains
NOT_AUTOMATICALLY_CLAIM_ELIGIBLE pending separate qualification/review. No new
acquisition, deployment, measurement or comparative experiment is enabled here.
