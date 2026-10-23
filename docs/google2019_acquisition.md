# Google ClusterData 2019 Acquisition (V4B → V4B.3)

**V4B.3 disposition: `READY_FOR_ZERO_COST_ACQUISITION`**  
**Chosen cells (outcome-blind cost ranking): `e`, `g`**  
**Projected cumulative query bytes: 825.671983 GiB (headroom 74.328017 GiB under 900 GiB)**  
**Executed query-processing bytes this gate: 0**  
**Billing: `billingEnabled=false` throughout; no paid resources created.**  
**No DynAPM/PW/Static/Full-Rewrite outcomes.**

V4A protocol fingerprint remains
`4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226`.
Entity/ALLOC_SET/300s/request-normalization semantics are unchanged. Cell
*scope* is narrowed solely by free-tier cost constraints.

## Frozen plan identities

| Item | Identity |
|---|---|
| Plan | `configs/google2019_zero_cost_plan_v1.{json,yaml}` |
| Plan fingerprint | `f9f4bb846adfe9a303eb3d63f2efba84f7aa233ae4b990eb0b292cb30d76cfba` |
| Plan JSON SHA-256 | `e547c3b7046c2f7f14d99dc8e06af16a929967a03f3f15b31d071591a1d15342` |
| Plan YAML SHA-256 | `e7496a3fe78403ea3cb00f0dc8d35dbfa04742c6d3ed23afd9177416c83f9f9b` |
| Cost matrix | `configs/google2019_v4b3_cost_matrix.json` |
| Metadata summary | `configs/google2019_v4b3_table_metadata_summary.json` |
| `20_usage_minimal.sql` | `3e6a250381cd0105508813813970873c72cd9dd144c5a74b9032aae55aa226b7` |
| `21_events_minimal.sql` | `a70068b5ffea8f0bad285cdcd26b8e49dbc3a4b13cdbf8cf3a61ec2dc12de077` |

## Table metadata (free `get_table`)

All cells `a`–`h`, tables `instance_usage` / `instance_events`:

- **Partitioning:** none
- **Clustering:** none
- **Logical size (examples):** cell `a` usage ≈ 2.10 TiB / 7.58e9 rows; events ≈ 0.39 TiB / 1.72e9 rows
- Smallest usage+events minimal-column pair: cell **`e`** (~406.60 GiB)
- Largest: cell **`c`** (~587.80 GiB)

`INFORMATION_SCHEMA` probes remain **Forbidden** for this public project. Schema
and previews use free `get_table` + `tabledata.list` / `list_rows` only.

Representative leaf fields confirmed via preview: `average_usage.cpus|memory`,
`resource_request.cpus|memory`. Never select whole nested structs or `SELECT *`
(cell `a` `SELECT *` usage dry-run ≈ 2104.71 GiB vs leaf CPU+memory projection
≈ 395.09 GiB).

## Projection cost matrix (dry-run only)

Per cell, minimal required columns (`collection_type=1`):

| Cell | Usage ID+CPU+Mem (GiB) | Events ID+req CPU+Mem (GiB) | Pair sum (GiB) |
|---|---:|---:|---:|
| e | 338.493 | 68.103 | **406.596** |
| g | 350.719 | 68.357 | **419.076** |
| h | 372.040 | 54.073 | 426.112 |
| b | 378.268 | 63.789 | 442.057 |
| f | 401.994 | 52.715 | 454.709 |
| a | 395.093 | 76.769 | 471.863 |
| d | 414.313 | 94.873 | 509.186 |
| c | 435.222 | 152.580 | 587.803 |

Tracked machine-readable matrix: `configs/google2019_v4b3_cost_matrix.json`.

## Plan alternatives (cell `e` evidence)

| Plan | Dry-run GiB | Verdict |
|---|---:|---|
| Separate minimal usage + events | 338.493 + 68.103 = **406.596** | **cheapest valid** |
| Single joined query (same leaf columns) | 406.596 | equal bytes; worse for local streaming |
| Usage with `[7d,15d)` time filter | 338.493 | **identical** — no scan reduction |
| Two-stage identity then full usage | 241.780 + 338.493 | redundant full-table re-read |
| Frozen pair `a`+`b` separate minimal | **913.919** | **exceeds 900 GiB cap** |

`TABLESAMPLE` is forbidden for the scientific corpus (non-deterministic blocks).

## Chosen zero-cost replication subset

**Rule (outcome-blind):** rank cells by ascending minimal pair dry-run bytes;
take the longest prefix with sum ≤ 900 GiB.

**Result:** `e`, then `g` (825.671983 GiB). Frozen `a`,`b` cannot fit safely.

Entity eligibility rules are **not** relaxed to save cost.

## Future execution plan (not executed in V4B.3)

Order (local streamed artifacts; no BigQuery destination tables):

1. `21_events_minimal` cell `e` — expect 68.103194 GiB — guard = exact dry-run bytes
2. `20_usage_minimal` cell `e` — expect 338.492611 GiB — guard = exact dry-run bytes
3. `21_events_minimal` cell `g` — expect 68.357208 GiB — guard = exact dry-run bytes
4. `20_usage_minimal` cell `g` — expect 350.718970 GiB — guard = exact dry-run bytes

| Metric | Value |
|---|---|
| Worst-case cumulative | 825.671983 GiB |
| Cap | 900 GiB |
| Headroom | 74.328017 GiB |
| Per-query `maximum_bytes_billed` | may exceed legacy 10 GiB **only** under billing-disabled + these frozen dry-runs + cumulative ≤900 GiB |

Local post-processing: causal request alignment, `usage/request` normalization
(no clip >1), 300s cadence, duplicate/missingness rules from V4B; manifests with
query/job IDs, bytes, hashes.

**Failure rules:** re-dry-run immediately before each execution; abort if billing
enabled, if dry-run bytes differ from frozen expectation by >1%, if projected
cumulative >900 GiB, or if any query exceeds its frozen guard. Do not raise
guards to force a run.

## Historical notes

- V4B/V4B.1/V4B.2: access bootstrap; joined bounded SQL refused at ~914 GiB.
- V4B.3 replaces that path with minimal-column separate scans and cell subset
  `{e,g}`. Legacy SQL under `queries/google2019/0*.sql` remains for provenance
  but is **not** the zero-cost execution plan.
