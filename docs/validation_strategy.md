# DynAPM Validation Strategy

This is an engineering and research-governance contract, not evidence of scientific benefit. It authorizes no experiments. Phase 2C implementation, corpus runs, system deployment, and manuscript drafting require their own tasks. The [roadmap](validation_roadmap.md) defines the gates.

## 1. Validation Principle

No feature or method becomes a manuscript contribution until a predefined experiment can falsify its claimed benefit. Implementation completion is not validation. Statistical significance alone is not sufficient validation. Offline accuracy alone is not sufficient system validation.

Before observing confirmatory outcomes, freeze the claim, eligibility rules, controls, endpoints, minimum practically important effects, uncertainty procedure, failure conditions, and analysis code. Publish negative and mixed outcomes in the evidence record. A failed gate narrows or rejects a claim; it does not justify changing the endpoint afterward.

## 2. Intended Claims

These are candidate claims, not conclusions:

- **C1 (WITHDRAWN after V2.4D/G):** Predictor-grounded profile maintenance improves future-profile fidelity relative to observation-window maintenance. Forecasting-superiority is retired.
- **C2 (WITHDRAWN after V2.4E–F/G):** Adaptive refresh provides benefit beyond periodic refresh when content and update opportunity/cost are controlled. Adaptive-refresh-superiority is retired for residual-RF, Reactive, and direct-observation ADWIN.
- **C3 (UNPROVEN):** Benefits or benchmark findings generalize beyond one workload corpus.
- **C4 (UNPROVEN):** Improvements in maintained profile state produce measurable downstream operational benefit.
- **C5 (UNPROVEN):** DynAPM maintenance overhead is acceptable relative to its benefit.
- **C6 (UNPROVEN):** Any empirical Cloud-Edge/continuum claim requires actual heterogeneous/edge evidence. Without that experiment, CECC remains motivation/context, not an empirical contribution.

See the [V2.4G claim disposition table](research_scope_redesign.md) for the full
SUPPORTED / WITHDRAWN / UNPROVEN ledger used for scope redesign.

A claim decision must address direction, effect magnitude, consistency, uncertainty, and operational relevance where applicable. The [V2.5 / V2.5A confirmatory design freeze](confirmatory_design_freeze.md) locks RQs, cohort, methods, endpoints, F1–F3 comparisons, and statistics as a **pre-specified estimation study**. Profile-level numeric practical-benefit / acceptable-harm margins are explicitly **`NOT_DEFINED_AT_PROFILE_LEVEL`** (not invented; not pilot-calibrated). V3 may establish direction, magnitude, uncertainty, and statistical distinguishability; statistical significance alone must never imply operational superiority (C4 remains for system gates). Separate system/operational margins before V8. Report estimates and intervals even when effects are null or small.

## 3. Claim-to-Evidence Matrix

