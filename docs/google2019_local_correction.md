# V4B.8 — local cell-e request ambiguity correction

Raw cell-e acquisition is VERIFIED. The old `data/google2019/canonical/e/`
generation remains byte-preserved and is invalid for scientific replication
because same-time conflicting request pairs were not excluded. Corrected
canonicalization is VERIFIED. V4C.1 validated the e availability contract
([clock contract](google2019_clock_contract.md)); V4C awaits g and final cohort
validation. No Google replication outcomes have been run. Dated execution
details below retain the V4B.8 handoff state.

## Frozen semantics

Positive finite CPU/memory request events are grouped by entity and timestamp.
Identical request pairs collapse; timestamps with more than one distinct pair
are excluded entirely. Usage aligns to the latest earlier-or-equal remaining
request. An earlier valid request may apply; rows must not simply be deleted
because the previous pipeline selected a conflict. There is no interpolation,
future request use, utilization clipping, new eligibility threshold or query.

## Producer and generation

`python -m dynapm.experiments.google2019_local_canonical --workers 4` requires
clean committed source, the exact verified local raw hashes/row counts and a
20-GiB reserve after a conservative peak-disk estimate. It has no cloud-client
entry point. Four workers operate on 256 entity-contained local partitions.
The frozen canonical-JSON row SHA and max-end/min-SHA duplicate tie-break are
unchanged. Canonical outputs additionally retain exact source start/end times.

A new immutable generation lives under
`data/google2019/canonical/generations/cell-e-unambiguous-v2-<identity>/`.
Its identity binds producer commit, raw parents, algorithm/schema and physical
partition configuration. The manifest records raw/part/job lineage, environment,
request ambiguity and exclusion diagnostics, cohort/entity/dataset hashes and
independent full-row verification. SUCCESS is written only after validation.
`require_corrected_generation()` rejects legacy schemas, incomplete or tampered
outputs. A separate `canonical/registry.json` marks the old generation invalid
and identifies the verified new generation; the old files are not edited.

Progress status is refreshed every minute (exceeding the required 30-minute
cadence), including stage, rows, percent, throughput, ETA, free disk and errors.
Current `monitor/status.json` is replaced; historical logs are not rewritten.
A new generation-specific progress log is retained.

## Validation and boundaries

All raw usage rows reconcile to canonical + reason-coded rejections. Independent
NumPy ASOF verification checks every canonical row, positivity, exact ratios,
request non-ambiguity/causality, bucket/source-window alignment, uniqueness and
entity eligibility. Sampled edge rows reproduce frozen source JSON hashes.
Eligibility remains >=2,000 observed slots AND >=7-day span; this is acquisition
eligibility, not a frozen V4C replication cohort. Raw/part/legacy canonical hashes
and the existing query ledger are checked unchanged before/after execution.

No V3 rerun, Google method outcomes, new BigQuery queries or billing changes.
After a valid corrected generation, the next gate is **V4C — Google corpus/cohort
protocol validation**. Cell g remains deferred; normalization validity is not
cross-corpus evidence or replication authorization.

## Verified execution — 2026-10-27

Producer source: `5a223f9cc32fa2cb55d0a9f90603f0b5a93e5206` (clean throughout regeneration).
Generation: `cell-e-unambiguous-v2-85c74588191efa0b`. Schema: `google2019-canonical-generation-v2`;
normalization: `google2019-unambiguous-local-canonical-v2`.

[Tracked correction record](../configs/google2019_v4b8_correction_record.json) and [independent audit](../configs/google2019_v4b8_validation_evidence.json) contain exact counts/hashes. Generated files remain ignored under the generation path; the previous `canonical/e/` files remain byte-identical.

| Quantity | Old generation | Corrected generation |
|---|---:|---:|
| Canonical rows | 502,046,052 | 462,821,691 |
| Entities | 157,333 | 157,259 |
| Acquisition-eligible entities | 63,167 | 62,451 |
| Duplicate-bucket rejections | 1,017,576 | 1,012,660 |
| Entities with >1 request pair | 50,778 | 41,256 |
| CPU utilization >1 rows | 9,791,603 | 6,488,637 |
| Memory utilization >1 rows | 8,645,033 | 1,252,541 |

