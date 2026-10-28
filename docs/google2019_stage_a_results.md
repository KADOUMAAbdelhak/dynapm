# Google cell-e Stage-A replication — V4E

**Stage A PASS. Stage B is still required regardless of these results. V4C is
incomplete; V5 is blocked until g replication.** This is a factual execution and
estimation record, not manuscript prose or an operational/practical-benefit claim.

## Frozen generation and scope

- Clean execution source: `ab2434f900e252e6909bedea8b0d509709bd3024`; no execution fixes.
- Design: `dd857518fd7471a2e7c8cce94f6922f52aa278b637ff38f2656db807c322d33d`.
- Google protocol v2: `88e11c165a05658fe587878a66ee2816f033957efceb883062b0577d4f98a2c1`.
- Experiment fingerprint: `01dbf6a7ff07ee66c8c49dd8dee92f6efe65c42caa7e5a180af9ab22581264ff`.
- Run ID: `2026-10-28T141340.735739Z-01dbf6a7ff07-527fcf67`.
- Output-manifest SHA-256: `2003fca1b7135a23acd5d7f3932a7825b699c8cd4f8893ac6822b26b8a970739`.
- Results: `results/runs/01dbf6a7ff07ee66c8c49dd8dee92f6efe65c42caa7e5a180af9ab22581264ff/2026-10-28T141340.735739Z-01dbf6a7ff07-527fcf67` (ignored/uncommitted).
- Exact e cohort SHA: `992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c`; all 1,000 frozen identities retained.

The pool has 62,444 protocol-eligible entities from 62,451 acquisition candidates
(seven prior, outcome-blind protocol exclusions). The fixed hash sample includes
1,000; the other 61,444 eligible entities are unsampled, not outcome-based
exclusions. No post-selection exclusions or cohort drift occurred.

All 5,000 planned method×entity evaluations completed. Each method uses the same
396,569 entity/read opportunities, totaling 1,982,845 evaluation records. Of the
unique reads, 140 lack a same-time observation; they still read nominally.
Measurement [start,end), end/q availability, the closing-slot view, bootstrap,
200/288 density and inherited 96-slot PW gate remain unchanged. No predictors,
adaptive triggers, interpolation, clipping, BigQuery/cloud calls, g data or
Materna result changes were used. The query ledger bytes/hash are unchanged.

## Entity-weighted method summaries

Class correctness is percent; p95 MAE is **request-ratio units**, never Materna
capacity percentage error. Means weight each of the 1,000 entities equally.

| Method | CPU correct % | Memory correct % | CPU p95 MAE | Memory p95 MAE | Mean refreshes/entity |
| --- | --- | --- | --- | --- | --- |
| static | 49.3068 | 29.0488 | 0.05587396 | 0.03526569 | 0.000 |
| pw_12h | 58.8231 | 59.4882 | 0.04646582 | 0.02298355 | 34.563 |
| pw_6h | 60.1149 | 60.9509 | 0.04523611 | 0.02198398 | 68.888 |
| pw_3h | 61.0184 | 61.8566 | 0.04438083 | 0.02143718 | 137.056 |
| full_rewrite | 61.8304 | 62.6932 | 0.04349241 | 0.02091910 | 5041.085 |

## Frozen F1/F2/F3 estimates

Unit: entity. Every comparison has n=1,000. Delta is treatment minus control;
positive correctness and negative MAE favor the treatment, positive refresh
counts mean more maintenance. Class effects/CIs below are percentage points.
Percentile paired bootstrap 95% CI: B=10,000, seed=20251022. Wilcoxon is two-sided
with `zero_method=wilcox`; Holm adjusts within the per-cell families across
15/10/5 tests. CIs are marginal, not simultaneous. No practical margins exist.

### F1_maintenance_vs_none

