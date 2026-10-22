# Predictor disposition — V2.4D

Development investigation only. No production predictor, residual RF, detector,
policy, protocol or accounting behavior is changed. V2.5 and V3 remain blocked.

## Frozen analysis plan

Candidates are the existing direct-profile RF (200 trees, depth 20, sqrt features,
seed 42, two outputs: future mean and p95) and seasonal-naive profile content.
The latter is exactly trailing `(t-24h,t]` PW content at a shared origin, requiring
200/288 actual nominal slots. Class is derived from the mean using frozen
bootstrap thresholds; future truth is canonical `(t,t+24h]`, >=200 paired slots.

Origins are taken from the validated corrected V2 pilot event artifact, not
selected using accuracy: PP6 periodic and V3 drift commits are reported separately. The all-origin set
is the deduplicated union of PP3/PP6/PP12/V3/BudgetMatched commits, including
non-adaptive budget extras; recorded source methods are retained. PP6 and V3 periodic commit sets must
match. Origins with unelapsed/insufficient truth are logged, never scored.
Native availability is reported separately; comparisons use identical origins
where both candidates are available. No fallback is introduced.

## Predefined bootstrap selector

For each VM, use four evenly indexed eligible origins from a six-hour grid
anchored at bootstrap start +72h. Each validation origin's complete 24h horizon
must lie inside bootstrap; both resources need 96 complete causal history slots
and >=200 trailing seasonal slots. Eligibility uses presence, not model outcomes.
At each rolling origin, train RF on the prefix ending there: every training
label's horizon has already elapsed. Thresholds are prefix-only for this
prequential validation, shared across candidates. After bootstrap, select RF
only if its four-origin mean class correctness is strictly higher AND its mean
p95 absolute error is strictly lower than seasonal. Every tie chooses seasonal.
The decision is frozen before evaluating streaming origins. Full-bootstrap RF
and thresholds are then used for operational comparisons. Choices are per
VM/resource; this is the explicitly requested selector, not an invented hybrid.

Aggregation is paired-origin within VM, then equal-VM macro averages. Drift-only
summaries include only VMs with verifiable drift origins; coverage denominators
are retained. Neither significance nor performance magnitude is an investigation
completion criterion. No confirmatory VM outcomes are accessed.

## Execution and disposition

Pending managed execution from clean committed source. No architecture choice
is inferred from the earlier eight-origin study. The one-step RF used for
residual/drift surveillance remains a separate, independently unvalidated role.
