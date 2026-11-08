# V8C.4 transport forensics and completed-run validity

Disposition: TRANSPORT_HARNESS_DEFECT. The campaign must remain stopped. This review does not authorise replacement, new treatment cells, integration or changes to frozen scientific inputs.

## Scientific and execution identity

Scientific source `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`; previous/active harness `d0ffc346e13d22f7b3d072fc59378831a668b3f2`; original factual result `7bfe9a942ce362d10f6f133d64f29d2a87a0a5aa`. Opt-in fix `0a68749c9dcef4fc7394a7c20539b62289a8e315` on `v8c4-transport-harness-fix`. Execution HEAD and original source files remain unchanged. The fix is not wired into the frozen launcher.

## Retrospective slot validity

These assessments do not rewrite the original COMPLETE/HARNESS_FAILED terminal records. A persistent failure to establish forwarding streams prevents application-only primary endpoint attribution even when every offered client attempt is counted. A broken-pipe warning alone does not invalidate a run. Timeout cause is not inferred from a resource target.

| Slot | Executor terminal | Transport validity | Warning lines | Stream creation failures | Connection resets | Timeouts | HTTP errors | Unattributed application_error | Observed / expected primary records |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | COMPLETE | HARNESS_FAILED | 7296 | 7284 | 1 | 7468 | 0 | 0 | 12600 / 12600 |
| 2 | COMPLETE | HARNESS_FAILED | 7193 | 7174 | 5 | 7465 | 0 | 0 | 12600 / 12600 |
| 3 | COMPLETE | VALID | 0 | 0 | 0 | 0 | 0 | 0 | 12600 / 12600 |
| 4 | COMPLETE | HARNESS_FAILED | 10905 | 10901 | 1 | 11336 | 0 | 0 | 21600 / 21600 |
| 5 | COMPLETE | INDETERMINATE | 181 | 0 | 1 | 1463 | 0 | 0 | 21600 / 21600 |
| 6 | COMPLETE | HARNESS_FAILED | 11098 | 11093 | 3 | 11317 | 0 | 0 | 21600 / 21600 |
| 7 | COMPLETE | VALID_WITH_TRANSPORT_WARNINGS | 122 | 0 | 0 | 938 | 0 | 0 | 21600 / 21600 |
| 8 | COMPLETE | HARNESS_FAILED | 10979 | 10955 | 11 | 11339 | 0 | 0 | 21600 / 21600 |
| 9 | HARNESS_FAILED | HARNESS_FAILED | 289 | 278 | 1 | 604 | 0 | 2416 | 3601 / 21600 |

Slots 1, 2, 4, 6 and 8 show sustained error/data stream creation failures, followed by no successful requests for the remainder of the primary window. They cannot retain valid application-only SLO/throughput attribution. Their recorded client-attempt counts are reproducible, but include transport-induced failures and overload drops.

Slot 3 is VALID: 12,600 successful HTTP 200 requests, zero transport warnings, complete telemetry and unchanged Pod identity. Slot 7 is VALID_WITH_TRANSPORT_WARNINGS for the frozen client-observed endpoints: successful responses continue to the end, warnings are late-response broken pipes, no recorded stream-creation/control-channel failure, and all expected requests reconcile. The 938 deadlines remain observed deadlines; their server-side causes are not asserted. Slot 5 is INDETERMINATE: responses continue, but one reset and 1,463 unattributed deadlines cannot be mapped to individual transport/application causes. That is an evidence limitation, not automatic invalidation for a warning.

No generator retries or port-forward restarts are implemented in the exact source. All eight completed windows have unique complete scheduled request IDs with no missing offers. There is no request-level exception/errno/local socket tuple in the original records, so exact connection-level error counts and causes cannot be recovered from them.

## Slot 9 aligned timeline

T0 = 2026-11-08 06:36:15.993875 UTC. Host request/enforcement times use the original monotonic origin. glog timestamps are interpreted in the host Europe/Helsinki timezone (UTC+02); raw log lines are retained. Untimestamped lines remain bounded observations rather than invented points.

