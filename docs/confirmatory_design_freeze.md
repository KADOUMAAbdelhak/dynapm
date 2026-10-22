# V2.5 / V2.5A — Empirical Contribution Freeze (Estimation-First)

**Gate status: PASS (V2.5A amendment)**  
**Blocker: none**  
**V3 status: NEXT — Materna confirmatory estimation study**  
**C4 operational/practical benefit: UNPROVEN (deferred to V7–V8)**

This freeze locks the non-adaptive confirmatory study design before any access to
outcomes from the 1,558 confirmatory Materna VMs. No scientific run was executed
in V2.5 or V2.5A. C1 (forecasting superiority) and C2 (adaptive-refresh
superiority) remain permanently withdrawn. No new predictor, trigger, selector,
cadence, or algorithm was introduced. Numeric practical-effect margins were
**not** invented.

### Amendment V2.5A

The original V2.5 freeze required numeric practical-superiority margins and was
**BLOCKED** when those margins could not be justified without arbitrary choices.
V2.5A resolves that blocker by converting V3 into a **pre-specified estimation
study**: report magnitudes, uncertainty, statistical distinguishability, costs,
and fidelity–cost trade-offs — without profile-level practical-superiority
thresholds.

| Artifact | Path | Role |
|---|---|---|
| Current design (JSON) | [`configs/materna_confirmatory_v1_1.json`](../configs/materna_confirmatory_v1_1.json) | Authoritative V2.5A |
| Current design (YAML) | [`configs/materna_confirmatory_v1_1.yaml`](../configs/materna_confirmatory_v1_1.yaml) | Twin |
| Previous V2.5 freeze (JSON) | [`configs/materna_confirmatory_v1.json`](../configs/materna_confirmatory_v1.json) | Immutable provenance |
| Previous V2.5 freeze (YAML) | [`configs/materna_confirmatory_v1.yaml`](../configs/materna_confirmatory_v1.yaml) | Immutable provenance |
| Candidate cohort | [`configs/materna_confirmatory_cohort_v1.json`](../configs/materna_confirmatory_cohort_v1.json) | Unchanged |
| Loader / validators | [`dynapm/experiments/confirmatory_design.py`](../dynapm/experiments/confirmatory_design.py) | |

## Frozen hashes

Compute with:

```sh
python -c "from dynapm.experiments.confirmatory_design import frozen_hashes; import json; print(json.dumps(frozen_hashes(), indent=2))"
```

### Current (V2.5A / v1.1)

| Input | SHA-256 / fingerprint |
|---|---|
| Design fingerprint | `62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296` |
| `configs/materna_confirmatory_v1_1.json` | `089782667006819d15201562dbf84e337d5d8688c85d535f8b2420f5f14097f7` |
| `configs/materna_confirmatory_v1_1.yaml` | `d03b6dc67896d50c8b22135de25f17b2c0a26f17b3854e74d8761f7a00f3f03c` |

### Preserved previous freeze (V2.5 / v1) — must not change

| Input | SHA-256 / fingerprint |
|---|---|
| Legacy design fingerprint | `d3c94bcdcf9cb626d915187ca8d5071c26197464ad6154e3f527f1f4d79bac26` |
| `configs/materna_confirmatory_v1.json` | `4ce8fb3a68005717a0a4062ea535d647b3e6a8cf75bc61bda3404cd682131caa` |
| `configs/materna_confirmatory_v1.yaml` | `4a27b96b71a9ad7c14cef1ca3cb2255461edc1b9f42a5361c09f8cf5828e7e5d` |

### Cohort (unchanged)

| Input | SHA-256 / fingerprint |
|---|---|
| Cohort entities fingerprint | `3a590437f108493b085f1cb34765e76bd5f10fa233a48c2e96f6bf3bd54b7939` |
| `configs/materna_confirmatory_cohort_v1.json` | `9adac57a35af69bf83ce5ee0751818ec242d04138d983d95f3441d0c278e02cd` |
| `dynapm/data/kept_vms.json` | `40b70dc8035c37bfacf4438a9b9e3ae86c455ab43cd5bbdb0cafc83394ab18d3` |

