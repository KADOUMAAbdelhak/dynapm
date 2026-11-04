# V7C.12 bounded reservation verification

Disposition: **RESERVATION_SEMANTICS_BLOCKED**. This engineering run is
non-comparative and non-claim-generating. It does not close V7C.11 or authorize V8.

Run `2026-11-04T074826-213408+0000-1ba6ac4d`, fingerprint
`785147397b4be41f684621e3961895e433ba34de505435156cec2668b8a68384`,
executed from clean `ad42e264ae9f5dc286c7d2a7481ab4ce6e770aa4`.
The complete adapter and hashed outputs are preserved under
`results/resource_semantics/v7c12/<run-id>/`. The earlier failed power preflight
is separately preserved. No historical run or bootstrap bytes are relabelled.

The fresh Kubernetes v1.35.8 cluster used Burstable QoS, CPU request=limit,
variable 64–512MiB memory reservation and fixed 1024MiB memory limit. Kubelet
configuration and cgroup memory.min/low and swap evidence were captured.
One PW6 profile initialized from qualified block #1; live stimuli were explicit
actuator engineering targets. No method comparison or compressed slots ran.

All 13 submitted patches reached reconciled spec/status/allocated reservation,
CPU cgroup quota and fixed memory.max with resolved resize conditions. Two
no-ops required no patch. There were 16 intentions, two skipped opportunities,
one superseded unsent recommendation and one released latest queued target.
No accepted patch was cancelled or overlapped. Transient PodResizeInProgress
conditions were recorded as 26 deferred observations across the polling stream;
these resolved. No unresolved actuation or actuation watchdog censoring occurred.
This is positive evidence for reservation resizing, not an end-to-end pass.

The repeated 100m CPU / 64MiB cycle produced 11 request read timeouts among
499 total requests. All 11 occurred within that cycle's extended observation
interval. Application-side Python cgroup diagnostic calls took 17.099s and
15.872s during the same cycle. This association does not establish whether CPU
quota, diagnostic interference or another mechanism caused the timeouts.
No memory-limit shrink or charged-usage rejection was observed. The record
does not establish a below-64MiB-reservation versus above-reservation charge
stress test. No physical page reclamation is claimed.

The adapter first checked a healthy response window, then ran final blocking
Pod/cgroup reads and reused the earlier window result. It consequently emitted
an overbroad mechanical-window completion for the affected cycle and continued
later engineering cases. The terminal whole-run request audit detected the
failures and correctly marked the run BLOCKED. Those original events remain
immutable; the independent validation must explicitly invalidate the affected
healthy-window claim and must not qualify later cases as a fail-closed run.

`finish_observed_window` corrects the completion adapter: after the final
blocking diagnostics, obtain a fresh locked request snapshot and use the ledger's
current monotonic clock. Recompute the frozen application predicate and record
terminal APPLICATION_REQUEST_FAILURE when failures are present. Keep accepted
state for postmortem and unset failure latency. Never issue the next queued
operation after that failure. Regression tests reproduce the stale-window
sequence. This correction has offline verification only; no live rerun occurred.
It changes neither the frozen v2 model nor physical 300s telemetry requirements.

Statistical settling remains unresolved. The next work is diagnosis of request
failures and review of a corrected bounded adapter. There is no automatic rerun,
no V8 execution, and no prospective repetition/precision gate closure.

## Descriptive observations and verification

| Finite enforcement path (seconds) | n | min | median | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| Patch submission to ACK | 13 | 0.0368 | 0.0437 | 0.0520 | 0.0542 | 0.0547 |
| ACK to reconciled enforcement | 13 | 0.0451 | 0.4996 | 1.0883 | 1.1323 | 1.1432 |
| Dispatch to enforcement | 13 | 0.1483 | 0.5819 | 1.1878 | 1.2315 | 1.2424 |

These finite resource-path observations remain descriptive despite the overall
failed application check. They are not healthy application-settling latencies.
The queued intent took 6.9983s from original intention to enforcement, including
waiting for the previous operation's window; it is distinct from dispatch latency.
The CPU-only paths (n=2) took 0.3672–1.0451s and memory-only paths (n=2) took
0.5851–0.5916s from dispatch. These small engineering samples establish no
population timing or SLO claim.

Clock evidence has zero rejections. Host maximum wall/monotonic drift was
0.002889s and maximum checkpoint gap 5.115031s, within frozen 2s/30s limits.
Owned assertions were released with ended_at and release_confirmed. AC/lid/boot
continuity passed. The run's protected evidence inventory had zero mismatches.

Focused checks: 78 passed. Full suite: 759 passed, one skipped. The completion
repair is covered by late-failure, fresh-window and missing/incomplete-registry
regressions; runtime validation of that repair remains outstanding. The separate
independent validation binds the original run, adapter, protocol, qualification,
artifact and output hashes and reconstructs the invalid window from request bytes.
