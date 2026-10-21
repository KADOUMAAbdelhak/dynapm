# DynAPM Validation Roadmap

This roadmap specifies future gates, not authorization to execute them. The sole active project is the current repository. Historical non-causal measurements cannot satisfy any new causal evidence gate. See [the validation strategy](validation_strategy.md), [protocol](protocol.md), and [consolidation record](consolidation_record.md).

## V0 — CAUSAL PROTOCOL CORRECTNESS

**STATUS: PASS**

- **Objective:** coherent causal construction, shared replay and deterministic timeline. Includes Phase 1 and Phase 2A.
- **Required artifacts:** causal interface tests, future-data invariance tests, horizon alignment assertions, shared event ordering/grid, protocol `causal-timeline-v2`, Phase 1 commit `07fe9efd4b62bea9de9f4c4b849759a8212e4c62` and Phase 2A commit `9a620142a657cd2c3ab21b13e1f1d6dba7485901`.
- **PASS criteria:** target features exclude current utilization; refreshes exclude future observations; `(t,t+24h]` forecast/label alignment; deterministic missing/coincident behavior; lightweight suite passes. Established by completed phases, retained in 123-test baseline.
- **Reviewer concern addressed:** TOCS 11; correctness prerequisite for future-lead claims.
- **Unproven:** corpus accuracy, lag semantics under irregular telemetry, generalization and operational benefit.

## V1A — UNIFORM REFRESH ACCOUNTING

**STATUS: PASS**

- **Objective:** one maintenance-operation definition across all six policies. Includes Phase 2B.
- **Required artifacts:** canonical `n_refresh_events`, separate initialization/writes/changes/triggers, `refresh-accounting-v1`, occurrence audit, Phase 2B commit `b70d4eee0cdb20226b8f63590984bc2fcd6db20c`.
- **PASS criteria:** PW/PP equal counts on equal schedules; V3 total=periodic+drift; coalesced ticks differ from commits; serialization preserves counters; no field-row inference or manual normalization. 123 tests passed, zero failed.
- **Reviewer concern addressed:** TOCS 10.
- **Unproven:** refresh efficacy, matched-budget advantage, cost of each operation.

## V1B — EXPERIMENT PROVENANCE

**STATUS: PASS — Phase 2C**

- **Objective:** independently attributable, fingerprinted, cache-safe result generations. Required before any new full-corpus evaluation.
- **Required artifacts:** [provenance schemas/store/CLI](provenance.md), source/config/input/model/environment fingerprints, raw/cohort manifests, commands/seeds/times, output hashes, failure/exclusion records, deterministic bounded-run tests and [lag semantics assessment](lag_semantics_assessment.md). Implemented with 195 passing lightweight tests; old unversioned entry points fail closed.
- **PASS criteria:** missing/changed relevant fingerprints and corrupt/partial caches are rejected by negative tests; bounded reruns are deterministic within declared tolerance; independent manifest verification succeeds; no archive fallback. Lag assessment either justifies current semantics with bounded scope or requires a separately authorized protocol correction.
- **Reviewer concern addressed:** reproducibility prerequisite for TOCS 1-9; protects 10-11 corrections.
- **Unproven:** scientific benefit, production scalability, full-corpus runtime and pilot-driver config-to-execution/coverage binding. No new empirical result is established.

## V2 — BOUNDED SCIENTIFIC PILOT

**STATUS: IN PROGRESS — Phase 3A authorized, awaiting clean-source pilot validation**

- **Objective:** small VM subset only; test provenance, 3h/6h/12h scheduling, prospective matched-budget design, runtime feasibility, output schema and statistical pipeline sanity.
- **Required artifacts:** [managed 18-VM pilot](bounded_pilot.md), permanent development-cohort exclusion manifest, explicit config-to-execution binding; development/confirmation split plan; bounded pilot config and manifests; runtime/resource estimates; eligibility/output checks; analysis dry-run; calibrated matched-budget proposal; practical-effect/budget margins and pre-registration for confirmation.
- **PASS criteria:** complete provenance; expected schedule/count invariants; no hidden output repair; feasible runtime; explicit handling of missing pairs/zeros/ties; calibration uses development data only; numerical success/harm margins frozen before confirmation. A pilot is exploratory and cannot pass a manuscript claim.
- **Reviewer concern addressed:** TOCS 7-9 design readiness and reproducibility.
- **Unproven:** full-corpus effects, held-out budget matching, generalization, systems relevance.

