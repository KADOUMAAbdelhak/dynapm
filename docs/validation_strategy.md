# DynAPM Validation Strategy

This is an engineering and research-governance contract, not evidence of scientific benefit. It authorizes no experiments. Phase 2C implementation, corpus runs, system deployment, and manuscript drafting require their own tasks. The [roadmap](validation_roadmap.md) defines the gates.

## 1. Validation Principle

No feature or method becomes a manuscript contribution until a predefined experiment can falsify its claimed benefit. Implementation completion is not validation. Statistical significance alone is not sufficient validation. Offline accuracy alone is not sufficient system validation.

Before observing confirmatory outcomes, freeze the claim, eligibility rules, controls, endpoints, minimum practically important effects, uncertainty procedure, failure conditions, and analysis code. Publish negative and mixed outcomes in the evidence record. A failed gate narrows or rejects a claim; it does not justify changing the endpoint afterward.

## 2. Intended Claims

These are candidate claims, not conclusions:

- **C1:** Predictor-grounded profile maintenance improves future-profile fidelity relative to observation-window maintenance.
- **C2:** Drift-triggered refresh provides benefit beyond predictor-grounded periodic refresh when update opportunity/cost is controlled.
- **C3:** Benefits generalize beyond one workload corpus.
- **C4:** Improvements in maintained profile state produce measurable downstream operational benefit.
- **C5:** DynAPM maintenance overhead is acceptable relative to its benefit.
- **C6:** Any empirical Cloud-Edge/continuum claim requires actual heterogeneous/edge evidence. Without that experiment, CECC remains motivation/context, not an empirical contribution.

A claim decision must address direction, effect magnitude, consistency, uncertainty, and operational relevance where applicable. Before confirmatory runs, a signed experiment specification must assign numerical minimum-benefit and maximum-harm margins to its endpoints. Those values are currently **unassigned** and therefore block claim-generating runs; choose them from engineering requirements and an explicitly exploratory pilot, never the held-out confirmatory outcomes. Freeze the margins before V3/V4, and separate system margins before V8. Report estimates and intervals even when a claim fails.

## 3. Claim-to-Evidence Matrix

| Claim | Experiment required | Datasets / environment | Controls / baselines | Primary metrics | Secondary metrics | Statistical analysis | Sensitivity / ablation | Minimum evidence required | Current status |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Same-origin causal profile evaluation, paired by entity, at matched intervals | Fresh Materna plus independently selected production corpus | PW vs PP at 3h/6h/12h; identical bootstrap, models, eligibility and observation timelines | CPU/memory future-profile class accuracy and p95 profile MAE; co-primary family frozen prospectively | Provisioning under/well/over rates, volatility strata, refresh counters | Paired entity bootstrap CIs, paired effects and inference; multiplicity control | Interval, missingness, predictor quality; forecast-origin vs stale-profile scoring | Desired accuracy increase/error decrease exceeds frozen practical margin with uncertainty bounded; no unacceptable resource-specific harm; consistent direction across entities/corpora or explicitly narrowed claim | Unvalidated; protocol tests only |
| C2 | V3 vs ordinary PP and prospectively calibrated matched-budget PP | Same fresh held-out traces; shared replay/protocol | PP 6h, PP interval grid, matched-budget PP; same fitted predictors and drift inputs | Fidelity/provisioning benefit at comparable committed refresh opportunity and measured cost | Drift vs periodic event decomposition, field writes/changes, drift timing | Paired effects/CIs and planned paired tests; budget discrepancy reported | Drift disabled, degraded/late/false detections, cost-matched sensitivity | Improvement exceeds frozen benefit margin and budget/cost tolerance; direction consistent; no claim that more refreshes alone prove drift benefit | Unvalidated |
| C3 | Locked-protocol external replication | At least one substantially different real production corpus; prefer two | Same controls; common protocol with documented domain adapters | C1/C2 endpoint replication per corpus | Coverage, exclusions, workload/cadence strata, negative transfer | Per-corpus paired inference; explicit heterogeneity; any pooled estimate secondary | Dataset, entity type, telemetry quality, forecast horizon | Practical benefit with bounded uncertainty across distinct corpora, or clear limits; not a pooled average masking failure | No dataset selected |
| C4 | Repeated controlled downstream resource decisions | Real Kubernetes application(s), telemetry and resource controller | PW, PP, V3, matched-budget PP; fair native mechanism only if semantics match | Preselected application/SLO endpoint and resource-efficiency endpoint | Latency quantiles, throughput, changes/churn, decision delay | Independent-run/scenario paired contrasts, CIs and planned tests | Workload scenarios, load transitions, actuation delay, controller guardrails | Operational effect exceeds frozen SLO/resource margin with uncertainty; no unacceptable safety/churn regression; repeated across scenarios | No systems evidence |
| C5 | Component microbenchmarks and service scale study | Dedicated recorded hardware/software; then system harness | Same workload/model/config across policies; separate component attribution | Maintenance CPU/time/memory relative to frozen service budgets and benefit | Training, one-step/horizon/ADWIN/commit latency; throughput and state | Repeated-run distributions, medians/p95 and uncertainty | Application count, event rate, horizon and model size within declared scope | Cost within predefined deployment budgets at supported scale and worthwhile relative to C4 benefit; no unrelated-machine timing comparisons | Unmeasured |
| C6 | Heterogeneous cloud-edge deployment and comparison | Actual edge/cloud nodes with recorded heterogeneity/network conditions | Same consumer and workload controls; placement/telemetry differences explicit | Preselected operational endpoint across tiers | Transfer delay, placement/resource diversity, controller cost | Independent repeated trials and cross-tier uncertainty | Network/compute heterogeneity and disconnected/degraded telemetry | Actual heterogeneous evidence supports a bounded continuum claim; cloud-only deployment cannot pass | Conditional; not demonstrated |

