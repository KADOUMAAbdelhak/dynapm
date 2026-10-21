# Observed-row lag semantics assessment

Scope: Phase 2C provenance/data characterization, not an experiment or a protocol change. `causal-timeline-v2`, feature construction, forecasting and scheduling remain unchanged.

## Code contract and causal meaning

`build_features` (`dynapm/core/features.py`) uses observed-row `shift`, trailing rolling windows and differences on a past-only series. Lag 1 means the previous observed row, not necessarily five elapsed minutes. Windows 6/12/24/48/96 likewise count observations. Calendar features use target timestamps. `_causal_feature_row` in `core/predictor.py` preserves that observed-history interpretation during recursive inference, while forecast targets after the origin are fixed five-minute steps. Phase 2A's future-data and horizon invariants remain in force.

A long past gap therefore changes elapsed history support without adding future information. Causality alone does not establish that the history is temporally representative. Evaluation's forward density threshold cannot repair sparse history before a refresh. Coalescing periodic ticks also does not repair feature history.

## Bounded evidence and deterministic raw characterization

The synthetic regression test creates a >20-hour gap before the last observation and confirms that the last feature still uses the previous observed value. It does not impute, resample, or change targets.

The new cohort manifest records, per entity, timestamp duplicates, counts above expected cadence, observed-step min/median/p95/max, and elapsed distances for configured lags plus 96-step context. This is computed while reading timestamps for row-count filtering; no utilization model, labels, forecasts or policy metrics are generated.

For the present local raw inputs and unchanged >=2000-row cohort: 1,576 entities are retained; 641 have at least one observed step above 300 seconds. The maximum observed step among retained entities is 918,300 seconds; maximum 96-observed-step elapsed distance is 977,700 seconds. These are input-quality diagnostics only. Per-VM distributions, not just maxima, are recorded in the cohort manifest; its SHA is listed in [provenance documentation](provenance.md). Original input files are not modified.

## Disposition and gate

Retain current observed-row semantics and identify them explicitly in `DataConfig.lag_semantics` and feature specifications. Do not reinterpret them as wall-clock lags. This closes the protocol-description/assessment requirement, not the empirical robustness question.

Before claim-generating experiments, V2 must predefine handling/reporting of long-history gaps and relevant strata, eligibility and sensitivity choices using development data. If a wall-clock lag/resampling or gap-reset policy is needed, it is a separately authorized scientific/protocol change with new fingerprints and reviewed versioning. No such correction is made here. Passing provenance checks cannot establish predictor quality across gaps.
