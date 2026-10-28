# V7B — System calibration and confirmatory-freeze preparation

**STATUS: BLOCKED. There is no completed V8 confirmatory freeze.**

This document distinguishes implemented preparation from unperformed calibration.
The versioned draft is `configs/system_trials_v8_draft_v1.json` (`system-trial-preparation-v1`).
Neither calibration execution nor comparative execution is enabled. Numeric
operational margins, CI precision targets, hardware reservation, practical
repetition cap and final repetition count are intentionally unset.

## Evidence and disposition

| Requirement | Current evidence |
|---|---|
| Measured initialization | Exact-grid raw-sample validation and production-factory initialization implemented; unit fixtures only |
| Real 24h measured bootstrap | **NOT DEMONSTRATED** |
| Stable + dynamic calibration | **NOT RUN**; no variance or bootstrap-variability estimate |
| Repeated isolated trial runner | Identity-only ordered plan implemented; continuous Kubernetes campaign executor **NOT IMPLEMENTED** |
| Overhead attribution | Component boundaries specified; full component instrumentation **NOT DEMONSTRATED** |
| Operational criteria | **BLOCKED**: no approved application error/resource/churn/overhead budget found |
| Repetition count and practical maximum | **NOT FROZEN**: calibration, justified precision targets and compute budget missing |
| V8 comparisons | **DISABLED** |

V7A's single synthetic-bootstrap smoke remains plumbing evidence only. It must not
supply run-to-run variance, operational benefit, bootstrap variability or a
calibration-derived N. Its generated outputs are unchanged.

## Measured bootstrap contract

Preserve 300-second nominal slots, `causal-timeline-v3` and
`refresh-accounting-v1`. Keep the fixed 1000m CPU /512MiB normalization reference,
the five existing factories, V7A controller, workload shapes and seed unchanged.

The proposed engineering campaign has 15min cooldown, fresh cluster/application/
Prometheus/profile/controller state, 30min actual stable warm-up, **24h actual
stable bootstrap**, then 48h measured scenario. Warm-up and cooldown values are
preparation choices, not thermally validated freeze evidence. No time compression
or reuse of another run's bootstrap is permitted.

Let bootstrap cover `[b,b+24h]` as 288 completed source buckets closing at
`b+5min ... b+24h`. Raw source sample times must be within each source bucket,
finite and nonnegative, and receipt must not precede source time or exceed the
actual initialization read. Each accepted bucket uses the V7A aggregation rule
(at least50 samples spanning270s, one application instance, no counter resets).
All buckets must refer to the same application instance, with no counter reset
between them. Missing buckets stay missing; never fill, repeat or interpolate.
The fixed bootstrap must retain at least200 paired finite slots and the last96
consecutive slots must be complete. Failure rejects that bootstrap, without
extending its endpoint until favorable data appear.

Thresholds use only valid bootstrap observations. Initialization uses the
unchanged production contract: Static whole bootstrap; PW cadence-length trailing
bootstrap window; Full-Rewrite trailing24h. Runtime windows remain `(t-24h,t]`
with the existing gates. Initialization remains one separate event, zero runtime
refreshes. Explicit receipt/source checks reject future data, duplicate buckets,
bootstrap warm-up contamination and synthetic-smoke role labels.

`MeasuredProfileAdapter` implements this initialization in memory. It is **not**
yet a deployed continuous measured-bootstrap HTTP service. Unit fixtures labelled
as raw samples test validation only; a JSON role label cannot independently attest
physical measurement. A real run additionally needs source UID, collection lineage,
managed hashes and environment evidence from the actual collector.

## Transition and continuous-run requirements

A future executable campaign must start the generator and collector before
bootstrap and keep them running without an observation gap. Bootstrap resources
stay fixed at the V7A initial allocation. At nominal close q, scenario workload
switches on the fixed clock; completed bootstrap is made visible only after q
and its receipt. Threshold/profile initialization and the first identical consumer
recommendation/actuation occur after that visibility point. Their delay, churn
and request consequences belong to the measured interval; do not hide them in a
policy-specific settling phase. Initialization cannot consume streaming buckets.
Periodic grids stay anchored to q, regardless of actual processing delay.

