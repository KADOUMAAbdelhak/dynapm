# V2.4G — Research Scope Redesign

Development-only scope decision. No confirmatory Materna outcomes were
accessed. No new predictor, trigger, threshold, or practical-effect margin was
invented or tuned. Quantitative trade-off numbers are traced to the corrected
Phase 3A-R pilot (`causal-timeline-v3`) plus a predictor-free diagnostic
reconstruction of signed bias/age on the same fixed 18 VMs.

**Disposition: `EMPIRICAL/SYSTEM STUDY VIABLE`.**

## 1. Claim disposition

| Claim / candidate contribution | Status | Evidence basis |
|---|---|---|
| C1 — Predictor-grounded profile content beats observation-window content | **WITHDRAWN** | V2.4D disposition B; seasonal/PW content stronger than learned profile RF |
| C2 — Adaptive refresh beats equal-budget periodic refresh | **WITHDRAWN** | V2.4E residual-RF not justified; V2.4F Reactive and direct-observation ADWIN not justified |
| Forecasting-superiority contribution (any retained learned profile generator) | **WITHDRAWN** | Same as C1; architecture recommendation is prediction-free content |
| Adaptive-refresh-superiority contribution (RF residual, Reactive, observation ADWIN) | **WITHDRAWN** | V2.4E–F equal-budget negative dispositions |
| C3 — Multi-corpus generalization of a maintenance benefit | **UNPROVEN** | No second corpus executed; Google 2019 ranked first in the dataset audit only |
| C4 — Downstream provisioning/placement/SLA benefit from maintained profiles | **UNPROVEN** | No Kubernetes/system loop; offline fidelity ≠ operational benefit |
| C5 — Maintenance overhead acceptable relative to benefit | **UNPROVEN** | Pilot wall times are feasibility only, not cost budgets |
| C6 — Cloud–edge continuum empirical claim | **UNPROVEN** | No heterogeneous edge deployment |
| Non-adaptive observation-window maintenance as a *correctness/reference* implementation | **SUPPORTED** (engineering, not novelty) | Shared content, accounting, and phase-balanced evaluation work on development VMs |
| Novel adaptive DynAPM algorithm ready for confirmatory superiority | **WITHDRAWN** | No retained adaptive or forecasting component |
| Cost-aware periodic cadence *selector* as a frozen product claim | **UNPROVEN** | Trade-offs exist (§2) but no selector was fit; not authorized as a contribution yet |
| Rigorous causal benchmark + negative findings as an empirical contribution | **UNPROVEN** pending freeze | Strongest remaining direction (§4B); not yet confirmatory evidence |

Statuses use only `SUPPORTED` / `WITHDRAWN` / `UNPROVEN`. Forecasting-superiority and
adaptive-refresh-superiority are explicitly retired.

## 2. Non-adaptive fidelity versus refresh-cost audit

### Source

| Item | Identity |
|---|---|
| Authoritative pilot | `results/runs/6d801e1fe87c2696c1d6f190ddb8aef96bd48cc1660d6650541afc68ded20682/2026-10-21T111323.571341Z-6d801e1fe87c-e3a215fe` |
| Source commit (pilot) | `82a79b90d70ce0405ffbf161698180bdf4f49ed7` |
| Protocol / grid / accounting | `causal-timeline-v3` / `phase-balanced-hourly-v1` / `refresh-accounting-v1` |
| Cohort | Fixed 18 development VMs; SHA-256 `6f6f0c78902f5ad6568dc0e299c97ca217d6449d971fa1a44f06ab2e04f6684f` |
| Methods | Static, PW-3h, PW-6h, PW-12h, Full-Rewrite |
| Bias/age reconstruction | `python -m dynapm.scripts.v24g_reconstruct_nonadaptive_tradeoff`; reconciled class/MAE/refresh/write counts to archived pilot within `1e-9` |
| Machine-readable outputs | `results/analysis/v24g_nonadaptive_tradeoff/` (`summary.json`, `per_vm_nonadaptive.parquet`, Pareto/contrast tables) |
| Confirmatory access | **False** (reconstruction used only the 18 pilot VMs) |

### Equal-VM macro averages

Class values are fractions; MAE/bias are utilization percentage points; ages are
hours. Refresh counts exclude the single initialization event.

