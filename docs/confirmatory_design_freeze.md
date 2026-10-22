# V2.5 — Empirical Contribution Freeze

**Gate status: BLOCKED**  
**Blocker: `practical_effect_margins_unassigned`**  
**V3 status: remains BLOCKED until V2.5 PASS**

This freeze locks the non-adaptive confirmatory study design before any access to
outcomes from the 1,558 confirmatory Materna VMs. No scientific run was executed
in this task. C1 (forecasting superiority) and C2 (adaptive-refresh superiority)
remain permanently withdrawn. No new predictor, trigger, selector, cadence, or
algorithm was introduced.

Machine-readable twins:

| Artifact | Path |
|---|---|
| Design config (JSON, authoritative) | [`configs/materna_confirmatory_v1.json`](../configs/materna_confirmatory_v1.json) |
| Design config (YAML twin) | [`configs/materna_confirmatory_v1.yaml`](../configs/materna_confirmatory_v1.yaml) |
| Candidate cohort manifest | [`configs/materna_confirmatory_cohort_v1.json`](../configs/materna_confirmatory_cohort_v1.json) |
| Loader / validators | [`dynapm/experiments/confirmatory_design.py`](../dynapm/experiments/confirmatory_design.py) |

## Frozen hashes (prove V3 used this freeze)

Compute with `python -c "from dynapm.experiments.confirmatory_design import frozen_hashes; import json; print(json.dumps(frozen_hashes(), indent=2))"`.

| Input | SHA-256 / fingerprint |
|---|---|
| Design fingerprint (`fingerprint(design)`) | `d3c94bcdcf9cb626d915187ca8d5071c26197464ad6154e3f527f1f4d79bac26` |
| `configs/materna_confirmatory_v1.json` | `4ce8fb3a68005717a0a4062ea535d647b3e6a8cf75bc61bda3404cd682131caa` |
| `configs/materna_confirmatory_v1.yaml` | `4a27b96b71a9ad7c14cef1ca3cb2255461edc1b9f42a5361c09f8cf5828e7e5d` |
| Cohort entities fingerprint | `3a590437f108493b085f1cb34765e76bd5f10fa233a48c2e96f6bf3bd54b7939` |
| `configs/materna_confirmatory_cohort_v1.json` | `9adac57a35af69bf83ce5ee0751818ec242d04138d983d95f3441d0c278e02cd` |
| `dynapm/data/kept_vms.json` | `40b70dc8035c37bfacf4438a9b9e3ae86c455ab43cd5bbdb0cafc83394ab18d3` |

If any of these change, this freeze is no longer the executed specification.

---

## 1. Study scope (frozen RQs)

| ID | Question |
|---|---|
| **RQ1** | Does periodic observation-window profile maintenance materially improve profile fidelity over Static? |
| **RQ2** | How do 12h, 6h, and 3h periodic refresh cadences trade profile fidelity against maintenance cost? |
| **RQ3** | Does Full-Rewrite provide practically meaningful fidelity improvement over PW-3h sufficient to justify its much higher refresh/write cost? |
| **RQ4** | Are these conclusions consistent across traces, resources, and predefined volatility strata? |

Do **not** claim adaptive or forecasting novelty. Working contribution: a rigorous
empirical methodology and benchmark for application-profile maintenance, refresh
cadence, freshness, cost, and downstream validity. Repository name `DynAPM` may
remain for continuity; manuscript framing must not imply validated adaptive or
predictive functionality. No manuscript title is chosen here.

Protocol bindings: `causal-timeline-v3`, `phase-balanced-hourly-v1`,
`refresh-accounting-v1`, observation window `(t-24h,t]` with ≥200/288 paired
finite CPU+memory slots where refresh eligibility applies
(`paired-observation-window-24h-v1`).

---

## 2. Confirmatory cohort (frozen)

| Quantity | Value |
|---|---|
| Materna retained pool | 1,576 VMs (`dynapm/data/kept_vms.json`) |
| Permanent development/pilot exclusions | 18 VMs (fixed pairs below) |
| Primary confirmatory **candidates** | **1,558** VMs |
| Protocol-validity exclusions | Applied only at V3 execution under rules below |
| 199 gap-audit `potential_eligibility_review` flags | **Diagnostics only** — not automatic exclusions |

### Permanent pilot exclusions (trace, vm_id)

Materna-Trace-1: 143, 213, 374, 64, 76, 96  
Materna-Trace-2: 11, 207, 388, 396, 398, 516  
Materna-Trace-3: 127, 133, 151, 212, 224, 83  

Authoritative ID list: `configs/materna_confirmatory_cohort_v1.json`
(entities fingerprint `3a590437…`).

### Protocol-validity exclusion codes (predefined; performance-blind)

1. `insufficient_bootstrap_history`
2. `insufficient_exact_grid_feature_or_window_validity`
3. `insufficient_globally_verifiable_evaluation_origins`
4. `corrupt_or_nonfinite_source_data`
5. `protocol_invalid_timeline_or_schema`

**Forbidden exclusion bases:** method performance; favorable/unfavorable effect
size; post-hoc use of gap-audit flags without a protocol rule above.

---

## 3. Method matrix (frozen)

Primary methods only:

| Method ID | Role |
|---|---|
| `static` | No maintenance after bootstrap |
| `pw_12h` | Periodic observation-window, 12h |
| `pw_6h` | Periodic observation-window, 6h |
| `pw_3h` | Periodic observation-window, 3h |
| `full_rewrite` | High-cost rewrite extreme |