| Claim | Experiment required | Datasets / environment | Controls / baselines | Primary metrics | Secondary metrics | Statistical analysis | Sensitivity / ablation | Minimum evidence required | Current status |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Same-origin causal profile evaluation, paired by entity, at matched intervals | Fresh Materna plus independently selected production corpus | PW vs PP at 3h/6h/12h; identical bootstrap, models, eligibility and observation timelines | CPU/memory future-profile class accuracy and p95 profile MAE; co-primary family frozen prospectively | Provisioning under/well/over rates, volatility strata, refresh counters | Paired entity bootstrap CIs, paired effects and inference; multiplicity control | Interval, missingness, predictor quality; forecast-origin vs stale-profile scoring | Desired accuracy increase/error decrease exceeds frozen practical margin with uncertainty bounded; no unacceptable resource-specific harm; consistent direction across entities/corpora or explicitly narrowed claim | V2.4D: unsupported on development VMs; retire as current contribution; see disposition |
| C2 | V3 vs ordinary PP and exact paired analysis-only matched-budget PP | Same fresh held-out traces; shared replay/protocol | PP 6h, PP interval grid, matched-budget PP; same fitted predictors and drift inputs | Fidelity/provisioning benefit at comparable committed refresh opportunity and measured cost | Drift vs periodic event decomposition, field writes/changes, drift timing | Paired effects/CIs and planned paired tests; budget discrepancy reported | Drift disabled, degraded/late/false detections, cost-matched sensitivity | Improvement exceeds frozen benefit margin and budget/cost tolerance; direction consistent; no claim that more refreshes alone prove drift benefit | Unvalidated |
| C3 | Locked-protocol external replication | At least one substantially different real production corpus; prefer two | Same controls; common protocol with documented domain adapters | C1/C2 endpoint replication per corpus | Coverage, exclusions, workload/cadence strata, negative transfer | Per-corpus paired inference; explicit heterogeneity; any pooled estimate secondary | Dataset, entity type, telemetry quality, forecast horizon | Practical benefit with bounded uncertainty across distinct corpora, or clear limits; not a pooled average masking failure | No dataset selected |
| C4 | Repeated controlled downstream resource decisions | Real Kubernetes application(s), telemetry and resource controller | PW, PP, V3, matched-budget PP; fair native mechanism only if semantics match | Preselected application/SLO endpoint and resource-efficiency endpoint | Latency quantiles, throughput, changes/churn, decision delay | Independent-run/scenario paired contrasts, CIs and planned tests | Workload scenarios, load transitions, actuation delay, controller guardrails | Operational effect exceeds frozen SLO/resource margin with uncertainty; no unacceptable safety/churn regression; repeated across scenarios | No systems evidence |
| C5 | Component microbenchmarks and service scale study | Dedicated recorded hardware/software; then system harness | Same workload/model/config across policies; separate component attribution | Maintenance CPU/time/memory relative to frozen service budgets and benefit | Training, one-step/horizon/ADWIN/commit latency; throughput and state | Repeated-run distributions, medians/p95 and uncertainty | Application count, event rate, horizon and model size within declared scope | Cost within predefined deployment budgets at supported scale and worthwhile relative to C4 benefit; no unrelated-machine timing comparisons | Unmeasured |
| C6 | Heterogeneous cloud-edge deployment and comparison | Actual edge/cloud nodes with recorded heterogeneity/network conditions | Same consumer and workload controls; placement/telemetry differences explicit | Preselected operational endpoint across tiers | Transfer delay, placement/resource diversity, controller cost | Independent repeated trials and cross-tier uncertainty | Network/compute heterogeneity and disconnected/degraded telemetry | Actual heterogeneous evidence supports a bounded continuum claim; cloud-only deployment cannot pass | Conditional; not demonstrated |

## 4. Layer A — Protocol Correctness

Established lightweight correctness evidence at baseline `b70d4eee0cdb20226b8f63590984bc2fcd6db20c`: Phases 1, 2A and 2B passed, with 123 tests passing and none failing. Those phases established `causal-timeline-v2`. Current [protocol](protocol.md) is `causal-timeline-v3`, with `phase-balanced-hourly-v1`; accounting remains `refresh-accounting-v1`. Phase 3A-R adds exact-grid histories, common eligibility, nominal clock reads and profile-age regressions; 256 lightweight tests and the corrected bounded pilot passed.

Covered invariants: causal features exclude target utilization; causal one-step residuals; causal recursive 288-step forecasting; future-data invariance; independent CPU/memory predictors; aligned `(t,t+24h]` targets; deterministic observation/residual/detector/trigger/commit/snapshot/delayed-verification ordering; anchored periodic grid; missing-observation/coalescing rules; uniform refresh accounting; PW/PP scheduling equality; V3 periodic-plus-drift decomposition. These are correctness properties, not accuracy or systems claims.

Phase 2C correctness/provenance disposition before claim-generating runs:

- Complete experiment provenance and deterministic run manifests are implemented and tested in [Phase 2C](provenance.md). Full scientific execution is gated by V2.5 PASS (met via V2.5A); V3 is the Materna confirmatory estimation study.
- Source/config/input/cohort/environment fingerprints, supported schemas and output hashes now govern cache rejection. Protocol/accounting labels alone are explicitly insufficient; old standalone reuse is refused.
- The historical [observed-row assessment](lag_semantics_assessment.md) is superseded by [exact-grid v3 semantics and eligibility](materna_gap_semantics_v3.md). No observed-row lag bridges a gap; confirmatory candidate IDs and protocol-validity exclusion codes are frozen in [V2.5A](confirmatory_design_freeze.md).
- Negative tests cover changed config/input/cohort/source/seed/protocol/schema/environment and incomplete/corrupt output; deterministic metadata/output tests and relocation recovery pass. Config-to-production binding passed bounded tests and execution; the non-adaptive estimation matrix is frozen in V2.5A.
- No implicit loading of archived outputs or legacy predictions as current causal measurements.

## 5. Layer B — Multi-Corpus Validation

