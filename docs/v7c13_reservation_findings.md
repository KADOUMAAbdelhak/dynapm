# V7C.13 reservation mechanics qualification

**RESERVATION_SEMANTICS_VERIFIED.** V7C.11/V7C.12 reservation mechanics close by
new evidence. The original V7C.12 run remains BLOCKED and immutable. This is a
bounded, non-comparative engineering qualification, not V8 execution or a claim
trial. Statistical settling remains unresolved.

The prospective taxonomy and two-run diagnostic plan were committed as
`8c715bb`, with ownership/overload checks in
`c90eb92ccb3d9232705fe4f8c706b68d8939eccc` before either execution. Both ran from
clean c90eb92. The code and each run's configuration, raw observations, adapter,
source commit and output manifest are hashed. No resource threshold was chosen
from the engineering outcomes.

## Failure taxonomy

Use `reservation-outcome-observability-v1`, explicitly superseding the old
zero-error adapter gate. Request timeout, HTTP/application error, SLO violation,
throughput loss and queue buildup are valid operational outcomes. Retain failed
attempt IDs, timestamps and offered-request denominators. Never require zero
application errors for enforcement PASS or silently exclude poor resource points.

Generator failure, missing/corrupt measurement records, lost independent control
telemetry, controller crash, unverifiable enforcement, missing provenance and
host continuity failure are measurement failures. Diagnostic timeout/error is a
separate category. Application diagnostics do not establish or gate Kubernetes
spec/status/allocated-resource/cgroup enforcement when independent evidence is
available; losing that independent evidence still fails closed.

A fresh final observation is evaluated after blocking diagnostics. Twenty
completed host request attempts and physical observation duration establish
measurement progress, not application health, server drain or statistical
stationarity. Errors remain in that observation. A client timeout does not
prove that server work ended. No successful finite actuation latency is assigned
to an unenforced/censored operation.

## Executions and physical checks

| Engineering mode | Run ID | Fingerprint |
|---|---|---|
| External node observation | 2026-11-04T221617-280859+0000-5404f4bd | ce913561d5fe6abe53ba1a5ed31206e48fcf5b1a8c998269b595a0ce91e2e218 |
| Additional asynchronous application-exec diagnostics | 2026-11-04T222011-818835+0000-4baeccba | dce610832f96b10a2e2f6c27cb7e64e2abc6b19b5eaab77a5b5740017e41f46f |

Each fresh Kubernetes v1.35.8 execution completed 15 operations: 13 patches and
two no-ops. Together they verified CPU up/down, memory reservation up/down,
simultaneous changes, consecutive opportunities, supersession and six repeated
100m/64MiB cycles. Each run recorded 16 intents, two skipped opportunities,
one superseded unsent intent and one released latest queued target. Accepted
patches never overlapped or were silently cancelled. Transient resize conditions
resolved; pending and censored operation counts ended at zero.

Pod spec, container status, allocated reservation, observed generation, CPU quota,
Burstable QoS, fixed memory.max=1073741824 and actual container identity agreed.
Node cgroup measurements came from outside the workload cgroup, with fresh
host-local read ordering and node boot/uptime evidence. Memory.min/low stayed zero,
workload swap stayed zero, and no memory high/max/OOM event occurred. The fixed
1GiB cap never changed. No memory-limit shrink rejection occurred. Charged usage
briefly exceeded the 64MiB reservation without changing that cap.

Both executions initialized PW6 from the same qualified bootstrap block #1.
Independent reconstruction matched history and initial profile hashes; actual
Pod/application/profile/controller/telemetry identities were distinct between
runs. Initialization refresh count remained zero. Engineering targets were
explicit actuator stimuli, not comparative policy outcomes. Physical 300s
bucket semantics and frozen workload/SLO contracts remain unchanged; no short
engineering observation is relabelled as a scientific bucket.

## Diagnosis and diagnostic overhead