| Contrast | Endpoint | Mean Δ | Mean 95% CI | Median Δ | Median 95% CI | Wilcoxon p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pw_12h − static | cpu_class_correctness | 9.51636 | [8.124721, 10.92757] | 2.217751 | [0.4024145, 4.415352] | 1.52744e-24 | 1.52744e-24 |
| pw_12h − static | memory_class_correctness | 30.43949 | [28.51781, 32.40527] | 26.49 | [23.75358, 29.17505] | 1.11176e-118 | 1.11176e-117 |
| pw_12h − static | cpu_p95_profile_mae | -0.009408147 | [-0.01132961, -0.007509564] | -0.002782339 | [-0.003553062, -0.001846183] | 2.08848e-25 | 4.17697e-25 |
| pw_12h − static | memory_p95_profile_mae | -0.01228214 | [-0.01404464, -0.01073602] | -0.005585952 | [-0.006650107, -0.004728196] | 2.35887e-72 | 1.65121e-71 |
| pw_12h − static | n_refresh_events | 34.563 | [33.90297, 35.21603] | 40 | [39, 41] | 8.27763e-168 | 1.24164e-166 |
| pw_6h − static | cpu_class_correctness | 10.80813 | [9.424416, 12.20903] | 3.929477 | [2.414487, 5.518658] | 2.23267e-33 | 8.93068e-33 |
| pw_6h − static | memory_class_correctness | 31.90214 | [29.98759, 33.86406] | 29.17505 | [25.96455, 31.94961] | 4.42954e-123 | 4.8725e-122 |
| pw_6h − static | cpu_p95_profile_mae | -0.01063785 | [-0.01253808, -0.008780398] | -0.003420381 | [-0.004373268, -0.002358272] | 5.04662e-33 | 1.51399e-32 |
| pw_6h − static | memory_p95_profile_mae | -0.0132817 | [-0.01503206, -0.01174808] | -0.006320866 | [-0.007055461, -0.005537673] | 4.12656e-84 | 3.30125e-83 |
| pw_6h − static | n_refresh_events | 68.888 | [67.58498, 70.17108] | 81 | [79, 82] | 9.5012e-166 | 1.33017e-164 |
| pw_3h − static | cpu_class_correctness | 11.71163 | [10.3335, 13.10193] | 4.601482 | [3.367876, 6.531619] | 9.37534e-41 | 5.62521e-40 |
| pw_3h − static | memory_class_correctness | 32.80785 | [30.89551, 34.78024] | 30.3583 | [27.48268, 32.79678] | 1.11744e-126 | 1.34092e-125 |
| pw_3h − static | cpu_p95_profile_mae | -0.01149313 | [-0.01342322, -0.009633673] | -0.003735629 | [-0.004596675, -0.002722323] | 3.39028e-38 | 1.69514e-37 |
| pw_3h − static | memory_p95_profile_mae | -0.01382851 | [-0.01557611, -0.01228633] | -0.006517435 | [-0.007355518, -0.005623496] | 7.18353e-90 | 6.46518e-89 |
| pw_3h − static | n_refresh_events | 137.056 | [134.47, 139.616] | 160 | [156, 163] | 2.6562e-165 | 3.45306e-164 |

### F2_cadence_increments

| Contrast | Endpoint | Mean Δ | Mean 95% CI | Median Δ | Median 95% CI | Wilcoxon p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pw_6h − pw_12h | cpu_class_correctness | 1.291772 | [1.091774, 1.490935] | 1.226994 | [1.207243, 1.408451] | 6.92258e-39 | 6.92258e-39 |
| pw_6h − pw_12h | memory_class_correctness | 1.462645 | [1.275894, 1.646462] | 1.234573 | [1.207243, 1.56127] | 2.43296e-49 | 4.86593e-49 |
| pw_6h − pw_12h | cpu_p95_profile_mae | -0.001229707 | [-0.001521186, -0.0009403432] | -0.0005675088 | [-0.0006467959, -0.0004736051] | 3.58047e-52 | 1.43219e-51 |
| pw_6h − pw_12h | memory_p95_profile_mae | -0.0009995633 | [-0.001104536, -0.0008968286] | -0.00064491 | [-0.0006984972, -0.0005560481] | 3.36062e-104 | 2.68849e-103 |
| pw_6h − pw_12h | n_refresh_events | 34.325 | [33.68, 34.962] | 40 | [39, 41] | 6.36495e-166 | 6.36495e-165 |
| pw_3h − pw_6h | cpu_class_correctness | 0.9035006 | [0.7929792, 1.014016] | 0.804829 | [0.6896552, 0.9132611] | 7.60347e-52 | 2.28104e-51 |
| pw_3h − pw_6h | memory_class_correctness | 0.9057141 | [0.8191983, 0.993326] | 0.804829 | [0.6637168, 0.9202454] | 1.20024e-73 | 7.20144e-73 |
| pw_3h − pw_6h | cpu_p95_profile_mae | -0.0008552744 | [-0.00103639, -0.0006798113] | -0.0003906573 | [-0.0004285133, -0.0003399968] | 4.82482e-65 | 2.41241e-64 |
| pw_3h − pw_6h | memory_p95_profile_mae | -0.0005468046 | [-0.0006203188, -0.0004743497] | -0.0003335917 | [-0.0003687893, -0.0002941325] | 8.67375e-89 | 6.07162e-88 |
| pw_3h − pw_6h | n_refresh_events | 68.168 | [66.87798, 69.44602] | 79 | [78, 81] | 2.43085e-165 | 2.18776e-164 |

