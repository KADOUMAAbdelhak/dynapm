# V8C-R.2 direct-Service primary executor

Scientific source remains fe3b870149a156e7fecb88741d51cfb5c1ed86d7.
Qualified request transport remains b3fd0d1; all its files remain unchanged.
The new primary adapter, CLI, checkpoint component, tests and documentation are
additions to that tree. Exact commit/branch and every addition's hash are bound
by a separately sealed prospective executor specification.

## Frozen lifecycle mapping

| Original primary | Service primary |
| --- | --- |
| UUIDPowerGuard and 900-second cooldown | Same guard and physical cooldown |
| local_kind | start_stack with same pinned stack and no application forwarder |
| host stream_requests | Pod scheduler calling unchanged qualified request/offer helpers |
| 1800-second reference warm-up | Exactly 21600 high12 offers on the generator clock |
| T0 recommendation and patch concurrent with load | Source T0 marker, host receipt, recommendation, same actuate/confirm |
| 1800-second primary window | Same fixed offer offsets, with 900-second periodic switch |
| five-second source/host receipt telemetry | Same NodeObserver/ObservationClock, no application diagnostic gate |
| six validated 300-second buckets | Same aggregate_bucket and immutable receipt timestamps |
| frozen request/resource arithmetic | Same functions, with explicit additional failure-class counts |
| attempt sealing | Raw seal and independent node/host verification, cleanup, manifest and slot checkpoint |

Cluster preparation, the original ten-second generator lead, request drain and
sealing add engineering overhead to the nominal 75-minute phase budget. They do
not shorten or extend the scheduled 30-minute exposure.

## T0 and clocks

The user chose the frozen T0 rule: enforcement latency is included in transition.
No enforcement-complete gate delays the measured offers. Snapshot identity and
expected target are bound before the generator starts and recomputed at T0.

The generator defines one Linux monotonic origin after its ten-second lead and
1800-second warm-up. It writes an atomic/fsynced T0 marker on the first measured
offer, then schedules all remaining offsets unchanged. The host has already
started a blocking Kubernetes exec observation of this marker. Application
requests still travel only through the Service; this exec is control evidence.
The marker/watch timestamps are in the same Linux boot/time namespace. The host
records its own request and complete-response receipt. Program order brackets
the source T0 between those host observations; the host uses receipt/admission
as its controller/resource origin. No Linux/macOS monotonic epoch subtraction or
cross-domain wall comparison establishes causality.

A prospective two-second maximum observation bracket is an engineering
observability ceiling; it adds no future tolerance and changes no telemetry
admission rule. The actual bracket and source-marker emission delay are retained.
This does not claim physically simultaneous observations across domains: the
resource origin is host receipt and request origin is the source event. Their
alignment has the recorded observation uncertainty. Old host-forwarded latency
measurements are not numerically combined with this campaign. A missed/late
watch, wrong clock identity or over-wide bracket invalidates the attempt.

## Storage model

An individual generator raw stream is capped at 64 MiB; crossing the cap records
an interrupted/undefined measurement, never silently dropping scientific rows.
Host observer writes have a 64 MiB cap, and total slot output is monitored against
144 MiB. These are engineering fail-closed budgets, not altered scientific data.
Before every owned write, atomic records/observer writers check reserve/buffer;
source/clock/host acquisition keeps its frozen implementation. An independent
observer also monitors host free space and total output. A 22 GiB operational
buffer is above the unchanged 20 GiB absolute reserve. Infrastructure writes are
covered prospectively by 3 GiB Docker growth plus 512 MiB safety. An unexpected
budget excursion invalidates rather than truncates an accepted endpoint.

Start requirement = 20 GiB + remaining_slots*144 MiB + 64 MiB node/host overlap
+ 3 GiB Docker growth + 512 MiB safety. For 18 slots this is 26.09375 GiB. The
full physical qualification must independently measure these quantities before
claim execution is considered ready. The thin Docker backing store is monitored
at host level; guest filesystem free space is not treated as host free space.

## Ownership, resume and host sessions

The slot checkpoint and exclusive lock span each owned session. The campaign
identity binds science, executor, contract, snapshots, transport amendment and
scope, but excludes current host-certificate paths/hashes. Each next slot runs a
full preflight and binds its separately verified session certificate. Reboot
never inherits a previous boot's qualification; a new boot needs an explicitly
approved matching certificate. Sealed earlier treatments remain immutable.

A fresh cluster, application UID, container, controller and telemetry identity
are created per slot. No previous cluster is used. Missing or invalid earlier
slots prevent advancement. RUNNING after restart becomes INTERRUPTED, retains
partial evidence and requires review; there is no halfway resume or automatic
replacement. Invalid attempts remain sealed and halt execution.

--max-slots and --stop-after-slot act only after verified sealing and cleanup.
The 18 primary cells remain fixed. The non-claim qualification uses the same
executor and first low-target periodic cell in its own scope/root. It cannot be
loaded into the claim checkpoint or analysis.

## CLI

