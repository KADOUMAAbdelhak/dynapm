# Bounded V8 campaign: blocked after slot 9

V8_CAMPAIGN_BLOCKED. Eight complete treatments passed frozen validators and independent endpoint/hash reconstruction. Slot 9 failed when kubectl port-forward exited; slots 10–18 were not launched. No replacement, reordering, Google experiment or integration run occurred.

Scientific source: `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`. Execution harness: `d0ffc346e13d22f7b3d072fc59378831a668b3f2`.

Launch preflight PASS, SHA-256 `ff3a386e43c4fb0a6e791c0f2c29b3d8514a870f14d4710b0822360093a8f65b`. Approved amendment `3d65d60ec02854e09825195b444d2f7742bd74645c217d84a0bbf548a3f8b937`.

Before launch, the two existing pinned image IDs were rebound to their exact frozen tags; image content remained unchanged. The original failed lookup preflight and metadata repair record are preserved separately.

## All frozen slots

| Slot | Rep | Scenario | Method | Seed | Run ID | Classification |
|---:|---:|---|---|---:|---|---|
| 1 | 1 | periodic | static | 2026110501 | 004-2026-11-07T194230-886669+0000-78bd0a0eb86e | COMPLETE |
| 2 | 1 | periodic | pw_12h | 2026110501 | 005-2026-11-07T205831-983391+0000-a92601fb9136 | COMPLETE |
| 3 | 1 | periodic | pw_3h | 2026110501 | 006-2026-11-07T221432-097994+0000-982768f454f8 | COMPLETE |
| 4 | 1 | abrupt_regime_shift | static | 2026110501 | 007-2026-11-07T233029-503103+0000-412ed716bccd | COMPLETE |
| 5 | 1 | abrupt_regime_shift | pw_3h | 2026110501 | 008-2026-11-08T004630-430637+0000-a87cd08e93a0 | COMPLETE |
| 6 | 1 | abrupt_regime_shift | pw_12h | 2026110501 | 009-2026-11-08T020229-416462+0000-d6762ca96e8a | COMPLETE |
| 7 | 2 | abrupt_regime_shift | pw_3h | 2026110502 | 010-2026-11-08T031831-596684+0000-506219e373bf | COMPLETE |
| 8 | 2 | abrupt_regime_shift | pw_12h | 2026110502 | 011-2026-11-08T043431-608661+0000-d5865ba0f5ad | COMPLETE |
| 9 | 2 | abrupt_regime_shift | static | 2026110502 | 012-2026-11-08T055032-093248+0000-749cdb7d0689 | HARNESS_FAILED |
| 10 | 2 | periodic | pw_12h | 2026110502 | — | NOT_LAUNCHED |
| 11 | 2 | periodic | pw_3h | 2026110502 | — | NOT_LAUNCHED |
| 12 | 2 | periodic | static | 2026110502 | — | NOT_LAUNCHED |
| 13 | 3 | periodic | pw_3h | 2026110503 | — | NOT_LAUNCHED |
| 14 | 3 | periodic | static | 2026110503 | — | NOT_LAUNCHED |
| 15 | 3 | periodic | pw_12h | 2026110503 | — | NOT_LAUNCHED |
| 16 | 3 | abrupt_regime_shift | pw_12h | 2026110503 | — | NOT_LAUNCHED |
| 17 | 3 | abrupt_regime_shift | static | 2026110503 | — | NOT_LAUNCHED |
| 18 | 3 | abrupt_regime_shift | pw_3h | 2026110503 | — | NOT_LAUNCHED |

## Completed-run descriptive endpoints

These are incomplete-campaign run summaries, not a completed N=3 analysis or evidence of a policy advantage. All timeouts/errors remain in recorded offered-request outcomes. Transport warnings are recorded separately; their contribution to observed application failures has not been established.

| Slot | SLO violation rate | Successful p95 s | Failures | Timeouts | Successful RPS | Requested CPU cores | Requested memory bytes | Used CPU cores | Used memory bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.99968254 | 4.1594942 | 12580 | 7468 | 0.011111111 | 0.070063651 | 67141016 | 0.0038060171 | 1.2672901e+08 |
| 2 | 0.99984127 | 4.4575663 | 12579 | 7465 | 0.011666667 | 0.070060202 | 67139273 | 0.004842762 | 1.2746133e+08 |
| 3 | 0 | 0.045598226 | 0 | 0 | 7 | 0.19005629 | 1.4263374e+08 | 0.093167754 | 84422803 |
| 4 | 0.99981481 | 4.5633786 | 21577 | 11336 | 0.012777778 | 0.070059347 | 67138841 | 0.0051580296 | 1.2703611e+08 |
| 5 | 0.92842593 | 4.6346426 | 6413 | 1463 | 8.4211111 | 0.19005331 | 1.4263228e+08 | 0.17872575 | 1.2330473e+08 |
| 6 | 0.99981481 | 4.9303925 | 21548 | 11317 | 0.028888889 | 0.070067407 | 67142913 | 0.0032486243 | 1.2616786e+08 |
| 7 | 0.56263889 | 4.4102945 | 4061 | 938 | 9.7272222 | 0.19005263 | 1.4263195e+08 | 0.17162397 | 1.2254022e+08 |
| 8 | 0.99976852 | 4.5499925 | 21574 | 11339 | 0.014444444 | 0.070058643 | 67138486 | 0.0046637822 | 1.2907103e+08 |

