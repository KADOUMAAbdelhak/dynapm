# Google ClusterData 2019 Acquisition (V4B → V4B.8)

**Current raw cell-e acquisition: VERIFIED. Old canonical: SUPERSEDED/invalid for scientific replication. V4B.8 local correction: VERIFIED; V4C metadata audit completed; BLOCKED by the aggregate-availability contract ([audit](google2019_protocol_validation.md)).** See [local correction](google2019_local_correction.md). Historical records below remain unchanged.

**V4B.7 disposition: `CELL_E_ACQUIRED`** (cell `g` deferred this month)  
**Recovery:** Storage Read of temporary query results (anonymous table; free per BQ pricing)  
**Google-side cumulative (incl. failed V4B.6 usage scan + retry): 745.088 GiB / 900 GiB**  
**Cell `g` not queried** — remaining ~154.9 GiB insufficient for the frozen `g` pair (~419 GiB)  
**Billing: `billingEnabled=false`; no GCS / permanent destination tables**  
**No DynAPM/PW outcomes.**

Record: `configs/google2019_v4b7_recovery_record.json`

---

## V4B.5 (historical) — streaming plan freeze

**V4B.5 disposition: `READY_FOR_STREAMING_ACQUISITION`**  
**Note:** `g_fraction_uncertain_runtime_disk_guard_required` (conservative g band)  
**Cells / SQL / V4A semantics: unchanged (`e`,`g`; minimal templates)**  
**Query-scan projection: 825.67 GiB ≤ 900 GiB cap (unchanged)**  
**Executed query bytes this gate: 0**  
**Billing: `billingEnabled=false`; no GCS / BQ destination tables / paid services**  
**No DynAPM/PW outcomes.**

V4A protocol fingerprint remains
`4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226`.

## V4B.5 — corrected local storage + streaming plan

### Old vs corrected storage logic

| | V4B.4 (wrong) | V4B.5 (corrected) |
|---|---|---|
| Local size proxy | BigQuery **bytes processed** | Output **row count × schema × Parquet/zstd** |
| e+g “required” | ~990.8 GiB (1.2× scan) | Peak **~40.6 GiB** point / **~96.2 GiB** conservative |
| Usable disk (~105 free − 20 reserve) | ~85 GiB | ~85 GiB |
| Fits point peak? | no (wrong metric) | **yes** |
| Fits conservative peak? | n/a | **no** → runtime guard before `g` |

Bytes processed measure columnar **scan** cost, not result payload. Unpartitioned
filters do not shrink scan bytes, but they do shrink returned ALLOC_SET rows.

Estimation inputs: free `get_table` row counts, stratified `list_rows`
`collection_type` fractions, local synthetic Parquet/zstd calibration
(200k rows) × 1.5 safety on bytes/row. No large calibration queries.

### Streaming architecture (per cell; e then g)

1. Acquire `instance_events` → chunked zstd Parquet  
2. Build local request-history index  
3. Stream `instance_usage` pages; causal join + normalize incrementally  
4. Write **canonical** chunked Parquet (retains usage+request audit fields)  
5. Do **not** keep a full uncompressed raw usage copy  
6. Validate cell `e` before starting `g`  
7. Never hold both cells’ raw streams simultaneously  

Preferred transport: paginated query results / Arrow batches → local Parquet.
No destination tables; no GCS export. Storage Read API not enabled in this
freeze (only if later verified zero-cost for temporary results).

### Peak disk (planning)

| Stage | Point GiB | Conservative GiB |
|---|---:|---:|
| Cell `e` streaming peak | 4.48 | 11.99 |
| Cell `g` streaming peak | 38.93 | 94.01 |
| During `g` with `e` canonical retained | **40.58** | **96.20** |
| Both canonical retained | 28.98 | 82.61 |

With ~105 GiB free and **20 GiB** reserve (~85 usable): cell `e` authorized;
`e`+`g` point peak authorized; conservative `g` band requires abort/external
volume if realized. Disk guard refuses before exhaustion; checkpoints allow
resume without rescanning completed queries.

### Retained audit fields (canonical)

`cell`, `collection_id`, `instance_index`, `timestamp_us`, utilizations,
`average_*`, `request_*`, `request_event_time_us`, source tables,
`source_row_sha256` — enough to recompute `usage/request` offline. Plus job
ID, SQL SHA, query bytes, row counts, exclusions, artifact hashes.

### Frozen streaming identities

| Item | Identity |
|---|---|
| Streaming plan | `configs/google2019_streaming_plan_v1.{json,yaml}` |
| Plan fingerprint | `10fdebfe5a2acc004ae0f70c3c84509f52a14f4c34b3e627498dc96d8c5d6688` |
| Storage estimate | `configs/google2019_v4b5_storage_estimate.json` |
| Module | `dynapm/experiments/google2019_streaming.py` |

## V4B.4 preflight (historical; superseded metric)

V4B.4 correctly verified billing/SQL/dry-runs but refused on an invalid local-size
proxy (~990 GiB). Records retained under `configs/google2019_v4b4_*`. Streaming
redesign replaces that disk gate; cells/SQL unchanged.

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