Materna alone is insufficient. Publication requires at least **one additional substantially different real production corpus**, preferably two when feasible. Dataset fame is not a selection criterion. No corpus is selected by this contract.

A dataset-selection report must audit each candidate before acquisition/preprocessing work is authorized:

| Audit dimension | Required evidence / rejection question |
|---|---|
| Source/environment and age | Primary source, collection period, production context, documented domain shift from Materna; does age limit the claim? |
| Entity type/diversity | VM, container, task or machine; entity identity stability; real workload diversity rather than duplicate entities |
| CPU and memory | Units, capacity denominators, utilization semantics, aggregation and availability of both resources; no invented memory values |
| Timestamps/cadence | Timezone, resolution, ordering, clock reliability, duplicates, native sampling and cadence distribution |
| Missingness | Nulls, off-grid observations, outages, dropout bias and any permitted transformation |
| Duration/entities/spans | Total/eligible counts, continuous span distribution, bootstrap plus forecast-horizon feasibility |
| Future-horizon suitability | Causal origin availability, exact target grid compatibility, density eligibility and label coverage; declared adapters and exclusions |
| Licensing/acquisition | Permission, redistribution limits, source identity/checksum, reproducible acquisition without credentials in Git |
| Preprocessing cost | Required transformations, runtime/storage estimate, reproducible scripts, loss of semantics and engineering feasibility |

Candidates may include Alibaba cluster traces, Google/Borg cluster data, or other modern cloud/container traces. These are candidates only; suitability, licensing and availability require a later primary-source audit. Select on compatible telemetry and meaningful diversity, not on name recognition. Freeze eligibility and preprocessing before evaluating policy benefits; report exclusion denominators by corpus. Cross-corpus time/entity leakage is forbidden.

## 6. Layer C — Refresh-Policy Validation

Pre-register the core experiment before running it:

| Family | Required configurations | Question |
|---|---|---|
| Periodic-Window | 3h, 6h, 12h | Benefit of refresh opportunity using observation windows |
| Periodic-Predictor | 3h, 6h, 12h | Benefit of predictor-grounded content at the same intervals |
| DynAPM-V3 | 6h periodic + drift | Incremental effect of drift-triggered timing |
| Matched-budget Periodic-Predictor | 6h base plus exactly K non-adaptive eligible extras; analysis-only | Does drift timing help beyond receiving more predictor-grounded opportunities? |

Use the same bootstrap split, thresholds, frozen per-VM predictors, test entities, density rules and snapshot protocol. The trace-study counterfactual obtains only K = paired V3 committed drift refreshes, retains identical common-eligible 6h base commits, and places exactly K extras using `budget-match-uniform-eligible-v2`. Candidates are observed predictor-eligible timestamps excluding base commits; midpoint equal-spacing is deterministic. Drift timestamps, residual magnitudes, accuracy and future ground truth are forbidden placement inputs. K=0 is PP6. Enforce exact total equality per VM; no interval conversion, manual normalization, post-hoc commit resampling or table overrides.

This paired offline control tests timing conditional on equal refresh opportunities; it is not a deployable online policy, and equal counts do not establish equal measured compute cost. Historical PP/V3/BudgetMatched rows above remain withdrawn from primary confirmation after C1/C2 retirement. Primary confirmatory methods are Static / PW-12h / PW-6h / PW-3h / Full-Rewrite only ([V2.5 freeze](confirmatory_design_freeze.md)). Maintenance-cost service benchmarking is V6 under the remapped roadmap. Any future online/system budget-control design must be specified prospectively after downstream-consumer semantics are fixed; it is not implemented or validated here.

Primary confirmatory measurements: future-profile CPU/memory class correctness and p95-profile MAE; primary cost `n_refresh_events`. Report writes/changes, age, eligibility delays, verified evaluation counts and bias as secondary/diagnostic. Retained stale profiles are scored according to the current causal-timeline-v3 protocol.

Require per-volatility robustness analysis (secondary), paired VM-level inference, effects, confidence intervals, and Holm multiplicity correction within each frozen family F1–F3. Distinguish exploratory pilot discovery from held-out confirmation. Full-Rewrite is an operational-cost extreme, not automatically an accuracy oracle. No confirmatory interval experiment is started while practical margins remain unassigned.

## 7. Layer D — Maintenance Cost

Future instrumentation must separately measure:

