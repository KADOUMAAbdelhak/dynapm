# V7A — System-validation design and harness

Version: `system-profile-provisioning-v1`. This is an engineering freeze for a
local plumbing smoke. Comparative and claim-generating execution are disabled.
The numerical settings below are predefined engineering choices, not calibrated
from Materna, Google or historical publication outcomes. Their adequacy for a
repeated system study remains to be reviewed before V8.

## Operational question and experimental unit

How do Static, PW-12h, PW-6h, PW-3h and Full-Rewrite maintained observation
profiles affect the **same** resource recommender, enforced CPU/memory allocation,
application SLO and resource use? No adaptive detector or prediction is included.
The independent unit is a fresh run/scenario replicate, never a request or
telemetry sample. This scaffold establishes interfaces, not operational benefit.

## Frozen loop and policy isolation

`open-loop workload → real HTTP application → completed telemetry bucket →
profile service → fixed resource recommendation → Pod resize → observed outcome`.

A two-node local kind cluster separates the workload worker from Prometheus on
the control-plane node. A host generator uses localhost `kubectl port-forward`.
The profile service is a separate host Python HTTP process, allowing its CPU,
RSS and per-step time to be measured separately from the controller. Prometheus
scrapes the in-cluster application every five seconds; the host also captures the
profile service's Prometheus-compatible exposition. This is a real hybrid local
harness, not a claim that every component is deployed as an in-cluster service.
Port-forward overhead is part of this environment; production ingress performance
and independent hardware isolation have not been established.

`ProfileAdapter` uses the existing `confirmatory_execution.factory_for` five-policy
mapping without changing its source. Static initializes from the whole bootstrap;
PW initializes from its cadence-length trailing bootstrap window; Full-Rewrite
initializes from trailing 24h. PW runtime content is trailing `(q-24h,q]`, at least
200/288 paired finite slots with the inherited 96-complete-slot eligibility gate.
Full-Rewrite writes at every observed slot with at least 200 paired trailing slots.
Static never refreshes after initialization. Periodic grids remain anchored to the
bootstrap end, coalescing delayed ticks without re-anchoring. Initialization,
refresh operations, field writes and changes retain `refresh-accounting-v1`.
Legacy `predicted_*_p95_next_24h` schema fields are observation summaries here;
the field name does not imply a trained forecast or new predictor.

## Clocks, measurements and causal visibility

Actual cgroup-v2 readings are sampled every five seconds. The nominal five-minute
bucket is `[b,q]`, `q=b+300s`. CPU is the cumulative-usage difference divided by
the actual in-bucket source span. Memory is the mean actual working-set bytes
(`memory.current - inactive_file`, bounded below by zero). At least 50 distinct
samples covering 270 seconds and one uninterrupted application instance are
required. Counter resets invalidate a bucket. No extrapolation, filling,
interpolation or clipping of utilization is performed. Container/host clocks must
agree within two seconds. Absolute source and receipt timestamps are retained.

A bucket is visible only after q and its latest receipt. The profile adapter
checks source times and availability before modifying state. It commits the
production policy step at nominal closing slot q. Actual receive/commit/read
wall times remain separate and recorded. An absent bucket remains absent and may
never be backdated into an earlier controller read. For future operational runs,
reads occur on wall time after completed data become visible; offline hourly
fidelity clocks remain `phase-balanced-hourly-v1` and are not time-compressed.
A scientific forward-profile diagnostic, if added later, must retain the exact
`(q,q+24h]` 288-slot target protocol and delayed verification. It is not computed
in this smoke.

Normalization uses immutable per-application reference **1000m CPU / 512MiB**,
never the changing current requests. Bootstrap thresholds are computed once from
the bootstrap only and classes are diagnostic. The downstream consumer consumes
only maintained CPU/memory p95, converted back through those fixed references.

## Fixed recommendation and actuation contract

For each resource, `ceil(1.2 * maintained_p95 / quantum) * quantum`, then clamp:

| Resource | Quantum | Minimum | Maximum |
|---|---:|---:|---:|
| CPU | 10m | 50m | 1000m |
| Memory | 4MiB | 64MiB | 512MiB |

