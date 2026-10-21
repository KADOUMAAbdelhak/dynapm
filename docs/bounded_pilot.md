# Bounded development pilot

Phase 3A / V2 is a development experiment, not claim evidence. Run only with `purpose=pilot`, clean committed Git source, Phase 2C manifests and the managed `RunSession`. No unmanaged predictions, thresholds, results or historical archive are inputs. No model tuning or confirmatory tests are permitted.

## Selection and separation

Use the existing >=2000-observed-row eligibility rule. Compute CPU utilization standard deviation (`ddof=0`) on the first 30% bootstrap rows only. As in the existing tier computation, use pooled retained-VM tertile cutoffs, with values <=q1 low and <=q2 medium. Within each of three traces and three tiers, order by SHA-256 of `dynapm-v2-pilot-selection-v1|trace|vm_id` and choose the first two. A deficient cell stops execution. Store the complete selection pool, cutoffs, ranks, reason, selected cohort manifest and its scientific digest. Outcomes are not selection inputs.

The resulting 18 entities are permanently the DEVELOPMENT PILOT COHORT. Primary future confirmatory Materna analysis must exclude them. A separate optional whole-corpus descriptive analysis may include them only after design freeze; it is not independent confirmation. The cohort manifest in the managed run is the authoritative exclusion identity.

## Frozen matrix and execution binding

Exactly 11 configurations per VM: Static; Reactive; Full-Rewrite; PW 3/6/12h; PP 3/6/12h; V3 6h with current ADWIN delta .002; BudgetMatched 6h plus paired extras. Total 198 evaluations. RF parameters remain 200 trees, max depth 20, sqrt features, seed 42, one inference job; CPU and memory have separate models trained once per VM. No pilot forest is trained separately for each policy.

`prepare_vm_inputs`, `replay_from_inputs` and `evaluate_replay` share production preparation, event timeline and snapshot verification. Independent policy states share immutable inputs/thresholds/labels and the frozen target models. Observation-only constructors receive no predictors. The driver binds model parameters, period, drift delta, lookback and evaluation/density settings explicitly; it rejects unsupported configuration rather than recording settings it ignores.

Exact recursive horizons may be reused only in process memory for the same VM, frozen target model, origin and SHA-256 of the entire available history. Returned Series are copies. There is no disk/model/result-cache reuse. Each forecast still uses the existing recursive implementation and `(t,t+24h]` targets. Runtime checks enforce finite outputs, 288 targets and exact five-minute cadence. Unit tests retain future-data invariance and target independence.

## Analysis-only matched budget

`budget-match-uniform-observed-v1` accepts the processed observation timeline, base 6h periodic commits and integer K = paired V3 drift-refresh count. It does not receive V3 drift timestamps, residuals, labels or fidelity. Remove base periodic commits from candidates. For N remaining candidates choose indices `floor((2*i+1)*N/(2*K))`, i=0..K-1. For K<=N these are ordered, unique, evenly spaced midpoint quantiles. K=0 is exactly PP6. Reject impossible K or collisions.

Base events are periodic; extras are `budget_extra`, never drift. This additive accounting category exposes `n_budget_extra_refreshes` under the existing refresh-accounting-v1 operation definitions. Existing policy counters/definitions are unchanged. Source fingerprint prevents older records from sharing this generation. Both total equality to V3 and equal periodic count to PP6 must hold per VM. This is an analysis-only counterfactual, not a deployable online policy: K is known from the completed paired V3 execution.

## Outputs and checks

`python -m dynapm.scripts.task20_bounded_pilot --help` is safe. Actual execution requires clean committed source and separate experiment authorization. This driver has no full-run mode: exactly 18 unique selected entities, two per trace/tier, maximum guard 50. Default workers=2, maximum 4, parallelizing VMs only.

Managed artifacts in ignored `results/runs/<fingerprint>/<run_id>/` include selection/cohort, per-VM results, events, exact extra schedules, evaluation alignment evidence, all-retained gap audit, diagnostics, descriptive summaries and per-VM completion logs. A post-completion verification record outside the immutable run reports exact-pilot acceptance, altered-config rejection, claim-purpose rejection and output tampering on a disposable byte COPY. No canonical output is edited.

All 198 evaluations must complete. PW/PP counts and periodic schedules match per interval; V3 total=periodic+drift; BudgetMatched total=periodic+budget-extra=V3 total; Static runtime=0. Initialization is separate. Verified timestamps, nominal horizon targets, observed target bytes, ground truth and thresholds agree across all methods. No field-row counting or manual normalization is used. Failures block the pilot; source bugs require a regression/commit and a completely new run/fingerprint, never patched outputs.

## Gap decision before confirmation

The audit reads timestamps across all retained VMs: intervals exactly 5m, >5m, >10m, >30m, >1h; total and per-VM maxima; VM counts; bootstrap and streaming subsets. The all-series record includes the split-crossing interval; each within-phase record excludes it.

Pre-execution conservative gate: any retained history gap >1h requires a separately reviewed preconfirmation gap policy. A row-based lag/window can silently bridge such an outage, while recursive forecasts advance nominal five-minute time. This does not imply future leakage; it makes the temporal meaning inconsistent with an unqualified elapsed-time interpretation. Passing the 18-VM replay cannot override this gate. Do not change feature semantics or exclude unfavorable VMs in this task.

## Decision status

Implementation and synthetic validation precede the first clean-source scientific pilot. Record actual run identity and factual diagnostics after execution. V2 passes only after all requested execution/integrity criteria and the gap-semantics decision permit proceeding. Otherwise V2 is BLOCKED and no full Materna generation is authorized. Practical benefit/harm margins, primary endpoints and comparison families must be frozen separately; exploratory pilot effects cannot be used to choose favorable thresholds.
