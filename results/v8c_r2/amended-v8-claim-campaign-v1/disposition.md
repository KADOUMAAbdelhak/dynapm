# Amended V8 claim campaign: disposition (HALTED_AT_SLOT_5)

Campaign root: `claim-campaign/` (identity 2e20a93d…, executor 4c1326c, spec f5d78b95…,
qualification b57c08ab…, boot UUID 6C470F9C-9B15-4093-87C3-DDE6D713D7E6, strict AC).
Launched 2026-11-19T15:57:46Z on the user's explicit "Start all 18". Executor exited
with returncode 1 at 22:08:34Z: `invalid_treatment_requires_review`.

| Slot | Cell | Status | Requests reconciled |
|---|---|---|---|
| 1 | static / periodic | SEALED_VALID | 34,200 / 34,200, 0 missing, 0 duplicate |
| 2 | pw_12h / periodic | SEALED_VALID | 34,200 / 34,200, 0 missing, 0 duplicate |
| 3 | pw_3h / periodic | SEALED_VALID | 34,200 / 34,200, 0 missing, 0 duplicate |
| 4 | static / abrupt_regime_shift | SEALED_VALID | 43,200 / 43,200, 0 missing, 0 duplicate |
| 5 | pw_3h / abrupt_regime_shift | SEALED_INVALID | n/a (HARNESS_MEASUREMENT_FAILURE) |
| 6-18 | | PENDING | not run |

## Slot 5 failure

`telemetry_failed: observer_storage_buffer_or_budget, slot_storage_buffer_or_budget_exhausted`.
Host free space fell below the unchanged in-slot 22 GiB floor (23.62 GB) about 18 min
into the measured window (T0 21:48:33Z). Free space at slot start was 28.38 GB
(requirement 27.41 GB, PASS). It fell to 25.87 GB during cooldown/warm-up (Docker
growth, as in slots 1-4), drifted to 25.41 GB, then dropped 1.54 GB within 5 s at
22:06:33Z, reaching 23.87 GB on the last recorded poll before the guard raised.
No pod restarts. The power guard recorded NO_FAILURE. Boot UUID unchanged.
Docker.raw grew from about 7.35 to 9.4 GB over the campaign.

This is an operational storage-guard trip, not a treatment outcome. Slot 5 gives
no endpoint and must not be analysed or imputed. No paired analysis exists
(finish_claim_analysis runs only after slot 18).

## Consequence

`next_slot` refuses to continue past a SEALED_INVALID slot
(`interrupted_or_invalid_slot_requires_replacement_review`), and this executor
has no approved replacement protocol. The campaign cannot be resumed without a
separately reviewed amendment, or a fresh campaign root on a host with enough
storage headroom. Slots 1-4 stay as sealed evidence. They are not a claim on
their own, and must not be pooled with any other campaign without a pre-stated
rule.

## Post-mortem export (non-evidence)

By design the cluster was preserved (`node_copy_preserved: true`) because the
raw request copy had not been taken. The orphaned generator ran to completion.
Its node directory was exported, with a hash check, to `slot-05-postmortem-node-export/`
for forensics only. The sealed attempt directory was not modified.