Measurement spans `[q,q+48h)` on actual time. Source and availability times,
actual reads, requests and actuation confirmations must be retained separately.
Clock events continue independently of telemetry availability. A collector must
not stop polling while the controller waits on a resize. This requires a genuine
continuous executor, not looping the V7A one-bucket smoke.

## Controlled execution and proposed ordering

Pinned stack: kind0.33.0, Kubernetes/kubectl1.35.8, V7A image digests, controller
`p95-fixed-headroom-quantized-v1`, fixed scenario seed20251022 and 30,000 CPU-work
iterations. The optional local CLI binaries remain ignored; no global install or
version change occurs in this task.

Before execution, reserve one awake, mains-powered host without competing
experiments. Fingerprint host CPU model, architecture, physical/logical CPUs,
memory, OS, Docker CPU/memory/cgroup settings, exact images, Kubernetes and CLI
binary versions. Scientifically relevant hardware belongs in compatibility;
hostname and paths remain execution metadata. Record host load, background-process
CPU/memory, power, available thermal diagnostics, wall/monotonic deltas and node
conditions. Unavailable thermal information must remain unavailable. No arbitrary
"idle" threshold or thermal acceptance budget has been validated here.

The proposed neutral method is **PW-6h only**, unchanged consumer and parameters.
Calibration scenarios are **stable and periodic** (7h period). The draft proposes
three independently recreated runs per scenario to obtain an initial run-variance
estimate; three is not a claim of adequate precision. Rank scenario/method
identities by a seeded hash, then use cyclic block orders. The future five-method
plan balances positions over five blocks; ordering depends on identities and seed,
never outcomes. There is no backfill, reused bootstrap or parallel trial on the
same host.

Six calibration runs cost at least **436.5 serial host-hours =18.1875 days** under
this proposal, excluding cluster setup and failures. One full repetition of five
methods × four scenarios costs at least1455 host-hours =60.625 days. A repetition
cap and total compute budget require an explicit feasibility decision. These are
schedule calculations, not observed runtime or calibration evidence.

## Failure and retry policy

Retain all attempts and reasons. No automatic retries. Infrastructure invalidation
includes source/input drift, sleep/clock failures, unusable fixed bootstrap,
missing required measurement/provenance and environment mismatch. Correctness
fixes require source versioning and comparable reruns. Host exclusions must be
decided from infrastructure evidence, before method summaries are examined.

SLO failures, workload errors, OOMs, rejected/deferred resizes and churn are
**operational outcomes**, not outcome-based exclusions. A continuous runner must
keep the load/collector active and retain these harms; V7A's fail-fast smoke is
not suitable as the repeated-trial executor. One outstanding resize and actual
status/cgroup confirmation remain mandatory; unresolved resize behavior must be
implemented consistently before calibration. Do not silently roll out/restart
or overwrite pending requests.

## Endpoints and operational criteria

Independent run/scenario is the unit. Requests and slots are correlated within a
run and cannot be used as independent replicates.

Primary scalar endpoints:

- SLO violation rate: failures/timeouts/drops or latency beyond the stated target,
  divided by all offered requests.
- Successful-request p95 arrival-to-completion latency, with failures reported
  jointly; missing p95 when no successful requests is not zero.
- Mean requested CPU cores and mean requested memory bytes, measured over fixed
  actual time; account for exact confirmed change boundaries.
- CPU and memory resource-time utilization efficiency, separately.

Secondary: p50/p99 latency, throughput, observed under/over-provisioning proxies,
resource changes/churn, recommendation/actuation delays and maintenance CPU/RSS/
runtime. Limits censor demand: zero observed deficit does not prove absence of
under-provisioning. Pair resource outcomes with SLO/throttling/OOM evidence.

