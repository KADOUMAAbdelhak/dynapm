# V7C.13 prospective failure taxonomy and neutral diagnostic plan

Version: reservation-outcome-observability-v1. This explicitly supersedes the
V7C.12 adapter's zero-application-error validity gate; original v2 resource targets,
serialized patch semantics, 60s censored actuation watchdog and physical 300s
telemetry contract remain unchanged. Historical runs stay immutable.

Application request timeout, HTTP/application error, SLO violation, throughput
loss and queue buildup are retained operational outcomes, not automatic run
invalidators. Successful and failed attempt IDs, timestamps and denominators
must all reconcile. A timeout is a completed host observation, not proof that
the server finished the request. Server drain and statistical settling are not
claimed when evidence is insufficient.

Generator failure, independent telemetry loss, controller crash, unverifiable
Kubernetes/cgroup enforcement, missing provenance, host discontinuity and
corrupt/incomplete streams invalidate measurement. Diagnostic timeout/error is
separate: it does not invalidate enforceability when fresh independent node
cgroup and Kubernetes evidence remains available. Diagnostic missingness and
cost are retained. Lost independent evidence still fails closed.

Before engineering outcomes: run two fresh non-comparative PW6-initialized
executions, external-only then application-exec diagnostics. Repeat fixed CPU
up/down, memory-reservation up/down, simultaneous, no-op, queue/supersession and
three 100m/64MiB cycles. Both use identical real 4 RPS, 30000 iterations, 32MiB
work and seed, fixed 1024MiB cap. The first low cycle has a fixed 45s observation;
later low cycles 15s, other operations >=5s/20 completed host attempts. These
are diagnostic exposures, not shortened scientific buckets or method outcomes.
No resource point is removed based on poor application performance.

Enforcement uses node-side cgroup reads and spec/status/allocated reservation,
observed generation, clear resize conditions, stable UID and fixed cap. It has
no dependency on application HTTP telemetry. Node sampling is independent at
nominal 1Hz with maximum 10s gap. Node boot identity, uptake clock, CPU usage/
throttle counters, memory current/stat/events, quota and request backlog are
recorded. The application-exec variant additionally performs two bounded Python
cgroup diagnostics during the first low cycle, asynchronously to the generator
and controller. Diagnostic failures never become fabricated finite timings.
All errors and observer overhead stay visible. Two ordered engineering runs
cannot by themselves establish a general causal effect; report correlations
and limits, including non-reproduction, without tuning exposure after outcomes.
