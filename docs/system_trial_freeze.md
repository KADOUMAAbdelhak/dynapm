# V7B — Estimation-first system validation

**Current amendment: estimation-first; neutral calibration required/in progress.**
Practical margins are **not a gate**. V8 comparative execution remains disabled
until calibration, prospective repetition/precision disposition and the remaining
hardware checks are complete. There are no comparative outcomes from this task.

The authoritative amendment is `configs/system_trials_v8_estimation_v2.json`
(`system-estimation-design-v2`). The v1 preparation at commit `88b5b1f` and
`configs/system_trials_v8_draft_v1.json` is superseded as the current governance
contract; its validation/history is retained. In particular, its demand for
practical margins before calibration no longer applies.

## Frozen question, parameters and interpretation

Estimate direction, magnitude, uncertainty, maintenance cost and operational
resource–SLO trade-offs for Static, PW-12h, PW-6h, PW-3h and Full-Rewrite, using
one identical profile-p95-to-resource consumer. No predictor/adaptive method is
introduced. Keep `causal-timeline-v3`, `refresh-accounting-v1`, exact 5min clocks,
the 250ms violation threshold and 20% recommendation headroom unchanged.
Those numbers are **experimental/controller parameters only**, not validated
practical-significance margins. Operationally meaningful benefit remains
**NOT_DEFINED**. No application-specific error/resource/churn/overhead budgets
exist, and none is invented.

Negative/null findings are valid. Statistical distinguishability alone cannot
establish practical superiority. Do not recommend a method from p-values or
choose a winner when a resource–SLO trade-off exists. An external/application-
specific contract could justify practical criteria only through a documented
later amendment; it must not be retrofitted from favorable outcomes.

## Endpoints and independent unit

The unit is one independently reset run/scenario, never a request or telemetry
slot. Primary endpoint families remain:

- SLO violation rate: failures, timeouts, generator drops or latency >250ms,
  divided by **all offered requests**.
- Successful-request p95 arrival-to-completion latency; failures reported jointly.
  No successful requests means undefined p95, not zero.
- CPU and memory resource requests/allocation, separately. Desired requests change
  at API acknowledgement; actual allocation is reported at status **and** cgroup
  confirmation. A pending or rejected resize is not an enforced resource saving.
- CPU and memory utilization efficiency, separately, with observed time coverage.

Secondary endpoints remain p50/p99 latency, throughput, under/over-provisioning
proxies, resource changes/churn, recommendation/actuation latency, maintenance CPU,
memory and runtime. Limits censor latent demand: zero observed deficit does not
prove sufficient provisioning. Report throttle/OOM and SLO evidence alongside.

## Frozen V8 estimation/reporting procedure

Analyze each scenario separately. Pair complete run blocks across methods with
identical offered workload/seed and randomized/counterbalanced order. Report
per-block differences, arithmetic mean and median paired effects and pointwise
95% paired-block percentile bootstrap CIs (B=10,000; seed20251022). Undefined
endpoints and failed attempts must be reported, not silently excluded to improve
estimates. With inadequate independent runs, report the uncertainty limitation.
Requests are not bootstrap units.

Freeze contrasts: each PW vs Static; PW6 vs PW12; PW3 vs PW6; Full-Rewrite vs PW3.
These are scenario-specific operational contrasts, not a new pooling of Google or
Materna results. Pointwise CIs do not provide familywise guarantees or operational
margins. No primary p-value decision/recommendation rule is introduced.

Report resource–SLO Pareto estimates using CPU/memory requests, confirmed CPU/
memory allocations, violation rate and p95 latency (all minimized). A can be called
strictly dominated **at the point-estimate level** only if it is no better on
**every** dimension and strictly worse on at least one. Equal vectors are not
strict dominance. Undefined dimensions yield no dominance classification. Show
endpoint CIs, mean and median summaries and any heterogeneity; never promote a
point-estimate ordering to certain population dominance or practical superiority.
Otherwise report the trade-off without choosing a winner. Churn and overhead
accompany every interpretation; resource efficiency alone cannot override harms.

## Measured bootstrap and phase transition

Each run uses a fresh cluster, application instance, Prometheus state, profile
service and controller. Proposed engineering timing is fixed before calibration:
15min cooldown, 30min stable warm-up, **24h real stable bootstrap**, then **48h
measured scenario**, without compression or bootstrap reuse. Warm-up/cooldown
values are engineering settings, not a claim of validated thermal equilibrium.

