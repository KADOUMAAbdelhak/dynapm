# DynAPM

DynAPM is a research implementation for application-profile maintenance. The simplified architecture uses exact trailing observation-window content and deterministic refresh scheduling/accounting. Bounded development studies did not justify learned profile generation, RF-residual timing, Reactive timing, or direct-observation ADWIN timing; those implementations remain isolated experimental controls for reproducibility. Scope redesign (V2.4G) recommends an empirical/methodological contribution path, not adaptive-algorithm confirmation. Protocol correctness does not establish scientific benefit or a system-level contribution.

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

Follow the [validation strategy](docs/validation_strategy.md) and [gated roadmap](docs/validation_roadmap.md). V0 (causal protocol), V1A (uniform accounting), and **V1B / Phase 2C provenance** passed. **V2 — Bounded Scientific Pilot PASS** under gap-safe `causal-timeline-v3` and `phase-balanced-hourly-v1`. **V2.5 / V2.5A — Empirical Contribution Freeze PASS** as an estimation-first confirmatory design ([freeze](docs/confirmatory_design_freeze.md)). **V3 — Materna confirmatory estimation PASS** ([results](docs/materna_confirmatory_results.md)). **V4A — independent corpus selection PASS** ([Google 2019](docs/independent_corpus_selection.md)); **V4B / V4B.1 = BLOCKED** ([acquisition](docs/google2019_acquisition.md); ADC + billing project required). C1/C2 are withdrawn; C3/C4 remain UNPROVEN. See [pilot diagnostics](docs/bounded_pilot.md) and [gap eligibility](docs/materna_gap_semantics_v3.md). Profile-level practical margins are not defined; statistical significance alone does not establish operational benefit. Manuscript drafting follows the evidence/claim audit, not implementation completion.

## Provenance tooling

See [experiment provenance and cache integrity](docs/provenance.md). Experiments use separate deterministic fingerprints and physical run IDs, explicit configuration/input/cohort/environment manifests, and verified output hashes. Smoke/pilot outputs never satisfy claim caches; dirty claim overrides remain noncanonical. Legacy directory-based corpus/report entry points now refuse unmanaged execution rather than reuse old outputs. Current compute APIs remain available for a separately authorized managed pilot; no corpus driver was run in Phase 2C.

```sh
python -m dynapm.scripts.provenance --help
python -m pytest
```
