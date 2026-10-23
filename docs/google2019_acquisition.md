# V4B / V4B.2 — Google ClusterData 2019 Acquisition & Canonical Preprocessing

**Disposition: `ZERO_COST_BOUNDED_SUBSET_REQUIRED`**  
**Blocker:** `frozen_queries_exceed_zero_cost_guards_unpartitioned_full_scans`  
**Billing:** `billingEnabled=false` (zero-spend / sandbox) on the configured quota project  
**No Google rows acquired; no Static/PW/Full-Rewrite outcomes; no paid resources created.**

V4B froze outcome-blind rules. V4B.1 added the budget-safe runner. V4B.2 verified
billing disabled, dry-ran frozen queries 01–05, and **refused all execution**
because processed bytes exceed the immutable 10 GiB guard (and 02/03 also exceed
the 900 GiB cumulative free-tier headroom). V4A remains PASS. Population /
normalization / entity semantics are unchanged.

## Frozen identities

| Item | Identity |
|---|---|
| V4A protocol | `4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226` |
| Acquisition config fingerprint | `7ca95beaba84f4af9583a1592e38f6a684147bcfbf11bbb4e4bd7ab6c826b91d` |
| Config JSON SHA-256 | `0c76dee14c6a646a670c2c83f76fdf38c7559e68ca0423823611142e9ab87ba9` |
| Config YAML SHA-256 | `2fe648f924fb8c0329c979939e761401dfc6d092ac54e58e85a8988cb7bce1cc` |
| Config | `configs/google2019_acquisition_v1.{json,yaml}` |

## Official tables and fields

Official public project: `google.com:google-cluster-data`; datasets
`clusterdata_2019_a` … `_h`, location US.

| Table | Fields used |
|---|---|
| `instance_usage` | `start_time`, `end_time`, `collection_id`, `instance_index`, `collection_type`, `average_usage.cpus`, `average_usage.memory` |
| `instance_events` | `time`, `collection_id`, `instance_index`, `collection_type`, `resource_request.cpus`, `resource_request.memory` |

## Zero-cost / billing gate (V4B.2)

| Check | Result |
|---|---|
| ADC | present |
| `google-cloud-bigquery` | present |
| `gcloud` / `bq` | present |
| Quota project | resolved from ADC / `--billing-project` (not committed) |
| `billingEnabled` | **false** (re-checked before dry-runs) |
| Billing account linked | none |
| Paid trial / reservations / paid storage | not created |
| Local V4 execution ledger | 0 executed bytes |

Hard controls:

- dry-run before every query class;
- record `total_bytes_processed`;
- enforce `maximum_bytes_billed` = **10 GiB** (not raised);
- cumulative executed-byte ledger cap = **900 GiB** / month for V4;
- prior monthly free-tier usage treated as **unverified** → conservative;
- if `billingEnabled==true` → stop with `BILLING_ENABLED_ZERO_SPEND_NOT_GUARANTEED`.

Time filters are **not** a cost guarantee: tables are unpartitioned on
`start_time`, so `[7d,15d)` still full-scans cell tables.

## Dry-run results (queries unchanged in selection semantics)

SQL files 02–05 received a BigQuery-compatible rewrite of the unambiguous-request
CTE only (`COUNT(DISTINCT …)` moved off `ANY_VALUE` aliases). Selection rules,
filters, strata, and ALLOC_SET population are unchanged.

| Query | File SHA-256 (prefix) | Dry-run bytes | GiB | Guard 10 GiB | 900 GiB headroom | Decision |
|---|---|---:|---:|---|---|---|
| `01_schema_probe.sql` | `3bc2d8fffd058c3369f9cd8bb731416d1cf401f04ef395ab49e55fa314d5bcfc` | n/a | n/a | n/a | n/a | **REFUSE** (`INFORMATION_SCHEMA` Forbidden) |
| `02_bounded_population.sql` | `9005356694a919420cdb43faae774ef44b6c772c2b40031909cfcfcf57d3df0f` | 981,313,230,072 | 913.92 | no | no | **REFUSE** |
| `03_bounded_validation_extract.sql` | `0e0486af4aee26eba292a6c9ea75e163c75c9eed2a021c13a5dc4cbf8b2f0eb3` | 981,313,230,072 | 913.92 | no | no | **REFUSE** |
| `04_full_cell_population.sql` (cell `a`) | `1fb83d4a8952d574315aa829c59563d30a45e3578eecbca19c61b202c73da26b` | 506,658,530,736 | 471.86 | no | yes | **REFUSE** |
| `05_full_cell_extract.sql` (cell `a`) | `0d42c95070a6da023c1ff7f624417932f20cc1a7d2d93563a3cce61615e77cd0` | 506,658,530,736 | 471.86 | no | yes | **REFUSE** |

Cumulative **executed** free-tier usage for V4: **0 bytes**.

## Bounded extract

**Not executed.** Planned cells `a`,`b`, days `[7,15)`, frozen strata unchanged.
Rows/entities/duration from Google: none.

## Projected full-acquisition volume (estimate only; not executed)

| Projection | Bytes | GiB | TiB |
|---|---:|---:|---:|
| Full-cell extract dry-run (cell `a`) | 506,658,530,736 | 471.86 | 0.461 |
| Eight cells if similar to `a` | 4,053,268,245,888 | 3,774.90 | 3.686 |

Far above free-tier / 900 GiB headroom. Storage for canonical Parquet is not
measured (no extract). Do **not** run full export under zero-cost policy.

## Why `ZERO_COST_BOUNDED_SUBSET_REQUIRED`

Scientific population rules remain valid. The blocker is **scan engineering**:
unpartitioned public tables make even the frozen “bounded” validation SQL scan
~914 GiB. Next step (separate task) must redesign a deterministic,
outcome-blind byte-reduction path (e.g. staged entity-key discovery that still
obeys ALLOC_SET / continuity / request rules) **without** raising guards,
enabling billing, or selecting on PW performance.

## Frozen outcome-blind population rules

| Rule | Freeze |
|---|---|
| Cells | all `a`–`h`; bounded validation uses `a`,`b` |
| Entity | `(cell, collection_id, instance_index)` |
| Population | `collection_type=1` (`ALLOC_SET`) only |
| Lifetime | ≥7 days; ≥2,000 aligned 300s slots |
| Selection | metadata / continuity / request only |
| Forbidden | method outcomes, fidelity, Materna-effect similarity |

## Normalization (unchanged)

```text
cpu_utilization    = average_usage.cpus   / request_cpu
memory_utilization = average_usage.memory / request_memory
```

Latest unambiguous positive request with `event.time <= usage.start_time`.
Utilization >1 preserved. No interpolation.

## Canonical artifacts

Managed (gitignored) dry-run provenance:
`data/google2019/provenance_dry_run_v4b2/`. No canonical extract directory was
written. Secrets/tokens/billing IDs are never committed.
