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

Each target has its own fitted predictor. `forecast_at_origin` filters observations to timestamps at or before the refresh origin. The predictor recursively appends predictions for its 288 future steps. Initialization uses bootstrap observations; refreshes use the causal horizon. Origins without 96 complete exact nominal slots are rejected, never bridged across gaps.

All policies implement `step(t, cpu_obs_window, mem_obs_window)`. DynAPM-V3 additionally accepts keyword-only `cpu_prediction` and `mem_prediction`: the current causal one-step predictions, not future arrays; unavailable predictions are None and pause ADWIN. Its ADWIN inputs are `observation(t) - prediction(t|t-1)`.

## Shared replay

Evaluation and provisioning both call `prepare_vm_replay` and `iter_verified_snapshots` in `dynapm/eval/replay.py`. Preparation fits CPU/memory predictors once per replay, on the first 30% bootstrap segment. Thresholds and provisioning capacity are derived from bootstrap data directly. Observation-only policies fit no models. V3 recomputes causal one-step predictions with the same fitted models; replay does not load cached residuals.

See [the temporal protocol](protocol.md) for the shared periodic grid, ordering, missing-observation rules, and exact forecast/label boundaries. Replay uses available bootstrap history and exact-grid eligibility, with nominal hourly reads independent of observations. Labels are derived in memory under the current convention; cached ground-truth files are not read. Snapshot copies are verified only once their 24-hour horizons have elapsed. Forward ground truth never enters policy construction or policy steps. `repo_root` supports isolated fixtures; `predictor_factory` supports lightweight test doubles or explicitly configured predictors.

The evaluation/provisioning compute APIs use the same factories. Legacy standalone Task 04/15/17b/18 orchestration now refuses unversioned execution; use an explicit managed run as described in [provenance](provenance.md). New outputs identify `causal-timeline-v3`; unversioned JSONs/tables are not accepted as current causal measurements. The separate `refresh-accounting-v1` schema is also required on per-VM results and summaries. These compatibility markers alone are not complete provenance; Phase 2C adds source/config/input/cohort/environment fingerprints and output integrity. Do not mix source revisions or experimental generations. Corpus-level provenance and performance validation remain separate research work.

## Lightweight validation

```sh
python -m pytest
python -m dynapm.scripts.task17b_provisioning --help
python -m dynapm.scripts.task18b_corpus_churn_rerun --help
python -m dynapm.scripts.provenance --help
```

Policy integration tests use one 720-row synthetic VM and a deterministic causal test double. Predictor tests use tiny forests. The two loader checks require the local Materna CSV fixtures described in `data/README.md`; other tests use synthetic data. No test runs full Task 15, provisioning corpus replay, or production model training.

Full corpus jobs, production-size forests, and extensive recursive inference require separate authorization. Standalone legacy corpus/report drivers are retired and reject unmanaged execution. Their pure compute/analysis helpers remain library APIs, not cache readers or claim-eligible outputs. The new provenance CLI performs metadata tooling only.

## Scientific state

Feature vectors for a target timestamp exclude that timestamp's actual utilization. Refresh snapshots can use actual observations through their origin, recursive predictions thereafter, and deterministic calendar information. CPU and memory models do not share utilization features. These properties are covered by invariance tests.

Small-fixture correctness does not establish corpus-level accuracy, drift effectiveness, or operating cost. Historical publication measurements are not an acceptance target for causal development.

## Accounting and analysis

Every policy delegates initialization and runtime assignments to `ProfileCommitter`. Read `accounting_metrics()` or the counters in `run_method_on_vm` results. Use `n_refresh_events` for runtime maintenance cost; field writes and actual changes are independent secondary quantities. Initialization is excluded from runtime counts.

Use `dynapm.eval.metrics.summarize_accounting` on per-VM summary rows for counter means and medians. It validates the accounting schema, nonnegative integer counters, write counts, and trigger decompositions. Do not reconstruct counts from event traces or sum repeated per-evaluation provisioning outcome rows. Provisioning executes the same policy commit path and exposes per-VM counters in `pairs.attrs["policy_accounting"]`; its per-evaluation outcome rows remain distinct from per-VM accounting summaries. These attributes are not summed across outcome rows; concatenated corpus outcome tables should use the separate canonical per-VM summary for accounting.

