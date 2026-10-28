# V4F — Google collection-aware secondary robustness freeze

**Status: procedure frozen before any g outcomes; primary analysis unchanged.**
This task audits e cohort identities and tests synthetic analyses. It does not
compute real e collection-aware outcome estimates or access g data/outcomes.
Any subsequent e application is **post-hoc sensitivity**, because Stage-A primary
outcomes were already available. The identical procedure is **prospective
secondary robustness for g**. Neither replaces the primary analysis.

Authority: `configs/google2019_collection_robustness_v1.{json,yaml}`.
The structure audit and its complete 130-row inventory are recorded in
`configs/google2019_v4f_structure_audit.json`. The original staged design,
Google clock/protocol, acquisition/cohort rule, five methods, primary F1/F2/F3,
entity bootstrap, Wilcoxon/wilcox, Holm families and practical-significance
framing remain byte-unchanged. This is an explicitly scoped secondary supplement
authorized after e, not a retroactive preregistration of e results.

## 1. Stage-A identity-only structure audit

Fixed cohort SHA-256:
`992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c`.
Only `(cell, collection_id, instance_index)` is read; no performance, utilization,
volatility, residual or outcome column influences this audit or procedure choice.

| Quantity | Value |
|---|---:|
| Selected entities | 1,000 |
| Represented collections | 130 |
| Entities/collection: min / median / mean | 1 / 2 / 7.6923 |
| p75 / p90 / p95 / max | 6 / 17 / 24.55 / 158 |
| Singleton collections | 56 (56 entities) |
| Collections with >=2 members | 74 (944 entities) |
| Collections with >=5 / >=10 members | 40 / 20 |
| Top 1 / 3 / 5 entity shares | 15.8% / 32.1% / 44.7% |
| Top 10 / 20 entity shares | 56.8% / 72.2% |
| HHI of selected-entity shares | 0.052904 |
| Inverse HHI | 18.9021624 |

For counts n_c, N=sum(n_c), HHI=sum((n_c/N)^2). Inverse HHI describes the number
of equally sized collections with equivalent concentration. It is **not** an
estimated independent sample size, degrees of freedom, ICC or design effect.
The largest collections are 35027604027 (158), 35039731113 (82), 47253798119 (81),
22146639972 (68) and 50359267525 (58). Selection is unchanged.

Full size histogram (`size: number of collections`):

```text
1:56  2:19  3:11  4:4   5:6   6:3   7:5   8:2   9:4
11:2  13:1  14:2  16:1  17:2  19:1  22:1  23:2  24:1
25:1  26:1  58:1  68:1  81:1  82:1  158:1
```

Collection-ID aggregation and resampling are computationally feasible: all 130
represented collections are nonempty, and 74 have repeated selected entities.
Singleton collection means are valid observed summaries and remain included;
their within-collection variance is not estimable separately. Strong size
imbalance limits precision/interpretation of entity-weighted results. Raw C=130
does not guarantee independent collections or nominal CI coverage. No size-based
exclusion or estimator choice is made to improve e results.

## 2. Frozen estimands and scope

For each unchanged family/contrast/endpoint, let d_ci be an entity's paired
`treatment - control` effect, n_c its selected collection size and m_c its
within-collection mean. The collection key is `(cell, collection_id)`.

1. **Primary entity mean:** D_E=sum(n_c*m_c)/sum(n_c). Display the original
   primary mean/median, entity-bootstrap CIs, Wilcoxon and Holm values unchanged.
2. **Cluster-adjusted uncertainty for the same entity-mean target:** retain D_E
   as the point estimate, but compute a whole-collection bootstrap CI below.
3. **Equal-collection mean:** D_C=mean_c(m_c). This is a different estimand,
   describing a typical represented collection with equal collection weights.
4. **Collection median of means:** median_c(m_c), with its cluster-bootstrap CI.
   This is neither the entity median nor an average of collection medians.

