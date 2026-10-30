# Shared measured-bootstrap implementation contract

V7C.4 decouples reusable measured initialization from a72h anchor. A genuine
bootstrap-only acquisition is sufficient; a48h measurement phase is not required.
No genuine completed24h artifact exists yet. Unit fixtures and failed warm-up
samples are not production evidence. Synthetic unit parents require an explicit
test-only creation path, remain labelled UNIT_TEST_ONLY, and are refused by
production creation and all pilot/claim block/treatment initialization paths. No collection was run in this phase.

## Frozen inputs and immutable artifacts

`configs/system_shared_bootstrap_v1.json` pins the implementation contract.
Artifact schema `shared-measured-bootstrap-v1` requires a clean managed pilot
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
