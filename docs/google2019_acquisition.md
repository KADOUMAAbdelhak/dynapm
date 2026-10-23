# V4B — Google ClusterData 2019 Acquisition & Canonical Preprocessing

**Disposition: `ACQUISITION_BLOCKED`**  
**Blocker:** `google_cloud_credentials_billing_project_and_bigquery_client_unavailable`  
**No Google rows acquired; no Static/PW/Full-Rewrite outcomes computed.**

V4B froze and locally validated the acquisition/preprocessing pipeline against
synthetic schema fixtures, but safely stopped before a BigQuery dry-run or
bounded extraction. This is not a dataset-suitability reversal: V4A remains
PASS. Acquisition requires authenticated dry-runs and a billed project.

## Frozen identities

| Item | Identity |
|---|---|
| V4A protocol | `4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226` |
| Acquisition config fingerprint | `ed1743237f24e87944f2e4adb2eab2d49d5544e146aba183aefe279fe243ffea` |
| Config JSON SHA-256 | `4766c9175575a71f81241d021fba5564ccf684cd293d3c1bd93a35a2b9b6d8b1` |
| Config YAML SHA-256 | `5769bbd9bfa9e86adffa665be79508c1d7403941788169966000899e175376f9` |
| Config | `configs/google2019_acquisition_v1.{json,yaml}` |

## Official tables and fields

Official public project: `google.com:google-cluster-data`; datasets
`clusterdata_2019_a` … `_h`, location US.

| Table | Fields used |
|---|---|
| `instance_usage` | `start_time`, `end_time`, `collection_id`, `instance_index`, `collection_type`, `average_usage.cpus`, `average_usage.memory` |
| `instance_events` | `time`, `collection_id`, `instance_index`, `collection_type`, `resource_request.cpus`, `resource_request.memory` |

