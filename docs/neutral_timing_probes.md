# Neutral timing-probe preparation

Configuration `system_neutral_timing_probes_v1.json` is preparation only: PW-6h,
no comparison, no compression-duration selection and no launch command. No live
probe was run in V7C.4. Controller settings, workload RPS/per-request work, methods
and scientific clock/accounting rules are unchanged.

The existing neutral controller now records recommendation computation and
telemetry collection, patch submit/ack, independent first-observed Pod CPU/memory
convergence and cgroup CPU/memory enforcement, pending durations, timeout/censoring
and skipped decisions. Measurements use local monotonic intervals and retain wall
provenance. No cross-host monotonic epochs are compared. API acknowledgment is
never counted as enforced allocation. An unchanged resource dimension is omitted,
not given a fabricated zero latency. Polling supplies first-observed upper bounds,
not exact kernel timestamps. No additional actuation or read call is introduced
just to obtain these timing observations.

`ResizeProbe` retains raw state-response observations. `distribution` reports n,
missing/censored counts,min,median,p95,p99,max; no confirmatory inference or
performance selection. `request_drain_seconds` measures completion of requests
already in flight at enforcement, one objective mechanical settling component.
Persistent memory-workset observations and raw post-actuation latency/throughput
responses support later settling analysis. **Statistical steady state remains
NOT_ESTABLISHED.** No favorable tolerance, stable-window length or compression
factor is invented from these diagnostics.

The next proposed experiment is a separately authorized genuine bootstrap-only
collection on an approved host, followed by bounded neutral PW-6h timing probes
with complete provenance. A synthetic plumbing check must remain labelled as such
and cannot satisfy genuine-bootstrap or measured-policy timing requirements.
No72h anchor, compressed validation, V8 comparison or Google acquisition is
started or authorized by these preparation tools.