## 4. Layer A — Protocol Correctness

Established lightweight correctness evidence at baseline `b70d4eee0cdb20226b8f63590984bc2fcd6db20c`: Phases 1, 2A and 2B passed, with 123 tests passing and none failing. The [temporal protocol](protocol.md) is `causal-timeline-v2`; accounting is `refresh-accounting-v1`.

Covered invariants: causal features exclude target utilization; causal one-step residuals; causal recursive 288-step forecasting; future-data invariance; independent CPU/memory predictors; aligned `(t,t+24h]` targets; deterministic observation/residual/detector/trigger/commit/snapshot/delayed-verification ordering; anchored periodic grid; missing-observation/coalescing rules; uniform refresh accounting; PW/PP scheduling equality; V3 periodic-plus-drift decomposition. These are correctness properties, not accuracy or systems claims.

Phase 2C correctness/provenance disposition before claim-generating runs:

- Complete experiment provenance and deterministic run manifests are implemented and tested in [Phase 2C](provenance.md). Full scientific execution remains gated by V2.
- Source/config/input/cohort/environment fingerprints, supported schemas and output hashes now govern cache rejection. Protocol/accounting labels alone are explicitly insufficient; old standalone reuse is refused.
- The [observed-row lag assessment](lag_semantics_assessment.md) records temporal distance distributions and causal meaning across gaps. Existing semantics remain unchanged; V2 must predefine handling/strata, and any correction needs separate protocol review.
- Negative tests cover changed config/input/cohort/source/seed/protocol/schema/environment and incomplete/corrupt output; deterministic metadata/output tests and relocation recovery pass. Config-to-production binding remains a pilot requirement.
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
| Matched-budget Periodic-Predictor | Fixed periodic interval calibrated prospectively | Does drift timing help beyond receiving more predictor-grounded opportunities? |

Use the same bootstrap split, thresholds, predictor training budget, test entities, density rules and snapshot protocol. Freeze any tuning on disjoint development entities/time. Do not select a periodic interval from test-set drift counts or outcomes. Calibrate the matched-budget interval against committed V3 refresh rate on a separate development set, freeze it, and report achieved held-out budgets. Pre-register the acceptable budget mismatch and a cost-matched sensitivity before confirmation. A missed tolerance makes the matched-budget causal contrast inconclusive; do not manually normalize counts, resample commits post hoc, or overwrite table cells.

Primary measurements: future-profile CPU/memory class accuracy, p95 forecast/profile error and declared provisioning outcomes. Report canonical `n_refresh_events`, trigger decomposition, writes/changes, nominal ticks due and periodic commits. Retained stale profiles are scored according to the Phase 2A protocol; origin-aligned forecast diagnostics are separate endpoints, not silently substituted.

Require per-volatility analysis, paired VM-level inference, effects, confidence intervals, and multiplicity correction for confirmatory families. Distinguish exploratory interval discovery from held-out confirmation. Full-Rewrite is an operational-cost extreme, not automatically an accuracy oracle. No interval experiment is started by this document.

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
| TOCS 8, Reviewer 1 confirmed | Predictor-grounded periodic control with comparable refresh budget | Prospective committed-budget calibration and tolerance | Matched-budget PP vs V3 | V2,V4 | OPEN |
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

High-selectivity/typically JUFO Level 3 aspirations do not waive any gate or establish venue fit. Check current venue scope/ranking only at V11; no current ranking claim is made here. Manuscript drafting starts after V10, with claims limited to evidence that passed its predefined criteria.

## Development pilot exclusion rule

Phase 3A uses the deterministic 18-VM DEVELOPMENT PILOT COHORT defined in [bounded_pilot.md](bounded_pilot.md). Its managed cohort manifest permanently records the selected trace/VM identities. Primary confirmatory Materna analysis excludes these 18 VMs; an optional later all-retained descriptive analysis is labeled separately after design freeze. Do not use viewed exploratory effects to choose practical benefit/harm margins or confirmatory families. V2 execution does not establish a manuscript claim.