Requests equal limits throughout (Guaranteed QoS). Initial deployment is 1000m /
512MiB. Future decisions use a fixed 300s cadence, write only changed quantized
resources, and permit one in-flight resize. No latency feedback, ADWIN, learned
content, adaptive gains or policy-specific controller parameters exist. The V7A
runner intentionally executes only one decision; a recurrent comparative trial
runner is a separate V8 prerequisite.

Actuation uses Kubernetes Pod `/resize` with `NotRequired` restart policies.
Accepted API patches are insufficient: the smoke requires desired spec, actual
`status.containerStatuses[].resources` and measured cgroup limits all to agree,
with unchanged Pod UID/restart count and successful post-resize requests. Deferred,
rejected or timed-out changes fail the smoke; there is no rollout fallback.
Namespace RBAC permits the controller only to get `application`, and to get/patch
its named `pods/resize` subresource (kubectl reads it before patching). A server-side
dry-run validates this path before workload collection and verifies that actual
allocations remain unchanged. Administration credentials are used for isolated-cluster
setup only; controller calls impersonate that restricted service account.

## Workloads frozen before outcomes

CPU work is deterministic PBKDF2 with 30,000 iterations/request, seed 20251022.
Memory working sets are allocated and touched by the application. Requests arrive
open-loop with bounded concurrency 32, timeout 5s; generator overload is recorded
as dropped offered work, not silently removed. Exact trace/seed are shared across
all future methods.

| Scenario | Offered requests/s | Workset | Timing |
|---|---|---|---|
| Stable | 4 | 32MiB | constant |
| Periodic | 2 / 12 | 32 / 96MiB | 7h cycle, half low/half high |
| Burst | 4 / 20 | 32 / 160MiB | 20min every 5h, first at 1h |
| Abrupt shift | 4 → 12 | 32 → 96MiB | at 24h |

Proposed future runs have actual 24h stable bootstrap and 48h measured scenario,
with fresh state, no compressed policy time and no synthetic bootstrap. These
runs are **disabled** pending precision/power planning, trial counts,
randomized/counterbalanced order, practical-benefit/harm margins, platform review
and separate authorization. Do not tune scenarios using policy outcomes.

## Operational endpoints and denominators

| Endpoint | Definition |
|---|---|
| SLO violation | failures/timeouts/drops or arrival-to-completion >250ms, divided by **all offered** requests |
| p50/p95/p99 latency | successful arrival-to-completion seconds, includes generator lag; failures/timeouts reported alongside, not hidden |
| Throughput | successful completions inside fixed window / window seconds |
| CPU/memory requested | desired Pod resources, actual status and actual cgroup enforcement, with timestamps |
| CPU/memory used | cumulative CPU-counter rate and actual cgroup memory working set |
| Utilization efficiency | integral used / integral requested, CPU and memory separately |
| Over-provisioning | integral max(requested−used,0), core-seconds / byte-seconds; not monetary cost |
| Under-provisioning | observed deficit integrals plus CPU throttling, OOMs and SLO; limits censor latent demand, so deficits are lower-bound proxies |
| Changes/churn | actual resource changes and sum absolute CPU/memory allocation changes, separate from profile refresh count |
| Recommendation latency | snapshot read through recommendation computation; wall and process CPU seconds |
| Actuation latency | submission to actual status **and** cgroup agreement; failures/defer/restart recorded |
| Maintenance overhead | separate service process CPU/RSS, per-step wall/CPU time, profile state bytes, canonical refresh/write/change counters |

Run-level summary and uncertainty belong to repeated trials. A successful smoke
is not evidence of acceptable cost, better SLOs or practical superiority. The
service CPU/RSS currently includes HTTP process/runtime overhead; a future V6/V8
benchmark must isolate warm-up, steady-state and scale effects.

## Reproduction and safety

Inputs: `configs/system_validation_v1.{json,yaml}`, Dockerfile, versioned kind and
resource manifests, exact smoke fixtures and source hash inventory. All results
are generated under ignored `results/system/runs/<fingerprint>/<run_id>/` with
managed purpose `smoke`, complete environment/source/config/input hashes,
output manifest and SUCCESS only after validation. Smoke outputs cannot satisfy
a claim cache. Clean committed source is mandatory before deployment.

