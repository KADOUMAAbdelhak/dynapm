# Experiment provenance and cache integrity

This layer records and validates experiments; it does not establish scientific benefit or authorize a corpus run. The supported API is `dynapm.core.provenance` plus `dynapm.core.run_store.RunSession`. Existing numerical policy/replay APIs remain unchanged and can be called inside a managed run. Direct library calls or old JSON files are not claim-eligible experiment records.

## Two identities

**Experiment fingerprint:** SHA-256 of canonical, explicitly enumerated scientific inputs. It includes source commit/dirty scientific state, temporal protocol, accounting schema, config digest, raw dataset digest, cohort digest, scientific environment and seeds. Identical scientific inputs yield the same identity.

**Run ID:** UTC timestamp, short experiment fingerprint and a random execution suffix. Two executions of the same experiment have distinct run IDs. Time, duration, hostname, command location and output directory do not decide scientific cache compatibility.

Canonical JSON sorts string keys, uses fixed separators and UTF-8, normalizes dataclasses/Path/enum values, and rejects unsupported reprs and nonfinite numbers. Reading JSON also rejects duplicate keys and nonfinite constants. Configuration paths must be relative; absolute paths belong only in execution metadata.

## Central versions

| Structure | Version |
|---|---|
| Experiment/run provenance | `provenance-schema-v1` |
| Explicit configuration | `experiment-config-v1` |
| Raw inputs | `dataset-manifest-v1` |
| Entity/cohort selection | `cohort-manifest-v1` |
| Output inventory | `output-manifest-v1` |

Definitions live in `dynapm/core/provenance.py`. Protocol/accounting versions are imported from the existing canonical constants: `causal-timeline-v2` and `refresh-accounting-v1`. They are not redefined in orchestration scripts. Unsupported schemas fail closed.

## Source identity

`SourceProvenance.capture(repo)` records commit, branch, Git tree status, dirty flag, full tracked-diff SHA, scientific-diff SHA and untracked scientific path/size/hash inventory. Source root is repository-relative `.`. Branch/status text is descriptive, not a separate scientific identity. Clean source is identified by commit; dirty source additionally includes the scientific diff and untracked source inventory, and can never share the clean fingerprint.

The scientific diff is a canonical HEAD-to-working-file delta (path, original blob/mode, current mode/SHA), including untracked additions. Staging a file does not change scientific identity. The untracked inventory remains descriptive source evidence. Full tracked patch generation separately overrides user color, context, rename and diff-algorithm preferences. Default scientific scopes include the package/tests, source/scripts/configs, requirements/lockfiles and execution configuration. Extend the explicit scopes when adding scientific code elsewhere. Scientific symlinks/submodules are rejected rather than following unrecorded external code. Ignored raw data/results are covered by their separate manifests, not Git status. Full tracked-diff metadata can include documentation; scientific diff scope excludes documentation-only changes while dirty status still prevents canonical claim execution.

`RunSession` recaptures source and checks inputs/environment before execution and before completion. Source/input/environment changes during execution prevent SUCCESS. The caller must capture fresh expected provenance before cache lookup; an old experiment file describes an old identity, not a declaration that current inputs are unchanged. `prepare_experiment` verifies the supplied dataset manifest and captures current source/environment.

## Explicit configuration

`ExperimentConfigProvenance` contains typed data/model/policy/statistics sections plus explicit preprocessing/analysis settings. It represents bootstrap fraction, observation eligibility, horizon/cadence, density threshold, lag semantics, RF family/parameters/targets/features, policy intervals/windows/detector settings and statistical seeds/specification. Its canonical digest is `config_sha256`.

No configuration is inferred from callable/object reprs. The configuration template records current defaults; it does not dispatch an experiment. A managed pilot driver must explicitly bind these settings to the production APIs and verify that recorded settings are the settings actually used. Unused model settings for observation-only methods must be identified, not described as executed training. Future policy settings fit explicit parameter maps; no matched-budget algorithm is implemented here.

## Raw dataset and cohort manifests