- **Model:** RF training time; ongoing causal one-step inference latency; recursive 288-step horizon latency. Attribute CPU and memory models separately and combined.
- **Drift:** ADWIN update latency and detector state memory, including no-trigger processing.
- **Profile:** refresh computation latency; commit latency; profile state size; canonical field writes and value changes.
- **Service/scale:** CPU consumption, memory consumption, managed-application throughput, queue/backlog behavior and overhead as application count/event rate grows.

Record dedicated hardware, OS, Python/package versions, threads, concurrency, power/resource limits and timing boundaries. Separate offline training from ongoing maintenance; count amortized one-step work even when no refresh fires. Avoid double-counting nested phases in totals. Record warm-up, repeated measurements, timer resolution, median, p95 and distributions where useful. Include run-level uncertainty and measurement overhead. Compare timings only on matched hardware/environment and controlled runs. Freeze supported-scale and overhead budgets before claiming acceptability.

## 8. Layer E — System-Level Validation

A real Kubernetes-based experiment is mandatory for a strong systems/FGCS-style contribution. This is a plan, not authorization to implement or deploy it.

Smallest meaningful architecture:

```text
workload generator -> Kubernetes application(s) -> Prometheus / telemetry
 -> DynAPM profile-maintenance service -> downstream resource consumer/controller
 -> Kubernetes resource decision -> observed application + resource outcome
```

Use a resource-recommendation/provisioning controller as the downstream consumer. Hold its decision logic, safety limits and actuation cadence fixed; vary the maintained profile source. DynAPM maintains profiles; it is not turned into a new autoscaling algorithm. A harness must demonstrate actual consumed recommendations and resulting resource decisions. State how the current 24-hour forecast and 3h/6h/12h grids can be tested in real elapsed time; do not call time-compressed replay a real 24-hour operational deployment. Any shorter-horizon system configuration needs its own reviewed protocol and bounded claim.

Compare PW, PP, V3 and matched-budget PP under identical workload scenarios. Native HPA/VPA is optional only after the consumer/action semantics make a fair comparison possible; disclose metric inputs, resource actions, constraints and tuning opportunities. A differently scoped autoscaler is not a substitute for the matched profile-maintenance controls.

Measure application p50/p95/p99 latency, throughput and SLO violation rate; requested/used CPU and memory, utilization efficiency, under/over-provisioning; resource changes, churn, oscillation, reaction time and decision latency; DynAPM service CPU/memory, forecast latency, ADWIN cost and maintenance throughput. Preselect primary endpoints and resource guardrails instead of selecting favorable metrics afterward. Cost proxies must state their pricing/measurement assumptions; resource savings alone do not demonstrate monetary savings.

Use repeated controlled trials with identical load seeds/traces, reset/cache state, controller settings and resource envelopes. Counterbalance/randomize trial order, record cluster/node/background state and failures, and measure actual decisions and outcomes with aligned timestamps. Include a sanity intervention confirming that profile changes reach the consumer. A successful deployment screenshot proves neither benefit nor acceptable overhead. Freeze a power/precision plan and trial count before V8.

## 9. CECC / Edge Validation Rule

**Path A:** If genuine heterogeneous cloud-edge evidence is implemented and passes C6, retain an empirically bounded continuum framing.

**Path B:** If validation is cloud/Kubernetes-only, future title, abstract and contributions must narrow scope accordingly. Do not build an edge testbed merely because an old title used CECC.

Evidence determines framing. Framing must never determine evidence.

## 10. Layer F — Controlled Robustness Tests

Predefine deterministic/mechanistic scenarios for stable, periodic and burst workloads; abrupt regime shifts; gradual drift; low/medium/high volatility; sparse observations; missing scheduled timestamps; telemetry gaps longer than the period; degraded predictor quality; ADWIN false triggers; and late triggers.

For each scenario freeze the injected mechanism, seeds, expected event order, telemetry availability, forecast horizon and observable failure modes. Compare profile fidelity, trigger timing, event decomposition, safety and cost against the relevant controls. Detector interventions must be clearly labeled synthetic, not evidence of real drift-detection performance. These tests establish mechanism behavior and limitations; they do not replace production-corpus validation.

## 11. Baseline Policy

| Baseline | Question answered |
|---|---|
| Static | What is gained over bootstrap-only state with no runtime maintenance? |
| Reactive | What is gained over class-change-triggered observation maintenance? |
| Periodic-Window | Is predictor-grounded content better than recent observations at the same schedule? |
| Full-Rewrite | What changes when observation-grounded state is rewritten at every eligible processed observation, at high cost? |
| Periodic-Predictor at several intervals | How do predictor-grounded benefit and cost vary with update opportunity? |
| Matched-budget Periodic-Predictor | Does drift-triggered timing help beyond extra predictor-grounded refreshes? |

