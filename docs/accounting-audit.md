# Refresh accounting reference audit

Baseline: `9a620142a657cd2c3ab21b13e1f1d6dba7485901`. The inventories below cover every matching Python/Markdown source line for the requested names; several names on one line share a classification. Generated/ignored research outputs and this inventory itself are excluded. No old data are migrated or normalized.

Current outcome: legacy numeric aliases, the changed-field-row log, sample normalization, timestamp inference, and Table 1 count relabeling are removed from executable paths. The old names survive only in this evidence and negative schema tests. `update_count` and `n_updates` had no executable baseline occurrences. Current `refresh_events` occurrences are typed runtime events, canonical counters, direct analysis, or tests. Initialization is separate.

## Baseline occurrence inventory

| Location | Matched names | Classification / disposition |
|---|---|---|
| `docs/protocol.md:64` | `refresh_events, total_updates, update_log` | Documentation / migration evidence |
| `dynapm/eval/metrics.py:10` | `count_unique_refresh_timestamps, update_log` | Unique-field-timestamp helper removed |
| `dynapm/eval/metrics.py:12` | `update_log` | Unique-field-timestamp helper removed |
| `dynapm/eval/metrics.py:16` | `update_log` | Unique-field-timestamp helper removed |
| `dynapm/eval/metrics.py:19` | `update_log` | Unique-field-timestamp helper removed |
| `dynapm/eval/runner_v2.py:3` | `update_log` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/eval/runner_v2.py:4` | `update_log` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/eval/runner_v2.py:48` | `update_log` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/eval/runner_v2.py:67` | `total_updates` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/eval/runner_v2.py:68` | `refresh_events` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/eval/runner_v2.py:73` | `update_log` | Mixed result fields replaced with explicit counters and separate initialization |
| `dynapm/methods/baselines_v2.py:25` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:29` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:30` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:37` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:52` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:65` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:198` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:225` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:235` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:244` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/baselines_v2.py:253` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/dynapm_v3.py:74` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/dynapm_v3.py:96` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/dynapm_v3.py:97` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/dynapm_v3.py:98` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/methods/dynapm_v3.py:101` | `update_log` | Divergent policy logging replaced by shared commit helper |
| `dynapm/scripts/task15_full_corpus.py:93` | `total_updates` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:94` | `refresh_events` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:119` | `total_updates` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:120` | `refresh_events` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:148` | `update_log` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:149` | `update_log` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:274` | `total_updates` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:507` | `total_updates` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:520` | `update_log` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:555` | `total_updates` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task15_full_corpus.py:643` | `update_log` | Row-count headlines replaced; field diagnostics explicitly renamed |
| `dynapm/scripts/task18_paper_packaging.py:15` | `count_unique_refresh_timestamps` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:28` | `refresh_count` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:106` | `update_log` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:112` | `count_unique_refresh_timestamps, refresh_events` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:113` | `total_updates` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:124` | `refresh_events` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:368` | `total_updates` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:369` | `total_updates` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:387` | `refresh_events` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18_paper_packaging.py:388` | `refresh_events` | Sample normalization and mislabeled table cells removed |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:2` | `update_log` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:29` | `refresh_count` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:47` | `update_log` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:130` | `update_log` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:167` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:195` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:196` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:209` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:210` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:243` | `refresh_events` | Log-based inference / PP override replaced by validated input counters |
| `dynapm/tests/test_causal_invariants.py:109` | `update_log` | Legacy test migrated |
| `dynapm/tests/test_dynapm_v3.py:41` | `update_log` | Legacy test migrated |
| `dynapm/tests/test_dynapm_v3.py:42` | `update_log` | Legacy test migrated |
| `dynapm/tests/test_dynapm_v3.py:43` | `update_log` | Legacy test migrated |
| `dynapm/tests/test_dynapm_v3.py:52` | `update_log` | Legacy test migrated |
| `dynapm/tests/test_periodic_predictor_integration.py:13` | `total_updates` | Legacy test migrated |
| `dynapm/tests/test_runner_v2.py:22` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:23` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:25` | `total_updates` | Legacy test migrated |
| `dynapm/tests/test_runner_v2.py:27` | `total_updates` | Legacy test migrated |
| `dynapm/tests/test_runner_v2.py:126` | `total_updates` | Legacy test migrated |
| `dynapm/tests/test_timeline.py:102` | `update_log` | Legacy test migrated |

## Current occurrence inventory

All executable matches below use canonical events/counters. Literal legacy names in tests assert their absence or reject old input; they are not compatibility fallbacks. Line references describe the reviewed Phase 2B source.

| Location | Matched names | Classification |
|---|---|---|
| `docs/development.md:50` | `refresh_events` | Documentation / migration evidence |
| `docs/protocol.md:107` | `refresh_events` | Documentation / migration evidence |
| `docs/protocol.md:115` | `refresh_events` | Documentation / migration evidence |
| `dynapm/core/accounting.py:13` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:15` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:89` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:120` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:124` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:127` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:130` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:131` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:132` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:136` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:151` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:153` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:155` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/core/accounting.py:166` | `refresh_events` | Authoritative typed events, counter derivation, or schema invariants |
| `dynapm/eval/runner_v2.py:55` | `refresh_events` | Canonical result schema / event serialization |
| `dynapm/eval/runner_v2.py:62` | `refresh_events` | Canonical result schema / event serialization |
| `dynapm/methods/baselines_v2.py:32` | `refresh_events` | Canonical event trace view only; no counter inference |
| `dynapm/scripts/task15_full_corpus.py:498` | `refresh_events` | Canonical counters copied, aggregated, and reported directly |
| `dynapm/scripts/task15_full_corpus.py:546` | `refresh_events` | Canonical counters copied, aggregated, and reported directly |
| `dynapm/scripts/task18_paper_packaging.py:340` | `refresh_events` | Table reads validated counters directly |
| `dynapm/scripts/task18_paper_packaging.py:359` | `refresh_events` | Table reads validated counters directly |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:170` | `refresh_events` | Direct counter aggregation / reporting; no log parsing |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:171` | `refresh_events` | Direct counter aggregation / reporting; no log parsing |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:185` | `refresh_events` | Direct counter aggregation / reporting; no log parsing |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:186` | `refresh_events` | Direct counter aggregation / reporting; no log parsing |
| `dynapm/scripts/task18b_corpus_churn_rerun.py:221` | `refresh_events` | Direct counter aggregation / reporting; no log parsing |
| `dynapm/tests/test_accounting.py:64` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:82` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:87` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:88` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:98` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:99` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:123` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:124` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:127` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:136` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:141` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:152` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:164` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:165` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:169` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:196` | `total_updates, update_log` | Negative regression: legacy keys rejected/absent |
| `dynapm/tests/test_accounting.py:198` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:199` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:232` | `total_updates` | Negative regression: legacy keys rejected/absent |
| `dynapm/tests/test_accounting.py:233` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_accounting.py:234` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_periodic_predictor_integration.py:13` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:25` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:26` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:28` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:30` | `refresh_events` | Explicit event/counter invariant test |
| `dynapm/tests/test_runner_v2.py:130` | `refresh_events` | Explicit event/counter invariant test |

## Untouched ignored development outputs

A read-only scan found 65 existing ignored pre-accounting development JSONs containing the old row-count key. These are not converted, relabeled, or regenerated. All 65 fail the new accounting-schema check. They remain local development artifacts, not current accounting inputs. This inventory concerns their schema, not a claim about their forecasting validity. Virtual environments and Git object history are not current implementation/analysis paths.

| Ignored artifact | Existing key(s) | Disposition |
|---|---|---|
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__02.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__03.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__04.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__05.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__06.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__07.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__08.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__09.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__10.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__100.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__101.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__102.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__103.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__104.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__105.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__106.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__107.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__108.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__109.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__11.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__110.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__111.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__112.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__113.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__114.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__115.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__116.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__117.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__118.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__119.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__12.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__120.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__121.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__122.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__123.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__124.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__125.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__126.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__127.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__128.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__129.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__13.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__130.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__131.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__132.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__133.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__134.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__135.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__136.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__137.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__138.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__139.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__14.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__140.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__141.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__142.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__143.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__144.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__145.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__146.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__147.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__148.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__149.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__15.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
| `dynapm/results/eval_full_corpus/periodic_predictor_6h_v2__Materna-Trace-1__150.json` | `total_updates` | Retain unchanged locally; reject as current accounting input |