`DatasetProvenance` records dataset/source/schema identities, traces, expected cadence, input selection rule and relative file path/size/SHA/trace/entity/role records. `total_file_count` counts selected inputs. Generation time is descriptive. Dataset location is supplied separately, so copying the bytes to another root preserves scientific identity.

The Materna adapter selects all VM CSVs and the three `00-Trace-Info.txt` files under the three named traces. It hashes and inventories other regular files as `ancillary_not_loaded`, outside scientific identity. The local `356.bak` is one such unused backup; it is neither consumed, deleted nor silently labeled trace metadata. Added/changed selected inputs invalidate the manifest. Symlinks and unsupported selection rules are rejected.

`CohortManifest` separately records every characterized entity, inclusion/reason, observation count, first/last timestamps, deterministic temporal characterization, filter configuration/version and raw dataset digest. The current rule is the existing `row_count >= 2000` predicate. It does not imply every retained VM will have eligible evaluation windows. Runtime exclusions/failures must also be reported. Removing an entity, changing selection/filtering, or changing a linked input changes cohort identity.

**Digest distinction:** `dataset_manifest_sha256` and `cohort_sha256` hash canonical scientific identity, excluding generation time (and dataset ancillary inventory). Full JSON file-byte hashes are separately recorded in run metadata. Do not substitute a timestamp-bearing file checksum for the scientific digest. Both checks have distinct purposes.

Local metadata-only generation for this phase, under ignored `results/provenance-phase2c/`:

- 1,592 VM CSVs + 3 trace-info inputs = **1,595 selected files**, plus one inventoried unused backup.
- Dataset scientific SHA-256: `9801b06c0a8dd3bfed9e7fd111e656b57f30d9a09f6634761208f72188e35e1a`.
- Cohort: **1,576 included / 1,592 characterized**, 16 below the existing threshold.
- Cohort scientific SHA-256: `d106af098af80e1a285410f0293baa2fd88b17ee4db2c4a6f15380cb761ae50d`.

These are input/provenance measurements, not regenerated scientific headline results. No legacy kept-list, predictor output, threshold table or historical archive was used to generate them. See [the lag assessment](lag_semantics_assessment.md).

## Environment compatibility versus execution metadata

The full installed package inventory, Python, OS/architecture, CPU model/counts, memory, hostname, timezone and executable are recorded. Missing required package metadata or disagreement between imported and installed versions fails loudly. Unavailable optional hardware fields are explicitly null, never invented.

Default scientific compatibility covers exact Python implementation/version, OS/platform/architecture, NumPy/pandas/SciPy/scikit-learn/River/joblib/pyarrow/python-dateutil/matplotlib versions, and declared numerical thread/hash-seed environment settings. Hostname, wall time and filesystem locations are excluded. Other installed packages are recorded but do not silently become compatibility inputs.

Callers adding scientific dependencies must extend `scientific_packages`; mandatory dependencies cannot be removed. Timing/system studies must declare hardware-sensitive `execution_compatibility_keys` (e.g. CPU model, core counts and memory) through `prepare_experiment`/environment capture. Required unavailable fields fail. Hostname/time/location cannot be promoted to scientific execution keys. New accelerators or numerical backends require an explicit reviewed compatibility extension, not assumed support.

Provenance does not guarantee bitwise equality across arbitrary hardware or nondeterministic libraries. Declare tolerance and relevant settings before new experiments; record unsupported domains rather than claiming complete compatibility.

## Run purpose and cleanliness

| Purpose | Dirty source | Claim reuse |
|---|---|---|
| `smoke` | Allowed; synthetic/small validation | Never |
| `pilot` | Clean preferred; dirty requires explicit `allow_dirty=True` | Never |
| `claim` | Clean required; explicit override permits DEVELOPMENT execution only | Only clean, complete `CANONICAL_CLAIM` records |

Dirty overrides record `allow_dirty`, `claim_eligible=false` and `classification=DEVELOPMENT_NONCANONICAL`. An override never produces canonical claim evidence. A pilot/smoke cache cannot satisfy a claim request, even with an identical scientific fingerprint. Re-run a pilot under claim rules; do not edit purpose fields to promote it.

## Canonical layout and lifecycle

