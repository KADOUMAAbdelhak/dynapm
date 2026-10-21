# Materna timestamp-gap audit

Phase 3A input-only characterization. Source `3d66c50f6bb3b87734f7857926f1d9f3844c3625`; run `2026-10-21T052752.223470Z-4f8536add087-68ffcfb8`. All 1,576 retained VMs were inspected for timestamps; only the selected 18 VMs underwent model/policy evaluation. No feature semantics were changed.

## Evidence

Managed artifacts: `/Users/fgtek002/dynapm/results/runs/4f8536add087f4eb2bcd2292067ecab2f86f9a24968bbdd1166c236d698ad510/2026-10-21T052752.223470Z-4f8536add087-68ffcfb8/outputs/materna_gap_audit.parquet` (per-VM maxima and within-phase counts) and `materna_gap_audit.json`. The raw dataset manifest and cohort/selection identities are in the same run. SHA integrity was independently validated.

| All retained consecutive intervals | Count | Percent of intervals | VMs containing category |
|---|---:|---:|---:|
| Exactly 5 minutes | 13,983,989 | 99.98990376% | 1,576 |
| Over 5 minutes | 1,412 | 0.01009624% | 641 |
| Over 10 minutes | 1,169 | 0.00835872% | 634 |
| Over 30 minutes | 421 | 0.00301028% | 342 |
| Over 1 hour | 320 | 0.00228810% | 265 |

Denominator: **13,985,401 intervals**. Threshold categories are nested, not additive. Maximum gap: **918,300 seconds (10.628472 days)**.

| Phase | Intervals | Over-1h intervals | VMs with over-1h gaps | Maximum seconds |
|---|---:|---:|---:|---:|
| bootstrap | 4,193,814 | 126 | 102 | 574,500 |
| streaming | 9,790,011 | 194 | 177 | 918,300 |

The all-series record includes the split-crossing interval; each within-phase record excludes it. Percentages alone understate entity prevalence: rare intervals affect many VMs. Per-VM maxima and counts are retained in the Parquet, rather than replacing them with aggregate averages.

## Historical v2 verdict: GAP SEMANTICS REQUIRES PRE-V3 CORRECTION

The pre-execution conservative gate flags any retained history gap over one hour. It was frozen before viewing pilot method effects. Observed-row lags and windows can silently bridge long outages while recursive forecasts advance five-minute calendar time. This is a temporal-modeling/eligibility issue, not evidence of future leakage. The successful causal replay does not establish acceptable missing-data semantics for confirmation.

Required before gate V3 (full Materna generation):

1. Separately review and freeze an explicit elapsed-time/grid or segment/reset history rule and warm-up/eligibility behavior. Do not silently impute, bridge, exclude or re-anchor data.
2. Apply the rule consistently to bootstrap training features, one-step residuals, recursive refresh history and observation-window controls. Define ADWIN gap/reset handling explicitly. Periodic-grid and evaluation rules must remain coordinated and versioned.
3. Ensure shared evaluation eligibility across policies, report exclusions by data-quality rules, fingerprint the rule/config/protocol, and add gap-boundary/causality regression tests.
4. Rerun bounded validation as a new clean-source generation before any full run. Retain the permanent development-cohort exclusion rule. Do not choose the correction or thresholds to favor viewed pilot effects.

This task implements none of those corrections. V2 remains BLOCKED; gate V3 is not NEXT. No full corpus, additional dataset, system experiment or manuscript work is authorized by this audit.

## Phase 3A-R temporal remediation

The previous pilot used `causal-timeline-v2` and a 12h read grid. Its execution
integrity passed, but observed-row gap handling and refresh/read aliasing blocked
scientific readiness. It is not reused by the corrected generation.

The corrected protocol is `causal-timeline-v3`, with `phase-balanced-hourly-v1`,
complete 96-slot nominal history, trailing 200/288 (24h) and 50/72 (6h) coverage,
and a shared PW/PP/V3 periodic eligibility gate. Reads remain nominal even when
telemetry is missing. Profile age is recorded at each read. Budget candidate
eligibility is versioned `budget-match-uniform-eligible-v2`.

The same permanent 18 development VMs are retained. Their outcomes cannot be
primary independent confirmation. After bounded validation, V2.5 must freeze
final eligible confirmatory cohort, pilot exclusions, endpoints, comparison
families, benefit/harm margins, multiplicity, tests/CIs, tiers, exclusion and
missing-data rules, exploratory/confirmatory distinctions and the exact method
matrix before the 1,558-entity maximum primary cohort is evaluated. No thresholds
may be chosen to favor observed pilot effects. See [protocol](protocol.md) and
[the v3 metadata audit](materna_gap_semantics_v3.md).

## Corrected-generation disposition

The blocked decision above describes the earlier v2 generation. The corrected v3 pilot passed gap-safe and hourly-read invariants; see [the v3 eligibility audit](materna_gap_semantics_v3.md) for metadata counts and [bounded pilot](bounded_pilot.md) for its immutable run identity. Gap frequency/maxima remain input facts, not justification for bridging. V2.5 remains required before full confirmation.