## V3 — FULL MATERNA CAUSAL EVALUATION

**STATUS: PLANNED — requires V1B and V2**

- **Objective:** fresh causal-generation evidence on the predeclared Materna eligible corpus.
- **Required artifacts:** locked configuration/source; complete run/output manifests; all six per-VM results; exclusion/failure accounting; paired baseline analysis and uncertainty; untouched confirmatory set.
- **PASS criteria:** every included output verifies under current protocols/fingerprints; complete predeclared coverage or justified exclusions; no reuse of historical TOCS metrics; analysis can be independently reconstructed. Record C1/C2 support or failure without requiring a positive result to call execution valid.
- **Reviewer concern addressed:** credible evidence prerequisite; TOCS 10-11 applied to real traces.
- **Unproven:** multiple-interval/matched-budget conclusions until V4, external validity and operational benefit.

## V4 — REFRESH TRADE-OFF EVIDENCE

**STATUS: PLANNED — requires frozen V2 design and V3-quality outputs**

- **Objective:** full 3h/6h/12h PW/PP and matched-budget PP/V3 analysis.
- **Required artifacts:** direct canonical counter summaries; actual budget discrepancy; per-volatility paired effects/CIs; provisioning outcomes; corrected confirmatory tests; benefit-cost curves; negative results and guardrails.
- **PASS criteria:** all planned comparisons reported; no manual counter normalization; calibration/test separation verified; matched-budget tolerance assessed; practical-magnitude/uncertainty criteria used. Mark each claim supported, limited or falsified; a failed scientific claim is not repaired by changing its gate.
- **Reviewer concern addressed:** TOCS 7-8 and update-opportunity confounding.
- **Unproven:** maintenance cost until V5 and downstream operational benefit until V8.

## V5 — MAINTENANCE OVERHEAD

**STATUS: PLANNED — instrumentation needs separate implementation task**

- **Objective:** attribute training, one-step/horizon inference, ADWIN, refresh/commit/state and service-scale cost.
- **Required artifacts:** instrumented boundaries; dedicated hardware/environment record; warm-up/repeated-run protocol; latency distributions/median/p95; CPU/memory/state/throughput scaling; declared overhead budgets.
- **PASS criteria:** repeatable same-environment measurements; no double counting or cross-machine timing comparison; amortized ongoing work included; C5 practical cost budget explicitly passed or failed at a stated scale.
- **Reviewer concern addressed:** TOCS 9 and overhead part of 3.
- **Unproven:** cost-benefit acceptability in a real consumer until V8; different hardware/scale.

## V6 — SECOND-CORPUS REPLICATION

**STATUS: PLANNED — dataset-selection report first**

- **Objective:** at least one substantially different real production corpus, preferably two where feasible.
- **Required artifacts:** formal suitability/acquisition/licensing report; reproducible adapters and hashes; eligibility audit; locked replication protocol; paired per-corpus effects and heterogeneity/negative-transfer report.
- **PASS criteria:** meaningful domain diversity; CPU/memory/time/horizon suitability; no post-outcome eligibility tuning; replication completes with uncertainty and transparent limitations. A broad C3 claim additionally requires frozen practical-benefit criteria to hold, or must be narrowed.
- **Reviewer concern addressed:** TOCS 4-5.
- **Unproven:** unseen domains outside the tested corpora and operational effects.

## V7 — SYSTEM HARNESS

**STATUS: PLANNED — design only in this task**