Bootstrap contains 288 actual five-minute buckets, each requiring >=50 source
samples spanning >=270s. Source times stay inside the bucket; visibility is after
its close and receipt. No interpolation, filling, replicated slots or future
samples. Require >=200 paired finite bootstrap slots and the final96 complete.
One application instance and monotone counters are required throughout bootstrap;
reject an unusable fixed window without extending it until data look favorable.
`measured_bootstrap` reconstructs values from raw sample evidence rather than
trusting precomputed utilization labels. Labels alone do not attest real data;
image/source/UID, sample lineage and managed hashes must agree.

Thresholds use bootstrap only. Initialization uses existing production factories:
Static whole bootstrap; PW cadence-length trailing bootstrap; Full-Rewrite
trailing24h. Initialization is separate from refresh accounting. Runtime content
and PW eligibility remain unchanged; no policy parameters are tuned.

At bootstrap close q, workload switches at the nominal clock and completed
bootstrap becomes visible only after q/receipt. Initialization and initial
consumer actuation occur inside the measured interval, with their delay/churn/
request consequences retained. Do not hide policy-specific settling costs.
Collectors/generators continue while the controller works. PW schedules remain
anchored to q. The measured interval is `[q,q+48h)`; no policy refresh is committed
at its excluded end. Actual receipts/reads/actuation times remain recorded.

## Calibration only, ordering and compute

Calibration uses **PW-6h only**, stable plus the frozen7h periodic scenario, three
independently recreated runs per scenario (six maximum). This count is for initial
noise characterization, not a final confirmatory sample-size assertion. The
identity-hash base order plus cyclic blocks is frozen with seed20251022; selection
never inspects method outcomes. Offered CPU work remains30,000 iterations and
all original workload shapes/seed are unchanged.

The serial campaign needs at least436.5 host-hours (18.1875 days), excluding
cluster setup/failures. A full five-method × four-scenario repetition would need
at least1455 host-hours (60.625 days). No financial or practical benefit is inferred
from those schedule calculations. Runs are strictly serial on the local engine. Other running Docker containers
are refused/preserved before setup and checked during collection; no unrelated
container or cluster is deleted. Host desktop activity is monitored, not falsely
asserted absent.

Calibration characterizes the actual research workstation; a reserved/dedicated
host is **not asserted**. Record host CPU/model/memory/OS, Docker allocation,
Kubernetes1.35.8, kind0.33.0, CLI hashes, image IDs and runtime fingerprints. Log
load, process CPU/memory, power and available thermal status every30min. Missing
thermal readings stay missing. Require mains power; prevent idle sleep and detect
clock discontinuities. Any background interference remains a transport/control
limitation for a later V8 freeze, not a reason to select favorable runs.

## Precision and N: independent of benefit or significance

Use calibration only for noise, bootstrap variability, feasibility and prospective
precision planning. Never derive a favorable benefit/harm threshold. Primary CI
half-width targets and a practical confirmatory repetition cap are currently
**NOT_DEFINED**; no N is fabricated. If a prospectively justified estimation
precision target can be supported, freeze N from uncertainty/precision before
comparisons. Otherwise report the limitation and leave comparative execution
disabled rather than selecting N by p-values.

The existing conditional planner documents normal-run and variance-transport
assumptions, uses an upper SD envelope and rejects all-zero variance as proof of
precision. Those assumptions are not established by three neutral runs. Bounded/
degenerate SLO rates need an appropriate uncertainty assessment; a zero observed
rate does not prove zero uncertainty. Resource/controller quantization may inform
a reporting-precision discussion but is never a practical-benefit margin.

## Overhead attribution and failure retention

Processes are separate: generator, collector/orchestrator, profile service and
controller. Pure recommendation computation uses thread CPU, not a shared
producer/controller process delta. Record process CPU/RSS and timestamped
warm-up/bootstrap/measurement baselines. Profile initialization and per-step costs
are distinct. Prometheus self CPU/RSS is measured separately; this is process
cost, not all kernel/container storage cost. The collector includes orchestration
and measurement I/O and is labelled accordingly.

An instrumented calibration application wraps the **unchanged workload handler**
to count workload, telemetry and health-handler thread CPU separately, exposing
these with actual cgroup totals and workset bytes. Container CPU also includes
server/thread/background cost; resets/uncovered intervals remain visible. Shared
runtime memory is not falsely allocated to one handler. The separate calibration
image preserves V7A's image/source and is applied uniformly in any future study.

Actuation records submit, acknowledge, status/cgroup confirmation, rejection,
queue/defer time and churn. One pending resize is allowed; further decisions are
logged as skipped while pending, not overwritten. An unresolved resize after60s
is an operational outcome and remains pending. OOM, SLO failure and rejected/
deferred actuation are retained, not silently excluded. Unexpected worker/source/
clock/data corruption invalidates the generation, retaining raw FAILED evidence.
No automatic retry, output patching or outcome-based replacement.

