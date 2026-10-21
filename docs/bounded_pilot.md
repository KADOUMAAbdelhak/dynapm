# Bounded development pilot

> Current verified generation: `causal-timeline-v3`, `phase-balanced-hourly-v1`, `budget-match-uniform-eligible-v2`. V2 PASS; V2.5 NEXT; V3 BLOCKED UNTIL V2.5. The earlier design/verdicts below are historical Phase 3A records, superseded by [the current protocol](protocol.md) and the verified remediation record at the end.


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

### Invalidated remediation attempt

Run `2026-10-21T110336.455748Z-e6812721436f-d6c72515`, fingerprint
`e6812721436f32c9eafce56504c73d17381fc075ce574cb192b2f8d1ee34a2ca`,
source `2fdc7db1152e5117e015dd3cab2a5d1f29199be2`, was stopped before
completion because the timestamp-only summary still emitted the superseded v2
readiness verdict. The actual gap-safe eligibility report was separate, but the
conflicting labels made the artifact set ambiguous. Worker termination caused
managed FAILED/BrokenProcessPool recording. No output was patched or reused.
The raw timestamp summary now reports only the requirement for exact-grid
eligibility, explicitly identifies the current protocol, and delegates readiness
to the eligibility audit plus bounded invariants. Regression coverage prevents
the stale verdict. The entire pilot must restart from a new clean commit.

## Verified corrected pilot — Phase 3A-R / V2

**V2: PASS. V2.5: NEXT. V3: BLOCKED UNTIL V2.5 PASS.**
This is bounded exploratory execution evidence, not a claim-generating result.
It supersedes the earlier pilot's readiness decision without editing its artifacts.

- Source: `82a79b90d70ce0405ffbf161698180bdf4f49ed7` (clean at execution).
- Protocol: `causal-timeline-v3`; grid: `phase-balanced-hourly-v1`; accounting: `refresh-accounting-v1`.
- Fingerprint: `6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682`.
- Run: `2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe`.
- Cohort SHA-256: `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f`. Same permanent 18 development VMs.
- Output-manifest SHA-256: `d554956ea600bd7d9aa24447f1df832d0a8166914fcd2473da5b27eef9e49c84`.
- Location relative to repository: `results/runs/6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe/`.
- Completed: **198/198** method/entity evaluations, with 11 fixed configurations each.
- Snapshot records: **99,231**, versus **8,129** in the earlier defective-clock pilot.
- Compute wall time: **7882.374 seconds**; preparation **186.087 seconds**; 4 VM workers. This is feasibility timing, not a controlled maintenance-cost benchmark.
- PW/PP nominal and actual commits match at every interval for every VM. V3 = periodic+drift; BudgetMatched = periodic+budget_extra = V3, independently reconstructed using only K and input eligibility.
- All methods use identical verified nominal timestamps, target bytes, labels and thresholds within each VM. Every periodic configuration has nonzero age coverage; no all-zero-age aliasing remains.
- Zero duplicate/colliding commits, nonfinite committed/scored values, or runtime causal/numeric assertion failures. Synthetic tests separately verify future-data invariance and exact-grid behavior.
- Exact pilot cache validates. Mutated configuration, claim-purpose request, tampered COPY and prior v2 protocol cache are rejected. Completed outputs were not rewritten.
- Unit validation: **256 passed, 0 failed, 0 skipped**; 66 Python files parsed/compiled, 41 modules imported. No full-corpus model/policy run or historical archive input.

### Observed periodic profile age (hours; PW and PP)

| Interval | Min | Median | p95 | Max | Fraction zero |
|---|---:|---:|---:|---:|---:|
| 3h | 0 | 1 | 2 | 43 | 32.823412% |
| 6h | 0 | 3 | 5 | 46 | 16.383993% |
| 12h | 0 | 5.08333 | 11 | 52 | 8.103314% |

Synthetic complete-series tests establish exact post-first-refresh phase sets 3h={0,1,2}, 6h={0,..,5}, 12h={0,..,11}. Sparse telemetry can delay eligible commits; bootstrap age before the first periodic commit is separately retained.