Prerequisites: local Docker engine, kind v0.33.0 and kubectl v1.35.8,
the repository `.venv`, at least 20GiB disk reserve and sufficient Docker memory.
Base images are digest-pinned in config. A metadata-only Prometheus wrapper
materializes the native platform for kind import, avoiding missing foreign-platform
blobs in Docker multi-architecture exports. The exact wrapper image ID/layers are
recorded, and both application and Prometheus Pods forbid registry pulls. Kubernetes v1.35.8 is pinned for stable in-place resize. The installed
1.33 stack rejected no-restart memory downscaling during server dry-run; that
attempt was invalidated. This is a platform correction, not controller tuning.
Hardware/software still require a dedicated V8 environment freeze. No cloud cluster or cloud credentials are used. Optional binaries live under
ignored `.local-tools/system-v1/bin`; other platforms may provide matching tools
on PATH. Exact binary hashes are included in environment provenance.

```sh
# Optional Mac ARM64 installer: verifies frozen official binary hashes; no global install.
.venv/bin/python -m dynapm.system_validation.install_tools
.venv/bin/python -m dynapm.scripts.task32_system_harness --help
.venv/bin/python -m dynapm.scripts.task32_system_harness
# Only after committing clean source; one real 300s bucket, no comparison:
.venv/bin/python -u -m dynapm.scripts.task32_system_harness --smoke
```

The runner uses a random task-specific cluster suffix, a private temporary
kubeconfig/context and an isolated anonymous Docker configuration (avoids desktop
credential-helper hangs for public images without changing personal credentials).
It refuses remote Docker/Kubernetes endpoints, never selects an existing cluster,
and deletes only its own created cluster in a finally block. It does not change
global kubeconfig, prune images, query BigQuery or load research-corpus outputs.
Images may remain cached. Status prints at most 30s apart while waiting/measuring;
subprocesses have bounded timeouts and smoke has an elapsed-time guard.

### Smoke limitations and verification state

One Full-Rewrite policy, one trivial stable workload (2rps,1000iterations,8MiB),
one real completed 300s bucket. The explicitly synthetic constant 288-slot fixture
is only past-state scaffolding: 50m CPU /48MiB memory. One fresh bucket cannot
replace a 24h bootstrap. Consequently the resulting p95 is dominated by the
fixture, and its 60m/64MiB recommendation demonstrates wiring and actual resource
enforcement only. It establishes neither workload suitability nor scientific
profile fidelity. No five-method comparison is executed.

**Actual cluster smoke: PASS (plumbing only).** Source `35bdb5d871a895067697d26cdde5641d9d3b4e32`;
run `2026-10-28T202821.479682Z-ff47ce4c3e96-c7850980`; experiment fingerprint `ff47ce4c3e96ba6aa769ced0bc8eaa573ed19b70de062b66002a5013cb0bce77`.
The [verification record](../configs/system_v7a_smoke_validation_record.json)
records all 23 output hashes verified, non-claim cache validation,
claim/config/tamper rejection, unchanged global kubeconfig, and actual status +
cgroup enforcement of 60m CPU /64MiB without a Pod restart. A successful request
was sent after confirmed enforcement. The profile committed one refresh/four
field writes. It was one Full-Rewrite run with 288 synthetic bootstrap slots and
one real completed 300s bucket, not a five-method comparative experiment.
Managed evidence: `results/system/runs/ff47ce4c3e96ba6aa769ced0bc8eaa573ed19b70de062b66002a5013cb0bce77/2026-10-28T202821.479682Z-ff47ce4c3e96-c7850980` (ignored, local). Output manifest SHA-256:
`bac9409f5d525b9d0cb575de993a8baa0e750996b335e69a1df12a60631f6613`. Full suite: 542 passed, 0 failed, 1 skipped.

Six discarded/incomplete plumbing attempts are retained as FAILED: image-import
failure; intentional interruption to strengthen enforcement/read-clock guards;
HTTP refresh-event serialization failure; intentional interruption after an RBAC
dry-run rejection; Kubernetes 1.33 rejecting no-restart memory downscaling; and the resize command
returning text instead of JSON. The final revision also includes the late generator
start in arrival-to-completion latency.
None is comparative evidence, none was patched, and no failed cache is reusable.
The final source adds regression tests and mandatory server-side resize preflight.
No system benefit claim follows from this gate.

## Platform references

- [kind 0.33 release and image digests](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0)
- [Kubernetes 1.35 in-place resize and resize status](https://v1-35.docs.kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/)
- [Prometheus text exposition](https://prometheus.io/docs/instrumenting/exposition_formats/)
