# V4A — Independent Corpus Selection and Protocol-Fit Freeze

**Disposition: `CORPUS READY FOR ACQUISITION`**  
**Preferred corpus: Google ClusterData 2019**  
**V4B acquisition: MAY START** (under the frozen adaptation + acquisition gates below). Later V4B record: **`ACQUISITION_BLOCKED`** on missing BigQuery credentials/billing/client ([acquisition](google2019_acquisition.md)); V4A disposition is unchanged.

Documentation/protocol-fit audit only. No full dataset download. No DynAPM/PW
outcome experiment. No Materna confirmatory redesign. Ranking uses protocol fit,
reproducibility, and independence — **not** expected favorable effects.

Frozen V3 study to replicate: Static / PW-12h / PW-6h / PW-3h / Full-Rewrite;
24h trailing profile; forward `(t,t+24h]` truth; CPU+memory fields; hourly
evaluation; estimation-first; no adaptive/predictive claims.

Machine-readable freeze:
[`configs/google_clusterdata_2019_replication_protocol_v1.json`](../configs/google_clusterdata_2019_replication_protocol_v1.json)

| Hash | Value |
|---|---|
| Protocol fingerprint | `4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226` |
| Config JSON SHA-256 | `01f84cba30966d7cfe0585cf9041bd19d356b7b768b015cadaec977ac6e46e5d` |
| Config YAML SHA-256 | `39ab05e5db33e79f21dff4ad542705e42a3fe32571c24c652324e262126e9ad6` |

---

## Ranked comparison

| Rank | Corpus | Protocol fit (24h+24h, 5m, CPU+mem) | Independence vs Materna | Access / licence | Main threat |
|---|---|---|---|---|---|
| **1** | **Google ClusterData 2019** | Strong: ~month, typical 300s usage windows, both resources | High (Borg cells, different operator) | BigQuery ~2.4 TiB; **CC-BY-4.0** | Cost; entity continuity; normalized≠% |
| 2 | Alibaba Cluster Trace 2018 | Moderate: ~8 days; container CPU/mem **percent** | High (colocation / containers) | Survey + archives ~48–49G gz; licence scope unclear at root | Short span; invalid −1/101; terms |
| 3 | Alibaba 2026 MaaS `instance_week_5min` | Weak for this protocol: **only 7 days** of 5-min series; CPU cores / mem GiB | High (LLM inference / xMaaS) | Direct OSS ZIPs (~15.3 GB compressed listed) | Duration; capacity denominators; GPU-centric |

No clearly stronger joint CPU+memory five-minute production corpus with clearer
fit than Google 2019 was identified in this audit (Azure remains CPU-only for
memory-usage replication; Alibaba GPU 2026 is hourly).

---

## Candidate assessments

### 1. Google ClusterData 2019 (preferred)

