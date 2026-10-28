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

**STATUS: PASS — V2.5A estimation-first amendment**

- **Objective:** freeze the non-adaptive empirical study (RQ1–RQ4) before accessing 1,558 confirmatory Materna VM outcomes—not an adaptive/forecasting superiority study.
- **Required artifacts:** [confirmatory design freeze](confirmatory_design_freeze.md); current `configs/materna_confirmatory_v1_1.{json,yaml}`; preserved provenance `configs/materna_confirmatory_v1.{json,yaml}`; `configs/materna_confirmatory_cohort_v1.json`; C1/C2 withdrawn; permanent 18-VM pilot exclusion; non-adaptive Static/PW/Full-Rewrite matrix; F1–F3 comparisons; estimation statistics/decision rules; future V3–V9 roadmap; design/config/cohort hashes.
- **PASS criteria (met via V2.5A):** source/config/cohort/endpoints/comparisons/statistics locked before confirmatory outcomes; study framed as pre-specified **estimation** with profile-level practical significance `NOT_DEFINED_AT_PROFILE_LEVEL` (no invented numeric margins; no pilot-effect calibration); no resurrection of withdrawn adaptive/forecast claims.
- **V2.5A disposition:** Original V2.5 superiority-margin freeze remains on disk as BLOCKED provenance. Amendment converts V3 into an estimation study (effects, CIs, tests, costs, Pareto/trade-offs) without inventing practical margins. **V2.5 = PASS.** **V3 = NEXT.**
- **Reviewer concern addressed:** contribution/venue match and fair evidence rather than post-hoc favorable comparisons or invented practical thresholds.
- **Unproven:** actual Materna confirmatory estimates (V3), multi-corpus and system effects (V4–V8), claim/venue audit (V9). C4 remains UNPROVEN.

## V3 — MATERNA CONFIRMATORY ESTIMATION STUDY

**STATUS: PASS — estimation execution complete**

- **Objective:** execute the frozen non-adaptive **estimation** study on the 1,558-candidate Materna cohort (minus protocol-validity exclusions only): report paired mean/median effects, bootstrap 95% CIs, Wilcoxon/Holm, effect sizes, costs, and fidelity–cost relationships — not profile-level practical superiority.
- **Required artifacts:** locked V2.5A config/hashes (`materna_confirmatory_v1_1`); complete run/output manifests; Static/PW-12h/PW-6h/PW-3h/Full-Rewrite matrix; exclusion accounting under predefined protocol codes; paired F1–F3 estimation analysis; [results record](materna_confirmatory_results.md); no adaptive/forecasting primary methods.
- **PASS criteria (met):** 7,790/7,790 method×VM evaluations; 0 protocol exclusions; shared evaluation stamps; output/hash/cache validation; F1–F3 estimation complete; no operational-superiority claims from p-values alone.
- **Execution:** source `5119957`; fingerprint `9be95e6c…`; run `2026-10-22T150748.006454Z-9be95e6c23a5-87fdc2de`; output manifest `f1da7159…`.
- **Reviewer concern addressed:** credible Materna confirmation under estimation framing; TOCS 10–11 applied to real traces under the non-adaptive scope.
- **Unproven:** external validity (V4–V5), maintenance-cost budgets (V6), operational benefit C4 (V7–V8).

## V4A — INDEPENDENT CORPUS SELECTION / PROTOCOL-FIT FREEZE

**STATUS: PASS — CORPUS READY FOR ACQUISITION (Google ClusterData 2019)**

- **Objective:** select the strongest second production corpus for independent replication of the frozen V3 estimation study; freeze protocol-fit adaptation without running DynAPM/PW outcomes.
- **Required artifacts:** [independent corpus selection](independent_corpus_selection.md); `configs/google_clusterdata_2019_replication_protocol_v1.{json,yaml}`; official-source audit of Google 2019, Alibaba 2018, Alibaba 2026 MaaS `instance_week_5min`, and checked alternatives.
- **PASS criteria (met):** disposition frozen; preferred corpus justified by protocol fit (not expected effects); adaptation specifies entity/units/cadence/eligibility; V3 methods/RQs/statistics inherited unchanged; no Materna redesign; no second-corpus outcomes.
- **Disposition:** Google ClusterData 2019 preferred; Alibaba 2018 optional backup; MaaS week-5min not preferred for 24h+24h five-minute replication.
- **Unproven:** eligible continuous-entity count, BigQuery export cost, and any second-corpus effects (V4B/V5).

