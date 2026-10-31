# V7C.1 calibration clock diagnosis

Historical analysis; the old cross-domain invariant is superseded prospectively
by [V7C.6 clock domains](system_clock_domains.md). Original failed evidence is unchanged.

## Disposition

ROOT_CAUSE_NOT_YET_PROVEN. Campaign `bdc6371f797b4206869068bc6aefd383`
failed at 2026-10-29T02:53:22Z during warm-up, before bootstrap. It attempted
one PW-6h stable run, completed none and exited without starting a second trial.
The historical run and campaign are preserved unchanged. There is no reusable
bootstrap or 48h anchor from that attempt.

## Forensic timestamp path

`application.read_cgroup()` reads Linux cgroup counters then calls integer
`time.time_ns()` in the container. The instrumented HTTP handler serializes this
integer directly to JSON. Previously `smoke.http()` completed `json.load(response)`
before the host collector called `time.time_ns()`. Thus an early host receipt
capture is not evidenced. No timezone parsing, float conversion or unit scaling
occurs in the source/receipt comparison. Local timestamps use different wall-clock
domains (Linux Docker VM and macOS host). Their synchronization is not assumed.

All 340 persisted samples pass the old check. Source timestamps span
1693.046312950 seconds; receipt minus source ranges 945078 to 7669042 ns.
The failing sample was checked before persistence. Neither its sign nor magnitude
is recoverable. Saved diagnostics report AC power and no thermal warning; those
do not establish clock synchronization. Application/controller logs contain no
explanation. The source check allowed a source-age of up to 2s but no future skew.

Possible mechanisms: source/host clock offset or step (including VM time sync),
a wall-clock adjustment during transport, or response/collector scheduling delay
exceeding 2s. A forward host step and backward source step can violate the age
bound; forward source/backward host can cause source-ahead. Monotonic clocks
cannot establish the cross-host epoch offset. Network/JSON delay ordinarily makes
receipt later, not earlier. Duplicate/stale/out-of-order responses were not
distinguished by the old check; now they fail explicitly. No evidence establishes
any of these as the historical cause. Do not claim an NTP correction was observed.

## Preserved clock semantics

Wall-clock availability remains causal. Exact integer nanoseconds are required:
`0 <= receipt_ns - source_ns <= 2000000000`. One nanosecond ahead fails; the
2s boundary is accepted. This does not widen the previous tolerance.

`receive_observation` captures receipt immediately after the complete body read,
before JSON decoding. This is a precise boundary improvement, not a proven fix
for the failed attempt. Request-start and receipt wall/monotonic pairs diagnose
local transport. Source responses include same-container wall/monotonic pairs,
hostname and PID. Only differences inside a monotonic domain are compared.
Host elapsed-time drift retains the existing 2s failure bound. Duplicates,
out-of-order source times and instance changes fail closed rather than entering
history. Source wall/monotonic discontinuities also fail explicitly.

## Rejection evidence

Schema `system-clock-observation-v1`. Rejected responses go only to
`outputs/clock_rejections.jsonl`, never accepted telemetry or bootstrap history.
Records retain exact base64 response bytes and SHA-256; raw parsed sample; source,
receipt and previous accepted timestamps; signed ns/us/ms delta; sequence index;
instance identity; request/receipt monotonic clocks; record wall/monotonic clocks;
exact invariant; run ID, source commit and experiment fingerprint. Each record is
checksummed and fsynced before raising. `clock_evidence_manifest.json` binds both
rejected and accepted diagnostic streams. The exception carries its file hash,
which `RunSession.fail()` persists in FAILED/manifest error metadata. Thus failure
does not depend on a SUCCESS output manifest. Success includes all diagnostic
files in the ordinary output manifest. Validate with `validate_clock_evidence`.

## Replacement boundary

No old attempt is promoted, modified, resumed or relabelled. Calibration remains
neutral PW-6h, 24h measured bootstrap +48h stable measurement, original controller,
workload, timing and accounting. First run the existing `--plumbing-check` from a
clean commit: one real 300s bucket, no profile initialization, no comparison.
If it passes managed provenance and clock evidence validation, a replacement may
be attempted as a new generation. A short check cannot prove clock stability for
72h; retain fail-closed checks. Use `--run-calibration --maximum-trials 1` to
prevent automatic continuation beyond the replacement anchor. No automatic
retry; a further failure requires inspection. No shared bootstrap or compression
implementation is authorized by this correctness fix.

## Later execution prerequisites

The V7C.1 one-bucket check above was a historical correctness prerequisite.
V7C.3/V7C.4 supersede it for long execution: require validated >=3h compatible
host-runtime endurance evidence and the [host operating contract](host_execution.md).
A short smoke alone does not authorize another anchor.
