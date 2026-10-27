# V4B.8 — local cell-e request ambiguity correction

Raw cell-e acquisition is VERIFIED. The old `data/google2019/canonical/e/`
generation remains byte-preserved and is invalid for scientific replication
because same-time conflicting request pairs were not excluded. Corrected
canonicalization is PENDING execution of the committed local-only producer.

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