V7C.12's original 11 timeouts among 499 requests remain recorded. Its sampled
low-CPU portion had 168/172 throttled CPU periods, about 97.7%, charged memory
around 61MB and no OOM. Sparse observations and synchronous application-exec
reads prevent an exclusive retrospective causal attribution.

The new repetitions retained the same real 4 RPS, 30000 iterations, 32MiB work,
seed, HTTP timeout and resource range. No generator drop or stream discrepancy
occurred. External-only: 0 failures / 612 requests. Diagnostic-enabled:
0 failures / 615 requests. No observed failure was discarded to obtain PASS.
The original timeout event did not reproduce.

The matched first low-resource intervals had 185 requests each:

| Observation | External-only | Additional app-exec diagnostics |
|---|---:|---:|
| Mean sampled CPU cores | 0.0605 | 0.0842 |
| Throttled CPU periods | 160/450 (35.6%) | 337/454 (74.2%) |
| Client latency median | 0.107s | 0.816s |
| Client latency p95 | 0.116s | 2.999s |
| Client latency max | 0.158s | 4.212s |
| Peak observed client in-flight attempts | 1 | 12 |
| Peak sampled charged memory | 52,547,584B | 68,300,800B |

The two application Python/cgroup exec calls took 11.023s and 14.097s despite
independent enforcement reads remaining available. Kernel throttled-time counters
are aggregate counters, not wall-time fractions; the period fractions above are
reported separately. Memory pressure/limit events stayed zero.

These observations demonstrate substantial diagnostic perturbation in this
bounded engineering setting, consistent with shared 100m quota contention and
backlog. They do not establish the exclusive cause of the earlier timeouts or
a randomized population effect. Client in-flight count is not a server queue
measurement. Client latency here is actual send-to-complete time; it does not
redefine the frozen offered-arrival SLO. No comparative V8 SLO estimate is made.

Use independent node/Kubernetes evidence for normal enforcement verification.
Application-exec diagnostics remain optional, explicitly instrumented engineering
observations and must not block the generator/controller or supply a health gate.
Do not raise the resource floor to remove slow application outcomes. The
100m/64MiB point remains observable and enforceable; no resource point or range
was excluded or raised on SLO grounds. This is bounded mechanics evidence, not
exhaustive live verification of every permitted grid value or a complete V8
outcome executor.

## Integrity, timing and disposition

Across both runs: zero harness failures, zero diagnostic failures, zero clock
rejections and no host AC/lid/boot/policy discontinuity. Maximum active node
observation gaps were 1.127s and 1.118s. Full node records also include intentional
startup initialization gaps below the predeclared 10s engineering bound.
Maximum host wall/monotonic drift was 0.289ms and checkpoint gap 5.126s, within
unchanged 2s/30s guard limits. Owned assertions were released and fresh clusters
were removed. All 5,800 historical protected files and all original V7C.12 output
hashes were unchanged; bootstrap and qualification hashes remain trusted originals.

All 26 actuation paths were finite. Dispatch-to-enforcement maxima were 1.014s
and 1.297s; per-run minima, medians, p95, p99 and maxima remain in the independent
record. Application measurement windows are not statistical-settling latencies.

Qualification record:
`results/resource_semantics/v7c13/qualification/validation.json`
SHA256 `5a6d1e2d1519a4bccebaa054162a09efbe7f061b5843c744f596bc4ec5259d19`.
It binds the two runs, source/adapter/taxonomy/output hashes, original acquisition
lineage, artifact/qualification identity, deterministic initialization and coverage.

V7C.11/V7C.12 mechanics are closed by this new record; their historical source
contracts and failed run are not rewritten. Next task: prospective V8 repetition/
precision design. V8 execution, compression and comparative outcomes remain
unauthorized by this qualification.

Verification: focused taxonomy/control/legacy tests 65 passed. Full suite with
required host socket/sysctl access: **783 passed, one skipped** (147.36s).
The initial restricted-sandbox invocation hit four local-socket failures and
12 host-provenance setup errors; rerunning with the required host access passed.
No failed live repetition was retried or selectively excluded.