| Method | CPU class | Mem class | CPU MAE | Mem MAE | CPU bias | Mem bias | Refreshes | Field writes | Value changes | Mean age | Median age | p95 age | Age zero % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 0.4978 | 0.5530 | 0.6492 | 1.0510 | +0.2341 | +0.3179 | 0.0 | 0.0 | 0.0 | 252.3 | 251.9 | 478.8 | 0.20 |
| PW-12h | 0.7407 | 0.7142 | 0.4285 | 0.7513 | −0.0437 | −0.0142 | 43.1 | 172.4 | 81.8 | 5.67 | 5.21 | 11.5 | 8.10 |
| PW-6h | 0.7480 | 0.7185 | 0.4276 | 0.7259 | −0.0357 | +0.0018 | 86.7 | 346.9 | 140.7 | 2.68 | 2.43 | 5.50 | 16.38 |
| PW-3h | 0.7529 | 0.7254 | 0.4132 | 0.7108 | −0.0217 | +0.0019 | 173.4 | 693.8 | 224.2 | 1.19 | 1.00 | 2.50 | 32.82 |
| Full-Rewrite | 0.7572 | 0.7270 | 0.4023 | 0.6943 | −0.0143 | +0.0035 | 6287.5 | 25150.0 | 900.9 | 0.15 | 0.00 | 0.47 | 99.45 |

Per-VM rows (all 18 × 5) are in `per_vm_nonadaptive.parquet`.

### Paired equal-VM contrasts (left minus right)

| Contrast | Δ CPU class | Δ Mem class | Δ CPU MAE | Δ Mem MAE | Δ refreshes |
|---|---:|---:|---:|---:|---:|
| PW-3h − PW-6h | +0.00486 | +0.00694 | −0.0144 | −0.0151 | +86.7 |
| PW-6h − PW-12h | +0.00733 | +0.00428 | −0.00086 | −0.0254 | +43.6 |
| PW-3h − PW-12h | +0.0122 | +0.0112 | −0.0153 | −0.0405 | +130.3 |
| PW-6h − Static | +0.250 | +0.166 | −0.222 | −0.325 | +86.7 |
| Full-Rewrite − PW-3h | +0.00431 | +0.00163 | −0.0109 | −0.0165 | +6114 |

Interpretation (descriptive only; no practical margin was invented):

1. **Static → any PW** is the large fidelity jump. Periodic observation-window
   maintenance is clearly better than freeze-at-bootstrap on these VMs.
2. **Among PW cadences**, fidelity gains are small relative to the Static jump,
   while refresh cost roughly doubles from 12h→6h and again 6h→3h.
3. **Full-Rewrite** buys only a few thousandths of class accuracy / ~0.01–0.02
   MAE over PW-3h at ~35× the PW-3h refresh count. It is not a plausible default
   operating point under any cost-sensitive reading of these numbers.
4. Strict all-four-metric fidelity improvement (ignoring cost) holds for
   PW-3h vs PW-6h on **7/18** VMs and PW-6h vs PW-12h on **7/18** VMs. Cadences
   are **not** universally ordered by fidelity.

### Pareto fronts (class ↑, MAE ↓, refresh count ↓)

- **All five methods:** Static is on the front for **18/18** VMs by construction
  (cost 0 cannot be dominated). PW-12h/6h/3h appear on 14/13/12 VMs;
  Full-Rewrite on 16. Multiplicity of undominated points means the front is a
  *set*, not a single preferred method.
- **PW-only (3h/6h/12h):** PW-12h is on the front for **18/18** (lowest PW cost);
  PW-6h 16/18; PW-3h 15/18. Most VMs have a multi-point front (15 VMs retain all
  three). Cadence preference is therefore **not** a single winner per VM under
  this three-objective definition.
- **Volatility association (descriptive):** PW-3h front members have lower mean
  bootstrap CPU volatility (~1.42) than PW-12h (~1.87), but tier crosstabs are
  mixed and no selector was fit. This does **not** authorize a volatility→cadence
  rule.

### Consequence for direction A

A non-adaptive fidelity–cost trade-off **exists** and is measurable under the
current protocol. It does **not** by itself establish a novel cadence-selection
algorithm, a practical operating point, or a confirmatory claim. Full-Rewrite is
dominated as a systems operating choice on cost grounds; Static is dominated on
fidelity grounds if *any* maintenance cost is acceptable.

## 3. Literature collision audit

Primary sources inspected for this gate (DOI/URL recorded). Overlap is stated
relative to DynAPM’s possible remaining scopes, not as a claim of exhaustive
survey coverage.

