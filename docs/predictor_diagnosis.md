# Predictor Diagnosis — V2.4

Exploratory development-only diagnosis under `causal-timeline-v3`. No policy, RF, ADWIN, scheduling or accounting parameter changes. No confirmatory entity outcomes or historical archive inputs.

## Frozen diagnostic design

The same eighteen permanent development VMs are loaded from the integrity-validated corrected pilot cohort. For each VM, select eight equal-index-spaced origins from observed, globally verifiable hourly times with complete CPU/memory exact-grid history. Selection uses eligibility/timestamps only, never forecast errors. This bounded sample is not every refresh or a confirmation study.

Fit unchanged bootstrap-only RF CPU/memory models once per VM: 200 trees, depth20, sqrt features, seed42, one model thread. Existing pilot files contain no serialized fitted models; fresh identical fits are necessary. Reuse each fit for every selected origin and diagnostic. No tuning or method selection is executed.

Compare 288-step recursive forecasts with persistence and exact timestamp 24h seasonal-naive. Missing seasonal slots remain unavailable. Report leads 1/12/72/144/288 (5min/1h/6h/12h/24h), error, bias, class-boundary distance, and per-VM variability. Summary lead comparisons use the common target set available to all controls. All available per-method rows remain in Parquet so availability restrictions can be inspected.

A separate `rf_one_step_actual_history_DIAGNOSTIC` uses actual intervening history for each target. It is causal at each target but **not** a deployable fixed-origin forecast. Its comparison with recursion diagnoses feedback accumulation and does not count as a competitor receiving the same information.

Profile diagnostics compute forward mean-based classes (as in production) and p95 error; p95 classes are an auxiliary diagnostic only. Record coverage, bootstrap/stream distribution shift, gap-related origin loss, threshold proximity, and forecast/actual variation. Never interpret p95 classes as the maintained mean-based class endpoint.

## Managed execution

Use `python -m dynapm.scripts.task21_predictor_diagnosis` from a clean committed tree. Run purpose is pilot, never claim. Config fingerprints include sample rule, controls, leads, unchanged model settings and class convention. The driver validates the prior pilot before reading its development cohort; it does not load fitted predictions/results as diagnostic outputs. Full raw hashes may be checked as provenance, but model/data-outcome diagnostics are restricted to the eighteen development entities.

Outputs: `lead_errors.parquet`, `profile_errors.parquet`, `vm_diagnostics.parquet`, `summary.json`, plus standard managed source/config/environment/dataset/cohort/output manifests. No generated scientific result is committed or manually edited.

## Gate

V2.4 completion requires validated managed outputs, lead/resource results and evidence-limited diagnosis, dataset suitability audit, full lightweight tests and source review. V2.5 stays blocked pending review; V3 stays blocked. Model redesign, if supported, is a separate authorized development phase and must precede freezing confirmation. No practical-benefit threshold may be chosen from favorable pilot effects.