```text
results/runs/<experiment_fingerprint>/<run_id>/
  manifest.json
  config.json
  environment.json
  dataset_manifest.json
  cohort_manifest.json
  outputs/
  logs/
  output_manifest.json
  SUCCESS
```

`manifest.json` initially has status INCOMPLETE, with command, start time, purpose, source and identity, required outputs and execution locations. The caller declares every required output and semantic role **before execution**. Declare the complete cohort/method coverage, not only successful files afterward. Failure/exclusion records are explicit manifest fields; cohort exclusions are copied automatically and runtime records are supplied at completion.

The caller writes outputs only inside outputs/logs and explicitly calls `complete(failures=..., exclusions=...)`. Completion verifies source/environment/inputs, the exact declared output inventory, JSON/CSV/Parquet readability where applicable, sizes, hashes and optional table shape. It writes `output_manifest.json`, records its deterministic SHA, then finalizes the run manifest, and only then writes SUCCESS. SUCCESS pins the final run-manifest byte hash and output-manifest hash. Unexpected root/output files, links, missing outputs or corrupt metadata are rejected.

Exceptions inside the context create FAILED plus error type/message/traceback and end time. Normal context exit without `complete()` is also failure. An abandoned/constructor-failed directory without a final marker remains incompatible. Outputs may legitimately record child failures, but coverage/failure acceptability is an experimental gate and must never be inferred merely from SUCCESS.

Minimal API pattern (planning example; not an experiment invocation):

```python
experiment, environment = prepare_experiment(
    repo, dataset_root, config, dataset_manifest, cohort_manifest, seeds)
with RunSession(
    result_root, experiment, environment, repo=repo, dataset_root=dataset_root,
    purpose="smoke", required_outputs=declared_outputs,
) as run:
    # Call explicitly configured compute APIs; write all declared outputs.
    run.complete(failures=recorded_failures, exclusions=runtime_exclusions)
```

All result directories and generated manifests remain ignored by Git. Moving a completed run does not change scientific compatibility; its original execution location remains descriptive metadata.

## One cache decision

`check_cache(run_dir, expected_experiment, requested_purpose)` is authoritative. `load_verified_output` delegates to it and refuses files outside the verified output inventory. Compatibility requires exact scientific fingerprint/dimensions, supported versions, purpose/canonical eligibility, complete SUCCESS state, consistent metadata snapshots, valid output manifest and all file hashes. Installed scientific environment is also checked. There is no fallback to filenames, modification times, row counts or protocol labels alone.

Representative explicit rejection reasons include `source_commit_mismatch`, `source_state_mismatch`, `dirty_source`, `protocol_mismatch`, `accounting_schema_mismatch`, `config_mismatch`, `dataset_mismatch`, `cohort_mismatch`, `environment_mismatch`, `environment_unresolved`, `seed_mismatch`, `experiment_fingerprint_mismatch`, `run_purpose_mismatch`, `noncanonical_run`, `incomplete_run`, `output_hash_mismatch`, `output_manifest_mismatch`, `metadata_hash_mismatch`, `completion_marker_mismatch`, `run_inventory_mismatch`, `unsupported_manifest_schema` and `invalid_or_unversioned_run`.

Hashes provide point-in-time integrity, not a cryptographic signature against an owner deliberately rewriting every manifest and checksum. Manual edits are prohibited; protected archival/authenticity infrastructure is a separate concern. A validator does not infer scientific success or coverage acceptability from valid checksums. A cache hit references an existing physical run ID; it is not a new independent replicate. System analyses must not count reused/copy-relocated runs as additional trials.

## Existing cache-path disposition

The explicit refusal option was chosen for legacy orchestration. No old output is upgraded or rewritten; the 65 ignored corrected-development JSONs remain incompatible. Old standalone entry points cannot establish complete input/config/source identity, so they fail before I/O. A future bounded managed pilot must use RunSession and explicitly configured current library APIs rather than re-enable those paths.

