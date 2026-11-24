# Amended V8 claim campaign v2: disposition (COMPLETE_18_OF_18_SEALED_VALID)

Campaign root: `claim-campaign/` (scope AMENDED_V8_PRIMARY, strict AC, boot UUID
26051F76-7B84-4CBD-A25D-1418E39980A2 throughout, power policy unchanged). Checkpoint
revision 40, sha256 fbc3914bfc3217ccbc61598eb71eb81972eb4f4c5436a71faf03c8015b70c1cd. `verify_checkpoint` passes and `next_slot` is None.

Executor history (one sealed identity transition, executor-only, under the approved
slot replacement amendment v3, `docs/primary_slot_replacement_amendment.md`):

- slots 1–8 and the replaced slot 9 attempt: executor 738139b, Step B qualification 8a87c578…
- slots 9–18: executor ce03b3d, spec v3 89072590…, Step B v3 qualification 72b53e25…
  (evidence commit d865b9c)

Executed in user-sized blocks 1–8 (`block-N-{gate,intent,slots,terminal}`); every gate
passed and every block exited 0.

| Slot | Cell | Status | Ran (UTC) | Requests accepted | Replaced attempts |
|---|---|---|---|---|---|
| 1 | static / periodic / rep 1 | SEALED_VALID | 2026-11-22T21:28Z–22:44Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 2 | pw_12h / periodic / rep 1 | SEALED_VALID | 2026-11-22T22:44Z–00:00Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 3 | pw_3h / periodic / rep 1 | SEALED_VALID | 2026-11-23T00:00Z–01:16Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 4 | static / abrupt_regime_shift / rep 1 | SEALED_VALID | 2026-11-23T01:16Z–02:32Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 5 | pw_3h / abrupt_regime_shift / rep 1 | SEALED_VALID | 2026-11-23T02:33Z–03:48Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 6 | pw_12h / abrupt_regime_shift / rep 1 | SEALED_VALID | 2026-11-23T03:49Z–05:05Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 7 | pw_3h / abrupt_regime_shift / rep 2 | SEALED_VALID | 2026-11-23T05:05Z–06:21Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 8 | pw_12h / abrupt_regime_shift / rep 2 | SEALED_VALID | 2026-11-23T07:00Z–08:16Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 9 | static / abrupt_regime_shift / rep 2 | SEALED_VALID | 2026-11-23T18:23Z–19:39Z | 43200 expected=43200 missing=0 dup=0 | 1 |
| 10 | pw_12h / periodic / rep 2 | SEALED_VALID | 2026-11-23T19:39Z–20:55Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 11 | pw_3h / periodic / rep 2 | SEALED_VALID | 2026-11-23T20:56Z–22:11Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 12 | static / periodic / rep 2 | SEALED_VALID | 2026-11-23T22:12Z–23:28Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 13 | pw_3h / periodic / rep 3 | SEALED_VALID | 2026-11-23T23:28Z–00:44Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 14 | static / periodic / rep 3 | SEALED_VALID | 2026-11-24T00:44Z–02:00Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 15 | pw_12h / periodic / rep 3 | SEALED_VALID | 2026-11-24T05:33Z–06:49Z | 34200 expected=34200 missing=0 dup=0 | 0 |
| 16 | pw_12h / abrupt_regime_shift / rep 3 | SEALED_VALID | 2026-11-24T06:50Z–08:06Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 17 | static / abrupt_regime_shift / rep 3 | SEALED_VALID | 2026-11-24T08:06Z–09:22Z | 43200 expected=43200 missing=0 dup=0 | 0 |
| 18 | pw_3h / abrupt_regime_shift / rep 3 | SEALED_VALID | 2026-11-24T09:22Z–10:38Z | 43200 expected=43200 missing=0 dup=0 | 0 |

All 18 slots: every scheduled request sent and recorded, 0 missing, 0 duplicate.

## Replaced attempt (must be reported in the paper)

One replacement (limits: 1 per slot, 2 per campaign). Slot 9 (static /
abrupt_regime_shift / rep 2, seed 2026110502), attempt
`slot-09-6cefd2f614e14681b594f7ad6b642553`, ran 2026-11-23T08:16:57Z and was sealed
SEALED_INVALID at 09:19:36Z: HARNESS_MEASUREMENT_FAILURE / PowerGuardError
`mains_power_lost` (host unplugged). `metrics: null`, so no outcome was observed.
It stays under `claim-campaign/attempts/` and in the slot's `replaced_attempts`, with
the user's sealed approval `claim-campaign/replacements/slot-09-approval.json`
(sha 50521326…, quote "Approve, start later"). Its cluster state was exported to
`slot-09-retained/` before the cluster was deleted. The checkpoint before the
replacement is kept as `checkpoint-before-replacement.json`.

## Paired analysis

`claim-campaign/paired-analysis.json` (sha f014326a177f5953a125bef2ae2f5756553a39302fdcbaa8ca6056bc2ff2dd44) was written by
`finish_claim_analysis` inside the executor after slot 18. It was independently
recomputed from the 18 sealed manifests and the frozen snapshot bundle and matches
exactly. Unit: physical treatment run; n = 3 pairs per contrast; intervals are
pointwise paired t (df = 2), model-based; practical superiority is NOT_DEFINED; every
contrast is labelled RESOURCE_SLO_TRADEOFF_NO_WINNER. pw_12h vs static is
STRUCTURAL_EQUAL_TARGET (it does not identify a target effect).

This campaign is not pooled with campaign v1 or with old port-forward V8 results.
Nothing has been submitted.