Primary metrics cover all 30 minutes. The sealed per-run JSON retains separate first-five-minute transition and following-25-minute descriptive slices. No full-window endpoint is inferred for slot 9.

## Actuation and transport

| Slot | Raw enforced patches | Latency s | CPU churn cores | Memory churn bytes | Controller CPU s | Port-forward warning lines | Lost connection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 1 | 0.546488 | 0.93 | 469762048 | 0.038065375 | 7296 | False |
| 2 | 1 | 0.5129505 | 0.93 | 469762048 | 0.037132541 | 7193 | False |
| 3 | 1 | 0.848230958 | 0.81 | 394264576 | 0.060111418 | 0 | False |
| 4 | 1 | 0.843155167 | 0.93 | 469762048 | 0.060005708 | 10905 | False |
| 5 | 1 | 1.158529584 | 0.81 | 394264576 | 0.076144916 | 181 | False |
| 6 | 1 | 0.884126958 | 0.93 | 469762048 | 0.074292667 | 11098 | False |
| 7 | 1 | 1.472887 | 0.81 | 394264576 | 0.08400075 | 122 | False |
| 8 | 1 | 1.51073875 | 0.93 | 469762048 | 0.090693375 | 10979 | False |
| 9 | 1 | 0.864224375 | undefined | undefined | undefined | 289 | True |

Slot 9 raw actuation shows 70m CPU / 64 MiB reservation enforced in 0.864224375 seconds, although the exception terminal intentionally has no completed episode metrics or returned actuation list. The raw trace is preserved; the terminal is not rewritten.

Slot 9 last accepted telemetry receipt offset: 100.250382 s. Partial exposure request records: 3601; outcomes: `{'success': 20, 'overload_drop': 561, 'request_timeout': 604, 'application_error': 2416}`. These are partial diagnostic counts only.

Port-forward logged error/data-stream timeouts followed by "lost connection to pod". The frozen terminal categorises this as HARNESS_MEASUREMENT_FAILURE / controller_crash; the direct invariant is workload_port_forward_exited. The underlying reason for the transport failure is not proven. Earlier completed runs also require transport-log scrutiny before attributing all request failures to application resource limits.

Static and PW-12h retain STRUCTURAL_EQUAL_TARGET in both scenarios. Their observed differences cannot be attributed to resource-target differences. No frozen N=3 paired contrast, completed matched-control conclusion or campaign method mean is reported from missing runs. No p95 is fabricated where undefined.

Runtime primary maintenance is absent by design: treatments consume frozen checkpoint states at T0. V8B offline maintenance counts/costs remain preserved in snapshots/maintenance.json and are not newly replicated physical overhead measurements.

## Continuity, storage and evidence

Host continuity has no recorded failure; campaign maximum discrepancy 102.670 ms and maximum checkpoint gap 5.151 s. All nine attempts have zero clock rejections and independently verified raw/envelope/source clock evidence. The campaign and treatment-9 assertions were released. The guard status is FAILED because the workload scope raised, while its failure field is null; this does not indicate a detected host continuity failure.

Free before: 30.583 GiB; minimum recorded heartbeat: 27.311 GiB; after: 29.070 GiB. One-second storage monitoring used a 22 GiB early-stop buffer above the 20 GiB reserve. No evidence deletion occurred.

All three reference attempts, snapshot/library hashes, bootstrap qualification and V8B ref `39082cf6ffdfe1884194f4160131fa82c58676f1` were revalidated. Complete exact output inventories and terminal hashes are in blocked-review.json. Original attempts and failed terminal remain immutable.

The separate 4h15m integration must not start as part of this blocked campaign. Next work requires a scoped transport/observability diagnosis and separately reviewed replacement authority under the frozen maximum-two exogenous rule; this record does not classify the failure as exogenous or authorise a replacement.

## Verification and factual commit

Focused tests: 89 passed. Full offline suite: 828 passed, 3 skipped. No source fix was made. Test log hashes are in test-results.json. Docker containers were absent after cleanup, and the campaign/failed-treatment owner and assertion PIDs had exited.

The factual report, verified run inventory and test summary are committed on a separate evidence ref, v8c-campaign-results. The execution branch and HEAD remain at the approved d0ffc346 harness commit; source_commit continues to denote the frozen fe3b870 scientific source. No campaign completion is claimed.
