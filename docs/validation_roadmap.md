# DynAPM Validation Roadmap

This roadmap specifies future gates, not authorization to execute them. The sole active project is the current repository. Historical non-causal measurements cannot satisfy any new causal evidence gate. See [the validation strategy](validation_strategy.md), [protocol](protocol.md), and [consolidation record](consolidation_record.md).

## V0 — CAUSAL PROTOCOL CORRECTNESS

**STATUS: PASS**

- **Objective:** coherent causal construction, shared replay and deterministic timeline. Includes Phase 1 and Phase 2A.
- **Required artifacts:** causal interface tests, future-data invariance tests, horizon alignment assertions, shared event ordering/grid, protocol `causal-timeline-v2`, Phase 1 commit `07fe9efd4b62bea9de9f4c4b849759a8212e4c62` and Phase 2A commit `9a620142a657cd2c3ab21b13e1f1d6dba7485901`.
- **PASS criteria:** target features exclude current utilization; refreshes exclude future observations; `(t,t+24h]` forecast/label alignment; deterministic missing/coincident behavior; lightweight suite passes. Established by completed phases, retained in 123-test baseline.
- **Reviewer concern addressed:** TOCS 11; correctness prerequisite for future-lead claims.
- **Unproven:** corpus accuracy, final gap-based cohort eligibility, generalization and operational benefit.

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

**STATUS: PASS — corrected 18-VM pilot, causal-timeline-v3 and phase-balanced-hourly-v1**

- **Objective:** small VM subset only; test provenance, 3h/6h/12h scheduling, exact analysis-only matched-budget design, runtime feasibility, output schema and statistical pipeline sanity.
- **Required artifacts:** [managed 18-VM pilot](bounded_pilot.md), permanent development-cohort exclusion manifest, explicit config-to-execution binding; development/confirmation split plan; bounded pilot config and manifests; runtime/resource estimates; eligibility/output checks; analysis dry-run; exact paired budget-control specification; phase/age and gap-eligibility artifacts. Practical margins and confirmation pre-registration belong to V2.5.
- **PASS criteria:** 198/198 complete with validated provenance/output hashes; exact schedules/budgets and shared nominal truth; finite causal outputs; exact-grid history and wall-clock windows; nonzero age phases; cache-negative probes; full metadata-only audit; no manual output repair. Numerical benefit/harm margins remain deliberately unfrozen until V2.5. A pilot is exploratory and cannot pass a manuscript claim.
- **Reviewer concern addressed:** TOCS 7-9 design readiness and reproducibility.
- **Unproven:** full-corpus effects, held-out budget matching, generalization, systems relevance.

## V2.4 — PREDICTOR DIAGNOSIS + DATASET SUITABILITY AUDIT

**STATUS: PASS — completion; pending review before V2.5**

- **Objective:** diagnose predictor-grounded underperformance on the fixed 18 development VMs; rank independent corpora from official documentation.
- **Required artifacts:** [predictor diagnosis](predictor_diagnosis.md), managed lead/profile/VM diagnostics, [dataset suitability audit](dataset_suitability_audit.md), source/config/output integrity evidence.
- **PASS criteria:** bounded clean-source exploratory diagnostics complete; causes and limitations documented; official-source dataset comparison and recommendation; lightweight suite and provenance validation pass. Accuracy improvement is not a criterion.
- **Reviewer concern addressed:** predictor validity, forecast horizon and cross-corpus readiness.
- **Unproven:** redesign efficacy, generalization, confirmatory effect or system benefit.

## V2.4B — PREDICTOR DESIGN INVESTIGATION

**STATUS: PASS — investigation complete; no single adequate candidate**

- **Objective:** compare four predefined causal fixed-origin forecast designs on the fixed 18 development VMs before freezing confirmation.
- **Required artifacts:** [design investigation](predictor_design_investigation.md), managed all-lead forecasts/metrics/costs, identical-origin and future-invariance tests, source/output provenance.
- **PASS criteria:** bounded, clean-source, paired-target execution completes; comparison to seasonal-naive and per-VM robustness supports an evidence-limited recommendation or explicit no-adequate-candidate conclusion. Beating recursive RF alone is insufficient. No production integration or confirmatory inference.
- **Reviewer concern addressed:** predictive validity, horizon behavior, cost and credible predictor controls.
- **Unproven:** confirmatory advantage, integrated policy outcomes, other-corpus generalization and operational value.

## V2.4C — TASK-ALIGNED PROFILE PREDICTION

**STATUS: PASS — task-aligned study complete; review required**