| Path | Previous weak path | Current disposition |
|---|---|---|
| `task04_full_corpus_predictor` | Unversioned kept list; fixed residual/summary output tree | Standalone main refuses; per-VM compute is not a cache reader |
| `task04_ground_truth` | Unversioned kept list/bootstrap threshold table | Main and threshold lookup refuse before reads |
| `task04_ground_truth_stats` | Glob of existing Parquets with no generation identity | Main refuses directory ingestion |
| `run_bootstrap_characterization` | Unversioned selection feeding thresholds | Main refuses; new cohort characterization does not call it |
| `task15_full_corpus` | Filename/schema-only JSON resume; merge arbitrary partial summary | Worker reuse removed; standalone path refuses; old-summary merge removed |
| `task17b_provisioning` | Existing records reused on existence plus protocol label | Weak reuse branch removed; standalone execution refuses after safe help parsing |
| `task18_paper_packaging` | Fixed-path summaries/provisioning consumed without full provenance | Standalone main refuses; pure in-memory table functions remain testable |
| `task18b_corpus_churn_rerun` | Filename JSON resume and glob aggregation of directory contents | Reuse/glob inference removed; standalone JSONs return no cache row; orchestration refuses |
| `eval/replay`, `runner_v2`, provisioning library | No persisted input/result/model cache | Continue fresh causal computation; managed wrapper required for experiment records |
| Raw loader and `filter` predicate | Raw-input discovery, not result reuse | Hash via dataset manifest; cohort generator calls the existing predicate without writing old kept list |
| Matplotlib font/cache setup | Rendering environment cache | Not scientific result reuse; package version/environment recorded |

No currently reachable result-reuse path uses “filename exists” as scientific compatibility. Legacy functions retained behind refusal are not a supported corpus interface. The next pilot must validate config-to-execution binding and performance; this phase neither ports nor runs the full-corpus drivers.

## Lightweight CLI

```sh
python -m dynapm.scripts.provenance --help
python -m dynapm.scripts.provenance manifest-dataset --root data/raw --output results/inputs/dataset_manifest.json
python -m dynapm.scripts.provenance check-dataset --root data/raw --manifest results/inputs/dataset_manifest.json
python -m dynapm.scripts.provenance manifest-cohort --root data/raw --dataset results/inputs/dataset_manifest.json --output results/inputs/cohort_manifest.json
python -m dynapm.scripts.provenance config-template --output results/inputs/config.json
python -m dynapm.scripts.provenance prepare-experiment --repo . --dataset-root data/raw --config results/inputs/config.json --dataset results/inputs/dataset_manifest.json --cohort results/inputs/cohort_manifest.json --output results/inputs/experiment.json
python -m dynapm.scripts.provenance fingerprint --experiment results/inputs/experiment.json
python -m dynapm.scripts.provenance validate-run --run RUN_DIRECTORY --experiment results/inputs/experiment.json --purpose smoke
python -m dynapm.scripts.provenance explain-cache --run RUN_DIRECTORY --experiment results/inputs/experiment.json --purpose claim
```

Dataset/cohort generation only hashes/characterizes raw inputs; preparation records identity but executes nothing. Cache rejection exits 2 with structured reasons. `pytest dynapm/tests/test_provenance.py` supplies bounded self-tests; no CLI trains or evaluates a corpus. Claim-eligibility is not evidence that validation gates V2 onward have passed.

## Phase 2C validation status

V1B PASS; V2 NEXT. The complete lightweight suite has 195 passes, zero failures and zero skips (72 additional cases beyond the 123-test baseline). Tests cover scientific-dimension mutations, source staging/clone invariance, dirty overrides, package resolution/compatibility, purpose separation, required coverage, metadata/output/marker corruption, schema rejection, deterministic output manifests, relocation, CLI behavior, legacy refusal and a tiny synthetic Static replay inside RunSession. A separate metadata-only smoke run validates the real local input manifests without computing policy/model results. The historical archive is not accessed.

This does not validate a full-corpus driver, scientific effect, runtime budget or a new dataset/system adapter. Legacy entry points remain intentionally blocked. V2 must implement the bounded managed driver, verify config binding/coverage and pre-register scientific decisions. No pilot, full corpus or interval experiment is authorized here.
