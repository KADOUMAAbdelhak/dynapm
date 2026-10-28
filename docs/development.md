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

V2 PASS: the corrected clean-source pilot completed 198/198. See [immutable run identities and diagnostics](bounded_pilot.md). The later V2.4 investigation chain supersedes “V2.5 is NEXT”: V2.5/V3 are blocked pending a non-adaptive scope decision after V2.4F. Earlier blocked-pilot statements above document their historical generation and do not describe the current gate.


## Observation-content candidate (V2.4E)

The candidate policies live in `dynapm/methods/observation_timing.py`. Their
`requires_predictors` flag is false: no profile-content models are accepted.
`AdaptiveResidualPolicy.requires_residuals` is true. Standalone replay prepares
one-step models when either dependency flag requires them and passes only current
causal prediction scalars to residual policies. WindowPeriodic/BudgetMatched need
no RF at all. In a managed matrix, two target-specific models are fitted once and
their one-step streams are shared only with Adaptive. Recursive forecasting is
explicitly prohibited by the bounded experiment's adapter.

Use `python -m dynapm.scripts.task25_adaptive_timing --help` for the fixed-18 managed
study interface. No unbounded cohort or parameter override is available. Legacy
PP/V3 modules and previous experiment drivers retain their historical development
interfaces; do not interpret them as the final candidate. See the [timing
investigation](adaptive_timing_investigation.md) and [protocol](protocol.md).


V2.4E completed validly but recommends **no retained prediction component**.
The residual-only policy above is a frozen experimental control, not an accepted
final signal. See [the disposition](adaptive_timing_investigation.md) before
choosing architecture/baselines. Keep both C1 and residual-driven C2 unsupported;
V2.5/V3 remain blocked pending scope review. Compatibility field names
`predicted_*_p95_next_24h` are inherited storage names; the new policies place
paired observation-window p95 values there and do not generate future samples.

## Predictor-free trigger disposition (V2.4F)

`ReactiveWindowPolicy` and `ADWINObservationPolicy` are fixed experimental
controls in `observation_timing.py`. Reactive preserves the legacy six-hour
class-transition trigger in separate trigger state while all profile commits
remain common 24h observation-window content. ADWIN consumes current CPU/memory
observations directly at delta `.002`. Neither constructs predictors.

Use `python -m dynapm.scripts.task26_predictor_free_adaptive --help` only for the
fixed-18 managed interface. The first generation is invalid because periodic
content reset Reactive trigger state and its resource aggregates were omitted.
Corrected source keeps the six-hour shadow independent of periodic commits and
records both aggregates. Its valid disposition is **ADAPTIVE MAINTENANCE NOT
JUSTIFIED**. Reactive/ADWIN remain reproducibility controls, not accepted
architecture; do not tune or add triggers. V2.5/V3 remain blocked pending a
non-adaptive scope decision; see the [investigation](predictor_free_adaptive_investigation.md).


## Supported staged Google evaluator — V4D

Use `python -m dynapm.scripts.task30_google_replication --help`; default invocation
is input verification only. Real outcomes require explicit `--execute`, a clean
committed source state and the exact frozen cohort manifest. V4D itself executes
only synthetic fixtures. See [the prospective contract](google2019_staged_replication.md).

The Google adapter projects completed bins to closing q and uses a nominal-time
bootstrap split, then calls existing `PreparedVM`/factories/shared replay/metrics/
accounting/statistics. It fits no model. Physical request ratios use legacy internal
CPU/memory column aliases without percent rescaling; unavailable provisioning
capacities are null. `parquet-shards-v1` extends the input inventory without changing
the Materna CSV adapter. All canonical shard/input/cohort hashes are verified;
no old canonical generation, unmanaged output, arbitrary cohort or incomplete
run is reusable. Each cell is separate and g is refused until validated inputs
are bound. Frozen scientific source hashes prevent silent post-e changes.

Current staged status supersedes historical next-gate prose above: V4D PASS, V5A
NEXT (not run), V5B BLOCKED; overall V4C incomplete. No Google policy outcomes,
BigQuery calls, g acquisition or Materna result changes occur in this task.


## V4E — sealed Stage-A execution

[Stage-A e findings](google2019_stage_a_results.md) and
`configs/google2019_v4e_validation_record.json` identify the exact clean source,
scientific fingerprint/run, immutable outputs and independent managed verifier.
All 5,000 evaluations and output/statistical checks pass; no production code was
changed. Generated scientific outputs remain ignored and untouched. The factual
documentation commit is separate from the execution source commit.

Current status supersedes prior V4D readiness prose: Stage A PASS, Stage B required
and unexecuted, V4C incomplete, V5 blocked until g replication. Do not reinterpret
e estimates as practical/operational benefit or change any frozen g parameter,
selection or statistical rule. No cloud/g/Materna-result access is authorized by
this status note.


## V4F — separate collection robustness postprocessor

`python -m dynapm.scripts.task31_google_collection_robustness --cell g` validates
the secondary spec only, without reading primary outcomes or g data. Future
authorized postprocessing requires `--execute --primary-run PATH`, clean
committed source, a sealed matching-cell canonical primary, and exact frozen
spec/source/parent hashes. It runs no policies or acquisition.

The output is a new managed derived generation; original primary files and
statistics remain untouched. Every summary labels e post-hoc versus g
prospective secondary. Technical canonical-purpose provenance never promotes a
post-hoc result to preregistered primary evidence. See [the formulas, scope,
failure rules and reporting contract](google2019_collection_robustness.md).
V4F runs identity-only e metadata and synthetic tests, not real sensitivities.


## V7A system harness

See [system validation design](system_validation_design.md). The default
`python -m dynapm.scripts.task32_system_harness` validates the source-bound
config without deployment. Only `--smoke` creates a unique local kind cluster,
using one Full-Rewrite policy, synthetic bootstrap and one real completed five-
minute telemetry bucket. Clean committed source is required. No comparative or
claim-generating command exists. Runtime results are ignored under
`results/system/`; private Kubernetes credentials stay outside results/Git.
System trials require a separate precision/replication/environment freeze.


V7A has one verified real-cluster smoke; see the factual record in
`configs/system_v7a_smoke_validation_record.json`. It proves completed telemetry,
profile-service serialization, fixed recommendation and actual resize plumbing.
It uses a synthetic bootstrap and must never be reused as comparative/system
claim evidence. Optional pinned CLI tools are installed only under ignored
`.local-tools/`; the runner does not download or install them automatically.


## V7B preparation (blocked)

`python -m dynapm.scripts.task33_system_trial_preparation` reports the blocked
V8 draft and deterministic calibration identities only. It has no execution flag.
The measured-bootstrap validator reconstructs fixed 24h history from raw sample
records and rejects missing coverage, future data and counter resets. Its unit
fixtures are not a real-bootstrap demonstration. See [the exact readiness table,
resource budget and remaining implementation](system_trial_freeze.md).
Do not reuse the V7A one-bucket smoke as a calibration or comparative trial runner.