Use `.venv/bin/python -m dynapm.scripts.task48_v8_service_primary` with explicit
--spec, --spec-sha256, --root and --scope. Diagnostic qualification additionally
requires --authorize-diagnostic; run with --max-slots 1. A claim session requires
--authorize-claim, --qualification and --qualification-sha256, and its record must
bind this exact executor/specification, passing lifecycle evidence and certified
storage. No claim execution is authorized by this implementation task.

Example bounded session: add --max-slots 3; later use the identical claim root
and identity with --resume --max-slots 3. Alternatively --stop-after-slot 6 stops
after slot 6. Stop boundaries already reached do not launch an extra cell.

After all 18 valid claim cells, the frozen paired_analysis function runs over
only the new checkpoint's manifests. No partial endpoint is extrapolated and no
old port-forward result is read as a treatment outcome.

## Failure taxonomy and qualification

Application errors, deadlines, connection refusals and cap drops are retained as
outcomes. No zero-error condition gates validity. Missing or duplicated records,
failed clock/provenance/telemetry checks, generator lifecycle failure or failed
collection invalidate an endpoint. Unfinished resize watchdogs remain explicitly
right-censored operational failures, never fabricated finite latencies.

Unit tests use synthetic clocks and orchestration fixtures and are labelled as
such. A passing physical 900/1800/1800-second non-claim execution, independent
raw reconstruction, reserve verification and cleanup proof are required in a
separate qualification record. Incomplete or blocked qualification is not READY.

## Docker reference resolution correction

The first qualification preflight at ee7950d stopped before cooldown, cluster
creation or generator launch: shorthand image lookup failed despite the exact
pinned image IDs being present. Explicit docker.io/library aliases resolved
to those same IDs. The corrected primary adapter canonicalizes only these two
local references in runtime copies, checks their exact frozen IDs, and records
frozen-reference → canonical-reference → ID. It passes the same canonical
names to kind loading and Pod manifests. Frozen config files, image content,
kind digest and request/actuation semantics remain unchanged. No rebuild/pull
or scientific input substitution is performed. The failed PENDING-only campaign
and its original prospective seal are preserved; a corrected commit/specification
requires a fresh qualification root.

## Explicitly non-qualifying battery mechanics mode

The user separately authorized a full battery-powered mechanics test, labelled
DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING. This is not AC qualification. The strict
preflight and UUIDPowerGuard branches remain intact and still reject battery.
A separate BatteryDiagnosticGuard observes discharge, source transitions, exact
boot, open lid, unchanged power policy and the unchanged 2 s/30 s continuity
bounds. It owns an idle-sleep assertion only; it does not claim the AC-only
PreventSystemSleep qualification on battery.

This mode requires power_mode=BATTERY_DIAGNOSTIC_ONLY in its prospectively sealed
specification and --authorize-battery-nonqualifying. It runs the identical
primary treatment body and frozen schedules, but all intents/checkpoints,
generator records and power evidence are labelled non-qualifying. SEALED_VALID
inside this scope means complete executor mechanics only. Claim qualification
and outcome eligibility are false. A distinct diagnostic admission status cannot
admit a strict slot. The claim launcher requires a separately hashed strict-AC
primary-lifecycle qualification with explicit eligible/schema/mode fields and
cannot consume battery evidence. Later AC qualification must be a new full run
under the unchanged strict gate; no mid-run or retrospective promotion exists.

## Readiness classification correction found by the non-qualifying test

The a41c986 battery test stopped at the 600-second exposure check. All independent
resource gates passed (70m CPU, 64MiB allocated reservation, 1024MiB cgroup cap,
correct spec/status/generation/container, no pending resize); only Pod Ready was
false. Kubernetes separately recorded a timed-out HTTP readiness probe. The
frozen verifier had incorrectly combined this application outcome with physical
resource enforcement. The failed attempt remains SEALED_INVALID and is not
retroactively promoted; it lost the remaining controller measurement window.

`primary_actuation.py` is an additive, versioned harness correction. It retains
all physical patch, serialization, censoring and watchdog logic, and every
independent resource gate. It records readiness separately as an application
observation. It does not disable or alter readiness probes, Service routing,
resources, workloads, snapshots, windows or endpoint denominators. Readiness
failures and their request consequences remain outcomes. No low-resource point
is excluded. The original frozen verifier/runtime files remain unchanged.

Regression tests use a copy of the actual non-qualifying failed frame and prove
that readiness alone cannot invalidate resource enforcement, while wrong CPU,
cap, spec/status, allocation, generation, container identity, pending resize,
stale evidence and restarts still fail closed. The fixed harness requires a new
complete physical qualification; neither the failed battery attempt nor its
separately recovered request stream qualifies the amended executor.

Completed analysis is finalized even when --max-slots or --stop-after-slot ends
exactly at slot 18. It first revalidates every new claim slot and the frozen
snapshot seal, then calls the unchanged frozen paired-analysis implementation.
Repeated finalization is idempotent; a changed prior analysis fails closed.
Diagnostic and battery scopes cannot create primary paired results.
