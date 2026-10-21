# DynAPM

DynAPM is a research implementation for adaptive application-profile maintenance. It includes predictor-grounded and drift-augmented profile refresh. The current development version uses causal feature construction and causal multi-step forecasting. Development is ongoing. Causal interface, timeline and refresh-accounting correctness passed their lightweight validation gates; scientific benefit and system-level validation remain open.

Datasets and generated outputs are external or untracked. Historical publication results are not stored in this repository.

## Environment

Use Python 3.13 (the currently checked development environment), or validate another compatible version against the requirements.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Lightweight checks

The following tests use synthetic inputs and do not train models or require the corpus:

```sh
python -m pytest dynapm/tests/test_drift.py dynapm/tests/test_evaluation_clock.py dynapm/tests/test_forecasting.py dynapm/tests/test_provisioning.py
```

The full suite (`python -m pytest`) includes small synthetic policy replays and tiny RandomForest fixtures. Two CSV-loader checks additionally use local raw traces. No test runs a corpus experiment. See the [causal dependency contract and development notes](docs/development.md).

## Layout

- `dynapm/core/`: feature construction, RandomForest forecasting, profile schemas, ground truth, and drift handling.
- `dynapm/data/`: dataset loading, filtering, bootstrap characterization, and capacity extraction.
- `dynapm/methods/`: observation-based baselines, predictor refresh, and DynAPM-V3.
- `dynapm/eval/`: snapshot-and-verify evaluation, provisioning metrics, and statistical helpers.
- `dynapm/scripts/`: experiment orchestration, provisioning analysis, and result aggregation.
- `dynapm/tests/`: unit and integration tests, including Periodic-Predictor integration.

See [the temporal protocol](docs/protocol.md), [data setup](data/README.md), [output handling](results/README.md), and [development notes](docs/development.md). Keep each new experiment's configuration and provenance with its external outputs.

## Project authority and research gates

The sole authoritative active project for current code, experiments and development is `/Users/fgtek002/dynapm`. Use repository-relative paths and configuration in runtime code; this workstation identity is documentation only.

Historical TOCS material is retained as an immutable external archive, not a second working project. The separately frozen original publication directory remains reference-only. Runtime code must never reference or automatically load that archive/publication material. Archive identity, integrity checks and the scoped duplicate search are documented in the [consolidation record](docs/consolidation_record.md).

Follow the [validation strategy](docs/validation_strategy.md) and [gated roadmap](docs/validation_roadmap.md). V0 (causal protocol), V1A (uniform accounting), and **V1B / Phase 2C provenance** passed. **V2 — Bounded Scientific Pilot PASS under gap-safe causal-timeline-v3 and phase-balanced-hourly-v1. V2.5 — Confirmatory Design Freeze is NEXT; V3 is BLOCKED UNTIL V2.5.** See [pilot diagnostics](docs/bounded_pilot.md) and [gap eligibility](docs/materna_gap_semantics_v3.md). No full-corpus claim-generating run is authorized before the design freeze. Implementation completion, statistical significance and offline accuracy alone do not establish a systems contribution. Manuscript drafting follows the evidence/claim audit, not implementation completion.

## Provenance tooling

See [experiment provenance and cache integrity](docs/provenance.md). Experiments use separate deterministic fingerprints and physical run IDs, explicit configuration/input/cohort/environment manifests, and verified output hashes. Smoke/pilot outputs never satisfy claim caches; dirty claim overrides remain noncanonical. Legacy directory-based corpus/report entry points now refuse unmanaged execution rather than reuse old outputs. Current compute APIs remain available for a separately authorized managed pilot; no corpus driver was run in Phase 2C.

```sh
python -m dynapm.scripts.provenance --help
python -m pytest
```