All share identical observation-window content semantics. **Excluded from primary
confirmation:** Periodic-Predictor, Reactive, DynAPM-V3, BudgetMatched, ADWIN
triggers, and any forecasting or adaptive method.

---

## 4. Endpoints (frozen)

**Primary fidelity (per VM):**

- `cpu_class_correctness`
- `memory_class_correctness`
- `cpu_p95_profile_mae`
- `memory_p95_profile_mae`

**Primary maintenance cost:** `n_refresh_events`

**Secondary cost/diagnostic:** `n_field_writes`, `n_field_value_changes`,
profile-age distribution, refresh eligibility delays, verified evaluation-point
count, bias.

**Statistical unit:** VM. Timestamp-level pseudo-replication is forbidden.

---

## 5. Comparison families (frozen)

| Family | Contrasts (treatment vs control) |
|---|---|
| **F1** Maintenance vs none | PW-12h vs Static; PW-6h vs Static; PW-3h vs Static |
| **F2** Cadence increments | PW-6h vs PW-12h; PW-3h vs PW-6h |
| **F3** High-cost limit | Full-Rewrite vs PW-3h |

No comparisons may be added after seeing confirmatory results.

---

## 6. Practical-effect margins — UNASSIGNED (V2.5 blocker)

| Endpoint | Practical-benefit margin | Acceptable-harm margin | Status |
|---|---|---|---|
| CPU class correctness | **null** | **null** | insufficient without arbitrary choice |
| Memory class correctness | **null** | **null** | insufficient without arbitrary choice |
| CPU p95-profile MAE | **null** | **null** | insufficient without arbitrary choice |
| Memory p95-profile MAE | **null** | **null** | insufficient without arbitrary choice |

### Why margins are not invented

Margins must be justified from metric semantics, measurement/profile resolution,
operational interpretation, and/or external domain rationale — **not** from the
18-VM pilot effect sizes.

- **Class correctness** uses bootstrap percentile gates
  (`idle`/`low`/`medium`/`high`/`burst`). Without a documented consumer that maps
  class misclassification to operational cost, any Δaccuracy (e.g. 0.01 or 0.05)
  is an arbitrary round number.
- **p95-profile MAE** is continuous utilization error. Capacity-headroom figures
  in rightsizing practice concern allocation decisions, not a transferable MAE
  threshold for offline profile fidelity; converting them requires an unstated
  consumer model.

No in-repository engineering SLO, provisioning tolerance, or external standard
supplies non-arbitrary numeric values. Therefore margins remain **null**, this
gate is **BLOCKED**, and V3 must not execute until a separate authorized margin
assignment freezes numbers without confirmatory outcome access and without
pilot-effect calibration.

---

## 7. Statistical plan (frozen)

For every predefined paired comparison:

1. Compute per-VM paired differences (treatment − control).
2. Report median and mean effect.
3. Paired bootstrap **95%** CI; **B = 10,000** repetitions; **seed = 20251022**;
   percentile method for paired mean and median differences.
4. Wilcoxon signed-rank test; `zero_method="wilcox"` (omit zeros); document
   tie handling / effective *n*; if all pairs tie → effect 0, *p* = 1.
5. Effect size: paired median difference; standardized mean difference /
   SD(paired differences); label undefined if SD = 0.
6. Holm multiplicity correction within each family F1, F2, F3 separately
   (familywise α = 0.05).
7. Report both statistical and practical significance. While margins are
   unassigned, practical significance is **NOT_EVALUABLE** and cannot support GO.

Volatility-tier / trace analyses are **secondary robustness** only — not
independent primary confirmation. No subgroup-driven primary claims beyond what
is predefined here (RQ4 descriptive consistency).

---

## 8. Decision logic (frozen templates; margins required for GO)

| ID | Rule |
|---|---|
| R1 | “Better” requires directionally favorable effect **and** practical-margin criterion; p-value alone is insufficient. |
| R2 | Do not recommend an added-cost method when fidelity improvement is practically negligible. |
| R3 | Full-Rewrite is **dominated** if incremental fidelity over PW-3h fails the practical-benefit criterion while refresh cost is materially greater. |
| R4 | Negative/null findings are valid outcomes. |
| R5 | Do not encode expected winners; comparisons stay F1–F3. |
| R6 | While margins are UNASSIGNED, confirmatory GO is impossible; V2.5 BLOCKED; V3 must not run. |

---

## 9. Future gates (Materna confirmation separate from generalization)

| Gate | Scope |
|---|---|
| **V3** | Materna confirmatory non-adaptive study |
| **V4** | Independent production-corpus suitability/acquisition |
| **V5** | Second-corpus replication (prefer Google ClusterData 2019 if suitability remains valid) |
| **V6** | Maintenance-cost/service benchmark |
| **V7** | Kubernetes profile→resource-management harness |
| **V8** | Repeated operational/system validation |
| **V9** | Final claim audit / venue decision |

Do not claim C3–C6 before the corresponding gates pass.

---

## 10. Verification record (this task)

- Confirmatory 1,558-VM **outcome** tables were not accessed (ID manifests only).
- Config/schema validated deterministically via `validate_design` /
  `validate_cohort_manifest`.
- Pilot IDs excluded; exactly **1,558** candidate confirmatory IDs before
  protocol-validity exclusions.
- Method and comparison matrices complete.
- Practical margins deliberately unassigned → **V2.5 = BLOCKED**; **V3 stays blocked**.
