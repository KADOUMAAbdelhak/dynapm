# November 2026 cell-g acquisition

The cell-g launcher uses the frozen minimal SQL, 900 GiB November cap, existing billing guard, corrected v2 request normalization, and Google v2 clock and selection rules. The historical cell-e launchers and sealed e records remain available.

Run from clean committed `dynapm` source in the repository root. The following invocation is offline and uses no cloud clients.

```sh
.venv/bin/python -m dynapm.scripts.task42_google2019_cell_g \
  --month 2026-11 --ledger data/google2019/v4_byte_ledger_2026-11.json
```

For a separately authorized live acquisition, append `--execute` to that command. Use the same source, Python dependencies, billing-disabled quota project and arguments to resume. Never move or delete the acquisition directory to clear an error.

## Accounting and download

- The launcher validates the pinned October ledger and refuses it as an execution target. It validates the exact initial November ledger or reconciles existing entries to the same g run. The live command holds the existing V8 campaign lock and requires an idle Docker engine. Before each submission it checks current billing and a fresh dry-run, then reserves the frozen per-query maximum against the monthly cap.
- Each query has a deterministic job ID and a durable intent written before submission. An existing intent permits lookup of that exact job. An unresolved job lookup stops the run. Neither download failure nor an uncertain submit can trigger a second execution. Processed and billed bytes are recorded separately as soon as a terminal job reports them. Dry-run bytes remain provenance fields.
- Both results use anonymous temporary tables and Arrow Storage Read. The checkpoint stores the serialized session, result-table identity, expected row count and stream names. Each atomic local chunk binds the stream, offset, footer row count and file hash. Restart resumes from contiguous committed chunks in the same session. An expired or incompatible unfinished session fails closed. Fully committed raw data remains recoverable from local files after expiration.
- Raw chunks are retained directly. Canonicalization partitions the chunk inputs without writing a second merged raw copy. The runtime checks the local reserve as it writes. BigQuery result cardinality and the observed storage peak remain live checks.

## Local phases

The managed root is `data/google2019/execution/v4c2-g-2026-11`. The launcher reconciles raw hashes and row counts before corrected canonicalization. Each completed local phase has a sealed inventory and the preceding phase hash. An interruption can restart unsealed local scratch from its sealed inputs. It never repeats a completed cloud job.

The clock audit uses the shared cell-e code for completed closing labels and admission. Cohort selection uses only g eligibility and the frozen identity hash. The staged inventory binds the existing e input and new g input separately. The final g binding is published for the Stage-B input validator. This command runs no policy outcomes.

## Offline regression

One complete sealed e shard was reconstructed from its canonical winners and rejected raw rows. The shared implementation reproduced all 1,922,553 canonical rows, 174,765 rejection counts and diagnostics, and the entity metadata for 610 entities. The shared clock audit reproduced that shard's sealed availability metadata exactly. All 1,032 sealed canonical e artifacts and the frozen e cohort were verified independently. This is shard-level replay and full-manifest integrity verification.

## Large request histories and source continuation

Raw request events and usage are coalesced in bounded batches, then partitioned by
the same entity key before local processing. All requests for an entity are
processed together. Each shard is audited independently against its unambiguous
request history. An oversized shard fails closed rather than loading the whole
cell. Raw download receipts and chunks remain the source of truth.

If a reviewed correction is committed directly on top of the source used to
journal an existing run, its operator can explicitly pass
`--resume-from-source ORIGINAL_COMMIT`. The launcher records the continuation
source and checks that the original header differs only by source commit. The
original run fingerprint, query IDs and Storage Read session remain bound.
The same continuation flag is required on another resume.

A failed billing check now occurs before the job intent is written. For the
already journaled usage intent in this run, the recovery path additionally
requires the immutable pre-submit traceback and an exact job lookup returning
`NOT_FOUND`. It runs a new dry-run and billing check, writes a one-use recovery
dispatch receipt, and submits only the original job ID. A second unresolved
dispatch fails closed. Each reviewed source continuation preserves the original
run ID and records the immediately preceding source.

## Offline continuation from the disk stop

The continuation launcher is bound to the original 1,444-file partial inventory,
the two sealed downloads and the exact November ledger. Run the command below
for a read-only preflight.

```sh
.venv/bin/python -m dynapm.scripts.task43_google2019_continue_g
```

Add `--execute-local` after verifying at least 40 GiB free. There are no cloud
operations on either path. Shards 0–185 remain in the original partial tree.
Each later shard is written to an isolated attempt, audited and sealed before
its directory is published atomically. The next invocation verifies contiguous
seals and promotes any complete attempt interrupted just before publication.
The command keeps interrupted attempts and uses hard links to assemble the
final generation on the same volume without copying canonical shards.

## Compact rejection evidence

Stage B requires the accepted canonical shards, eligibility metadata and cohort.
The availability audit uses three duplicate-interval counters computed from
rejected rows. It can read those exact counters from the g compact audit. The
full rejected payload is audit-only and regenerable. Request history, conflict
groups and positive-event timing are needed for the independent canonical
validation and are retained. Partition scratch is needed until its shard seals.

The offline compactor checks two complete raw replays before any retirement.
It records the typed, ordered Arrow logical-row hash, full reason counts,
duplicate-interval counters, conflict and entity counts and the accepted-file
hash for every historical shard. The deletion ledger preserves the original
path, byte size, hash and the exact replacement or shard seal. The historical
inventory stays intact and every missing file must reconcile to the ledger.

To regenerate rejected rows for a shard, iterate sealed chunks in receipt
order, project `KEYS + PAIR` for events and `USAGE_COLUMNS` for usage, and keep
rows with `(collection_id * 1000003 + instance_index) % 256` equal to the shard.
Run `prepare_request_history` followed by `canonical_partition(cell='g')`.
Verify the resulting logical hash, reason counts and interval counters against
the compact record. The record pins the raw receipts, producer source,
derivation files, runtime and protocol. This reproduces logical content.

Use the offline plan command to assess capacity.

```sh
.venv/bin/python -m dynapm.scripts.task44_google2019_compact_g
```

To execute, add `--execute-local --proof-log PATH` with the completed raw replay
log for shards 0 and 185. Subsequent invocations use the sealed proof. After the
186 compact audits are independently verified, the launcher checks capacity and
continues at the first unsealed shard. Each remaining scratch shard is retired
only after its canonical and compact rejection outputs seal. All writes keep
the 20 GiB reserve. The canonical files for shards 0–185 are reused by link and
checked against their original hashes.