Choose a system-level baseline only after downstream consumer semantics are fixed. Keep inputs, tuning opportunity, timing rules and safety constraints comparable. Avoid weak-baseline theater: a convenient but semantically mismatched competitor cannot support a superiority claim.

## 12. Statistical Validation Contract

For trace studies, the primary unit is the **VM/application**, not correlated timestamps. Aggregate declared endpoints within each entity, then compare paired entities on a common predeclared eligibility set. Report entity counts, coverage, missing pair/exclusion reasons and workload duration. Longer traces must not silently receive extra inferential weight. Interval snapshots remain descriptive observations, not independent replicates.

Freeze primary endpoint/comparison families, practical-effect margins, signed effect directions, and confirmatory versus descriptive analyses. Use paired entity bootstrap CIs, paired raw effects and standardized paired effects where appropriate (state the denominator, e.g. SD of paired differences). Report both benefit and harm tails/strata. Use signed-rank or another justified paired procedure with assumptions stated. Default signed-rank treatment: omit zero differences (`zero_method="wilcox"`), handle ties using a documented suitable approximation/permutation procedure rather than an invalid exact-no-ties assumption; report effective n. If all pairs tie, report effect zero and no evidence of a difference, with p=1 by the frozen reporting rule; if a statistic is undefined (e.g. zero effect-size denominator), label it undefined rather than inventing an effect. Freeze bootstrap method, replicate count, seed and CI level before runs.

Control multiplicity, by default Holm at familywise alpha 0.05, across each predeclared confirmatory family. Exploratory strata/sensitivity results are explicitly descriptive unless separately powered and registered. A small p-value cannot replace the practical-effect and uncertainty criteria. Per-corpus failures must remain visible; any pooled synthesis is secondary and declares heterogeneity assumptions.

For Kubernetes, the primary unit is an **independent experimental run/workload-scenario replicate**, not each request. Request latency distributions form within-run metrics. Pair runs by scenario/seed where designed, and account for scenario/cluster blocking. Run a future power/precision planning task with target CI width/practical margins, pilot variance, feasible trial count and stopping rules before trials. Do not choose replication count after observing significance or stop when p crosses a threshold.

## 13. Reproducibility Contract

Before any new full-corpus claim-generating run, record:

- Git commit and dirty status (with source diff/fingerprint if allowed; confirmatory runs should use clean committed code).
- Temporal protocol and accounting schema versions.
- Complete configuration file and SHA-256; source-tree/scientifically relevant code fingerprint.
- Dataset manifest, file hashes/stable immutable identifiers, preprocessing identity and eligible entity list.
- Environment/package versions, Python, OS/hardware, threads and relevant resource settings.
- Random seeds and nondeterministic-library settings.
- Exact command invocation; UTC start/end times; output path and output manifest with hashes.
- Completion status, partial runs, failures, exclusions and denominators.

Cache compatibility must include every scientifically relevant source/config/input/model/seed/protocol/schema/environment fingerprint. Reject missing or different fingerprints, partial/corrupt outputs, and stale fitted models. No unversioned result reuse. An explicit compatibility exception, if ever necessary, requires a reviewed scientific justification before reuse; it cannot silently relabel an older generation. Checkpoints and historical archives must never be fallback runtime inputs. Phase 2C implements and negatively tests the shared [provenance contract](provenance.md); old unversioned workflows are refused. V2 must validate its binding to actual scientific execution before full-corpus use.

## 14. Reviewer Concern Traceability

TOCS concerns below are the human-confirmed requirements supplied for this consolidation. They are paraphrases, **not claimed verbatim quotations** from a locally located decision letter. Correctness completion addresses only concerns 10-11; concerns 1-9 remain open.