## V4B — CORPUS ACQUISITION / CONTINUITY EXPORT

**STATUS: RAW CELL E VERIFIED; OLD CANONICAL SUPERSEDED; V4B.8 CORRECTION VERIFIED**

- **Objective:** acquire a reproducible, outcome-blind Google 2019 export under the frozen adaptation (budgeted BigQuery; pin snapshot/hashes; continuity + request-coverage filters only).
- **Required artifacts:** [acquisition record](google2019_acquisition.md); `configs/google2019_streaming_plan_v1.{json,yaml}`; storage estimate; chunked writer/disk guards; canonical manifests after extract.
- **Current result (V4B.5):** corrected local-size model (not bytes-processed); streaming per-cell events→usage→canonical; peak point ~40.6 GiB for e+g staging vs ~85 GiB usable (20 GiB reserve). Conservative g band ~96 GiB → runtime disk guard. Cells/SQL unchanged. Executed bytes **0**.
- **PASS criteria for acquisition execution:** streaming preflight; billing disabled; cumulative scan ≤900 GiB; disk guards; canonical manifests; V4A mapping unchanged.
- **Next after successful acquisition:** **V4C — Google protocol/cohort validation** (not PW/Static outcomes).
- **Unproven:** second-corpus estimation effects until V5.

## V4B.8 — LOCAL CANONICAL CORRECTION

**STATUS: PASS — corrected generation independently verified; old canonical superseded**

- **Objective:** apply frozen unambiguous positive-request history locally without rescanning raw data in BigQuery.
- **Evidence:** raw/old preservation hashes, new generation identity/lineage, full-row independent normalization/ASOF/eligibility checks, regression/full tests.
- **PASS:** corrected generation VERIFIED, old generation rejected for replication, zero query bytes, raw and legacy bytes unchanged.

## V4C — GOOGLE CORPUS/COHORT PROTOCOL VALIDATION

**STATUS: INCOMPLETE — cell e validated under V4C.1; g missing and final two-cell cohort unfrozen**

- **Objective:** validate corpus adapter, timeline/bootstrap/window rules, eligibility and cell scope without method outcomes.
- **Required:** corrected generation manifest/hashes; outcome-blind cohort/protocol freeze; explicit treatment of deferred cell g.
- **Current evidence:** [V4C.1 clock audit](google2019_clock_contract.md), `configs/google2019_v4c1_validation_record.json`, `configs/google2019_replication_cohort_v2.json`, and `configs/google2019_current_protocol.json`: 62,444/62,451 availability-aware eligible e candidates; the same 1,000 identity-hash provisional selections. Earlier v1 records remain historical.
- **Resolved e blocker:** [V4C.1 completed-slot contract](google2019_clock_contract.md) explicitly separates measurement, availability and read clocks; containment/visibility/maturity checks pass. V2 canonical normalization stays verified.
- **Current staged amendment:** V4D freezes e-first execution readiness without completing two-cell V4C. g still requires independent acquisition/validation and cohort binding; see V4D/V5A/V5B below.
- **Boundary:** this metadata audit does not authorize V5 replication outcomes or further cloud scans.

## V4C.1 — GOOGLE MEASUREMENT / AVAILABILITY / READ CLOCKS

**STATUS: PASS — AVAILABILITY_CONTRACT_READY for cell e**

- **Objective:** preserve 288-slot windows while preventing unfinished interval averages from entering any state/read.
- **Evidence:** [clock contract](google2019_clock_contract.md), v2 protocol/cohort configs, `configs/google2019_v4c1_validation_record.json`, and independent verification.
- **PASS:** all 462,821,691 rows fit their bins; zero retained overlaps/crossings/duplicate slots; 62,444 eligible entities and 1,000 cohort members unchanged; leakage/integrity tests pass.
- **Boundary:** no queries, g acquisition, policy outcomes, or V3 changes. Per-cell readiness is not final V4C completion or V5 authorization.

