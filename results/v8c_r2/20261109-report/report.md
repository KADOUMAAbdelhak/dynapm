# V8C-R.2 executor implementation and non-qualifying diagnostic findings

**PRIMARY_SERVICE_EXECUTOR_BLOCKED.** The executor is implemented and offline-tested,
but no complete successful physical qualification exists on the fixed harness.
No claim treatment or integration run was launched. The battery diagnostic remains
non-claim and non-qualifying; its failed treatment was not relabelled or repeated.

## Source and implementation

- Frozen scientific source: `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`.
- Qualified Service transport: `b3fd0d1fa095dbaa13c2b035624d6336b24d60ca`; lineage `e32d192`; evidence `2246b49`.
- Physical battery diagnostic source: `a41c986d7e9ea6c34b91292002436c35d7995b93`.
- Fixed executor source: `67bfd37ee72e0096e4dfec974fd145f7a347e6e0`.
- Commits: `340c615` checkpoints; `ee7950d` primary executor; `3786483` canonical image resolution; `8a2500b` explicit battery-only mode; `a41c986` terminal lifecycle capture; `67bfd37` readiness classification and bounded-final-analysis fixes.
- Scientific contract, reference bundle/snapshots, V8B ref and 125 Service-qualification evidence files verify unchanged. Strict AC preflight AST and approved power/UUID/clock files are unchanged.

The new executor reuses the pinned stack, qualified generator request semantics,
frozen plans, recommendation consumer, physical actuation/watchdog logic, receipt
clock validation, bucket aggregation, endpoint arithmetic and paired analysis.
Application traffic is exclusively generator Pod → Kubernetes Service → application
Pod. No forwarding process was observed. Canonical Docker aliases resolve the same
pinned image IDs; no image was rebuilt or pulled.

## Actual execution and failure

All dates below use Europe/Helsinki.

| Item | Actual result |
| --- | --- |
| Launcher start | 2026-11-09T10:37:25.110578+02:00 |
| Controller exit | 2026-11-09T11:33:33.647789+02:00 |
| Cooldown | 900.006328 physical seconds |
| Reference warm-up offers | 21,600, exact frozen 30-minute schedule |
| T0 snapshot/target | Bound before offers; 70m CPU / 64MiB reservation; fixed 1024MiB limit |
| T0 observation bracket | 1.004506 seconds; causal source marker/host receipt, no epoch conversion |
| Physical actuation | ENFORCED in 0.466126 seconds |
| Exposure controller coverage | Two valid 300-second buckets; four remaining buckets unvalidated |
| Validated coverage | Both buckets have 60 samples and approximately 295-second host-receipt spans |
| Failure | `allocation_unverifiable` at the 600-second check |
| Original state | SEALED_INVALID; full-window composite endpoint undefined/censored |
| Generator horizon | 1800.068295 source-monotonic seconds after T0 |
| Recovery | Full sealed generator stream recovered and independently hash-verified before owned cluster cleanup |

The failed frame had every independent resource gate true: requested and allocated
70m/64MiB, correct spec/status/generation/container, CPU quota `7000 100000`,
memory cap `1073741824`, and no resize pending. Only Pod readiness was false.
Kubernetes recorded a timed-out `/healthz` readiness probe. This is an application
availability outcome; the verifier incorrectly treated it as failed resource
enforcement. The fixed additive verifier records readiness separately, retains
all resource gates, and leaves probe configuration, Service behaviour, resource
points, requests, failures and endpoint denominators unchanged. It neither raises
the resource floor nor discards bad application outcomes. Frozen source files
were not modified. The fix was made before any amended comparative outcome.

The original controller stopped recording the remaining resource window. A
separate forensic observer did not resume the treatment, issue patches or create
requests. It preserved the existing generator's data and later failed closed on
`lid_closed_or_unobservable`. Its evidence is separate, with an observed gap of
341.884 seconds from the original guard. It cannot
fill or qualify the failed primary window.

## Request reconciliation — forensic non-qualifying records only

| Terminal class | All offers | Measured-exposure offers |
| --- | ---: | ---: |
| Scheduled offers | 34,200 | 12,600 |
| Sent attempts | 29,183 | 7,583 |
| Success | 24,354 | 2,754 |
| Unsent concurrency-cap drop | 5,017 | 5,017 |
| Connection deadline | 2,642 | 2,642 |
| Response deadline | 1,326 | 1,326 |
| Connection refusal | 861 | 861 |
| HTTP/application response error | 0 | 0 |
| Other transport exception | 0 | 0 |
| Missing / duplicate records | 0 / 0 | 0 / 0 |