| Dimension | Assessment |
|---|---|
| Environment / entity | Eight Borg production cells, May 2019; jobs/tasks/alloc instances |
| CPU + memory | `average_usage.cpus` / `.memory` (normalized NCUs / RAM); requests separate |
| Cadence | Usage windows typically 300s; may shorten at lifetime edges |
| Lifetime / missingness | Must audit continuous spans; incomplete windows; restarts/migrations |
| Duration / scale | One month — supports bootstrap + repeated forward-24h origins |
| Trailing-24h + forward-24h | Feasible for long-lived instances after continuity filter |
| Profile transfer | Request-normalized utilization preserves paired two-resource profile **form**; not Materna provisioned-% |
| Cross-corpus normalization | Declare unit adaptation; do not claim % equivalence |
| Causal bootstrap thresholds | Yes — first 30% of entity timeline |
| Acquisition | BigQuery only; pin SQL, snapshot, export hashes; budget required |
| Licence | CC-BY-4.0 ([repo licence](https://github.com/google/cluster-data#license)) |
| Preprocessing | High: identity joins, dedupe, request join, five-minute binning without imputation |
| Diversity | Strong independent provider / container-managed workloads |
| Threats | Export cost; unknown eligible long-lived count; alloc vs child double-count |

Official sources: [ClusterData2019.md](https://github.com/google/cluster-data/blob/master/ClusterData2019.md),
[clusterdata_trace_format_v3.proto](https://github.com/google/cluster-data/blob/master/clusterdata_trace_format_v3.proto),
[trace doc (Drive)](https://drive.google.com/file/d/10r6cnJ5cJ89fPWCgj7j4LtLBqYN9RiI9/view).

### 2. Alibaba Cluster Trace 2018 (optional backup)

| Dimension | Assessment |
|---|---|
| Environment / entity | ~4,000 machines, 8 days; long-running containers + batch |
| CPU + memory | `cpu_util_percent` / `mem_util_percent` (machine & container); invalid −1/101 |
| Cadence | Relative seconds; fixed 5-min cadence **not** guaranteed by schema alone |
| Duration | Eight days — tight for bootstrap + multi-day evaluation diversity |
| Profile transfer | Percent fields closer to Materna; container denominator still needs care |
| Access / licence | Survey + hashed archives; research use encouraged; standalone LICENSE not confirmed at prior checks |
| Threats | Short horizon; cadence/presence audit; redistribution terms |

Official: [trace_2018.md](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/trace_2018.md),
[schema.txt](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/schema.txt).

### 3. Alibaba 2026 MaaS / `instance_week_5min` (not preferred for V3 protocol)

| Dimension | Assessment |
|---|---|
| Environment / entity | Production LLM inference (xMaaS); instance_id; online/offline |
| CPU + memory | `cpu_usage` (cores), `mem_usage` (GiB); also GPU SM/mem % |
| Cadence | Five-minute averages of 20s samples; window `[time_s, time_s+300)` |
| Duration | **Weekly table only days 140–146** (~7 days); daily table is day-grain for six months |
| Trailing+forward 24h | Marginally possible for some instances, but weak for repeated hourly origins / strata |
| Profile transfer | Absolute cores/GiB need capacity; host capacity not in weekly schema |
| Access | OSS ZIPs: `instance_week_5min.zip` ≈ 4.81e9 bytes; daily ≈ 1.05e10 bytes |
| Threats | Duration; denominators; GPU-centric domain may change operational interpretation of “memory profile” |

Official: [cluster-trace-v2026-maas README](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2026-maas),
[schema.md](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-maas/docs/schema.md),
[data_download.md](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-maas/docs/data_download.md).

### Stronger alternatives checked (rejected for this protocol)

- **Alibaba GPU 2026 (ASI):** hourly facts — cannot establish five-minute dynamics without upsampling (forbidden).
- **Azure 2017/2019:** memory is capacity metadata, not utilization series — cannot support joint CPU+memory V3 endpoints.
- Prior audit notes in [dataset_suitability_audit.md](dataset_suitability_audit.md) remain consistent with this ranking.

---

## Preferred corpus rationale

Google ClusterData 2019 remains the strongest **protocol-fit** match: month-scale
coverage, both CPU and memory usage, five-minute-oriented windows, clear
CC-BY-4.0 licensing, and high independence from Materna VMs. Alibaba 2018 is
closer in percent units but short. MaaS `instance_week_5min` is scientifically
interesting for LLM diversity but fails the duration/capacity bar for a faithful
V3-style 24h+24h estimation replication.

---

## Frozen adaptation specification (Google 2019)

### Inherited unchanged from V3

Methods Static/PW-12h/PW-6h/PW-3h/Full-Rewrite; F1–F3; fidelity + `n_refresh_events`;
estimation-first; `NOT_DEFINED_AT_PROFILE_LEVEL`; causal-timeline-v3 /
phase-balanced-hourly-v1 / refresh-accounting-v1; `(t-24h,t]` with ≥200/288;
forward `(t,t+24h]`; bootstrap fraction 0.30; B=10000 seed=20251022;
Wilcoxon/`wilcox`/Holm; C1/C2 withdrawn.

### Corpus-specific mapping

| Aspect | Freeze |
|---|---|
| Canonical entity | `(cell, collection_id, instance_index)`; prefer long-lived alloc/job instances; avoid parent/child double count |
| Resource fields | `average_usage.cpus`, `average_usage.memory` |
| Units / normalization | Request-normalized utilization when request>0; **not** Materna provisioned-% |
| Nominal cadence | 300s grid; shorter edge windows allowed as observed; **no upsampling** |
| Duplicates / missing | Deterministic dedupe; leave gaps empty; nonfinite → missing |
| Minimum history | ≥200 paired slots for refresh; 96 feature history; ≥2000 obs guidance |
| Bootstrap | First 30% by time; thresholds causal |
| Profile / eval eligibility | Same 24h trailing / forward density rules as V3 |
| Exclusions | Protocol-validity only (+ missing positive request / insufficient continuous span) |

### Changes that do **not** change RQs

Entity type (Borg vs VM), request-normalized NCU/RAM vs Materna %, optional
single-cell export for cost — all declared adaptations; RQs remain magnitude/
uncertainty of maintenance, cadence, Full-Rewrite cost, and robustness.

---

## Unresolved issues (V4B, not V4A blockers for disposition)

1. BigQuery project billing / export budget authorization.
2. Outcome-blind continuity + request-coverage SQL to establish eligible *n*.
3. Pin table snapshot time and export content hashes.
4. Choose initial cell set before entity filtering.
5. Confirm alloc-instance population rules on a metadata sample (no PW outcomes).

Licence for Google 2019 is resolved (CC-BY-4.0). Alibaba 2018 licence/redistribution
and MaaS terms remain unresolved if those corpora are later revived.

---

## Verification

- Official sources cited above (fetched 2026-10-23).
- No Materna confirmatory redesign; V3 design fingerprint only referenced.
- No second-corpus outcome access; no full download in this task.
- Deterministic protocol hashes via `dynapm.experiments.replication_corpus`.