---

## 1. Study framing and amended RQs

**Framing:** `estimation_first`. V3 estimates effects; it does not declare
profile-level practical superiority.

| ID | Question |
|---|---|
| **RQ1** | What are the magnitude and uncertainty of paired fidelity and cost effects of periodic observation-window maintenance (PW-12h, PW-6h, PW-3h) relative to Static? |
| **RQ2** | What are the magnitude and uncertainty of paired fidelity and cost effects for successive cadence increments (PW-6h vs PW-12h; PW-3h vs PW-6h)? |
| **RQ3** | What is the incremental fidelity effect of Full-Rewrite relative to PW-3h, and what is the associated incremental refresh, write, and change cost? |
| **RQ4** | Are the estimated effects directionally and quantitatively consistent across predefined traces, resources, and volatility strata? |

Do **not** use “materially better” / “practically meaningful improvement” for
profile endpoints unless later operational evidence (C4) supports that language.
Do **not** claim adaptive or forecasting novelty.

Working contribution: a rigorous empirical methodology and benchmark for
application-profile maintenance, refresh cadence, freshness, cost, and
downstream validity. Repository name `DynAPM` may remain for continuity;
manuscript framing must not imply validated adaptive or predictive
functionality.

Protocol bindings: `causal-timeline-v3`, `phase-balanced-hourly-v1`,
`refresh-accounting-v1`, observation window `(t-24h,t]` with ≥200/288 paired
finite CPU+memory slots where refresh eligibility applies
(`paired-observation-window-24h-v1`).

---

## 2. Confirmatory cohort (unchanged)

| Quantity | Value |
|---|---|
| Materna retained pool | 1,576 VMs |
| Permanent pilot exclusions | 18 VMs |
| Primary confirmatory **candidates** | **1,558** VMs |
| 199 gap-audit review flags | Diagnostics only — not automatic exclusions |

Protocol-validity exclusion codes (performance-blind): insufficient bootstrap
history; insufficient exact-grid feature/window validity; insufficient globally
verifiable evaluation origins; corrupt/nonfinite source data; protocol-invalid
timeline/schema.

---

## 3. Method matrix (unchanged)

`static`, `pw_12h`, `pw_6h`, `pw_3h`, `full_rewrite` — shared observation-window
content. Forecasting/adaptive methods excluded from primary confirmation.

---

## 4. Endpoints (unchanged)

Primary fidelity: CPU/memory class correctness; CPU/memory p95-profile MAE.  
Primary cost: `n_refresh_events`.  
Secondary: writes, value changes, age, eligibility delays, verified eval count, bias.  
Unit: VM.

---

## 5. Comparison families (unchanged)

| Family | Contrasts |
|---|---|
| **F1** | PW-12h / PW-6h / PW-3h vs Static |
| **F2** | PW-6h vs PW-12h; PW-3h vs PW-6h |
| **F3** | Full-Rewrite vs PW-3h |

---

## 6. Practical significance disposition

**Status: `NOT_DEFINED_AT_PROFILE_LEVEL`**

Numeric practical-benefit and acceptable-harm margins for the four fidelity
endpoints remain **null** and are **not invented**.

### Why numeric margins are unavailable (methodology / systems rationale)

This section is **not** DynAPM empirical evidence.

1. **Profile error units** are utilization percentages / class fractions on
   offline profiles, not SLO or capacity outcomes.
2. **Operational effect** depends on resource capacity, request/limit mapping,
   controller policy, and SLO definitions.
3. **No validated universal conversion** from profile MAE/class error to
   operational benefit currently exists for this study.
4. **Pilot-derived margins** would be outcome-driven and are forbidden.
5. Therefore **operational meaningfulness** must be calibrated/validated in the
   later system study (C4 / V7–V8), not invented before V3.

### External sources (clearly separated from DynAPM evidence)