## Execution, provenance and source freeze

```sh
.venv/bin/python -m dynapm.scripts.task34_system_calibration       # plan only
.venv/bin/python -m dynapm.scripts.task34_system_calibration --help
# Clean committed source only, real one-bucket I/O check; NO bootstrap claim:
.venv/bin/python -m dynapm.scripts.task34_system_calibration --plumbing-check
# Authorized neutral campaign, six trials maximum, no comparative method flag:
caffeinate -ims .venv/bin/python -u -m dynapm.scripts.task34_system_calibration --run-calibration
```

Generated outputs stay under ignored `results/system_calibration/`. Every real
trial uses the managed lifecycle, purpose `pilot`, a unique run ID, explicit
source/config/input/cohort/environment identities and output hashes. All raw
sample/response/event streams and operational errors are retained. SUCCESS is
written only after all required outputs and source/environment integrity checks.
A pilot or partial real-collection smoke cannot satisfy a claim request. No
comparative CLI exists. `--maximum-trials` can only bound the predeclared neutral
campaign to1–6; it cannot introduce another policy.

**Keep Git source/HEAD unchanged while a trial is active.** Current managed
provenance validates source during/finally; edits or new commits invalidate the
active generation. Status/heartbeat files are generated and ignored. Source fixes
require a new clean commit and a new run/fingerprint; do not patch old outputs.
To stop a task-owned campaign, send SIGINT to the Python PID in `ACTIVE.json`;
cleanup removes only its uniquely named local cluster and records failure.

## Gate disposition

The **estimation-first interpretation contract is frozen**. Practical margins are
not a prerequisite. Actual bootstrap/calibration, technical integrity and the
prospective repetition/precision disposition remain to be evidenced. V8 remains
disabled until those requirements are satisfied. A started 24h collection is not
a completed bootstrap; a one-bucket check is not calibration variance. C4/C5
remain unproven and no system-method superiority is claimed.


## Technical validation before long collection

A managed physical check at source `242e69e` collected one actual five-minute
bucket and1200 offered requests with **zero profile initializations**, no synthetic
bootstrap and no method comparison. Its immutable evidence is purpose=smoke,
not calibration; source/hash and claim/pilot cache rejection were independently
verified. It validates the real collector/process plumbing, not a24h bootstrap,
variance estimate, trial N or practical benefit. Subsequent startup isolation
checks do not change workloads, policy, controller or measured clocks.
Live campaign and per-trial status are under ignored `results/system_calibration/`;
no completed calibration is asserted merely because the campaign was launched.


Validation record: `configs/system_v7b_estimation_collector_check.json` indexes
the immutable physical check (31 hashes,1200 requests,60 samples, no bootstrap
initialization). Latest lightweight suite: **594 passed,0 failed,1 skipped**.
New source/isolation/full-summary tests do not change any workload/controller
parameter. Calibration starts only from a clean committed source; no completed
replicate, variance, N or practical benefit is asserted at launch.

## V7C.1 clock correctness amendment

The original first attempt failed during warm-up and is not calibration evidence.
See [clock forensics and rejection evidence](system_clock_diagnosis.md). The strict
source/receipt invariant is unchanged. New attempts preserve rejected response
bodies outside scientific telemetry, bind diagnostics to run/source hashes, and
record local wall/monotonic timing. This amendment changes diagnostics/source
identity, not the methods, controller, bootstrap or measurement duration. A
replacement is limited to one PW-6h stable anchor after a successful managed
plumbing check; no automatic second long replicate is authorized.

## V7C.3 execution-host gate

V7C.2 failed during confirmed clamshell sleep on battery, before bootstrap.
See [host execution contract](host_execution.md). Runtime hardening adds owned
verified assertions and an independent continuity monitor; scientific clock
checks, methods, scenarios, controller and durations remain unchanged. Another
long run requires a completed compatible-host-runtime >=3h managed host observation and
separate execution authorization. Endurance validation is pending; V8 stays shut.

## V7C.4 shared prehistory amendment

The3h host-only observation passed. See [host contract](host_execution.md).
Shared measured-bootstrap artifacts and isolated factory initialization are
implemented independently of a completed72h anchor; see [shared bootstrap](shared_bootstrap.md).
The original five methods/parameters and estimation-first study remain unchanged.
Neutral timing instrumentation is prepared, not executed; see [probe scope](neutral_timing_probes.md).
No real24h artifact exists yet and no comparative or compressed execution is enabled.
