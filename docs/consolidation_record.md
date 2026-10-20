# DynAPM consolidation record

Date: 2026-10-20. Scientific implementation baseline: `b70d4eee0cdb20226b8f63590984bc2fcd6db20c`. This consolidation changes governance documentation only. It starts no Phase 2C implementation or scientific experiment.

## Authority and immutable history

The sole authoritative active repository for current code, experiments and development is `/Users/fgtek002/dynapm`, branch `dynapm`.

Historical TOCS evidence is stored only as a preservation archive, not an alternate development project:

- Archive: `/Users/fgtek002/Archives/dynapm/DynAPM-TOCS-2026-0109-baseline-20261020.tar.zst`.
- SHA-256 sidecar: the archive filename followed by `.sha256`.
- SHA-256: `2cc1c59f40b12e9b3a80fb6eb9ddd86a943f477ca081dc6a5f6a6c720a5d8c7c`.
- Size: 771,537,495 bytes; original payload: 2,608,151,009 bytes.
- Compression: tar + zstd; no format/filename deviation.
- Both archive and sidecar are mode `0444` and have the macOS user-immutable (`uchg`) flag. This prevents ordinary accidental writes; an owner can deliberately unlock them. Hash verification remains the content-integrity authority, not a claim of WORM storage.

The verified expanded checkpoint `/Users/fgtek002/DynAPM-canonical-checkpoint-20261020` was removed only after independent archive recovery passed. The frozen original publication directory `/Users/fgtek002/Downloads/DynAPM__Drift_Aware_Profile_Maintenance` remains untouched as explicitly required; it is publication reference material, not an active implementation.

The archived A area is an older implementation snapshot, not today's source baseline. B is frozen publication material; C contains historical non-causal measurements; D explains provenance and pre-cleanup state. None is a runtime dependency. Do not restore them over active code, treat archived measurements as causal output, or configure automatic archive fallbacks. Manual forensic recovery must use a separate temporary destination and an explicit provenance task.

## Verification performed before deletion

Available space before archiving: 134,441,082,880 bytes (about 125.2 GiB), sufficient for creation and independent full extraction.

1. Ran the checkpoint's own sealed integrity verifier: all manifest and SHA256SUMS entries passed; 22,364 files and all 18,955 scientific allowlist entries verified.
2. Created one archive containing the complete checkpoint contents, including all four A/B/C/D areas, root manifest, sums and restore/provenance instructions.
3. Listed all 22,423 archive entries. All 22,364 file entries were regular files with safe relative paths; no `.git`, symlink, hardlink or external reference was present.
4. Independently extracted the entire archive into temporary storage and reran the checkpoint verifier against those recovered bytes, rather than reading the original checkpoint.
5. Parsed representative A source; read B manuscript/CSV files; read C historical evaluation/event JSON and residual/ground-truth Parquets; read D provenance JSON. Read the canonical tier summary (9,456 rows), provisioning records (382,932 rows), and normalized historical refresh records (3,152 rows). These are format/integrity checks, not new scientific analysis or causal validation.
6. Confirmed canonical counts: 9,456 method/VM JSONs, 3,152 residuals, 1,576 ground-truth files, 3,152 event-log JSONs, plus the complete scientific allowlist. Read all three canonical CSVs (6, 12 and 18 rows respectively).
7. Verified all 29 original publication files against the frozen directory manifest; none was changed. Removed the temporary recovery tree.
8. Rehashed the archive, set read-only/immutable flags, then deleted only the authorized expanded checkpoint and verified its absence.

| Canonical item | Verified SHA-256 |
|---|---|
| Manuscript | `ab6da73f883be765da4301a7d26d751fdf7c2495967b5e4c736703c1fb9cc32c` |
| Table 1 CSV | `b180dccab99b12cb1cc5ff61142c814abd41883f75c20753ce849600f9ceaa51` |
| Table 2 CSV | `984b086fc2c2fc36791e5c5fc96a011902cf79e8306cd64eb5db0e6b242bcc5e` |
| Table 3 CSV | `798afef51da8bc7df99f7c7beb8bf3417dc4374d682680aa84cad687f0e3dfad` |