All 21,600 warm-up offers succeeded. These counts are recovered client observations,
not valid treatment-level comparative endpoints. No partial resource endpoint was
extrapolated and no old port-forward data was mixed. Raw record SHA-256:
`a15a858eb003469d7b80919ab8d7710a4ea22378ae7be36c676ac045314659a7`.

## Host, storage and preservation

- Original battery guard: no continuity failure; max wall/monotonic discrepancy 85.719 ms; max checkpoint gap 5.324 s; owned idle assertion released.
- Battery: 89% initially, 77% at controller stop, 73% at last forensic checkpoint. Discharge/source details remain in raw continuity logs.
- Later forensic guard: lid closed or unobservable; released its owned assertion. No claim of continuous full-window host validity is made.
- Free disk before / lowest sampled / after: 26.990 / 23.871 / 27.251 GiB.
- Peak sampled Docker backing growth: 2.593 GiB. Storage sampling stopped with the controller; continuous full-window reserve proof is incomplete.
- Engineering start guard: 26.09375 GiB for 18 remaining slots. Budgets include per-slot host outputs, node overlap, 3GiB Docker growth and safety margin. A full successful strict qualification must verify the final model.
- No scientific evidence was deleted. Owned ephemeral cluster cleanup happened only after the retained authoritative raw copy matched the node/DONE hashes.
- Final verification: no Docker containers active, no claim campaign, no integration, no cloud calls, clean committed source.

## Checkpoint/resume

The atomic, fsynced checkpoint stores all 18 frozen cells with PENDING, RUNNING,
SEALED_VALID, SEALED_INVALID or INTERRUPTED status, treatment identity, manifest,
request, endpoint and continuity hashes, session bindings and timestamps. An
exclusive lock spans verification/execution/sealing. Resume independently hashes
every sealed output, requires a contiguous prefix, rejects gaps/orphaned attempts
and rolled-back checkpoints, and never reruns a valid cell. RUNNING after restart
becomes INTERRUPTED and requires review. Host certificate paths are session-level;
science/executor/input identity remains fixed. Every new slot builds a fresh cluster.

Synthetic tests prove slots 1–2 → resume at 3, new host-session binding, explicit
stop boundaries, cluster recreation, missing/tampered evidence rejection and
analysis finalization even at an explicit stop on slot 18. They are not physical
qualification evidence. Actual resume of the failed battery checkpoint refused
with `interrupted_or_invalid_slot_requires_replacement_review`; checkpoint hash
was unchanged and no new container/treatment was created. There was no halfway
resume or automatic replacement.

`--max-slots N` and `--stop-after-slot N` only return after verified sealing and
cleanup. `--resume` is mandatory for an existing campaign. Completed analysis is
idempotent and rejects changed output; only 18 new valid claim slots can enter
frozen paired inference. Diagnostic data is excluded.

## Tests and next authorized step

Final focused suite: **74 passed**. Full suite: **916 passed, 3 skipped**.
Regression tests include the actual non-qualifying failure frame, all independent
resource-gate failures, unchanged physical patch/watchdog AST, strict AC rejection
of battery, battery-evidence rejection for claims, deterministic schedules, exact
request reconciliation, tamper rejection and checkpoint/recovery behaviour.

The current strict power prerequisite snapshot reports Battery Power. A new full
75-minute **strict-AC** qualification on the fixed source remains required, with
open lid, valid continuity/assertions, unchanged pinned inputs and adequate disk.
The following is prepared only; it has not been executed:

```sh
cd /Users/fgtek002/dynapm-v8c-frozen
/Users/fgtek002/dynapm-v8c-frozen/.venv/bin/python -m dynapm.scripts.task48_v8_service_primary --spec /Users/fgtek002/dynapm-v8c-frozen/results/v8c_r2/20261109-next-strict-ac/executor-spec.json --spec-sha256 97544b3717a2dc3d66ed9880fc6ecb6cd7f2d45e4e6eaa4225d6dd5f6e8a8bce --root /Users/fgtek002/dynapm-v8c-frozen/results/v8c_r2/20261109-next-strict-ac/qualification-campaign --scope DIAGNOSTIC_NON_CLAIM --authorize-diagnostic --max-slots 1
```

After a valid bounded stop, the same exact command with `--resume --stop-after-slot 1`
verifies the sealed prefix and stops without starting slot 2. For a later authorized
claim campaign, the same CLI supports `--max-slots 3`, then `--resume --max-slots 3`
or `--stop-after-slot 6`; an actual strict primary qualification file/SHA is mandatory.
No valid claim-launch command can be issued today because that qualification does
not exist. Neither this battery run nor its recovered raw stream qualifies the
executor. Do not start the 18-treatment campaign or the separate integration.

PRIMARY_SERVICE_EXECUTOR_BLOCKED

V8C-R.2 STATUS: BLOCKED
