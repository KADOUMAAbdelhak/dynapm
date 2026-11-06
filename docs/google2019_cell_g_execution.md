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