See [Refresh Accounting](protocol.md#refresh-accounting) and [the reference audit](accounting-audit.md). Old counter schemas require fresh, separately authorized experimental generations; this phase does not regenerate outputs.

## Single-project governance

The sole authoritative active repository is `/Users/fgtek002/dynapm`, branch `dynapm`. This absolute location identifies the workstation project only. Scientific code must use repository-relative paths or explicit configuration and must not hard-code the user's home directory.

Historical TOCS evidence exists as an immutable external archive, not an alternate implementation tree. The frozen original publication reference is also inactive. Neither may be loaded automatically by current experiments, used as a fallback cache, or described as current causal results. See the [consolidation record](consolidation_record.md) for archive identity and verification; historical provenance paths must not be rewritten into runtime defaults.

The [validation strategy](validation_strategy.md) governs intended claims, corpus selection, fair controls, statistics, overhead, real systems evidence and reproducibility. The [roadmap](validation_roadmap.md) records V0/V1A/V1B/V2 PASS and V2.5 NEXT. Phase 2C implements and tests complete manifests/fingerprint-based cache rejection. Before any new full-corpus run, obtain a bounded-pilot scope, bind explicit configs to current compute APIs, validate managed outputs and freeze confirmation criteria. No scientific benefit is inferred from the passing lightweight suite.

## Managed experiments

Use `prepare_experiment` with freshly checked dataset/cohort manifests, then `RunSession` with a purpose and predeclared output coverage. Configuration serialization is explicit: drivers must honor the recorded values, not infer settings from callable reprs. Use `check_cache` or `load_verified_output` as the only reuse decision; never bypass with filenames, protocol labels or a directory glob. A dirty claim override can finish only as DEVELOPMENT_NONCANONICAL; no cache option makes it canonical.

Schema versions, CLI examples, exact legacy-path audit, cache rejection reasons and input identities are in [provenance.md](provenance.md). [Observed-row lag assessment](lag_semantics_assessment.md) records temporal-distance distributions without changing features or horizons. Current package versions are checked against imported distributions. Future dependencies and timing-sensitive hardware must be explicitly added to compatibility; this infrastructure cannot infer hidden scientific inputs.

Historical Phase 2C validation: 195 passed, 0 failed, 0 skipped; raw manifests and a metadata-only managed smoke check verified. No corpus evaluation, interval experiment, provisioning replay, Kubernetes trial or historical-result rewrite was performed. The next pilot must check config-to-execution binding, required coverage/failures, numerical determinism and runtime feasibility. Provenance integrity is not scientific validation.

## Bounded managed pilot

[Phase 3A / V2](bounded_pilot.md) adds an exactly 18-VM / 198-evaluation managed driver, shared frozen per-VM predictors, an analysis-only exact budget counterfactual and timestamp-only all-retained gap audit. It refuses dirty scientific execution and cannot become a full-corpus run. Synthetic tests may inject cheap predictors; real runs use the recorded RF configuration. Output manifests and cache probes must pass. A complete pilot is not confirmation; the selected entities are excluded from the primary future confirmatory cohort. See the pilot document for the preconfirmation gap gate and no-tuning rule.

Historical Phase 3A v2 execution: 198/198 completed; 223 unit tests passed, zero failures/skips; independent artifact/count/schedule reconciliation passed. V2 is BLOCKED on [gap handling](materna_gap_audit.md), with source/run/output identities and permanent pilot pairs in [bounded_pilot.md](bounded_pilot.md). Correct gap semantics and evaluation phase coverage in a separately authorized task and rerun bounded validation before full experiments. No implementation commit is pushed while the requested final V2 PASS condition is unmet.

## Phase 3A-R remediation

Current semantics are [causal-timeline-v3](protocol.md), `phase-balanced-hourly-v1`
and unchanged `refresh-accounting-v1`. The earlier v2 pilot remains a frozen
readiness failure, not an input/cache for the corrected generation. The same 18
development entities were rerun from clean committed source; verified identities are below. Full-corpus work
remains blocked; V2.5 must freeze confirmatory design before V3. Exact-grid
metadata-only eligibility characterization may inspect all retained entities,
but must not fit predictors or execute policies on that cohort.

## Verified remediation status

V2 PASS: 256 tests passed, 0 failed, 0 skipped; the corrected clean-source pilot completed 198/198. See [immutable run identities and diagnostics](bounded_pilot.md). V2.5 is NEXT. V3 remains BLOCKED UNTIL V2.5. Earlier blocked-pilot statements above document their historical generation and do not describe the current gate. No new model/policy tuning or full-corpus execution was performed.