### F3_high_cost_limit

| Contrast | Endpoint | Mean Δ | Mean 95% CI | Median Δ | Median 95% CI | Wilcoxon p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_rewrite − pw_3h | cpu_class_correctness | 0.812019 | [0.7355159, 0.8904729] | 0.804829 | [0.7961153, 0.8574737] | 5.72692e-79 | 5.72692e-79 |
| full_rewrite − pw_3h | memory_class_correctness | 0.8366093 | [0.7658259, 0.9061863] | 0.804829 | [0.7407407, 0.8300041] | 5.10677e-90 | 1.02135e-89 |
| full_rewrite − pw_3h | cpu_p95_profile_mae | -0.0008884206 | [-0.001028657, -0.0007537975] | -0.0004151903 | [-0.0004573393, -0.0003800817] | 3.47158e-95 | 1.04147e-94 |
| full_rewrite − pw_3h | memory_p95_profile_mae | -0.0005180767 | [-0.0005746167, -0.000460836] | -0.0003286546 | [-0.0003612462, -0.0003002412] | 2.53537e-112 | 1.01415e-111 |
| full_rewrite − pw_3h | n_refresh_events | 4904.029 | [4811.839, 4995.053] | 5725.5 | [5565, 5821] | 2.10094e-165 | 1.05047e-164 |

All 30 predeclared tests are statistically distinguishable at Holm-adjusted
alpha=.05, with mean/median fidelity direction favoring maintenance/faster refresh
and increased maintenance counts. This establishes neither practical nor
operational superiority. Full-Rewrite adds 4,904.029 refreshes/entity over PW-3h
for mean class differences of +0.8120 CPU / +0.8366 memory percentage points; its
CPU/memory p95 MAE differences are −0.00088842 / −0.00051808 request-ratio units.
No method, interval, statistic or future design is changed based on these values.

## Heterogeneity and predefined robustness

Bootstrap CPU population-std tertiles contain 334 low, 333 medium and 333 high
entities. Cuts: q1=0.02716074985073639, q2=0.11713725627558116. All frozen contrasts
have the same mean fidelity directions within each tier, but this is descriptive
robustness, not additional confirmatory inference or universal per-entity benefit.

| Tier | Entities | PW3−Static CPU pp | Memory pp | CPU MAE Δ | Memory MAE Δ |
| --- | --- | --- | --- | --- | --- |
| low | 334 | 12.2920 | 33.6658 | -0.00276699 | -0.01491976 |
| medium | 333 | 10.7509 | 42.4949 | -0.01485238 | -0.01949733 |
| high | 333 | 12.0902 | 22.2603 | -0.01688622 | -0.00706516 |

Favorable/tied/unfavorable entity counts (descriptive, exact zero ties):