All 30 existing contrast/endpoint combinations are mandatory, including
`n_refresh_events`. No contrast is added, dropped or selected after inspection.
All selected entities and singleton/multi-member collections remain. Do not
subsample one member per collection, trim large collections, weight by exposure,
impute missing pairs, backfill, or silently drop nonfinite/failed records.
Incomplete or inconsistent primary input raises an error instead.

Collection means summarize **selected members of represented collections**.
They do not recover unselected members or represent an equally sampled population
of all Google collections. The original identity-hash cohort remains entity-based.
Report both estimands even if they disagree; never choose the favorable weighting.
The primary entity-median CI is displayed unchanged. This supplement does not
claim a cluster-adjusted CI for the entity median.

## 3. Whole-collection bootstrap

Fixed B=10,000, seed=20251022, confidence=95%, percentile intervals. These values
are inherited from the primary design, not selected from e effects. NumPy PCG64
is explicit; relevant environment/package versions are recorded by managed
provenance. Collection IDs sort numerically, members by canonical entity string.
The same seeded collection-index draws apply to every contrast/endpoint.

For each replicate, sample C collection IDs uniformly with replacement. Include
**all selected members** each time a collection is drawn, preserving multiplicity
and paired outcomes. Do not resample members within a drawn collection.

- Entity-mean replicate: sum_draw(n_c*m_c)/sum_draw(n_c). The denominator may
  vary because collection sizes differ. It is not an unweighted collection mean.
- Collection-mean replicate: mean of the C drawn collection means.
- Collection-median replicate: median of the C drawn collection means.

Use the 2.5th/97.5th percentiles with linear quantile interpolation. Intervals are
nominal marginal secondary intervals, not multiplicity-adjusted simultaneous
intervals. No new p-values, signed-rank/sign tests, Holm family, practical margin,
significance declaration or automatic claim/gate upgrade is introduced.

If C<2, retain points/counts/signs, return null secondary CIs and
`INSUFFICIENT_COLLECTIONS`. Do not substitute entity-IID CIs, pool cells or alter
the cohort to manufacture cluster precision. For C>=2 the algorithm runs and
reports C/concentration explicitly; small C/coarse distributions remain limitations,
not grounds for a new exclusion or favorable-method decision.

Collections are treated as resampling units, not proven independent units.
Between-collection, shared-provider/month and workload dependencies remain.
Singleton noise and selected-member coverage also limit generalization. These
sensitivity CIs do not establish operational/practical benefit.

## 4. Cluster-aware direction consistency

For each contrast/endpoint report collection mean signs as raw
positive / exact zero / negative counts and fractions, with denominator C
including zeros. There is no epsilon or margin. Also report the fraction whose
sign agrees with the original entity-mean sign; an exactly zero primary mean
agrees only with zero collection means. These are descriptions, not sign tests.

Compare entity/equal-collection mean directions using `same_positive`,
`same_negative`, `same_zero`, `discordant_or_one_zero`. Preserve endpoint
orientation: higher correctness, lower MAE; positive cost means more refreshes,
not a fidelity benefit or automatic utility judgment. No effect weighting score.

## 5. Separate-cell synthesis

Analyze e and g separately before any synthesis. For every fixed key, show:

- original entity mean/median, original CIs/p-values/Holm;
- cluster-adjusted entity-mean CI;
- equal-collection mean and median-of-means with their CIs;
- N, C, size/concentration diagnostics and collection sign counts/fractions;
- explicit **e POST_HOC** versus **g PROSPECTIVE SECONDARY** labels.

Across cells, apply the same four direction categories separately to entity mean,
collection mean and collection median-of-means. Show g-minus-e point differences
as descriptive magnitude/heterogeneity only. No pooled entities, pooled CI/p-value,
favorable-cell selection or global superiority rule. Report shared collection-ID
counts once g exists; do not exclude shared IDs after outcomes or treat disjoint
IDs as proof of independence. No Google/Materna absolute-error pooling.
Stage B must run regardless of e direction, with unchanged identity hash/no
backfill/methods and primary statistics.