For later manual verification, run `shasum -a 256 -c` on the sidecar from the archive's directory, list with `zstd -dc ARCHIVE | tar -tf -`, and recover to a new temporary directory. The contained `D-provenance/verify_checkpoint.py` performs standard-library checksum/count validation there. Parquet reads need compatible pandas/pyarrow. Historical paths inside archived provenance identify original sources; they are not recovery dependencies.

## Duplicate-project search

Searched readable user project roots, Desktop, Documents, Downloads, the TimeTrack research directory, and managed Codex worktrees. Excluded Library, application/package/browser caches, environments, node_modules, Git object stores, raw-data traversal, archives and temporary system directories. The search traversed 2,971 nonexcluded directories and identified 25 Git roots, plus a separate managed-worktree check.

Only `/Users/fgtek002/dynapm` matched the DynAPM/old-repository Git identity. Only its existing `dynapm` package matched the implementation signature (`core`, `methods`, `eval`, `dynapm_v3.py`). No other DynAPM checkout or managed worktree was found. The old repository path does not exist. Unrelated user projects were not deleted or changed.

Two protected macOS Photos/Photo Booth library directories could not be read; they are outside the sensible project/research search scope. The result is a scoped search finding, not a filesystem-wide assertion about inaccessible media or excluded caches.

## Previous-rejection evidence search

**Exact previous rejection decision letter not found locally.**

Searched research/project locations using FGCS, TimeTrack, old_fgcs_rejected, decision, reviewer and rejection filename/content patterns. No editor/reviewer letter was identified in the readable search scope. The following were inspected and must not be represented as reviewer correspondence:

- `/Users/fgtek002/TimeTrack/old_fgcs_rejected/ARCHIVE_MANIFEST.md`: internal archive record identifying the rejected FGCS / Computer Networks study.
- `/Users/fgtek002/TimeTrack/old_fgcs_rejected/docs/CONTRIBUTION_SELECTION_DECISION.md`: internal development-gate contribution decision.
- `/Users/fgtek002/TimeTrack/old_fgcs_rejected/fgcs/FINAL_MANUSCRIPT_REVIEW.md`: internal manuscript readiness review.

Plausible downloaded submission/dataset/research PDF candidates were inspected for decision wording; none was a decision letter. No quotations or reconstructed reviewer statements are used. The four lessons about future lead, resource sharing, machine sharing and machine-specific benefit in the strategy are human-confirmed historical project lessons, not verbatim reviewer comments.

The eleven TOCS requirements in [the strategy](validation_strategy.md#14-reviewer-concern-traceability) are likewise explicitly labeled human-confirmed paraphrases supplied for this task. Concerns 1-9 remain open. Phases 1/2A/2B establish correctness for concerns 10-11, not scientific/system benefit.

## Validation and scope

Complete lightweight suite: 123 passed, 0 failed, 0 skipped. All 53 Python files parse/compile and 38 non-test modules import. Governance checks cover required strategy sections/gates, claim/concern coverage and local documentation links. Scientific source/config/test bytes are unchanged from the baseline. No corpus evaluation, interval sweep, provisioning replay, model training experiment, Kubernetes deployment, historical result rewrite or manuscript drafting was performed.

V1B / Phase 2C is **NEXT**, not started. Documentation is a contract; its presence does not establish C1-C6.

## Historical-path occurrence classification

All matches of the four requested search patterns are classified below. No tracked Python/runtime/configuration file matches. This table gives every matching line in the reviewed documentation; the table itself adds no searched path literals.

| File | Matching lines | Classification |
|---|---|---|
| `README.md` | 40 | Documentation-only authority/provenance/search evidence; no runtime dependency |
| `docs/consolidation_record.md` | 7, 11, 18, 48, 58, 59, 60 | Documentation-only authority/provenance/search evidence; no runtime dependency |
| `docs/development.md` | 58 | Documentation-only authority/provenance/search evidence; no runtime dependency |