| Treatment | Control | Endpoint | Favorable | Tied | Unfavorable |
| --- | --- | --- | --- | --- | --- |
| pw_12h | static | cpu_class_correctness | 535 | 50 | 415 |
| pw_12h | static | memory_class_correctness | 783 | 46 | 171 |
| pw_12h | static | cpu_p95_profile_mae | 616 | 0 | 384 |
| pw_12h | static | memory_p95_profile_mae | 736 | 8 | 256 |
| pw_6h | static | cpu_class_correctness | 564 | 28 | 408 |
| pw_6h | static | memory_class_correctness | 789 | 24 | 187 |
| pw_6h | static | cpu_p95_profile_mae | 649 | 0 | 351 |
| pw_6h | static | memory_p95_profile_mae | 758 | 4 | 238 |
| pw_3h | static | cpu_class_correctness | 579 | 21 | 400 |
| pw_3h | static | memory_class_correctness | 802 | 17 | 181 |
| pw_3h | static | cpu_p95_profile_mae | 666 | 0 | 334 |
| pw_3h | static | memory_p95_profile_mae | 761 | 2 | 237 |
| pw_6h | pw_12h | cpu_class_correctness | 613 | 125 | 262 |
| pw_6h | pw_12h | memory_class_correctness | 643 | 150 | 207 |
| pw_6h | pw_12h | cpu_p95_profile_mae | 756 | 0 | 244 |
| pw_6h | pw_12h | memory_p95_profile_mae | 864 | 12 | 124 |
| pw_3h | pw_6h | cpu_class_correctness | 665 | 133 | 202 |
| pw_3h | pw_6h | memory_class_correctness | 661 | 185 | 154 |
| pw_3h | pw_6h | cpu_p95_profile_mae | 805 | 0 | 195 |
| pw_3h | pw_6h | memory_p95_profile_mae | 840 | 11 | 149 |
| full_rewrite | pw_3h | cpu_class_correctness | 762 | 84 | 154 |
| full_rewrite | pw_3h | memory_class_correctness | 768 | 98 | 134 |
| full_rewrite | pw_3h | cpu_p95_profile_mae | 867 | 0 | 133 |
| full_rewrite | pw_3h | memory_p95_profile_mae | 914 | 4 | 82 |

Thus PW-3h CPU correctness is lower than Static in 400 entities despite a positive
paired mean; memory correctness is lower in 181. Aggregate/tier direction is
not evidence that every entity benefits. Complete machine-readable strata and
paired deltas are in the sealed outputs.

## Uniform accounting

Initialization is separate. All field-write/change totals below cover runtime
refreshes only. No changed-field-row normalization or manual override is applied.

| Method | Initializations | Refresh events | Field writes | Field value changes |
| --- | --- | --- | --- | --- |
| static | 1000 | 0 | 0 | 0 |
| pw_12h | 1000 | 34563 | 138252 | 70753 |
| pw_6h | 1000 | 68888 | 275552 | 105970 |
| pw_3h | 1000 | 137056 | 548224 | 158272 |
| full_rewrite | 1000 | 5041085 | 20164340 | 891541 |

Total: 5,000 initializations, 5,281,592 runtime refreshes, 21,126,368 field writes
and 1,226,536 field value changes. Static has zero runtime refreshes. PW counts
decompose exactly into periodic events; Full-Rewrite into eligible rewrites.
No duplicate per-method commit timestamps or non-frozen triggers occurred.

## Age / bias / availability diagnostics

Ages below pool verified read records, unlike the entity-weighted fidelity means.
They do not replace the primary endpoint estimand. Per-entity bias/delay/age
statistics and complete read-level bias are also in the primary outputs.

| Method | Mean age h | Median h | p95 h | Maximum h | Age-zero % |
| --- | --- | --- | --- | --- | --- |
| static | 218.468 | 207 | 454 | 496 | 0.252163 |
| pw_12h | 5.5502 | 5.08333 | 11 | 160.083 | 7.99634 |
| pw_6h | 2.61753 | 3 | 5 | 160.083 | 16.0555 |
| pw_3h | 1.13679 | 1 | 2 | 160.083 | 32.2491 |
| full_rewrite | 0.013024 | 0 | 0 | 160.083 | 99.9561 |

Five entities have a maintained-profile maximum age above 24h.
The 160.083h maximum for maintained profiles is retained under the frozen
initialization/pending eligibility rules, not excluded or repaired after outcomes.
The independent replay-free audit reproduces every last-commit/read age and
profile content from actual input timestamps. Static initialization time differs
from the inherited PW/Full-Rewrite bootstrap-last-observation convention as
preregistered; age is time since recorded commit, not measurement recency.