## V4D — SEQUENTIAL GOOGLE REPLICATION FREEZE + SHARED EVALUATOR

**STATUS: PASS — synthetic/integrity validation; zero real Google outcomes**

- **Objective:** preregister e then mandatory held-out g before seeing e; make one managed availability-aware evaluator executable.
- **Artifacts:** [staged contract](google2019_staged_replication.md); `configs/google2019_staged_replication_v1.{json,yaml}`; exact e input binding; `task30_google_replication`; synthetic managed/cache regression tests.
- **PASS criteria:** five unchanged methods, protocol v2, independent hash cohorts/no backfill, frozen F1–F3 inference/synthesis, no outcome-driven changes, corrected-generation/clock/cohort enforcement, full lightweight suite and input integrity pass.
- **Amendment:** prospectively replaces the earlier simultaneous two-cell prerequisite for Stage A only. Original protocol/cohort/validation records stay unchanged. Overall V4C remains incomplete.
- **Unproven at V4D completion:** Google policy effects. V4E below now records Stage A; cross-cell consistency and practical/operational benefit remain unproven. g is within-corpus replication, not another independent corpus.

## V4E — GOOGLE STAGE-A CELL-E REPLICATION

**STATUS: PASS — 1,000 entities; 5,000/5,000 evaluations; independent integrity/statistics reconciliation PASS**

- **Objective:** execute Stage A exactly as frozen, retaining all selected entities and every prespecified comparison.
- **Artifacts:** [factual findings](google2019_stage_a_results.md); `configs/google2019_v4e_validation_record.json`; sealed managed scientific run and separate read-only verification generation.
- **PASS criteria met:** clean source `ab2434f`; frozen design/protocol/cohort; 396,569 common verified reads and 1,982,845 records; exact schedules/counters/content/truth; 30 comparisons with 1,000 paired entities; all hashes/cache/CI/Wilcoxon/Holm checks; no invalidated attempts or outcome-based exclusions.
- **Boundary:** all effects are estimates without practical margins. No operational superiority or Google/Materna absolute-error equivalence. No g access or design changes.
- **Next:** mandatory held-out g acquisition/validation and unchanged Stage-B replication under separate authorization. V4C stays incomplete and full V5 stays blocked until g replication.

## V4F — COLLECTION-AWARE GOOGLE SECONDARY ROBUSTNESS FREEZE

**STATUS: PASS — metadata audit and secondary procedure frozen before g outcomes**

- **Objective:** quantify Stage-A collection concentration and prospectively fix g sensitivity to within-collection dependence, without replacing primary entity inference.
- **Artifacts:** [secondary contract](google2019_collection_robustness.md); `configs/google2019_collection_robustness_v1.{json,yaml}`; `configs/google2019_v4f_structure_audit.json`; separate managed postprocessor and synthetic tests.
- **Structure:** 1,000 entities / 130 collections; 56 singletons; median size 2, max 158; top five 44.7%; inverse HHI 18.90 is concentration, not inferential sample size.
- **PASS criteria:** whole-cluster bootstrap and deterministic paired aggregation; unmodified primary F1–F3/Holm; separate equal-collection estimand; no size/outcome exclusions, new p-values, practical margins, pooling or favorable-cell selection; e post-hoc/g prospective labels enforced; primary Stage-B hashes unchanged.
- **Boundary:** no real collection-aware e/g outcome analysis in V4F. A future e analysis is post-hoc sensitivity; g secondary is prospectively frozen and must accompany g reporting. Primary Stage A remains intact.
- **Unproven:** independence across collections/cells, nominal CI coverage under remaining dependence, operational/practical benefit. V4C remains incomplete and V5 blocked until mandatory g replication.

## V5 — STAGED SECOND-CORPUS REPLICATION

**STATUS: BLOCKED UNTIL G REPLICATION — V5A / V4E PASS; V5B REQUIRED**