### Per-VM paired refresh budget

| Trace | VM | V3 | BudgetMatched | Drift/extra K | Verified times per method |
|---|---|---:|---:|---:|---:|
| Materna-Trace-1 | 143 | 88 | 88 | 7 | 464 |
| Materna-Trace-1 | 76 | 84 | 84 | 3 | 464 |
| Materna-Trace-1 | 374 | 83 | 83 | 2 | 464 |
| Materna-Trace-1 | 213 | 81 | 81 | 0 | 464 |
| Materna-Trace-1 | 96 | 98 | 98 | 18 | 464 |
| Materna-Trace-1 | 64 | 73 | 73 | 4 | 396 |
| Materna-Trace-2 | 516 | 88 | 88 | 7 | 471 |
| Materna-Trace-2 | 11 | 91 | 91 | 10 | 463 |
| Materna-Trace-2 | 396 | 104 | 104 | 18 | 497 |
| Materna-Trace-2 | 207 | 87 | 87 | 1 | 497 |
| Materna-Trace-2 | 388 | 86 | 86 | 0 | 497 |
| Materna-Trace-2 | 398 | 77 | 77 | 1 | 437 |
| Materna-Trace-3 | 224 | 110 | 110 | 10 | 581 |
| Materna-Trace-3 | 127 | 116 | 116 | 16 | 581 |
| Materna-Trace-3 | 212 | 105 | 105 | 5 | 581 |
| Materna-Trace-3 | 151 | 103 | 103 | 3 | 581 |
| Materna-Trace-3 | 83 | 108 | 108 | 11 | 564 |
| Materna-Trace-3 | 133 | 101 | 101 | 6 | 555 |

### Exploratory diagnostics only

No confirmatory tests, practical-margin fitting or parameter tuning were performed. Means below are unweighted per-VM descriptions. They cannot establish publication claims.

| Method | CPU class accuracy | Memory class accuracy | CPU p95 MAE | Memory p95 MAE | Mean refreshes |
|---|---:|---:|---:|---:|---:|
| budget_matched | 0.371807 | 0.288350 | 2.701067 | 3.611845 | 93.500 |
| full_rewrite | 0.757170 | 0.727047 | 0.402271 | 0.694314 | 6287.500 |
| pp_12h | 0.376480 | 0.290829 | 2.690887 | 3.579405 | 43.111 |
| pp_3h | 0.371182 | 0.281101 | 2.677444 | 3.609910 | 173.444 |
| pp_6h | 0.371520 | 0.287823 | 2.702575 | 3.608498 | 86.722 |
| pw_12h | 0.740675 | 0.714194 | 0.428464 | 0.751333 | 43.111 |
| pw_3h | 0.752860 | 0.725420 | 0.413162 | 0.710801 | 173.444 |
| pw_6h | 0.748002 | 0.718477 | 0.427604 | 0.725887 | 86.722 |
| reactive | 0.669363 | 0.599778 | 1.095632 | 1.035319 | 218.056 |
| static | 0.497765 | 0.552956 | 0.649198 | 1.051004 | 0.000 |
| v3 | 0.374043 | 0.289576 | 2.687693 | 3.605327 | 93.500 |

Exploratory V3 minus BudgetMatched paired per-VM mean deltas: cpu_class_accuracy=0.00223589, memory_class_accuracy=0.00122671, cpu_p95_mae=-0.01337453, mem_p95_mae=-0.00651745. Error deltas use raw error direction (negative means lower error); these descriptions do not set confirmatory thresholds.

### Nominal reads during missing telemetry

Raw timestamp reconciliation finds **16** globally verifiable nominal hourly origins without an observation (VM 96: 1; VM 396: 1; VM 516: 7; VM 133: 7), yielding **176** method snapshots. All retain their exact nominal evaluation time and future target horizon. The independent `-clock-read-check.json` report is stored beside the cache/event verification reports outside the immutable completed run.
