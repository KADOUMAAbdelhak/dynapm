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

**STATUS: BLOCKED — practical_effect_margins_unassigned**

- **Objective:** freeze the non-adaptive empirical study (RQ1–RQ4) before accessing 1,558 confirmatory Materna VM outcomes—not an adaptive/forecasting superiority study.
- **Required artifacts:** [confirmatory design freeze](confirmatory_design_freeze.md); `configs/materna_confirmatory_v1.{json,yaml}`; `configs/materna_confirmatory_cohort_v1.json`; C1/C2 withdrawn; permanent 18-VM pilot exclusion; non-adaptive Static/PW/Full-Rewrite matrix; F1–F3 comparisons; statistics/decision templates; future V3–V9 roadmap; design/config/cohort hashes.
- **PASS criteria:** source/config/cohort/endpoints/comparisons/statistics locked before confirmatory outcomes; practical-benefit and acceptable-harm margins assigned from metric/operational/domain rationale **without** pilot-effect calibration or confirmatory peeking; no resurrection of withdrawn adaptive/forecast claims.
- **Current disposition:** RQs, cohort (1,576−18=1,558 candidates), methods, endpoints, F1–F3, bootstrap (B=10000, seed=20251022), and decision templates are frozen. Numeric practical margins remain **null** because no defensible non-arbitrary values exist without inventing round numbers or using pilot effects. Therefore V2.5 is **BLOCKED** and V3 must not execute.
- **Reviewer concern addressed:** contribution/venue match and fair evidence rather than post-hoc favorable comparisons.
- **Unproven:** actual Materna confirmatory effects (V3), multi-corpus and system effects (V4–V8), claim/venue audit (V9).

## V3 — MATERNA CONFIRMATORY NON-ADAPTIVE STUDY

**STATUS: BLOCKED UNTIL V2.5 PASS**

- **Objective:** execute the frozen non-adaptive confirmatory study on the 1,558-candidate Materna cohort (minus protocol-validity exclusions only).
- **Required artifacts:** locked V2.5 config/hashes; complete run/output manifests; Static/PW-12h/PW-6h/PW-3h/Full-Rewrite matrix; exclusion accounting under predefined protocol codes; paired F1–F3 analysis with frozen statistics; no adaptive/forecasting primary methods.
- **PASS criteria:** every included output verifies under current protocols/fingerprints; complete predeclared coverage or justified protocol exclusions; analysis reconstructible from the frozen design hashes; negative/null findings remain valid.
- **Reviewer concern addressed:** credible Materna confirmation; TOCS 10–11 applied to real traces under the non-adaptive scope.
- **Unproven:** external validity (V4–V5), maintenance-cost budgets (V6), operational benefit (V7–V8).

## V4 — INDEPENDENT PRODUCTION-CORPUS SUITABILITY / ACQUISITION

**STATUS: PLANNED — requires V2.5 PASS; Materna confirmation remains separate**

- **Objective:** select and acquire (or refuse) an independent production corpus for generalization; prefer continuing the Google ClusterData 2019 suitability track when still valid.
- **Required artifacts:** formal suitability/licensing/acquisition report; reproducible adapters and hashes; eligibility audit; no confirmatory Materna outcome use in corpus choice.
- **PASS criteria:** meaningful domain diversity and CPU/memory/time/horizon suitability decided before second-corpus benefit evaluation; acquisition reproducible without secrets in Git.
- **Unproven:** actual second-corpus effects until V5.

## V5 — SECOND-CORPUS REPLICATION

**STATUS: PLANNED — requires V4 PASS**

- **Objective:** replicate the frozen non-adaptive maintenance/cadence study on the acquired corpus (preferably Google ClusterData 2019 if V4 affirms suitability).
- **Required artifacts:** locked replication protocol; paired per-corpus effects; heterogeneity/negative-transfer report.
- **PASS criteria:** no post-outcome eligibility tuning; uncertainty and limitations transparent; C3 only if practical-benefit criteria hold or the claim is narrowed.
- **Unproven:** domains outside tested corpora; operational effects.

## V6 — MAINTENANCE-COST / SERVICE BENCHMARK

**STATUS: PLANNED — instrumentation needs separate implementation task**

- **Objective:** attribute refresh/commit/state and service-scale maintenance cost under declared budgets (C5 track).
- **Required artifacts:** instrumented boundaries; dedicated hardware/environment record; warm-up/repeated-run protocol; latency/CPU/memory/throughput distributions; declared overhead budgets.
- **PASS criteria:** repeatable same-environment measurements; no double counting or cross-machine timing comparison; C5 budget explicitly passed or failed at a stated scale.
- **Unproven:** cost-benefit acceptability in a real consumer until V8.