### V5A — CELL E FIRST REPLICATION

**STATUS: PASS — completed as V4E; see factual findings**

- **Objective:** execute the frozen five-method study on exactly the existing 1,000 e entities under Google protocol v2 and the V4D design.
- **Artifacts:** managed clean-source run, common verified reads/truth, complete method/entity matrix, output manifests/hashes, paired F1–F3 estimates/uncertainty and secondary diagnostics.
- **PASS criteria:** all frozen outputs/invariants/integrity checks complete; no selective exclusions or tuning; no practical-benefit claim from significance alone.
- **Evidence:** all 5,000/5,000 evaluations and independent checks pass; no execution fixes, exclusions or invalidated attempts.
- **Unproven:** g replication and other domains; practical/operational benefit. V4D was preparation only; actual e outcomes belong to V4E.

### V5B — CELL G HELD-OUT WITHIN-CORPUS REPLICATION

**STATUS: BLOCKED — g not acquired/validated/bound**

- **Objective:** acquire and independently validate g, apply identical max-1,000 hash rule/no backfill, execute/report regardless of e direction.
- **Artifacts:** validated corrected canonical/clock/cohort binding, separate managed primary outcomes, identical per-cell primary analysis and V4F secondary collection sensitivity, predefined all-contrast direction/heterogeneity synthesis.
- **PASS criteria:** zero-spend/monthly/disk acquisition safeguards; valid g input binding; unchanged methods/config/statistics; comparable complete analysis and reporting of both cells. Correctness fixes require versioned amendment and comparable reruns.
- **Unproven:** independent third corpus, operational effects or edge generalization. No opportunistic pooling or favorable-cell choice.

## V6 — MAINTENANCE-COST / SERVICE BENCHMARK

**STATUS: PLANNED — instrumentation needs separate implementation task**

- **Objective:** attribute refresh/commit/state and service-scale maintenance cost under declared budgets (C5 track).
- **Required artifacts:** instrumented boundaries; dedicated hardware/environment record; warm-up/repeated-run protocol; latency/CPU/memory/throughput distributions; declared overhead budgets.
- **PASS criteria:** repeatable same-environment measurements; no double counting or cross-machine timing comparison; C5 budget explicitly passed or failed at a stated scale.
- **Unproven:** cost-benefit acceptability in a real consumer until V8.

## V7 — KUBERNETES PROFILE→RESOURCE-MANAGEMENT HARNESS

**STATUS: PARTIAL — V7A plumbing PASS; comparative trial harness/design not validated**

- **Objective:** working Kubernetes telemetry → profile service → fixed provisioning consumer → resource decision loop.
- **Required artifacts:** environment/deployment configs; observed decision/actuation traces; workload scenarios; policy isolation; trial plan frozen.
- **PASS criteria:** real application and real consumed profile/resource actions; no future data; operational metrics captured. A deployment screenshot is insufficient.
- **Unproven:** operational advantage until V8.

## V7A — FROZEN SYSTEM QUESTION + LOCAL HARNESS SCAFFOLD

**STATUS: PASS — isolated real Kubernetes smoke, not comparative evidence**

- **Objective:** real telemetry → existing observation-policy profile service → identical fixed p95 consumer → enforced Pod resource change.
- **Required artifacts:** [system design](system_validation_design.md), `configs/system_validation_v1.*`, `harness/system/`, managed single-method non-claim smoke with actual cgroup/status proof.
- **PASS criteria:** all unit checks and one local plumbing smoke pass, no comparative trials or corpus-driven tuning; source/config/input/output manifests validate. Established from clean source `35bdb5d`, 542 passed/0 failed/1 skipped; [factual verification record](../configs/system_v7a_smoke_validation_record.json). Synthetic bootstrap is expressly limited to smoke.
- **Unproven:** C4/C5, multi-method trials, power/precision/trial-count plan, overhead budgets, dedicated platform and operational margins. V8 remains blocked pending those prerequisites and authorization.

## V7B — MEASURED BOOTSTRAP, CALIBRATION AND SYSTEM FREEZE

**STATUS: BLOCKED — preparation implemented; no real bootstrap/calibration or justified numeric operational criteria**