## 6. Implementation, managed execution and verification

`dynapm/experiments/google_collection_robustness.py` implements identity-only
structure auditing, validated complete paired aggregation, whole-cluster bootstrap,
side-by-side preservation of primary fields and separate-cell synthesis.
`task31_google_collection_robustness` is a separate, explicit postprocessor;
`task30` and all primary runtime files are untouched. JSON/YAML, source hashes
and the parent primary contract are checked by `frozen_spec`.

Safe command (no primary/result/raw/g access or analysis):

```sh
python -m dynapm.scripts.task31_google_collection_robustness --cell g
```

A future **separately authorized** invocation adds `--execute --primary-run PATH`
and requires clean committed source plus a sealed matching-cell canonical primary
run. Unversioned, failed, incomplete, wrong-cell or scientifically incompatible
parents are rejected. No parent result is edited. Each real derivation is a new
managed generation under ignored `results/google2019_collection_robustness/runs/`.
Its fingerprint binds source/environment, this secondary spec, parent experiment,
output manifest, cohort and summary hashes. Parent hashes are rechecked at end;
output manifests/SUCCESS or FAILED use the existing lifecycle/cache validator.

Outputs: within-collection effects Parquet, side-by-side estimates Parquet,
frozen secondary design/parent binding and coverage diagnostics. The technical
`claim` run-purpose flag denotes canonical provenance only: **e is always post-hoc
sensitivity**, even in a clean managed run, and this output never replaces the
primary analysis. No real sensitivity analysis is run in V4F.

Tests use synthetic paired data, including unequal collection sizes, singletons,
C=1, exact ties, reversed estimand directions, shuffled order, incomplete/nonfinite
pairs, config tampering, scoped cross-cell synthesis and a managed synthetic parent.
A literal repeated-member bootstrap independently checks the vectorized algorithm.
No real e/g outcomes, policy execution, BigQuery calls, acquisition or method tuning
are part of these checks.

## 7. Gates

V4F freezes secondary robustness only. Stage A stays PASS with its original
entity-level findings intact. V4C remains incomplete; V5 stays blocked until
mandatory g acquisition/validation and replication. Primary Stage-B design,
cohort rule, methods, F1/F2/F3, Holm and estimation-first/no-margin framing are
unchanged. e sensitivity is optional post-hoc reporting under this same procedure;
g secondary robustness is prospectively specified and must be reported with g.


## Verification record

`configs/google2019_v4f_validation_record.json` records **492 passed, zero failed,
one skipped** in the full lightweight suite; **33 passed, zero failed/skipped**
in the focused secondary suite. The existing access-blocker test skips on this
machine with local dry-run credentials and issues no query. All 124 Python files
parse; module imports, CLI help, the no-analysis default and local documentation
links pass. Managed synthetic-parent tests preserve every parent file byte and
validate the new derived output manifest. No real secondary outcomes are computed.

- Secondary schema: `google2019-collection-robustness-v1`.
- Secondary spec/JSON SHA-256: `83a39740c9902c654512c24d1bc0e33f7e20544a0ef82964513294a5a5eee6e6`.
- YAML SHA-256: `29f91a38b684dc5e53de9be54ee809b2f1b33f35f3ad2f3e55fd8c8332ba4ed8`.
- Identity-structure inventory SHA-256: `0a6f0bac3baed92dc22c5cbca03f24cbd7c1a2a8948d2febd05b96614a0ed6ff`.
- Unchanged primary staged-design SHA-256: `dd857518fd7471a2e7c8cce94f6922f52aa278b637ff38f2656db807c322d33d`.
- Unchanged Stage-B primary config SHA-256: `c1d79eda67ce751d09d139df6fb95f76b133a0e93a2386e9a25a952d78392b32`.

Primary cohort/rule/runtime, Stage-A manifest/output-manifest and query-ledger
hashes remain exact. No BigQuery/cloud calls, g data access, tuning, policy
execution or changes to primary results/statistics occurred.