| Offset from T0 | Evidence |
|---|---|
| −1800 to 0 s | All 21,600 reference-resource warm-up requests succeeded. This was true for all nine attempts. |
| +0.002089 s | Resource decision intended. |
| +0.071518 s | Resize patch submitted. |
| +0.114144 s | Kubernetes patch accepted. |
| +0.795048 s | Last recorded Pod snapshot: same UID/container, Running, Ready, restartCount=0, no last termination. |
| +0.866313 s | 70m CPU / 64 MiB reservation confirmed enforced; actuation duration 0.864224 s. |
| +5.953304 s | Last successful request completion. |
| +6.676536 s | First recorded deadline completion; request offered at +1.666667 s. Its cause is not recorded. |
| +8.613653 s | First broken pipe: potential consequence of a client closing after its deadline; not alone proof of global path failure. |
| +61.922396 s | First recorded connection reset in the forwarding path. |
| +63.280128 s | First data-stream creation timeout; +63.306153 s first error-stream creation timeout. This is definite control/forwarding-path failure evidence. |
| +100.250382 s | Last accepted node/cgroup telemetry; OOM-kill count remains zero. Node-side Docker execution still worked at this instant. |
| +100.554665 s | Last timestamped stream-creation error. Untimed “lost connection to pod” follows in the log. |
| +101.410756 s | First completed generic application_error with null HTTP status. The original recorder discarded its actual exception; this is not proof of an application HTTP error. |
| approximately +300 s | Main control loop finally consumes the failed collector future at the first bucket boundary. Remaining full-window endpoints are undefined. |
| 06:41:16.693106 UTC | Treatment guard scope ends and owned assertion release is recorded. |
| 06:41:17.585388 UTC | Supervisor records sealed HARNESS_FAILED and stops before slot 10. |

For the original slot 9, whether the Pod still existed/restarted/exited at the exact connection-loss instant, whether endpoints disappeared, and whether API access still worked after that instant are not recorded. The last Pod snapshot is at +0.795 s, not at transport loss. No OOM was observed in available cgroup telemetry. Exact child return code/signal and exit timestamp were not persisted. One cannot turn the final “lost connection” text into proof of Pod termination. The root observed failure is C (forwarding process/stream failure), with D (harness classification/supervision defects); the ultimate cause of the original process exit is unresolved.

## Per-slot aligned timelines

- Slot 1: `timeline-01.jsonl.gz`, T0 `2026-11-07T20:28:15.663054+00:00`; final telemetry +1800.229166 s; last successful response completion +11.814527 s. persistent failure to create request forwarding/error streams, no successful response after stream collapse; client outcomes cannot represent application-only primary endpoints.
- Slot 2: `timeline-02.jsonl.gz`, T0 `2026-11-07T21:44:16.167921+00:00`; final telemetry +1800.232328 s; last successful response completion +7.575006 s. persistent failure to create request forwarding/error streams, no successful response after stream collapse; client outcomes cannot represent application-only primary endpoints.
- Slot 3: `timeline-03.jsonl.gz`, T0 `2026-11-07T23:00:17.314217+00:00`; final telemetry +1800.243526 s; last successful response completion +1799.537671 s. complete expected request IDs, all HTTP 200 successes, no recorded transport warnings or observability gaps.
- Slot 4: `timeline-04.jsonl.gz`, T0 `2026-11-08T00:16:13.728673+00:00`; final telemetry +1800.248999 s; last successful response completion +13.174378 s. persistent failure to create request forwarding/error streams, no successful response after stream collapse; client outcomes cannot represent application-only primary endpoints.
- Slot 5: `timeline-05.jsonl.gz`, T0 `2026-11-08T01:32:14.296470+00:00`; final telemetry +1800.238444 s; last successful response completion +1802.883751 s. responses continue, but a connection reset and unattributed timeouts lack request-level transport provenance; full-window attribution cannot be proven.
- Slot 6: `timeline-06.jsonl.gz`, T0 `2026-11-08T02:48:14.434559+00:00`; final telemetry +1800.245565 s; last successful response completion +24.282111 s. persistent failure to create request forwarding/error streams, no successful response after stream collapse; client outcomes cannot represent application-only primary endpoints.
- Slot 7: `timeline-07.jsonl.gz`, T0 `2026-11-08T04:04:16.132112+00:00`; final telemetry +1800.246749 s; last successful response completion +1803.007339 s. only late-response broken pipes; successful responses continue through window; no recorded stream creation/control-channel failures; client-observed deadlines retained without claiming server-side timeout cause.
- Slot 8: `timeline-08.jsonl.gz`, T0 `2026-11-08T05:20:15.467121+00:00`; final telemetry +1800.228628 s; last successful response completion +22.788049 s. persistent failure to create request forwarding/error streams, no successful response after stream collapse; client outcomes cannot represent application-only primary endpoints.
- Slot 9: `timeline-09.jsonl.gz`, T0 `2026-11-08T06:36:15.993875+00:00`; final telemetry +100.250382 s; last successful response completion +5.953304 s. port-forward exited; telemetry stops at +100 s and full exposure is absent.

Every timeline contains original request rows aligned by completion, resource decisions/enforcement, timestamped port-forward errors, sampled Pod state, cgroup/OOM observations and host continuity records. Unknown-time lines stay explicitly unknown. Original raw paths and hashes bind the timelines; per-slot JSON gives full counts and Pod observations.

The original clusters were deleted by the normal finally block. No Kubernetes event stream, continuous endpoints history, node/kubelet log archive or application stdout was saved. Historical Docker event collection returned no records during a bounded read and was stopped; this is unavailable evidence, not evidence of zero historical events. Docker node deletion is recorded in kind.log but its original lines have no timestamps. Readiness is sampled; no liveness probe was configured. A Ready snapshot does not prove continuous request-path health between snapshots.

