# V7C.11 prospective resource actuation and physical-system decision

**Decision: UNCOMPRESSED_SYSTEM_VALIDATION_REQUIRED.** Select memory semantics B,
versioned as `scheduler-reservation-actuation-v2`, and PATH U. No compression
factor or candidate physical duration is selected. The v1 contracts, Google/
Materna results and shared-bootstrap block #1 are not modified. No comparative
outcomes were observed. This freeze is an offline specification and tested
state-machine/payload library, not a deployed or runtime-qualified controller.

The user explicitly directed **offline only** after preflight found battery power.
Consequently no cluster, workload, timing probe, counterfactual resize or new
acquisition was launched in V7C.11. Fresh neutral verification of B remains a
blocker. V7C.10's retained actual Kubernetes v1.35.8 observations establish A's
memory-limit deferral; they do not empirically validate B or C.

## Mechanism audit and alternatives

Kubernetes 1.35 forbids changing a running Pod's QoS class. Guaranteed requires
CPU and memory requests to remain equal to limits; Burstable must not become
Guaranteed. See the [versioned resize documentation](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/).
The [v1.35.8 kubelet source](https://raw.githubusercontent.com/kubernetes/kubernetes/v1.35.8/pkg/kubelet/kuberuntime/kuberuntime_manager.go)
checks current memory usage when a memory limit decreases; with no decreasing
limit that particular guard returns without an admission check. The C10 error
matches that source branch: 67,108,864 bytes requested below 69,595,136 bytes used.
This source audit supports B's mechanism but cannot replace a real verification.

| Alternative | System / allocation meaning | SLO and churn | Comparability and completeness | Disposition |
|---|---|---|---|---|
| A: requests = limits | Vary hard CPU/memory budgets and reservations together; Guaranteed | Quota/OOM/deferral can affect service; memory-limit churn is physical | Original question is coherent, but a below-usage shrink may not complete; no timeout establishes success | Preserve v1 and its failure evidence; not the new bounded reservation consumer |
| B: variable requests, common fixed memory limit | CPU request/quota stays variable; memory target is scheduler/kubelet reservation accounting | Memory can exceed reservation up to the common cap; no claimed page reclamation; request churn is counted separately from limit churn | All methods use identical Burstable QoS, cap, queue and workload. Reservation savings are not physical RAM or billing savings. Capacity/API errors can still fail a decision | Select as the simplest explicit reservation-oriented downstream consumer |
| C: recreate on failed shrink | Replace the running application/Pod to apply a different hard budget | Cold start, request interruption, new instance/counters, cache loss and restart churn become treatment-mediated effects | Same fallback rule is possible across methods but changes the continuous-system question; recreation can still fail admission or OOM | Reject as unnecessary disruptive fallback; do not hide restarts from SLO/failure denominators |

The choice is based on the question and enforcement mechanism, not favorable
method performance. Memory reservation alone may have little SLO effect on an
uncontended node without MemoryQoS protection. That is a possible structural null,
not a reason to select another consumer. B is a new physical-system estimand;
old hard-cap experiments/results cannot be relabelled or pooled as B outcomes.

## B: fixed resources and endpoints

The old p95, 1.2 headroom, CPU 50–1000m/10m grid and memory 64–512MiB/4MiB grid
produce reservation requests unchanged. CPU requests equal CPU limits. Memory
limit is fixed at **1024MiB**, identical across every method and fixed from Pod
creation; initial memory request is 512MiB. This guarantees requests stay strictly
below the memory limit, preserving Burstable QoS throughout the permitted grid.

The cap is twice the **pre-existing 512MiB maximum reservation**, not a quantile of
new outcomes. The predefined workload's maximum persistent workset is 160MiB;
serialized workset replacement can temporarily hold old and new allocations.
A 1GiB cap provides a common engineering envelope above that workload and avoids
the QoS boundary at the maximum request. This basis is prospective, not a proof
that no future OOM is possible. OOM/capacity failures remain recorded harms;
the cap cannot be increased after seeing favorable/unfavorable treatment results.

New resources are in `harness/system/reservation-v2-resources.json`, separate from
v1. The immutable input history retains its original 512MiB reference and actual
acquisition clocks/resources. Normalization and physical quantities are explicit;
the reused history is not represented as fresh telemetry from a 1GiB Pod.

Memory allocation endpoint is the time integral of observed kubelet allocated
reservation. Desired spec, allocated request, actual used memory, fixed limit,
OOMs and churn remain separate. No clipping at the reservation is allowed;
used/reserved ratios may exceed one. Scheduler reservation does not imply that
resident pages are dedicated, freed or capped at the request. Runtime verification
must capture kubelet MemoryQoS/swap configuration and cgroup memory.max/min/low;
no unobserved memory protection is assumed. The baseline requires MemoryQoS off
and no workload swap; unexpected configuration requires a new explicit decision.

## Pending, deferred and stale decisions

`ActuationLedger` is a serialized single-owner model. Every event has an ID and
host-local monotonic/wall timestamps. A future transport adapter must preserve
those observations and run the unchanged host/clock guards.

1. Record every **INTENDED** target. Only one API patch may be submitted/accepted
   at a time. Use Pod UID and resourceVersion to reject stale ownership/writes.
2. Record **ACCEPTED** only after an explicit server acknowledgement. An unknown
   acknowledgement is not rejection and cannot permit a second patch.
3. Kubelet pending/error conditions are **DEFERRED** evidence, not enforcement.
   Retain desired, allocated, status and cgroup state and the raw reason.
4. While the accepted operation or application window is outstanding, record each
   new **SKIPPED_OPPORTUNITY** and retain one latest unsubmitted target. Replace
   an older unsent target with **SUPERSEDED_BEFORE_SUBMISSION**. An already
   accepted server patch is never silently cancelled or overwritten.
5. A resolved target gets **PHYSICALLY_ENFORCED** / **ENFORCEMENT_COMPLETE** only
   after all gates below. For memory this means reservation metadata reconciled
   and the fixed cap verified, not reclaimed physical pages.
6. A no-op requires the same reconciled gates and records **ACCEPTED_NO_CHANGE**;
   there is no fabricated patch acknowledgement or zero patch latency.
7. After the mechanical response window, release the latest queued target. Never
   overlap patches or pretend a superseded intent was physically enforced.
8. The existing engineering 60s watchdog bounds unresolved dispatch/ACK/actuation;
   a separate 60s window watchdog starts at enforcement. Expiry is a terminal
   right-censored operational failure, with latency unset and accepted state kept
   for postmortem. It is not a compression acceptance criterion or a finite
   enforcement latency. Cancel unsubmitted queued intents explicitly. No auto-retry.
9. Explicit API rejection, unknown ACK, infrastructure/identity failure and
   application failure remain distinct. Late callbacks cannot relabel terminal
   failure. Operational harms are retained, not selectively rerun or erased. A
   terminated trial cannot manufacture a completed 48h resource endpoint.

B removes the known variable-memory-limit admission predicate, not every possible
capacity/error condition. Every intended decision has an auditable disposition;
not every intent is promised physical enforcement. Prospective outcome analysis
must include supersession/skips, terminal failures and censoring.

## Enforcement and application window

**ENFORCEMENT_COMPLETE** requires patch ACK, expected spec, allocated reservation,
status resources, observed generation, CPU cgroup quota, fixed memory.max,
resolved resize conditions, Ready, and unchanged Pod/application identity with
no restart/OOM. Both Pod and admitted telemetry observations must follow ACK;
admission and read must follow physical local monotonic order. Original cluster
source causality, zero future tolerance and 2s age semantics stay unchanged.

A distinct mechanical/healthy window then requires an explicitly captured
in-flight request registry at enforcement, all those requests drained, at least
20 completed post-enforcement requests with unchanged verified work, no failed
requests in that window, and at least **5 physical seconds** of observation. The
5s basis is the configured HTTP-I/O timeout interval, not a total-request deadline
or a fitted stability tolerance. Waiting 5s alone never proves drain; the explicit
in-flight registry must reconcile every captured request. Twenty
responses retain the previously declared engineering progress window; they do
not establish a stable latency distribution. At lower RPS collection takes longer.
Failures are recorded even when they prevent the next actuation.

`APPLICATION_STATISTICALLY_SETTLED` remains **UNRESOLVED**. No mean/p95 tolerance,
confidence rule or stationarity cutoff is inferred from these engineering facts.

## PATH U and shortest defensible physical study

Retain physical 300s host-receipt `[start,end)` buckets, at least 50 observations
and at least 270s receipt span. Keep real RPS, per-request work, scenario periods,
source-monotonic CPU rates and physical admission order. No logical compression.

PATH C could define a different short-time system estimand, but preserving 288
logical slots and cadence ratios is not enough to validate the original one.
With fixed real RPS, shortening physical slots changes request exposure,
averaging support, information/noise, workload phase speed and physical policy
windows. Initial genuine 300s bootstrap buckets would also differ in support
from shortened streaming buckets. Timing-path feasibility alone cannot establish
unchanged conclusions; statistical settling/equivalence is not demonstrated.
There is no first-principles polling rule that by itself proves that equivalence.
No accelerated protocol is approved or given a candidate duration in this freeze.

For a future, separately authorized v2 study, reuse the qualified real 24h/288-slot
bootstrap within block #1, with fresh independent runtime state for each treatment.
Retain the existing **48h measurement = 576 real 300s slots per treatment** and
predeclared 15m cooldown + 30m warmup. Do not reacquire a 24h bootstrap for each
treatment or shorten exposure based on fast resizes. Initialization/initial
actuation stay measured costs. A five-method/four-scenario block is 960 measured
host-hours plus 15 startup hours if serial; this is a budget illustration, not a
chosen repetition count or an authorization to execute it. Precision, repetition,
randomization and controlled-host gates remain outstanding.

## Verification and remaining gate

Offline tests cover request/limit/QoS separation, all enforcement gates, old
clocks/admission, superseded unsent targets, no overlapping patches, ACK uncertainty,
terminal timeout censoring, no-op distinction, response-window/drain requirements,
and immutable base manifests. They are UNIT fixtures, not Kubernetes evidence.

The frozen engineering plan uses PW-6h only: natural request down to 64MiB with
1GiB cap, CPU up/down, reservation up/down, no-op and consecutive intents; queue
250m/128MiB then 500m/256MiB while the first accepted target awaits reconciliation
and verify only the latest unsent target is released after enforcement/window.
Verify QoS stays Burstable, actual request/status/allocated accounting agrees,
memory.max stays 1GiB, CPU quota matches, resize conditions clear, no restart,
no overlapping patches and no hidden pending state. Capture the immutable
bootstrap/history/threshold identity and all counters. This has **not run**, at
the user's explicit offline-only direction. No fresh B runtime result is claimed.

V7C.11 therefore remains **BLOCKED on actual-cluster B verification**. The code and
prospective decision can be reviewed at this commit; no live action is authorized
by this document. V7C.12 cannot silently bypass this gate or treat it as approval
of accelerated outcomes. Any live verification needs a new execution instruction
and the existing AC/open-lid guard; no additional permission is requested here.