- **Objective:** test direct future mean/p95 prediction against the four previously fixed point strategies, on the same 18 development VMs/eight origins only.
- **Required artifacts:** [profile investigation](profile_predictor_investigation.md), managed RF/Ridge task-aligned predictions, per-VM/tier errors, costs/state and timestamp-only seasonal availability across 1,576 VMs.
- **PASS criteria:** canonical bootstrap-only labels, future-data invariance, identical origins/truth, valid managed lineage/output integrity and an evidence-limited A/B/C/D disposition. A negative finding can complete the investigation; no automatic integration.
- **Reviewer concern addressed:** task-aligned predictive validity, meaningful profile fields, deployability/availability and maintenance cost.
- **Unproven:** confirmatory effects, integrated policy behavior, cross-corpus generalization and systems benefit.

## V2.4D — PREDICTOR DISPOSITION

**STATUS: PASS — disposition B; architectural follow-up requires review**

- **Objective:** decide whether profile-content forecasting is justified, keeping the one-step residual RF separate.
- **Required artifacts:** [disposition report](predictor_disposition.md), managed actual-periodic/drift-origin comparisons, bootstrap-only prequential selector evidence, per-VM/tier coverage and errors.
- **PASS criteria:** fixed 18 development VMs, identical origins/truth, strict two-metric bootstrap selector, future invariance, clean-source provenance/output integrity, explicit A/B/C architecture disposition; negative findings can pass the investigation.
- **Unproven:** independent confirmation, residual-predictor value, integrated revised architecture, cross-corpus and system benefits. No production integration is authorized by this gate alone.

## V2.4E — ARCHITECTURE SIMPLIFICATION & DRIFT-SIGNAL JUSTIFICATION

**STATUS: PASS — disposition B; review final scope before V2.5**

- **Objective:** compare RF-residual/ADWIN timing against equal-budget nonadaptive timing using identical paired observation-window content.
- **Required artifacts:** [timing investigation](adaptive_timing_investigation.md), same-content commits, shared hourly truth/age records, per-VM/tier deltas and provenance.
- **PASS criteria:** 54/54 valid evaluations, exact budgets/base schedules, causal gap/content eligibility, finite aligned snapshots, output integrity, and conservative A/B/C residual-signal disposition. Negative evidence can complete the investigation.
- **Unproven:** practical margins, independent confirmation, alternative detector benefits, cross-corpus and system effects. V2.5 remains blocked until review.

## V2.4F — PREDICTOR-FREE ADAPTIVE TRIGGER INVESTIGATION

**STATUS: PASS — adaptive maintenance not justified**

- **Objective:** determine whether either of two predefined predictor-free triggers—existing Reactive class change or direct-observation ADWIN—provides a consistent advantage over its own equal-budget nonadaptive control.
- **Required artifacts:** [predictor-free adaptive investigation](predictor_free_adaptive_investigation.md), identical 24h content and periodic bases, matched Reactive/ADWIN budgets, aligned hourly truth/age records, trigger/ineligible-trigger accounting, per-VM/tier effects, and managed provenance.
- **PASS criteria:** 90/90 valid method/VM evaluations; exact per-VM adaptive/control budgets; no prediction; finite causal snapshots; verified shared content, base schedules and evaluation truth; output/hash/cache integrity; and one predefined architecture disposition. A negative scientific result can pass investigation validity.
- **Unproven:** practical margins, independent confirmation, other triggers, cross-corpus or systems benefit. No additional trigger search follows a negative disposition.

## V2.4G — RESEARCH SCOPE REDESIGN

**STATUS: PASS — EMPIRICAL/SYSTEM STUDY VIABLE**

- **Objective:** decide whether a defensible non-adaptive research contribution remains after withdrawing forecasting and adaptive-refresh superiority.
- **Required artifacts:** [research scope redesign](research_scope_redesign.md), claim disposition table, non-adaptive Static/PW/Full-Rewrite trade-off summary from the corrected pilot, literature collision audit, A/B/C direction assessment, GO/NO-GO criteria.
- **PASS criteria:** one predefined disposition; every quantitative figure traced to valid development generations; no confirmatory outcomes; no new mechanism; literature sources identified by DOI/URL; next gate only (no method implementation).
- **Unproven:** multi-corpus external validity, system-level benefit, and any cost-aware cadence *selector* claim. Direction A is motivational only.

## V2.5 — EMPIRICAL CONTRIBUTION FREEZE

**STATUS: BLOCKED PENDING AUTHORIZATION UNDER V2.4G GO CRITERIA**