| Source | Contribution | Environment | Overlap / difference |
|---|---|---|---|
| [AdaMC, NOMS 2025](https://doi.org/10.1109/noms57970.2025.11073663) | Adaptive scrape-frequency controller for microservice monitoring cost | Cloud/edge microservices vs Prometheus | **High collision with adaptive sampling cost claims.** Differs: scrape intensity, not 24h CPU/memory class+p95 profile commit semantics or equal-budget refresh accounting. |
| [AdaM / Trihinas et al., IEEE TSC](https://doi.org/10.1109/TSC.2018.2808956) | Low-cost adaptive IoT monitoring (sampling + filtering) | IoT / edge streams | **High collision with adaptive monitoring novelty.** Differs: device energy/volume, not VM application-profile maintenance for provisioning. |
| [PolarisProfiler formalization, arXiv:2504.20740](https://doi.org/10.48550/arXiv.2504.20740); [SOSE 2023](https://doi.org/10.1109/SOSE58276.2023.00010) | Metadata-based workload profiling + feedback updates for continuum placement | Alibaba ML / Google cluster style traces | **High collision with “profiling for resource management.”** Differs: a priori metadata → runtime profile groups; not causal trailing-window profile fields with refresh accounting and equal-budget timing falsification. |
| [CNSM 2022 K8s edge autoscaling](https://dl.ifip.org/db/conf/cnsm/cnsm2022/19.pdf) | Application resource profiles for QoS-aware scheduling/autoscaling | Kubernetes edge clusters | **High collision with profile→system direction (C).** Differs: control-oriented resource/QoS models, not offline causal fidelity of class/p95 maintenance. |
| [IBM Resource Profile Advisor, SoCC’18](https://doi.org/10.1145/3267809.3275448) | Rolling-window container CPU/memory profiles to advise K8s requests | IBM Watson production containers | **High collision with rolling observation profiles and rightsizing.** Differs: request refinement / stationarity, not scheduled profile *refresh policies* under forward 24h verification. |
| [uPredict, arXiv:1908.04491](https://ar5iv.labs.arxiv.org/html/1908.04491) | User-level profiler for VM performance under multi-tenancy; notes periodic re-profiling as future work | Private OpenStack + public clouds | **Partial overlap** on re-profiling need. Differs: contention/latency prediction, not Materna-style utilization class/p95 profiles. |
| [Workload Intelligence, arXiv:2404.19143](https://ar5iv.labs.arxiv.org/html/2404.19143) | Workload↔platform hint exchange for cloud optimizations | Large-scale cloud provider optimizations | **Low direct overlap** with profile refresh; frames characterization for efficiency features. |
| [FederatedCloudSim / Materna traces](https://doi.org/10.1145/2676662.2676674) | SLA-aware federation simulation; released Materna VM traces | Simulation + German CSP traces | **Trace provenance overlap only.** Differs: federation scheduling, not application-profile maintenance evaluation. |
| [Vitali et al., VM profiling methodology](https://vitali.faculty.polimi.it/wp-content/papercite-data/pdf/p29.pdf) | Build application profiles from monitoring for QoS | Monitoring-driven profiling | **Partial overlap** on profile construction from monitoring. Differs: methodology for QoS analysis, not causal refresh-policy experiment design. |
| Industry rightsizing (e.g. AWS EKS guidance, Datadog) | p95-based request sizing, VPA recommendations | Kubernetes production practice | **Collision with “use trailing utilization percentiles.”** Differs: operational runbooks, not journal-grade causal refresh-policy evidence. |

**Gap that remains comparatively open:** a *falsifiable, causal, equal-budget,
refresh-accounted* evaluation of application-profile *maintenance policies*
(including published negative results on predictors/adaptive triggers), with
explicit profile age and phase-balanced reads—especially on Materna-like
five-minute VM utilization. Adaptive monitoring and rightsizing are crowded;
“yet another ADWIN/RF refresh policy” is not a gap.

## 4. Candidate directions A / B / C

### A — Cost-aware periodic profile maintenance

| Dimension | Assessment |
|---|---|
| Research question | Can application-specific refresh cadence be selected under an explicit fidelity-versus-maintenance-cost objective? |
| Novelty risk | **High.** Adaptive monitoring (AdaMC/AdaM), rightsizing/VPA, and rolling-window advisors already occupy cost–freshness territory. |
| Current support | §2 shows Static≪PW≪Full-Rewrite cost structure and small PW marginal gains—plausible *motivation*, not a selector result. |
| Missing experiments | Predeclared utility/cost model; held-out confirmation; multi-corpus; no post-hoc margin from pilot deltas. |
| Google/Alibaba | Needed if claiming generality of cadence economics. |
| K8s | Optional for A as offline contribution; required if cost includes actuation. |
| New algorithm necessary? | **Not yet evidenced.** A fixed PW cadence already captures most available fidelity. |
| Journal strength | Weak as a standalone algorithmic claim; stronger only as a secondary empirical subplot under B. |

### B — Empirical / methodological study

| Dimension | Assessment |
|---|---|
| Research question | What does a causal, refresh-accounted, equal-budget benchmark show about application-profile maintenance—including negative findings on forecasting and adaptive refresh? |
| Novelty risk | **Moderate.** Profiling papers exist, but few publish the combination of temporal protocol, profile age, accounting, matched budgets, and *negative* adaptive/predictor results. |
| Current support | **Strongest.** Phases 1–2C + V2 + V2.4D–F already produced the artifact stack and negative dispositions. |
| Missing experiments | Locked contribution statement; multi-corpus replication of the *benchmark behavior* (not of a dead algorithm); optional expanded non-adaptive trade-off reporting; no requirement to resurrect C1/C2. |
| Google/Alibaba | **Yes** for a selective venue if claiming external validity of findings/methodology. |
| K8s | Not required for a pure empirical/method paper; strengthens a systems venue if added later as C. |
| New algorithm necessary? | **No.** |
| Journal strength | **Best current fit** for a selective software/cloud systems or empirical methods venue, provided claims stay evidence-limited. |

### C — Profile-to-system framework

| Dimension | Assessment |
|---|---|
| Research question | Do maintained profiles improve provisioning/placement/SLA/efficiency under a real controller loop? |
| Novelty risk | **High competition** (K8s autoscaling, profile-based edge control), but still room if profiles are simple PW and the *system effect* is the claim. |
| Current support | **Weak.** C4/C5/C6 remain unproven; no harness deployed. |
| Missing experiments | Full V7/V8-style system validation; frozen SLO/resource margins; fair baselines. |
| Google/Alibaba | Helpful for offline profile inputs; insufficient alone. |
| K8s | **Required.** |
| New algorithm necessary? | **No** for the profile module (PW suffices on current evidence). |
| Journal strength | Potentially high *if* system effects clear; currently blocked by missing work, not by scope logic. |

## 5. Final disposition and rationale

### `EMPIRICAL/SYSTEM STUDY VIABLE`

**Rationale.** Forecasting and adaptive-refresh superiority are withdrawn. The
non-adaptive audit shows a real fidelity–cost structure but not a ready novel
cadence algorithm. The project’s distinctive, already-built asset is a
validation-hardened causal evaluation stack plus honest negative results. That
supports an empirical/methodological contribution (B), optionally extended later
toward system validation (C) without restoring withdrawn C1/C2. Direction A may
appear only as a secondary descriptive trade-off, not as a rescue of DynAPM’s
original adaptive narrative.

This disposition preserves scientific honesty over brand preservation.

### GO / NO-GO criteria (next authorization only)

**GO to the next gate** only if all hold:

1. Written contribution statement excludes C1/C2 superiority and any new trigger
   search.
2. Primary claim family is methodological/empirical (benchmark protocol +
   negative findings + non-adaptive trade-off characterization), optionally with
   a deferred system-effect appendix.
3. Practical margins and confirmatory families are chosen from engineering
   requirements, **not** from pilot effect magnitudes.
4. The 18 development VMs remain excluded from primary independent confirmation.
5. Any multi-corpus work follows the existing dataset-suitability ranking without
   outcome-driven corpus shopping.

**NO-GO** (remain blocked / pivot) if any hold:

1. Stakeholders require a novel adaptive or forecasting algorithm as the main
   claim without new positive equal-budget evidence (none exists).
2. Venue pressure expands claims to continuum/SLA benefits without system
   experiments.
3. Confirmatory design would reintroduce PP/V3 superiority comparisons as if
   C1/C2 were live.

### Recommended next gate

**V2.5 — Empirical contribution freeze** (replaces the blocked adaptive-era
confirmatory freeze):

- Freeze the evidence-limited contribution statement and claim ledger (C1/C2
  withdrawn; C3–C6 optional/deferred).
- Freeze the non-adaptive reporting matrix (Static / PW-3h / PW-6h / PW-12h /
  Full-Rewrite diagnostics; no new mechanisms).
- Freeze multi-corpus replication plan (Google 2019 first) for *benchmark
  external validity*, not algorithm rescue.
- Explicitly defer K8s system validation to a later gate unless C is selected as
  co-primary (would require separate authorization and resources).

Do **not** implement a cadence selector, new detector, or full confirmatory run
in this gate.

## 6. Unresolved risks

- Empirical/method papers can be rejected as “engineering without a system
  effect” if C4 remains absent—mitigate by honest claim narrowing or funding C.
- Multi-corpus continuity/licence/cost gates remain open (dataset audit).
- Small PW marginal gains may be judged insufficient even as descriptive
  trade-off evidence once practical margins are frozen.
- Name “DynAPM” still encodes adaptivity; publication branding may need
  decoupling from withdrawn claims.

## Integrity

- No confirmatory (1,558-VM) outcomes accessed.
- Class/MAE/refresh/write figures reconcile to the corrected pilot; bias/age
  from the documented reconstruction.
- Literature entries use primary DOI/URL identifiers listed above.
- Lightweight suite not required for this docs/analysis gate beyond the
  reconstruction script’s successful clean run (wall ~419 s, 90/90 diagnostic
  evaluations).