The existing250ms latency threshold and20% headroom are V7A engineering choices.
They do **not** justify an error budget, allowed SLO-harm margin, meaningful CPU/
memory saving, efficiency improvement or churn/overhead budget. No approved
operational contract or deployment-specific valuation was found in the inspected
system configs/docs. Numeric criteria therefore remain **null**. Required inputs
are an attributable application SLO/error budget and resource/control/maintenance
budgets, with rationale, units and comparison direction. Neither Materna/Google
effects nor favorable smoke/pilot metrics can supply those inputs.

## Calibration and precision planning

No calibration results/manifests exist from this task. No SD, variance, confidence
interval or N is reported as observed. A future campaign must produce managed
purpose=pilot outputs, source clean and committed, raw measured-bootstrap lineage,
per-run endpoints, component diagnostics, failures and SHA-verified outputs.
Smoke/pilot caches must never satisfy a claim request.

`conditional_precision_plan` is a testable planning utility, not a frozen sample
size. It takes independent run-level calibration endpoints, an externally justified
CI half-width target and a practical N cap. Under explicit normal-endpoint
assumptions it uses a one-sided95% chi-square upper SD bound, and searches N using
Student-t95% half-widths. A conservative contrast SD bound of twice the neutral
SD envelope permits unknown covariance. The **unproven** assumption remains that
both compared methods' SDs lie within that neutral envelope. This is not a power
or significance search and does not guarantee precision for other policies.
Zero observed variance blocks planning instead of implying small N is adequate.

For bounded, degenerate or non-normal endpoints, especially an all-zero SLO rate,
this approximation cannot justify final N. Freeze a suitable bounded/distribution-
robust plan after the operational precision target is justified. Do not quietly
swap inferential methods after confirmatory outcomes. Choose final N to cover all
primary endpoint precision goals; report infeasibility if the required N or total
host-hours exceeds the declared cap. No cap or precision goals have been invented.

## Overhead attribution requirements

| Component | Required measurement boundary | Current readiness |
|---|---|---|
| Application | own cgroup CPU, memory, throttling/OOM | V7A instrumentation available |
| Telemetry | Prometheus container and separate collector process; include probe cost | full attribution unimplemented |
| Profile maintenance | separate service process CPU/RSS, step CPU/wall, startup versus warm-up versus steady state | V7A partial; measured service integration unimplemented |
| Controller | separate process from generator; thread CPU for local computation, own RSS/CPU | unimplemented; V7A process timer includes cohosted generator CPU |
| Actuation | API submit/acknowledge, status generation and actual cgroup enforcement | single-resize V7A proof; recurrent failure retention unimplemented |

Do not label process CPU deltas from a shared generator/controller process as
exclusive recommendation cost. RSS includes runtime/libraries; profile serialized
state size is a separate quantity. Do not subtract unrelated-machine timings.

## Tooling and remaining gate

```sh
.venv/bin/python -m dynapm.scripts.task33_system_trial_preparation --help
.venv/bin/python -m dynapm.scripts.task33_system_trial_preparation
```

This command reports the blocked draft and identity-only calibration plan. It
cannot launch Kubernetes, accept `--run`, compare methods or invent a completed
measurement. `measured_bootstrap` and `MeasuredProfileAdapter` are tested library
preparation, not evidence of a real collector/executor run.

**V7B = BLOCKED. V8 = BLOCKED.** Resolve operational budgets and host feasibility;
implement the continuous isolated runner/attribution; perform valid real-bootstrap
calibration; then freeze justified margins, precision targets, N and total budget
before any comparative trial. Existing V7A/Google/Materna artifacts remain intact.


## Preparation verification record

Lightweight suite: **568 passed, 0 failed, 1 skipped**. Python parse/import,
CLI report, rejection of an execution flag, and preserved V7A output/hash/cache
checks passed. Draft SHA-256: `b8f026bd210dbf488f7e0d82a38b9129b292e5ca6eb615e92f068f316a341410`.
There is **no calibration experiment fingerprint, output manifest or empirical
variance** from this task; this is not a completed managed calibration run.
A separate local host inventory captured hardware, power, thermal-status command
output, load and process metadata. It was collected after unit tests on an
unreserved host, and is explicitly not a quiet baseline or calibration.
No Kubernetes resources were created and no policy comparisons were executed.