- **Objective:** freeze an evidence-limited empirical/methodological contribution and confirmatory design—not an adaptive superiority study.
- **Required artifacts:** contribution statement with C1/C2 withdrawn; claim ledger; permanent pilot exclusion; non-adaptive reporting matrix; practical margins chosen independently of pilot effects; multi-corpus plan (Google 2019 first) for benchmark external validity; explicit deferral or separate authorization for K8s/system validation.
- **PASS criteria:** source/config/cohort and analysis plan locked before confirmatory outcomes, without optimizing margins to exploratory pilot effects or resurrecting withdrawn adaptive/forecast claims.
- **Reviewer concern addressed:** contribution/venue match and fair evidence rather than post-hoc favorable comparisons.
- **Unproven:** actual multi-corpus and system effects until later gates.

## V3 — FULL MATERNA CAUSAL EVALUATION

**STATUS: BLOCKED UNTIL V2.5 PASS**

- **Objective:** fresh causal-generation evidence on the predeclared Materna eligible corpus.
- **Required artifacts:** locked configuration/source; complete run/output manifests; the complete frozen per-VM method/config matrix; exclusion/failure accounting; paired baseline analysis and uncertainty; untouched confirmatory set.
- **PASS criteria:** every included output verifies under current protocols/fingerprints; complete predeclared coverage or justified exclusions; no reuse of historical TOCS metrics; analysis can be independently reconstructed. Record C1/C2 support or failure without requiring a positive result to call execution valid.
- **Reviewer concern addressed:** credible evidence prerequisite; TOCS 10-11 applied to real traces.
- **Unproven:** multiple-interval/matched-budget conclusions until V4, external validity and operational benefit.

## V4 — REFRESH TRADE-OFF EVIDENCE

**STATUS: PLANNED — requires frozen V2.5 design and V3-quality outputs**

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

V0, V1A, V1B, V2 and the V2.4 investigation chain through V2.4G are PASS as executions. C1 and C2 are withdrawn. V2.4G disposition is **EMPIRICAL/SYSTEM STUDY VIABLE**; V2.5 is redefined as an empirical contribution freeze and remains blocked until authorized under the V2.4G GO criteria. V3 remains BLOCKED UNTIL V2.5 PASS. The earlier v2 pilot was blocked on gaps and aliasing; the corrected v3 pilot resolves those protocol defects with independently verified bounded execution. V4 requires frozen interval/budget comparisons; V6 requires dataset selection; V8 requires the V7 harness and V5 cost discipline. Every future experiment still requires explicit scope and authorization. No manuscript prose before V10 passes and V11 begins.

Primary confirmation must exclude the same 18 development-pilot VMs. Final eligibility and all exclusion rules remain for V2.5; 1,558 is the maximum retained primary cohort before any further predefined exclusions. Optional whole-corpus description is separate from independent confirmation.

Both pilot generations and the stopped diagnostic attempt are recorded in [bounded_pilot.md](bounded_pilot.md). Current lightweight validation is 312 passed, 0 failed, 0 skipped. No practical benefit/harm margins or confirmatory families were chosen from pilot effects.

## Phase 3A-R execution record

V2 PASS at source `82a79b90d70ce0405ffbf161698180bdf4f49ed7`; run `2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe`. 256 tests passed, no failures/skips. [Bounded pilot](bounded_pilot.md) records execution and exploratory diagnostics. V2.5 is blocked pending V2.4 review; V3 remains BLOCKED UNTIL V2.5. The earlier v2 pilot remains preserved as a readiness failure. No full experiment follows automatically.

## V2.4 completion record

Managed exploratory diagnosis completed on the fixed 18 development VMs, eight origins each, from source `8ad366a0a282c3981d135f26fe9cde34b1cb80ee`. 259 tests passed, zero failed/skipped. Exact run identity and lead/profile diagnostics are in [predictor diagnosis](predictor_diagnosis.md). Recursive feedback/long-horizon bias is the strongest evidenced issue; predictor redesign investigation is recommended before confirmation freeze, but no predictor change is made. [Dataset audit](dataset_suitability_audit.md) ranks Google 2019 first and Alibaba 2018 as optional third, subject to acquisition/continuity/semantics checks. **V2.5 remains BLOCKED pending V2.4 review and disposition of predictor adequacy; V3 remains BLOCKED.** No confirmatory outcomes, model tuning or candidate raw downloads were used.

Current prerequisite: V2.4B is complete and requires review. No single adequate two-resource predictor was selected; V2.5/V3 remain blocked pending explicit predictor disposition. No result authorizes automatic predictor integration.

