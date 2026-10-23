# V4B / V4B.1 — Google ClusterData 2019 Acquisition & Canonical Preprocessing

**Disposition: `ACQUISITION_BLOCKED`**  
**Blocker:** `google_cloud_adc_and_billing_project_unavailable`  
**V4B.1:** Python BigQuery client installed; ADC + billing/quota project still required.  
**No Google rows acquired; no Static/PW/Full-Rewrite outcomes computed.**

V4B froze outcome-blind population/normalization/SQL/canonical rules. V4B.1
adds a budget-safe dry-run/execute runner and installs `google-cloud-bigquery` in
the project environment, but **stops before any authenticated query** until you
complete the human auth steps below. V4A remains PASS. Query SQL hashes are
unchanged from V4B.

## Frozen identities

| Item | Identity |
|---|---|
| V4A protocol | `4067689f6147a4eba191ad578c1b061af71c3d50b6342ce88a3d8498fb7b4226` |
| Acquisition config fingerprint | `8a850d8c5318c7cf029d8940d74e3c29a80b7b494c8332e5bfc37e66a087867c` |
| Config JSON SHA-256 | `d91cc92103410753f0893393f037671b69c8339048fc9d605829ade90ac337a2` |
| Config YAML SHA-256 | `446f495852ad61f11cc99e3ca9017e0a7380685ce61c707485b565136046f9e0` |
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

## Access and budget guard (V4B.1)

Local inspection after V4B.1 tooling:

| Check | Status |
|---|---|
| `google-cloud-bigquery` in `.venv` | present |
| `bq` / `gcloud` CLI | absent |
| Application Default Credentials | **absent** |
| Billing / quota project | **absent** (not fabricated) |

Dry-run and bounded execution are refused. No BigQuery API call was made.

Optional dependency file: `requirements-google2019.txt`.  
Managed extracts/provenance (gitignored): `data/google2019/`.  
Secrets, tokens, service-account keys, and billing IDs are never committed.

Official on-demand pricing at freeze time is $6.25/TiB processed, with the first
1 TiB/month/account listed as free. Remaining free allowance is unknown and is
never assumed. Default `maximum_bytes_billed` guard is **10 GiB** (cap, not an
estimate). Every new query class requires:

1. authenticated BigQuery dry-run;
2. recorded processed bytes and pre-free-tier cost;
3. explicit `maximum_bytes_billed`;
4. refusal when dry-run bytes exceed the guard;
5. approval before execution.

Time predicates on `instance_usage`/`instance_events` are **not** a cost
guarantee: those tables are not documented as partitioned on `start_time`, so a
`[7d,15d)` filter may still scan a full cell table. Dry-run bytes, not the SQL
window, determine billed cost.

| Query class | Dry-run bytes | Cost estimate | Fits 10 GiB guard | Executed |
|---|---:|---:|---|---|
| Schema probe (`01`) | unavailable | unavailable | n/a | no |
| Bounded population (`02`) | unavailable | unavailable | n/a | no |
| Bounded validation extract (`03`) | unavailable | unavailable | n/a | no |
| Full-cell population (`04`, cell `a`) | unavailable | unavailable | n/a | no |
| Full-cell extract (`05`, cell `a`) | unavailable | unavailable | n/a | no |

No query-specific byte/cost estimate is fabricated from the documented
~2.4 TiB compressed corpus size. Full acquisition cost/storage remains unknown.

## Exact human actions required (do these, then re-run V4B.1)

Replace `YOUR_BILLING_PROJECT` with your real billed GCP project ID. Do not invent one.

```bash
# 1) SDK (once) for ADC login
brew install --cask google-cloud-sdk

# 2) Create/select a billed project; enable BigQuery API in Console
#    https://console.cloud.google.com/projectcreate
#    https://console.cloud.google.com/apis/library/bigquery.googleapis.com

# 3) Application Default Credentials
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_BILLING_PROJECT
export GOOGLE_CLOUD_PROJECT=YOUR_BILLING_PROJECT

# 4) Client (already installed in this workspace; re-run if needed)
.venv/bin/pip install -r requirements-google2019.txt

# 5) Verify (exits 0 only when ADC + billing project are usable)
.venv/bin/python -m dynapm.scripts.task28_google2019_acquisition \
  --access-check --billing-project YOUR_BILLING_PROJECT

# 6) Dry-run frozen queries 01–05 (no execution)
.venv/bin/python -m dynapm.scripts.task28_google2019_acquisition \
  --dry-run-all --billing-project YOUR_BILLING_PROJECT

# 7) Only if 01–03 fit the 10 GiB guard: bounded extract (cells a,b; days [7,15))
.venv/bin/python -m dynapm.scripts.task28_google2019_acquisition \
  --execute-bounded --billing-project YOUR_BILLING_PROJECT
```

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

`write_canonical_artifacts` immutably writes under a managed directory:

- `canonical_usage.parquet`;
- `entity_manifest.parquet`;
- `rejected_rows.parquet`;
- `manifest.json` (query/job/config hashes, continuity summary, file SHA-256).

CLI also records dry-run/execution provenance JSON under
`data/google2019/` (gitignored). Scientific identity paths remain
repository-relative only.

## Reproducible SQL (unchanged from V4B)

| Query | SHA-256 |
|---|---|
| `01_schema_probe.sql` | `3bc2d8fffd058c3369f9cd8bb731416d1cf401f04ef395ab49e55fa314d5bcfc` |
| `02_bounded_population.sql` | `a6eddc6b7b6f7808c96f1834c5fc4c24b412c0c707159c693a4e4cb0e7b2f516` |
| `03_bounded_validation_extract.sql` | `5619a565996527bf519a618b9485f39a006bb418e8bbd6b40f7fdabd388aa8fa` |
| `04_full_cell_population.sql` | `d3ec8ced459fb22b6342551c7b5d504e6fb0a9a7049b3e3cd1d211be8b5ed3d9` |
| `05_full_cell_extract.sql` | `206bf9161750b4d28046a27a1fd980180b1c8b7d8d36b8b08fba33106661c674` |

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

## Full-acquisition disposition

`ACQUISITION_BLOCKED` — awaiting ADC + explicit billing project, then real
dry-run bytes for queries 01–05 before any bounded execute or full-export
decision (`READY_FOR_FULL_ACQUISITION` / `BOUNDED_SUBSET_REQUIRED`).