- **Objective:** real fixed bootstrap, single-method calibration, component cost attribution and prospective operational precision/decision contract.
- **Artifacts:** [blocked freeze record](system_trial_freeze.md), `configs/system_trials_v8_draft_v1.json`, measured-bootstrap validator, production initialization adapter and deterministic identity-only plans.
- **Current evidence:** unit fixtures only. Real 24h bootstrap not demonstrated; zero calibration/comparative runs; variance/N unavailable. Continuous repeated Kubernetes executor is not implemented.
- **Blockers:** owner operational error/resource/control budgets; dedicated host feasibility; continuous collection/isolated process attribution; real calibration and output manifests; justified precision targets and practical run cap.
- **PASS criteria:** all above evidenced before freezing N and numeric harm/benefit criteria. Never substitute V7A synthetic smoke or treat requests as replicates.
- **Unproven:** C4/C5. V8 cannot start.

## V8 — REPEATED OPERATIONAL / SYSTEM VALIDATION

**STATUS: BLOCKED — requires V6 and completed V7B calibration/design freeze**

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

V0, V1A, V1B, V2 and the V2.4 investigation chain through V2.4G are PASS as executions. C1 and C2 are withdrawn. V2.4G disposition is **EMPIRICAL/SYSTEM STUDY VIABLE**. V2.5 / V2.5A is **PASS**. V3 is **PASS** (Materna confirmatory estimation; [results](materna_confirmatory_results.md)). V4A is **PASS** ([corpus selection](independent_corpus_selection.md); Google 2019 ready for acquisition). **Raw cell e is VERIFIED; the old canonical generation is SUPERSEDED/invalid; V4B.8 local correction is VERIFIED; V4C.1 is PASS for cell e; V4C is INCOMPLETE pending g validation and final cohort freeze** ([correction](google2019_local_correction.md)). Existing scans consumed 745.088415 GiB; this correction executes zero query bytes. The v2 availability contract is validated for e. V4D prospectively freezes sequential execution: V4E / V5A e is PASS ([findings](google2019_stage_a_results.md)); V5B g remains mandatory and blocked until its acquisition/validation, independent cohort binding and replication. Full V5 remains blocked until g replication. V4F freezes secondary collection robustness only: future e post-hoc, g prospective; primary inference remains unchanged. Overall V4C remains incomplete. C3 and C4 remain UNPROVEN. V5–V9 follow. Every future experiment still requires explicit scope and authorization. No manuscript prose before V9.

Primary confirmation must exclude the same 18 development-pilot VMs. Candidate confirmatory set is exactly **1,558** IDs before protocol-validity exclusions ([cohort manifest](../configs/materna_confirmatory_cohort_v1.json)). The 199 gap-audit review flags remain diagnostics, not automatic exclusions. Optional whole-corpus description is separate from independent confirmation.

Both pilot generations and the stopped diagnostic attempt are recorded in [bounded_pilot.md](bounded_pilot.md). See [confirmatory design freeze](confirmatory_design_freeze.md) for V2.5A hashes and estimation rules.

## Phase 3A-R execution record

V2 PASS at source `82a79b90d70ce0405ffbf161698180bdf4f49ed7`; run `2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe`. 256 tests passed, no failures/skips. [Bounded pilot](bounded_pilot.md) records execution and exploratory diagnostics. V2.5A estimation amendment PASS; V3 is NEXT. The earlier v2 pilot remains preserved as a readiness failure. No full experiment follows automatically from this record alone.

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
**EMPIRICAL/SYSTEM STUDY VIABLE**. V2.5 initially froze the non-adaptive design
and blocked on unassigned practical margins; V2.5A amends to estimation-first
([freeze record](confirmatory_design_freeze.md)). No cadence selector is
authorized by these gates alone.

## V2.5 execution record

Initial freeze (v1, BLOCKED provenance): design fingerprint
`d3c94bcdcf9cb626d915187ca8d5071c26197464ad6154e3f527f1f4d79bac26`; preserved at
`configs/materna_confirmatory_v1.{json,yaml}`. Candidate confirmatory cohort:
1,558 IDs (entities fingerprint
`3a590437f108493b085f1cb34765e76bd5f10fa233a48c2e96f6bf3bd54b7939`).