| Source | Concern | Validation requirement | Implementation/experiment | Gate | Status |
|---|---|---|---|---|---|
| TOCS 1, confirmed | No system-level contribution/integration demonstrated | Actual consumer of maintained profiles and measured outcomes | Kubernetes resource-recommendation/provisioning loop | V7-V8 | OPEN |
| TOCS 2, confirmed | No scheduler/autoscaler/capacity-planner/SLA-monitor integration | Integrate one justified downstream role, identify interfaces/actions | Fixed provisioning consumer; not a claim of all four integrations | V7-V8 | OPEN |
| TOCS 3, confirmed | No genuine latency/throughput/utilization/cost/control-overhead evidence | Repeated operational measurements and uncertainty | System endpoints plus overhead instrumentation | V5,V8 | OPEN |
| TOCS 4, confirmed | Only one Materna VM corpus | Distinct real production corpus | Suitability audit and external replication | V6 | OPEN |
| TOCS 5, confirmed | No cross-workload/cross-dataset generalization | Replication and heterogeneity/negative-transfer analysis | Locked-policy multi-corpus study | V6,V10 | OPEN |
| TOCS 6, confirmed | CECC framing exceeds edge/container/Kubernetes/heterogeneity evidence | Actual heterogeneous evidence or narrower framing | Conditional C6 path; Kubernetes alone insufficient for edge claim | V7-V8,V10 | OPEN |
| TOCS 7, Reviewer 1 confirmed | Multiple periodic intervals needed | PW/PP 3h/6h/12h | Pre-registered interval comparison | V2-V4 | OPEN |
| TOCS 8, Reviewer 1 confirmed | Predictor-grounded periodic control with comparable refresh budget | Exact paired event budget with non-adaptive eligible placement; cost measured separately | Analysis-only BudgetMatched vs V3 | V2.5,V3,V4,V5 | Bounded mechanism PASS; scientific benefit OPEN |
| TOCS 9, Reviewer 1 confirmed | Forecast, ongoing prediction, ADWIN and memory costs missing | Separate component and service measurement | Training/inference/drift/commit/state/scale benchmarks | V5 | OPEN |
| TOCS 10, confirmed | Refresh counts ambiguous | Initialization/events/writes/changes separated | Phase 2B, canonical counters and schema | V1A | Correctness PASS; empirical comparisons not run |
| TOCS 11, confirmed | Scheduling/missing/coincident/snapshot semantics unclear | One causal deterministic timeline and tests | Phase 1 + Phase 2A, shared replay/grid | V0 | Correctness PASS; corpus benefit unproven |
| Historical project lesson — not verbatim reviewer comment | Previous design did not genuinely establish future forecast-lead capability | Exact origins/targets and causal lead evaluation | Origin-invariance and horizon tests; declared future endpoints | V0,V2-V3 | Protocol PASS; scientific claim still unproven |
| Historical project lesson — not verbatim reviewer comment | Cross-resource information-sharing effects were not established | Any future sharing claim requires controlled removal/addition of information | Separate future design only; current CPU/memory models are independent | V10 | No such current claim |
| Historical project lesson — not verbatim reviewer comment | Cross-machine information-sharing effects were not established | Matched local/shared training ablation with held-out machines if claimed | No new sharing algorithm in current scope | V10 | No such current claim |
| Historical project lesson — not verbatim reviewer comment | Machine-specific predictive benefit was not established | Per-entity held-out paired benefit and heterogeneity if claimed | Paired entity analysis, no inference from pooled aggregates alone | V3,V6,V10 | OPEN if claimed |

**Exact previous rejection decision letter not found locally.** Search and evidence limitations are recorded in [the consolidation record](consolidation_record.md). Internal manuscript reviews, contribution decisions and rejection-directory names are not reviewer letters. Do not reconstruct reviewer wording. The four previous-study lessons above are human-confirmed historical project lessons only.

## 15. Venue Rule

FGCS is a candidate, not the predetermined destination. Journal selection occurs after major validation evidence exists. A target journal must fit the actual demonstrated contribution. We do not expand claims to fit a journal.

High-selectivity/typically JUFO Level 3 aspirations do not waive any gate or establish venue fit. Check current venue scope/ranking only at V9 (claim audit / venue decision); no current ranking claim is made here. Manuscript drafting starts after V9, with claims limited to evidence that passed its predefined criteria.

## Development pilot exclusion rule

Phase 3A uses the deterministic 18-VM DEVELOPMENT PILOT COHORT defined in [bounded_pilot.md](bounded_pilot.md). Its managed cohort manifest permanently records the selected trace/VM identities. Primary confirmatory Materna analysis excludes these 18 VMs; an optional later all-retained descriptive analysis is labeled separately after design freeze. Do not use viewed exploratory effects to choose practical benefit/harm margins or confirmatory families. V2 execution does not establish a manuscript claim.