## Minimal non-claim diagnostics

Two earlier preflights were preserved: the connected 35 W supply was draining the battery, so no cluster or load started. After the user confirmed power and the strict recheck passed at zero battery current, the following fixed short conditions ran with the exact pinned image/cluster stack. They are DIAGNOSTIC_NON_CLAIM and never enter campaign accounting.

| Condition | CPU / reservation; fixed limit | Planned load | Request outcomes | Path probe success counts (API / Pod / Service / PF) | Restarts | Live-scope process exits |
|---|---|---|---|---|---|---|
| neutral | 1000m / 512 MiB; 1024 MiB | 12 RPS, 96 MiB, 180 s | {'success': 2160} | 36/36 / 36/36 / 36/36 / 36/36 | [0] | [] |
| low | 70m / 64 MiB; 1024 MiB | 12 RPS, 96 MiB, 240 s | {'success': 18, 'overload_drop': 1360, 'request_timeout': 1502} | 48/48 / 41/48 / 40/48 / 1/48 | [0] | [] |

Each condition has a fresh cluster and initial resource enforcement, identical request work/seed/deadline/concurrency, no request retry and no automatic forwarding restart. The three health paths add observational load; these are not identical replicas of the 30-minute V8 history. Host/clock/power guards remained active and were released. Probe failures and exact process exit evidence are in diagnostic-summary.json, alongside final Pod/endpoints/events/nodes/application logs and cgroup counters where captured. They can localise a mechanism but cannot retroactively supply missing slot-9 state.

Diagnostic localisation: neutral: 0 cycles had API + direct Pod + Service success but port-forward failure; low: 38 cycles had API + direct Pod + Service success but port-forward failure. The low-resource condition reproduces forwarding-only failure while its Pod remains present and does not restart. This supports domain C (forwarding stream mechanism), rather than a continuing whole-cluster/API outage for those intervals. Initial low-resource readiness/health disruption is retained separately; it does not explain the later forwarding-only outage. The internal trigger for the original slot-9 process exit remains unavailable.

Final cumulative cgroup evidence: neutral had zero throttled periods; low had 694/1046 throttled periods and 206,328,503 throttled microseconds. Both had zero oom/oom_kill and no memory limit events. CPU throttling is a real observed condition, but it does not license attributing later forwarding-only failures to application latency. The diagnostic process remained alive until deliberate SIGTERM cleanup in both conditions; the original slot-9 spontaneous-exit code remains unknown.

## Harness audit and correction

1. stdout/stderr goes to a regular file, not an unread PIPE. No pipe-buffer blockage is supported by the code.
2. Readiness is one successful HTTP /healthz request; subsequent transient stream errors are merely written to the log. Process liveness alone can stay true while all request streams fail.
3. The collector polls child liveness, but the main thread checks collector exceptions only at five-minute boundaries. The generator can continue making invalid attempts for roughly 200 s after the slot-9 forwarding path disappears.
4. OSError/URLError failures are merged into application_error, while deadlines lose their socket stage/cause. New opt-in request_once preserves exception chains, errno, HTTP status and stage, and separates HARNESS_TRANSPORT, UNATTRIBUTED_TIMEOUT and actual HTTP responses.
5. ProcessObserver preserves observed returncode/signal and deliberate-cleanup state. supervised_wait checks guard/process at intervals up to 250 ms. No retry, reconnect, finite latency for incomplete work or policy change is introduced.

Fix commit `0a68749c9dcef4fc7394a7c20539b62289a8e315` is separate and additive. It implements attribution/supervision primitives; it does not fix the upstream kubectl stream-collapse mechanism or wire a new measurement path into the campaign. Exact behavioural boundaries and tests are in docs/v8_transport_amendment.md on that review ref.

## Tests, preservation and recommendation

Focused final additive tests: 14 passed. Full final suite: 842 passed, 3 skipped. Tests were offline, before the successful short diagnostics; no implementation changed afterward.

All 244 protected input-file hashes reverified, including original attempts 1–9, the three reference sessions and snapshot bundle. Original source/branch/HEAD, V8B ref, cohort inputs and campaign attempt inventory remain unchanged. No slot 10–18, replacement, Google work or integration was launched.

Recommendation: TRANSPORT_HARNESS_DEFECT. Do not continue or authorise an isolated slot-9 replacement. Persistent transport corruption affects multiple earlier primary cells, and exogeneity is not established. A prospective measurement-path/harness amendment and comparability review must precede any further frozen treatment or replacement decision. Preserve the tested resource domain; do not raise resource floors or change targets merely to remove bad outcomes. The maximum-two replacement rule is not waived, and no additional repetitions are authorised.
