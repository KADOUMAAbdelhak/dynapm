# Development and validation

## Scientific state

Causal feature construction, predictor training interfaces, recursive forecasting, policy refresh, and the evaluation runner are preserved as the current development baseline. Cleanup does not change their scientific behavior.

The DynAPM-V3 unit tests still use the earlier constructor signature. They currently omit `cpu_predictor`, `mem_predictor`, `cpu_obs_full`, and `mem_obs_full`. Provisioning policy construction also needs reconciliation with the corrected predictor interfaces. Address these together with new causal validation before starting a new full experiment.

The full-corpus runner supports selecting methods, but its cached summaries need explicit generation checks when methods are rerun separately. Do not combine measurements from different source revisions or forecast-origin protocols.

## Checks and expensive tests

For lightweight checks with local raw data available:

```sh
python -m pytest dynapm/tests --ignore=dynapm/tests/test_runner_v2.py --ignore=dynapm/tests/test_periodic_predictor_integration.py -k 'not test_predictor_fits_and_predicts and not test_predictor_residuals_finite and not test_predictor_train_test_separation'
```

This deliberately excludes three predictor-training tests and four runner/policy integration tests. Integration runs can fit forests and perform recursive multi-step forecasting. They require local selection, bootstrap, residual, and ground-truth artifacts. Run them only as separately authorized scientific jobs.

The extracted `test_periodic_predictor_integration.py` is retained without changing its assertions. The remaining unit tests preserve their existing assertions as well.

The safe CLI help entry points are:

```sh
python -m dynapm.scripts.task17b_provisioning --help
python -m dynapm.scripts.task18b_corpus_churn_rerun --help
```

Other orchestration scripts execute work from `main()` and may not implement `--help`; do not invoke them as smoke checks.

## Implementation entry points

- Loading and filtering: `dynapm.data.loader.load_vm_csv`, `iter_corpus`, `dynapm.data.filter.filter_corpus`.
- Bootstrap: `dynapm.scripts.run_bootstrap_characterization.main`.
- Features and predictor: `dynapm.core.features.build_features`, `dynapm.core.predictor.VMPredictor`.
- Policies: `dynapm.methods.baselines_v2`, `dynapm.methods.dynapm_v3.DynAPMPolicyV3`.
- Evaluation: `dynapm.eval.runner_v2.run_method_on_vm`, `dynapm.scripts.task15_full_corpus`.
- Ground truth: `dynapm.core.ground_truth`, `dynapm.scripts.task04_ground_truth`.
- Provisioning: `dynapm.eval.provisioning`, `dynapm.scripts.task17b_provisioning`.
- Statistical aggregation: `dynapm.eval.metrics`, `dynapm.scripts.task18_paper_packaging`, `dynapm.scripts.task18b_corpus_churn_rerun`.

Existing module names are retained for import compatibility. Statistical aggregation scripts include table/plot generation and sample-oriented entry points; use their reusable functions with explicitly validated current inputs. No generated tables or figures are version-controlled.