Phase 3A completed 198/198 managed development evaluations with passing count/alignment/integrity checks. V2 remains BLOCKED because [timestamp-gap semantics](materna_gap_audit.md) and the phase-locked evaluation grid require separate preconfirmation corrections and bounded revalidation. See [the pilot record](bounded_pilot.md) for permanent trace/VM exclusions and exact provenance. No scientific benefit is established by successful execution.

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
primary independent confirmation. The [V2.5 / V2.5A freeze](confirmatory_design_freeze.md)
locks the 1,558-candidate confirmatory cohort, pilot exclusions, endpoints,
F1–F3 comparisons, multiplicity, tests/CIs, protocol-validity exclusion codes,
and the non-adaptive method matrix as an estimation study. Profile-level
practical significance is `NOT_DEFINED_AT_PROFILE_LEVEL`. No thresholds may be
chosen to favor observed pilot effects. See [protocol](protocol.md) and
[the v3 metadata audit](materna_gap_semantics_v3.md).

## Corrected bounded gate status

V2 passed under causal-timeline-v3 and phase-balanced-hourly-v1; see [pilot record](bounded_pilot.md). After V2.4G (**EMPIRICAL/SYSTEM STUDY VIABLE**), V2.5A amends the confirmatory design to estimation-first (**V2.5 = PASS**) and V3 completes the Materna confirmatory estimation study (**V3 = PASS**; [results](materna_confirmatory_results.md)). V4A freezes Google ClusterData 2019 for independent replication (**V4A = PASS**; [selection](independent_corpus_selection.md)). **V4B.5 streaming acquisition READY** ([acquisition](google2019_acquisition.md); extract not started). The 18 development entities remain excluded from primary Materna confirmation. C3/C4 remain UNPROVEN.

## V2.4 prerequisite to confirmation freeze

Before V2.5, review [predictor diagnosis](predictor_diagnosis.md) on only the fixed eighteen development VMs and the [official-source dataset audit](dataset_suitability_audit.md). Distinguish recursive feedback, one-step model quality, distribution shift, threshold sensitivity and gap availability using exploratory diagnostics. Do not tune models here or inspect the 1,558 possible confirmatory entities. Dataset ranking must reflect resource semantics, usable horizon, continuity, reproducibility and independent workload evidence, not expected favorable performance. V2.5 remains blocked until this work is reviewed; V3 remains blocked. A redesign recommendation requires a separate development/validation step before freezing claims.

V2.4 diagnostics are complete (259 tests; managed fixed-development execution verified). Review found strong recursive-error growth and weak profile forecasting; a separate predictor-design investigation is recommended before the design freeze. This is not a change to current parameters or permission to inspect confirmatory outcomes. V2.5 remains blocked pending review/disposition; V3 remains blocked. See the diagnosis for uncertainty and the dataset audit for official-source ranking and unresolved acquisition gates.


## V2.4D predictor disposition — current design prerequisite

[Predictor disposition](predictor_disposition.md) records **PREDICTOR NOT JUSTIFIED**
for profile-content generation. C1 is unsupported and is withdrawn from the
current intended contribution set; its earlier matrix row remains for traceability,
not as an executable plan to rescue a favorable outcome. C2 and the predictor-based
controls in the earlier policy/system plans require review and re-scoping before
V2.5: compare drift timing against periodic and exact matched-budget timing with
the same observation-window content. Do not call seasonal/PW-equivalent content a
separate learned predictive contribution. One-step RF residual surveillance has
not been independently justified by these content studies. It requires a separate
incremental-value test. Cross-corpus and system claims remain unproven.

No production interfaces or scientific behavior are changed by this decision.
An architecture follow-up must predefine drift refresh behavior when a 200-slot
trailing content window is unavailable and revalidate common periodic eligibility,
exact budgets, accounting and phase-balanced reads on the same development cohort.
Only then can a reviewed V2.5 freeze the final architecture/comparison matrix.
V2.5 and V3 remain blocked. No model search or confirmatory run is authorized.


## V2.4E — observation-content timing investigation

The candidate architecture drops predictor-generated content. The bounded matrix
is PW-6h, Adaptive-Residual (same PW content, frozen one-step RF/ADWIN timing), and
analysis-only BudgetMatched with the same base plus K nonadaptive eligible extras.
The primary exploratory contrast is Adaptive minus BudgetMatched; Adaptive minus
PW is secondary. All methods use exactly the same paired finite >=200/288 trailing
slots, thresholds, hourly read events and forward truth. Residual availability adds
a requirement only for drift decisions, not periodic content eligibility.

