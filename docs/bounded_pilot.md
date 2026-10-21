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

## Verified execution record

- Source commit: `3d66c50f6bb3b87734f7857926f1d9f3844c3625` (clean, committed before execution).
- Purpose: `pilot`; not claim-eligible.
- Experiment fingerprint: `4f8536add087f4eb2bcd2292067ecab2f86f9a24968bbdd1166c236d698ad510`.
- Run ID: `2026-10-21T052752.223470Z-4f8536add087-68ffcfb8`.
- Pilot cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`.
- Managed run: `/Users/fgtek002/dynapm/results/runs/4f8536add087f4eb2bcd2292067ecab2f86f9a24968bbdd1166c236d698ad510/2026-10-21T052752.223470Z-4f8536add087-68ffcfb8`.
- Output manifest SHA-256: `e8e9df629285b085774aea9178743ab6e431a643f5bc2a67d8314fa0d5fbf494`.
- Attempted/completed: 198/198; all 18 VM matrices complete.
- Managed duration (manifest start/end): 4432.155 seconds. Matrix compute wall time: 4430.425 seconds; preparation: 28.204 seconds. These are feasibility timings with shared forecasts, not independent policy overhead measurements.
- Unit tests: 223 passed, 0 failed, 0 skipped.
- Count, periodic-schedule, common-evaluation/target/threshold, numeric and exact-budget checks: PASS for every VM. Zero periodic/extra collisions.
- Exact pilot cache: accepted. Changed configuration and a tampered disposable COPY: rejected. Pilot-to-claim reuse: rejected. Canonical outputs were not edited.
- Independent event/counter, schedule and output-schema reconciliation: PASS.
- Invalidated scientific attempts: none. This is the first and only scientific pilot execution in this task.
- Gap semantics: **REQUIRES PRE-V3 CORRECTION**. V2: **BLOCKED**.

### Permanent development cohort

These exact `(trace, VM ID)` pairs are excluded from primary future confirmation. IDs repeat across traces, so exclusion must use the pair, not the numeric ID alone.

| Trace | Tier | VM IDs (hash-rank order) |
|---|---|---|
| Materna-Trace-1 | low | 374, 213 |
| Materna-Trace-1 | medium | 96, 64 |
| Materna-Trace-1 | high | 143, 76 |
| Materna-Trace-2 | low | 396, 207 |
| Materna-Trace-2 | medium | 388, 398 |
| Materna-Trace-2 | high | 516, 11 |
| Materna-Trace-3 | low | 212, 151 |
| Materna-Trace-3 | medium | 83, 133 |
| Materna-Trace-3 | high | 224, 127 |

### Gate disposition

All 198 evaluations completed under the recorded current protocol. Execution integrity does not override the gap gate. See [the full input gap audit](materna_gap_audit.md). No method parameters were tuned; the machine-readable summaries are PILOT / EXPLORATORY only. No confirmatory significance tests, historical-number comparisons, full-corpus evaluation or manuscript generation were performed.

Before full confirmation, separately freeze primary endpoints, benefit/harm margins and confirmatory comparison families. Do not derive favorable thresholds from these pilot effects.

### Evaluation phase-aliasing finding

All 5,912 scored periodic-policy snapshots coincide with periodic commits; every one is read at zero refresh age. Across 739 VM/origin pairs, the five predictor configurations have confirmed pointwise-identical class-correctness and p95-error values. The 12h evaluation cadence shares its anchor with 3h/6h/12h refresh grids. Therefore these snapshots cannot identify the benefit of between-tick drift timing or more frequent predictor refresh. This is a structural measurement-design defect, not evidence that adaptive timing has no benefit.

Before confirmation, separately pre-register phase-balanced shared evaluation opportunities, verify nonzero profile-age coverage for each period, and rerun bounded validation under a new fingerprint. Preserve refresh-before-read ordering at genuine coincidences. Do not alter or tune methods to manufacture differences. V2 is BLOCKED on this issue as well as gap semantics.