| Method | Mean CPU bias | Mean memory bias |
| --- | --- | --- |
| static | 0.03365637 | 0.02517009 |
| pw_12h | -0.00720171 | -0.00214828 |
| pw_6h | -0.00578564 | -0.00176795 |
| pw_3h | -0.00488635 | -0.00158119 |
| full_rewrite | -0.00365392 | -0.00124148 |

All committed values, truth, primary endpoints and errors are finite. The 2,000
null `period_hours_executed` entries belong to Static/Full-Rewrite and mean
not-applicable interval metadata, not failed measurements. No numeric, causal,
accounting or common-grid violation was found.

## Integrity and independent verification

Verification run: `results/google2019_v4e_verification/runs/c1fb64bed56073f952148b752c3e489dc8c9de1b1b7c1646bdbe5f40868f7bca/2026-10-28T160815.188960Z-c1fb64bed560-0bffb31d`. Its output-manifest SHA-256 is
`58ad31ad9fd098bd23773d1d39a8c033b30162d61271f77ae76e3de971342592`; exact verifier source SHA is
`037bb57746f903656894aab1b10af7dd36c527037662304d494605932907f8ae` and its bytes are preserved in that managed audit.

The separate managed read-only verification reconstructs closing-slot reads,
bootstrap thresholds, all scored profile content/truth, every committed periodic
and full-rewrite timestamp, age, accounting totals and metric aggregations from
local canonical inputs. It independently recomputes all 30 mean/median bootstrap
CIs, Wilcoxon results, Holm adjustments and 30,000 paired entity deltas. There are
1,000 paired entities per test and no outcome-based missing pairs. It executes
no maintenance policy. Its `smoke` purpose labels verification-only evidence;
scientific results remain in the original canonical-purpose Stage-A run.

Exact generation cache validation passes; altered configuration is rejected; a
deliberately tampered temporary COPY is rejected and the canonical run remains
valid. Both output manifests and every declared file hash pass. Neither original
outputs nor raw/canonical data were edited. There were zero invalidated scientific
attempts and zero execution fixes.

Full preflight unit suite: **459 passed, 0 failed, 1 skipped**, from execution
source `ab2434f900e252e6909bedea8b0d509709bd3024`. The existing credential-access blocker test
skips because local dry-run credentials exist; it issues no query. Parse/import/CLI
checks pass. Managed wall time: **6834.620792s**
(113.910min); this includes whole-job scheduling/verification
and is not an isolated maintenance-overhead measurement. Four workers were used.
A temporary local keep-awake assertion ended with its process.

## Gate / claim boundary

The 1,000 entities belong to **130 distinct collection IDs**. The
frozen primary unit remains entity; its uncertainty does not fully account for
possible within-collection dependence. No post-outcome clustered reanalysis or
selective exclusion is substituted for the frozen tests. Contrasts estimate the
complete frozen policy contracts, including initialization exceptions and the
inherited PW history gate; they do not isolate timing under identical
initialization. These limitations apply to interpreting the estimates.

Stage A is valid first Google replication evidence for the frozen maintenance/
cadence estimands on this cell/cohort. No practical margins were introduced.
C1 forecasting and C2 adaptive superiority remain withdrawn. Broad C3
generalization remains unproven; C4 operational benefit, acceptable measured
overhead and edge/heterogeneous deployment claims remain unproven. No absolute
Google/Materna error pooling or capacity-equivalence claim is made.

**Stage B remains mandatory**, including if e had been negative. Its source/design/
methods/statistics/identity-hash rule are unchanged; no e outcome enters g
selection or configuration. g is held-out within-corpus replication, not another
independent corpus. Acquire/validate g only under separately authorized zero-spend,
monthly-ledger and disk safeguards, then bind its independent cohort and run the
same frozen study. No g access/acquisition occurred here. **V4C INCOMPLETE;
V5 BLOCKED UNTIL G REPLICATION.**

Post-findings focused regression checks: **55 passed, zero failed/skipped**.
Frozen Stage-B config SHA remains `c1d79eda67ce751d09d139df6fb95f76b133a0e93a2386e9a25a952d78392b32`, identical to the preregistered
source/design. These checks do not execute real Google outcomes.