No practical-effect margin is defined retrospectively. Report effect distributions,
VM/tier directions, age, counts and uncertainty limitations rather than inventing
a favorable threshold or performing confirmatory inference. Choose a conservative
A/B/C residual-signal disposition after the fixed development run; prediction is
not retained merely because a pooled number is positive. V2.5 remains blocked
until this architectural investigation is reviewed. No confirmation follows
without a separate frozen design and authorization.


## V2.4E disposition — no retained prediction component

The [timing-only study](adaptive_timing_investigation.md) completed 54/54 bounded
comparisons with exact equal budgets, identical observation-window content and
verified provenance. **RESIDUAL SIGNAL NOT JUSTIFIED**: modest class-average
changes did not accompany consistent p95-error/VM/tier benefit. No post-hoc
meaningful-effect threshold or confirmatory inference was used. Recommend removing
prediction entirely from the final framework; both profile-content RF and
residual RF are unsupported roles under the tested development design.

This supersedes the earlier proposed predictor-driven C1/C2 superiority plans.
C1 remains withdrawn; residual-driven C2 is unsupported. The old matrix and
predictor baseline plans remain historical candidate requirements, not execution
authorization. New window/residual controls are preserved only for development
reproducibility pending separately reviewed refactoring. Observation-window
maintenance alone is a reference implementation, not established novel adaptive
or systems evidence. Review the final contribution/research scope before V2.5;
V2.5/V3 remain blocked. No full run or new model search is authorized.

## V2.4F disposition — adaptive maintenance not justified

The corrected [predictor-free trigger study](predictor_free_adaptive_investigation.md)
completed 90/90 fixed-development comparisons with exact Reactive and ADWIN
matched budgets, common 24h content, zero prediction calls, and independently
reconstructed schedules/content/truth. Reactive worsens both average class
correctness values and both MAEs against its control. Direct-observation ADWIN
is mixed: memory MAE worsens, VM wins split, and no volatility tier is uniformly
favorable. The first technically invalid generation remains explicitly superseded.

**ADAPTIVE MAINTENANCE NOT JUSTIFIED.** C2 is withdrawn as a candidate contribution.
Do not add trigger searches. Deterministic observation-window maintenance remains
a reference implementation, not a demonstrated novel adaptive method.


## V2.4G — research scope redesign

The [scope redesign](research_scope_redesign.md) consolidates claim status,
audits the non-adaptive Static/PW/Full-Rewrite fidelity–cost trade-off on the
corrected development pilot, and compares candidate directions against primary
literature. Disposition: **EMPIRICAL/SYSTEM STUDY VIABLE**. Forecasting and
adaptive-refresh superiority stay withdrawn. A cost-aware cadence *selector* is
not authorized; system validation remains optional/deferred. No new algorithm or
confirmatory run is authorized by V2.4G alone.

## V2.5 — empirical contribution freeze / V2.5A estimation amendment (current)

The [confirmatory design freeze](confirmatory_design_freeze.md) and
`configs/materna_confirmatory_v1_1.{json,yaml}` lock estimation-framed RQ1–RQ4,
the 1,558-candidate cohort, Static/PW-12h/PW-6h/PW-3h/Full-Rewrite,
primary/secondary endpoints, F1–F3 comparisons, bootstrap B=10000 seed=20251022,
Wilcoxon/Holm plan, cost/Pareto reporting, and estimation decision rules. The
original margin-blocked freeze remains at `configs/materna_confirmatory_v1.*`
for provenance. C1/C2 remain withdrawn. Profile-level practical significance is
**`NOT_DEFINED_AT_PROFILE_LEVEL`** (numeric margins not invented). **V2.5 STATUS:
PASS (V2.5A).** **V3 STATUS: PASS** ([Materna confirmatory estimation results](materna_confirmatory_results.md)).
**V4A STATUS: PASS** ([independent corpus selection](independent_corpus_selection.md)):
Google ClusterData 2019 frozen for acquisition under
`google_clusterdata_2019_replication_protocol_v1`. **V4B.5 = PASS
(streaming redesign)** ([acquisition](google2019_acquisition.md)): local size
no longer equated to bytes-processed; per-cell streaming plan ready for e,g
under ~105 GiB free with 20 GiB reserve (runtime guard for conservative g).
Extract not yet executed. Next after extract: **V4C** protocol/cohort
validation. C3 and C4 remain UNPROVEN. Future gates: V5 second-corpus
replication; V6 cost benchmark; V7 K8s harness; V8 operational validation; V9
claim audit / venue decision. Do not claim C3–C6 before the corresponding gates
pass.