## V2.5A execution record

Estimation-first amendment (v1.1, PASS): design fingerprint
`62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296`;
`configs/materna_confirmatory_v1_1.{json,yaml}`. Profile-level practical
significance `NOT_DEFINED_AT_PROFILE_LEVEL`. Cohort/methods/F1–F3/bootstrap
unchanged. **V2.5 = PASS**. C4 remains UNPROVEN.

## V3 execution record

Confirmatory estimation completed from source `5119957` (clean). Experiment
fingerprint `9be95e6c23a5b58688b74f57a4a91b0e8003109d3075c5351581f5bbb4163f11`;
run `2026-10-22T150748.006454Z-9be95e6c23a5-87fdc2de`; output manifest
`f1da7159691467338d8d759a1830a4118c52713ab8eefa49c3770e6a1a0064be`. Eligible
1,558 / excluded 0; 7,790/7,790 method×VM complete; F1–F3 estimation reported.
See [materna_confirmatory_results.md](materna_confirmatory_results.md).
**V3 = PASS**.

## V4A execution record

Independent corpus selection/protocol-fit freeze: disposition **CORPUS READY FOR
ACQUISITION**; preferred **Google ClusterData 2019**; protocol fingerprint
`4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226`. See
[independent_corpus_selection.md](independent_corpus_selection.md). No full
dataset download; no second-corpus outcomes. **V4A = PASS**. C3/C4 UNPROVEN.

## V4B execution record

Google 2019 acquisition/preprocessing freeze: disposition **`ACQUISITION_BLOCKED`**.
Population, normalization, SQL, and canonical pipeline frozen and tested on
synthetic fixtures. No authenticated dry-run, no Google rows, no method
outcomes. See [google2019_acquisition.md](google2019_acquisition.md).
**V4B = BLOCKED**.

## V4B.1 execution record

BigQuery access bootstrap: `google-cloud-bigquery` installed; guarded
`--dry-run-all` / `--execute-bounded` runner with `maximum_bytes_billed` and
immutable provenance under gitignored `data/google2019/`.
**V4B.1 = BLOCKED** (ADC/project later supplied in V4B.2).

## V4B.2 execution record

Zero-cost dry-run gate: `billingEnabled=false` verified; queries 01–05 dry-run;
all **REFUSE** under 10 GiB guard / 900 GiB headroom; executed ledger = 0;
no bounded extract; no method outcomes. Disposition
`ZERO_COST_BOUNDED_SUBSET_REQUIRED`. **V4B.2 = BLOCKED**.

## V4B.3 execution record

Zero-cost query redesign (dry-runs + free metadata only): unpartitioned tables
confirmed; projection matrix for cells a–h; separate minimal-column strategy
selected; cells **`e`,`g`** frozen at 825.67 GiB cumulative; plan
`configs/google2019_zero_cost_plan_v1.*`; disposition
`READY_FOR_ZERO_COST_ACQUISITION`; executed bytes still 0. **V4B.3 = PASS**
(plan freeze).

## V4B.4 execution record

Execute frozen zero-cost acquisition: preflight PASS on billing/SQL/dry-runs;
**STOP** on invalid local-size proxy (`bytes processed` ≠ disk). Ledger 0;
disposition `ACQUISITION_BLOCKED`. **V4B.4 = BLOCKED**.

## V4B.5 execution record

Disk-efficient redesign: Parquet/zstd calibrated storage model; streaming
events→index→usage→canonical per cell; 20 GiB free reserve; chunk
flush/atomic finalize/checkpoints. Disposition
`READY_FOR_STREAMING_ACQUISITION` (conservative g uncertainty → runtime guard).
Configs: `google2019_streaming_plan_v1.*`, `google2019_v4b5_storage_estimate.json`.
Executed bytes still 0. See [google2019_acquisition.md](google2019_acquisition.md).
**V4B.5 = PASS**. Extraction remains the next authorized step before V4C.