- **Objective:** working Kubernetes telemetry -> profile service -> fixed provisioning consumer -> resource decision loop.
- **Required artifacts:** environment/deployment configs; observed decision/actuation traces; workload scenarios; policy switch isolation; telemetry/clock verification; reset/randomization plan; system power/precision and trial-count plan; real-time horizon feasibility decision.
- **PASS criteria:** real application and real consumed profile/resource actions; no future data; identical consumer/guardrails across PW/PP/V3/matched-budget PP; operational metrics captured; trial plan frozen. A deployment screenshot is insufficient.
- **Reviewer concern addressed:** integration parts of TOCS 1-2 and 6.
- **Unproven:** operational advantage, acceptable service overhead and empirical edge claims.

## V8 — REPEATED SYSTEM VALIDATION

**STATUS: PLANNED — requires V5 and V7**

- **Objective:** operational benefit and harm estimates under controlled repeated trials.
- **Required artifacts:** independent run/scenario replicates; randomized/counterbalanced order; identical scenarios; environment state; application/resource/control/DynAPM metrics; SLO and resource guardrails; run-level paired CIs/effects and planned inference.
- **PASS criteria:** sufficient preplanned replication to estimate uncertainty; predefined operational magnitude/harm criteria assessed; all failed trials reported; fair native comparison only when justified. C4/C5 support is a separate evidence decision, not inferred from successful deployment.
- **Reviewer concern addressed:** TOCS 1-3; empirical scope part of 6.
- **Unproven:** heterogeneous edge generalization without a dedicated C6 experiment.

## V9 — ROBUSTNESS / ABLATIONS

**STATUS: PLANNED — designs frozen before their runs**

- **Objective:** explain mechanism behavior and boundaries, including negative cases.
- **Required artifacts:** stable/periodic/burst/abrupt/gradual/volatility fixtures; sparse/missing/>period-gap tests; degraded predictor and ADWIN false/late-trigger interventions; drift-off and budget/cost controls; seeds/configs/manifests.
- **PASS criteria:** expected invariants checked; fidelity/cost/safety failure cases exposed; ablations isolate mechanisms; synthetic results labeled mechanistic and never substitute for V6/V8.
- **Reviewer concern addressed:** interpretation of TOCS 7-9 and limits of C1-C5.
- **Unproven:** real-workload prevalence of synthetic stress conditions.

## V10 — CLAIM AUDIT

**STATUS: PLANNED — after relevant evidence gates**

- **Objective:** map every intended manuscript claim to evidence and remove unsupported scope.
- **Required artifacts:** C1-C6 claim ledger; pre-registration IDs; source/config/input/output fingerprints; effect/CI/margin decisions; negative outcomes; reviewer traceability; CECC Path A/B decision.
- **PASS criteria:** every retained claim meets its predefined evidence requirement and declared domain; no significance-only or offline-to-system leap; no historical metrics described as causal; no resource/machine sharing claim without its own experiment; unresolved concerns explicitly limit claims.
- **Reviewer concern addressed:** all TOCS concerns and confirmed historical project lessons.
- **Unproven:** transfer beyond demonstrated scope and editorial acceptance.

## V11 — JOURNAL SELECTION + WRITING

**STATUS: PLANNED — only after V10**

- **Objective:** select a venue fitting the demonstrated contribution, then begin drafting.
- **Required artifacts:** evidence-limited contribution statement, venue-scope/current-ranking audit, approved claim ledger and reproducibility package plan.
- **PASS criteria:** actual evidence fits venue; FGCS treated as candidate rather than destination; no claim expansion to satisfy journal framing; manuscript drafting begins only now.
- **Reviewer concern addressed:** overclaiming and contribution/venue mismatch.
- **Unproven:** peer-review outcome or journal acceptance.

## Dependency and execution rule

V0, V1A and V1B are complete. V2 is NEXT; Phase 2C implements provenance but does not run the scientific pilot. V2 precedes any new full Materna run. V4 uses pre-registered interval/budget evidence, V6 requires dataset selection before replication, and V8 requires the real V7 harness and V5 cost discipline. Planning can identify dependencies, but execution of any experiment requires explicit scope and authorization. No manuscript prose before V10 passes and V11 begins.

Primary V3 confirmation must exclude the 18 development-pilot VMs identified by the V2 cohort manifest. Whole-corpus descriptive analysis is optional and separate. Gap semantics must be resolved before any full run.