## V7 — KUBERNETES PROFILE→RESOURCE-MANAGEMENT HARNESS

**STATUS: PLANNED — design/authorization separate**

- **Objective:** working Kubernetes telemetry → profile service → fixed provisioning consumer → resource decision loop.
- **Required artifacts:** environment/deployment configs; observed decision/actuation traces; workload scenarios; policy isolation; trial plan frozen.
- **PASS criteria:** real application and real consumed profile/resource actions; no future data; operational metrics captured. A deployment screenshot is insufficient.
- **Unproven:** operational advantage until V8.

## V8 — REPEATED OPERATIONAL / SYSTEM VALIDATION

**STATUS: PLANNED — requires V6 and V7**

- **Objective:** operational benefit and harm estimates under controlled repeated trials (C4/C5 evidence).
- **Required artifacts:** independent run/scenario replicates; predefined operational magnitude/harm criteria; run-level paired inference.
- **PASS criteria:** preplanned replication; all failed trials reported; C4/C5 support is a separate evidence decision.
- **Unproven:** heterogeneous edge generalization without a dedicated C6 experiment.

## V9 — FINAL CLAIM AUDIT / VENUE DECISION

**STATUS: PLANNED — after relevant evidence gates**

- **Objective:** map every intended manuscript claim to evidence, remove unsupported scope, and only then select a venue / begin drafting.
- **Required artifacts:** C1–C6 claim ledger (C1/C2 remain withdrawn unless separately revived with new evidence); source/config/input/output fingerprints including V2.5 freeze hashes; effect/CI/margin decisions; negative outcomes; venue-scope audit.
- **PASS criteria:** every retained claim meets its predefined evidence requirement; no significance-only or offline-to-system leap; manuscript drafting begins only after this gate.
- **Unproven:** peer-review outcome or journal acceptance.

### Historical gate aliases (superseded numbering)

Earlier documents used a denser V3–V11 numbering (full Materna + refresh trade-off + overhead + second corpus + harness + system + ablations + claim audit + writing). That numbering is **superseded** by the V3–V9 empirical/system path above. Ablations remain allowed as nested protocol/mechanistic checks inside later gates when pre-registered; they are not a separate publication claim gate.

## Dependency and execution rule

V0, V1A, V1B, V2 and the V2.4 investigation chain through V2.4G are PASS as executions. C1 and C2 are withdrawn. V2.4G disposition is **EMPIRICAL/SYSTEM STUDY VIABLE**. V2.5 froze the non-adaptive design but is **BLOCKED** on unassigned practical-effect margins. V3 remains **BLOCKED UNTIL V2.5 PASS**. Materna confirmation (V3) stays separate from generalization (V4–V5). V6 cost, V7–V8 system, and V9 claim/venue gates follow. Every future experiment still requires explicit scope and authorization. No manuscript prose before V9.

Primary confirmation must exclude the same 18 development-pilot VMs. Candidate confirmatory set is exactly **1,558** IDs before protocol-validity exclusions ([cohort manifest](../configs/materna_confirmatory_cohort_v1.json)). The 199 gap-audit review flags remain diagnostics, not automatic exclusions. Optional whole-corpus description is separate from independent confirmation.

Both pilot generations and the stopped diagnostic attempt are recorded in [bounded_pilot.md](bounded_pilot.md). See [confirmatory design freeze](confirmatory_design_freeze.md) for hashes and the margin blocker.

## Phase 3A-R execution record

V2 PASS at source `82a79b90d70ce0405ffbf161698180bdf4f49ed7`; run `2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe`. 256 tests passed, no failures/skips. [Bounded pilot](bounded_pilot.md) records execution and exploratory diagnostics. V2.5 design freeze exists but is BLOCKED on unassigned practical margins; V3 remains BLOCKED UNTIL V2.5 PASS. The earlier v2 pilot remains preserved as a readiness failure. No full experiment follows automatically.

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
**EMPIRICAL/SYSTEM STUDY VIABLE**. V2.5 froze the non-adaptive design under
explicit GO/NO-GO templates but remains **BLOCKED** on unassigned practical
margins ([freeze record](confirmatory_design_freeze.md)); V3 remains BLOCKED.
No cadence selector or full run is authorized until V2.5 PASS.

## V2.5 execution record

Design freeze committed with configs/cohort manifests and validators. Design
fingerprint `d3c94bcdcf9cb626d915187ca8d5071c26197464ad6154e3f527f1f4d79bac26`.
Candidate confirmatory cohort: 1,558 IDs (entities fingerprint
`3a590437f108493b085f1cb34765e76bd5f10fa233a48c2e96f6bf3bd54b7939`). Practical
margins unassigned → **V2.5 = BLOCKED**; **V3 = BLOCKED**. No confirmatory
outcomes accessed; no scientific run.