The official proto defines resource values as normalized/scaled NCUs and RAM;
usage windows are typically 300 seconds and may be shorter at lifetime edges.
Sources: [trace README](https://github.com/google/cluster-data/blob/master/ClusterData2019.md),
[v3 proto](https://github.com/google/cluster-data/blob/master/clusterdata_trace_format_v3.proto),
[CC-BY-4.0 licence](https://github.com/google/cluster-data#license).

## Access and budget guard

Local inspection found:

- no `bq`, `gcloud`, or `gsutil`;
- no `google-cloud-bigquery` Python package;
- no Application Default Credentials;
- no billing project environment setting.

The guarded dry-run command stopped with exit 2 and the blocker above. It did
not contact BigQuery or execute SQL.

Official on-demand pricing at freeze time is $6.25/TiB processed, with the first
1 TiB/month/account listed as free. Remaining free allowance is unknown and is
never assumed. Every new query class requires:

1. authenticated BigQuery dry-run;
2. recorded processed bytes and pre-free-tier cost;
3. explicit `maximum_bytes_billed`;
4. approval before execution.

Time predicates on `instance_usage`/`instance_events` are **not** a cost
guarantee: those tables are not documented as partitioned on `start_time`, so a
`[7d,15d)` filter may still scan a full cell table. Dry-run bytes, not the SQL
window, determine billed cost.

Because dry-run access was unavailable:

| Query class | Dry-run bytes | Cost estimate | Executed |
|---|---:|---:|---|
| Schema probe | unavailable | unavailable | no |
| Bounded population | unavailable | unavailable | no |
| Bounded validation extract | unavailable | unavailable | no |
| Full-cell population | unavailable | unavailable | no |
| Full-cell extract | unavailable | unavailable | no |

No query-specific byte/cost estimate is fabricated from the documented
~2.4 TiB compressed corpus size.

## Frozen outcome-blind population rules

| Rule | Freeze |
|---|---|
| Cells | all `a`–`h`; bounded validation uses `a`,`b` |
| Entity | `(cell, collection_id, instance_index)` |
| Population | `collection_type=1` (`ALLOC_SET`) only |
| Rationale | avoid parent task + alloc instance double counting |
| Lifetime | at least seven trace-relative days |
| Valid aligned observations | at least 2,000 nominal buckets |
| Selection inputs | metadata, continuity, request availability only |
| Forbidden | method outcomes, fidelity, Materna-effect similarity |

Bounded validation is frozen for trace days `[7,15)`: up to two deterministic
`FARM_FINGERPRINT`-ranked entities per
`(cell, has_request_change, has_missing_slot)` stratum. This intentionally
exercises request changes and gaps without outcome selection.

## Normalization and request semantics

For each usage window:

```text
cpu_utilization    = average_usage.cpus   / request_cpu
memory_utilization = average_usage.memory / request_memory
```

`request_cpu` and `request_memory` are from the latest unambiguous positive
`instance_events.resource_request` with `event.time <= usage.start_time`.

- Zero/missing requests make that row ineligible.
- Request changes are causally realigned per usage window.
- Conflicting request pairs at the same entity/event timestamp are excluded.
- Utilization above 1 is preserved; it is **not clipped**.
- Units are request-relative NCU/RAM ratios, not Materna capacity percentages.

## Cadence, duplicates, and missingness

- nominal bucket: `floor(start_time / 300s) * 300s`;
- positive windows up to 300s retained (short lifetime edges are observed data);
- duplicate entity/bucket: greatest `end_time`, then smallest source-row SHA-256;
- missing buckets remain absent—no interpolation, forward-fill, or upsampling;
- usage must be finite and nonnegative; requests finite and positive.

The local synthetic validation exercised 2,017 slots (seven days), a request
change, over-request utilization (>1), a duplicate, invalid/future requests,
and a missing nominal slot. These are **pipeline fixtures**, not Google outcome
data.

## Canonical format and manifests

`write_canonical_artifacts` immutably writes:

- `canonical_usage.parquet`;
- `entity_manifest.parquet`;
- `rejected_rows.parquet`;
- `manifest.json`.

Canonical columns include cell/entity key, trace-relative `timestamp_us`,
normalized CPU/memory, raw normalized usage/request audit fields, causal request
event time, source table IDs, and source-row SHA-256. Manifests record
repository-relative query path/hash, extraction time, row/entity/cell counts,
file hashes, preprocessing fingerprint, and exclusion reasons. Existing output
directories are never overwritten.

## Reproducible SQL

| Query | SHA-256 |
|---|---|
| `01_schema_probe.sql` | `3bc2d8fffd058c3369f9cd8bb731416d1cf401f04ef395ab49e55fa314d5bcfc` |
| `02_bounded_population.sql` | `a6eddc6b7b6f7808c96f1834c5fc4c24b412c0c707159c693a4e4cb0e7b2f516` |
| `03_bounded_validation_extract.sql` | `5619a565996527bf519a618b9485f39a006bb418e8bbd6b40f7fdabd388aa8fa` |
| `04_full_cell_population.sql` | `d3ec8ced459fb22b6342551c7b5d504e6fb0a9a7049b3e3cd1d211be8b5ed3d9` |
| `05_full_cell_extract.sql` | `206bf9161750b4d28046a27a1fd980180b1c8b7d8d36b8b08fba33106661c674` |

These hashes are embedded in the acquisition config. Any SQL change invalidates
the config and tests.

## Bounded extract result

| Item | Actual |
|---|---|
| Cells | none acquired (planned `a`,`b`) |
| Entities | 0 |
| Rows | 0 |
| Duration | none |
| Missingness/continuity findings | none from Google data |
| Request-change findings | none from Google data |

The bounded extraction requirement therefore did **not** pass. A full export
was not estimated or attempted.

## Resolution required

1. Install `google-cloud-bigquery` (or official `bq` CLI).
2. Supply an authenticated ADC identity and billed project with BigQuery API.
3. Dry-run all five query classes and record bytes/costs.
4. Execute bounded cells `a`,`b` only if each query is under an approved cap.
5. Validate bounded canonical manifests and continuity.
6. Estimate full-cell acquisition; only then choose full vs deterministic subset.

Until these steps pass, V5 replication remains blocked.
