# Causal policy interface and validation

## Dependency contract

Policies declare `requires_predictors` and `requires_residuals` on their classes. Use `dynapm.methods.factories.policy_factory(method)` or a policy class / `functools.partial` of that class. Opaque callable factories are rejected; requirements are never inferred from function names.

Every constructor receives a profile, CPU/memory thresholds, and keyword-only bootstrap CPU/memory series. Observation-only policies require no predictors or prediction artifacts.

Periodic-Predictor and DynAPM-V3 additionally require four explicit keyword-only dependencies:

```python
cpu_predictor=cpu_predictor,
mem_predictor=mem_predictor,
cpu_obs_full=cpu_observations,
mem_obs_full=memory_observations,
```

Each target has its own fitted predictor. `forecast_at_origin` filters observations to timestamps at or before the refresh origin. The predictor recursively appends predictions for its 288 future steps. Initialization uses bootstrap observations; refreshes use the causal horizon. Short histories without 96 observations produce no horizon.

All policies implement `step(t, cpu_obs_window, mem_obs_window)`. DynAPM-V3 additionally requires keyword-only `cpu_prediction` and `mem_prediction`: the current causal one-step predictions, not future arrays. Its ADWIN inputs are `observation(t) - prediction(t|t-1)`.

## Shared replay

Evaluation and provisioning both call `prepare_vm_replay` and `iter_verified_snapshots` in `dynapm/eval/replay.py`. Preparation fits CPU/memory predictors once per replay, on the first 30% bootstrap segment. Thresholds and provisioning capacity are derived from bootstrap data directly. Observation-only policies fit no models. V3 recomputes causal one-step predictions with the same fitted models; replay does not load cached residuals.

See [the temporal protocol](protocol.md) for the shared periodic grid, ordering, missing-observation rules, and exact forecast/label boundaries. The replay grid preserves streaming-only feature warmup. Labels are derived in memory under the current convention; cached ground-truth files are not read. Snapshot copies are verified only once their 24-hour horizons have elapsed. Forward ground truth never enters policy construction or policy steps. `repo_root` supports isolated fixtures; `predictor_factory` supports lightweight test doubles or explicitly configured predictors.

Task 15, provisioning, and event-log orchestration use the same factories. New outputs identify `causal-timeline-v2`; unversioned JSONs/tables are not accepted as current causal measurements. This protocol marker is a compatibility guard, not a complete input/source/environment provenance manifest. Do not mix source revisions or experimental generations. Corpus-level provenance and performance validation remain separate research work.

## Lightweight validation

```sh
python -m pytest
python -m dynapm.scripts.task17b_provisioning --help
python -m dynapm.scripts.task18b_corpus_churn_rerun --help
```

Policy integration tests use one 720-row synthetic VM and a deterministic causal test double. Predictor tests use tiny forests. The two loader checks require the local Materna CSV fixtures described in `data/README.md`; other tests use synthetic data. No test runs full Task 15, provisioning corpus replay, or production model training.

Full corpus jobs, production-size forests, and extensive recursive inference require separate authorization. Some orchestration scripts execute `main()` without a help parser; do not invoke them as smoke checks.

## Scientific state

Feature vectors for a target timestamp exclude that timestamp's actual utilization. Refresh snapshots can use actual observations through their origin, recursive predictions thereafter, and deterministic calendar information. CPU and memory models do not share utilization features. These properties are covered by invariance tests.

Small-fixture correctness does not establish corpus-level accuracy, drift effectiveness, or operating cost. Historical publication measurements are not an acceptance target for causal development.
