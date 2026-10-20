# DynAPM

DynAPM is a research implementation for adaptive application-profile maintenance. It includes predictor-grounded and drift-augmented profile refresh. The current development version uses causal feature construction and causal multi-step forecasting. Development is ongoing, and policy integration is still being validated.

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

Run `python -m pytest dynapm/tests/test_dynapm_v3.py` to see the currently known constructor-integration failures. The full suite also contains data-dependent and model-training tests; review [development notes](docs/development.md) before running it.

## Layout

- `dynapm/core/`: feature construction, RandomForest forecasting, profile schemas, ground truth, and drift handling.
- `dynapm/data/`: dataset loading, filtering, bootstrap characterization, and capacity extraction.
- `dynapm/methods/`: observation-based baselines, predictor refresh, and DynAPM-V3.
- `dynapm/eval/`: snapshot-and-verify evaluation, provisioning metrics, and statistical helpers.
- `dynapm/scripts/`: experiment orchestration, provisioning analysis, and result aggregation.
- `dynapm/tests/`: unit and integration tests, including Periodic-Predictor integration.

See [data setup](data/README.md), [output handling](results/README.md), and [development notes](docs/development.md). Keep each new experiment's configuration and provenance with its external outputs.