V2.4B record: source `ff7388ab3ec122d3f528e45216adc5882cacbc13`; managed run `2026-10-22T004212.427895Z-62f5727e20e2-905e675d`; 18 development VMs, identical eight origins, four candidates, all 288 leads. 265 tests passed. Direct RF improves recursion but loses to seasonal on CPU and has large state cost; no production integration is recommended. See the design investigation for full metrics, mixed resource findings and limitations.

Current prerequisite: V2.4C is complete and requires review/disposition. Seasonal-naive is the strongest tested scalar-profile reference and equals trailing-window PW refresh content. No learned predictor integration is recommended. V2.5/V3 remain blocked.

V2.4C record: source `d579c46be0691e72db87814fbd86f636b05e7d3b`, study-v2 run `2026-10-22T071114.218486Z-807040bbf43c-322dd54d`; same 18 development VMs/eight origins, six methods, 1,728 resource/profile rows and a timestamp-only 1,576-VM availability audit. 274 tests passed. The metadata-v1 generation is superseded unchanged. See [task-aligned investigation](profile_predictor_investigation.md) for A/B/C/D disposition, seasonal/PW identity and unresolved availability/residual/claim contracts. No full run follows automatically.


V2.4D completed on the fixed 18 VMs from source `0ada9c14ead1621039830ade86963193ba8a446a`;
managed run `2026-10-22T073824.175800Z-77f3f60abcd1-ef449ae2`, 288 tests passing.
Disposition: **PREDICTOR NOT JUSTIFIED** for profile generation. Direct-profile RF
loses to seasonal/PW content at operational origins; the strict bootstrap selector
does not generalize robustly. The first, incomplete no-mature-label attempt is
preserved as FAILED. See [disposition](predictor_disposition.md) for all choices,
coverage and architecture consequences. C1 is unsupported and should be retired;
residual RF remains a separate unvalidated role. Review observation-content
architecture, its gap eligibility and same-content matched budgets, then perform
bounded revalidation before freezing confirmation. **V2.5/V3 remain BLOCKED.**
No production policy change, confirmatory inference or extra model search occurs.


V2.4E completed from clean source `11131f64b8f4ce69ebf22ba8d3fc5a8d756623f2`,
run `2026-10-22T080121.494735Z-4fd1541d4a30-1e730315`; 304 tests pass,
54/54 method/VM evaluations, 18/18 exact equal budgets and base schedules,
shared paired-window content and hourly verification. See [adaptive timing
investigation](adaptive_timing_investigation.md). Disposition: **RESIDUAL SIGNAL
NOT JUSTIFIED**. Small class averages coexist with worse CPU/memory p95 MAE
at equal budget and mixed VM/tier effects. Recommend dropping prediction entirely
from the final architecture, keeping legacy/residual controls for reproducibility.
C1 and residual-driven C2 are unsupported. V2.5 remains BLOCKED until review
accepts a defensible final architecture and research scope; V3 remains BLOCKED.
No full experiment or model search follows automatically.


The first V2.4F generation from source
`10cae8cfb77b142fcad8548235c8d21694f6345c`, run
`2026-10-22T092211.896873Z-f4f66f61eb48-deed1373`, remains **INVALID FOR
DISPOSITION** due to Reactive trigger-state reset and aggregate-counter defects.
The corrected generation completed from clean source
`d8b8421226ebd989476323c2f955eb676e2c0d7f`, run
`2026-10-22T094401.887475Z-7f855e124a48-b40753f6`; 312 tests pass,
90/90 method/VM evaluations, 18/18 exact Reactive and ADWIN matched budgets,
shared paired-window content, zero prediction calls, and independently verified
schedules/content/truth. See [predictor-free adaptive investigation](predictor_free_adaptive_investigation.md).
Disposition: **ADAPTIVE MAINTENANCE NOT JUSTIFIED**. Stop trigger search and
retire C2 as an active contribution.


V2.4G completed from existing development evidence only (corrected Phase 3A-R
pilot + predictor-free bias/age reconstruction on the same 18 VMs; no
confirmatory access; no new mechanism). See [research scope redesign](research_scope_redesign.md).
Claim table withdraws forecasting and adaptive-refresh superiority. Non-adaptive
audit: Static≪PW fidelity jump; PW 3/6/12h show small marginal gains at roughly
doubling refresh cost; Full-Rewrite is cost-dominated. Literature collision is
high for adaptive monitoring/rightsizing and moderate for a causal
benchmark-with-negatives contribution. Disposition:
**EMPIRICAL/SYSTEM STUDY VIABLE**. V2.5 is an empirical contribution freeze under
explicit GO/NO-GO criteria; V3 remains BLOCKED. No cadence selector or full run
is authorized by this gate.