| Source | Role |
|---|---|
| Wasserstein & Lazar (2016), ASA Statement on p-Values, *The American Statistician* 70(2), [doi:10.1080/00031305.2016.1154108](https://doi.org/10.1080/00031305.2016.1154108) | Scientific conclusions / decisions must not rest on p-value thresholds alone; motivates estimation reporting (effects + uncertainty) over bright-line practical claims from *p* alone. |
| Kubernetes Horizontal Pod Autoscaling — resource metrics ([docs](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)) | Official controller semantics: utilization is usage relative to configured requests and targets; shows why offline profile-error margins cannot be universal without capacity/request/controller context. |

---

## 7. Inferential / estimation rules (frozen; stats config unchanged)

For every predefined paired comparison, V3 **must** report:

1. Per-VM paired differences (treatment − control).
2. Paired **mean** and **median** effects.
3. Paired bootstrap **95%** CI; **B = 10,000**; **seed = 20251022**; percentile method.
4. Wilcoxon signed-rank; `zero_method="wilcox"`; documented ties / effective *n*; all-ties → effect 0, *p* = 1.
5. Effect sizes (paired median difference; standardized mean / SD of paired diffs).
6. Holm-adjusted *p*-values within each family F1 / F2 / F3 (α = 0.05).
7. Refresh / write / change costs.
8. Pareto / fidelity–cost relationships (dominance label only under R4).

Profile-level practical significance is **`NOT_DEFINED_AT_PROFILE_LEVEL`**.

Volatility-tier / trace analyses remain secondary robustness (RQ4), not
independent primary confirmation.

---

## 8. Decision language (frozen)

| ID | Rule |
|---|---|
| R1 | V3 may establish direction, magnitude, uncertainty, and statistical distinguishability. |
| R2 | Statistical significance alone must never imply practical/operational superiority. |
| R3 | Do not recommend a cadence solely from p-values. |
| R4 | Strict Pareto dominance only when both paired median and mean effects show the dominating method is nowhere worse on all four fidelity endpoints and primary cost, and strictly better on at least one fidelity endpoint or cost; otherwise report the trade-off. |
| R5 | Operational/practical benefit remains **C4**, deferred to system-validation gates. |
| R6 | Negative / null / small effects remain publishable findings. |
| R7 | No expected winners; comparisons stay F1–F3. |
| R8 | No “materially better” wording for profile endpoints without later operational evidence. |

---

## 9. Future gates

| Gate | Scope |
|---|---|
| **V3** | Materna confirmatory **estimation** study (non-adaptive) — **NEXT** |
| **V4** | Independent production-corpus suitability/acquisition |
| **V5** | Second-corpus replication |
| **V6** | Maintenance-cost/service benchmark |
| **V7** | Kubernetes profile→resource-management harness |
| **V8** | Repeated operational/system validation (C4 track) |
| **V9** | Final claim audit / venue decision |

Do not claim C3–C6 before corresponding gates pass.

---

## 10. Unchanged vs changed elements

| Element | V2.5A disposition |
|---|---|
| Cohort / 18 pilots / 1,558 IDs | **Unchanged** |
| Protocol exclusion codes | **Unchanged** |
| Method matrix | **Unchanged** |
| Endpoints | **Unchanged** |
| F1–F3 comparisons | **Unchanged** |
| Bootstrap B/seed, Wilcoxon, Holm | **Unchanged** |
| RQs wording | **Amended** (estimation) |
| Study framing | **Changed** → estimation-first |
| Practical margins / superiority GO | **Superseded** → `NOT_DEFINED_AT_PROFILE_LEVEL` |
| Decision rules | **Amended** (estimation + Pareto + C4 deferral) |
| Gate status | **PASS** |

---

## 11. Verification

- No confirmatory 1,558-VM outcome access (ID manifests only).
- Legacy v1 configs byte-identical to original freeze hashes.
- Cohort fingerprint unchanged; methods/comparisons/stats unchanged.
- Schema/hash tests pass; working tree clean after commit.