All 513,023,210 raw usage rows reconcile to 462,821,691 canonical rows plus 50,201,519 rejections: 49,188,859 missing usable requests and 1,012,660 duplicate buckets. The old rejected-row artifact contained duplicate buckets only, so its count is not comparable to the new comprehensive rejection count.

The event audit collapsed 120,725 identical copies. All 26,002 conflicting entity/timestamp groups (52,352 distinct request tuples) are absent from the 2,523,458-entry usable request history. Independent old-generation scanning found 39,224,379 selected-conflict rows, affecting 26,002 entities and 25,718 old eligible entities.

The corrected ASOF procedure evaluated earlier-valid fallback rather than deleting old rows. In these actual inputs all 26,002 conflicting timestamps have no earlier usable request: 39,229,277 raw rows encounter such conflicts, 0 recover an earlier request, and 39,229,277 have none. Canonical fallback rows/entities are zero. Synthetic regressions demonstrate successful fallback where earlier history exists. After later valid requests, 25,928 conflict-affected entities remain represented and 25,002 remain eligible. Exactly 74 entities disappear and 716 lose eligibility; none gain eligibility.

All 462,821,691 corrected rows passed independent latest-request, ambiguity exclusion, causality, exact-ratio, finite-value, bucket/duration and entity-eligibility verification; 7,667 edge/sample rows reproduced the frozen generic JSON source hash. No ambiguous request was selected.

Cadence audit: 462,664,432 consecutive within-entity intervals; 99.97138358% exactly 5 minutes, 0.02861642% >5 minutes, 0.00191348% >10 minutes, 0.00022716% >30 minutes, 0.00014762% >1 hour. There are 55,751 entities with gaps, 1,080,772 missing nominal slots, and a maximum gap of 1,903,800 seconds. No interpolation or clipping. This is acquisition metadata, not outcome evidence or a finalized replication cohort.

### Pinned identities

| Artifact | SHA-256 |
|---|---|
| Raw events | `7e70a9bea2763b3ffd4676ca16595726cfbbcf3f07527811b150ba34526c0e2e` |
| Merged raw usage | `5f3fa7120ee5587e87cc42be0d6ecb732de8f8e2c0f7cb6f564551263a4e3fe0` |
| Generation manifest | `0bbf63c3a99a92d0d10124b44b531c2d0b1bac6ab5ec4de6104527a847e3c1c3` |
| Canonical dataset partition manifest | `06ec0ce8a599890bc98f5c2adb1bfb01c3858c83b6d0630a1f0a29335b77fdaf` |
| Entity manifest | `33654157136e4c5da303e6b36f4241be471de8f57aa529e5b03cba8b3332a289` |
| Acquisition cohort | `6ce8a5b219133245657ca0a412ab36f264212aea5caa1e18bb8ab450d60e2fce` |

The canonical dataset SHA is SHA-256 over the ordered canonical-part metadata (paths, sizes, row counts and per-file hashes), rather than a monolithic Parquet hash. The generation manifest pins every output artifact and records part/job lineage. Parent raw files, the download part, historical manifests/checkpoints, the old canonical files and scan ledger were rehashed unchanged after regeneration.

Wall time through manifest generation: 3290.5 seconds. Full lightweight suite: **388 passed, 0 failed, 1 skipped**; targeted canonicalization/streaming tests: **18 passed**. Python parsing/imports and CLI help passed. Two existing tests were isolated from the workstation's nonzero historical ledger; no budget guard or ledger value was changed. Legacy-generation rejection and output-tampering tests passed.

Current monitor/final registry point to the corrected VERIFIED generation. Historical logs and V4B.7 recovery records remain untouched. Query bytes for V4B.8: **0**; no cloud client/billing operation, V3 rerun or Google replication outcome. The existing ledger remains 800,032,593,872 bytes (745.088415 GiB); cell g remains deferred. **V4C is NEXT; V5 remains blocked until V4C PASS.**
