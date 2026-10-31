# V7C.6 — Cluster and host clock domains

## Correctness amendment

V7C.5 failed on sample401 at2026-10-31 00:28:22 Helsinki
(2026-10-30T22:28:22Z). Source exceeded macOS receipt by4.309552ms.
The host continuity guard reported no failure; all failed artifacts remain
immutable. This proves that the former absolute comparison was unsuitable for
this deployment; it does not establish an NTP step or its cause.

Docker Desktop runs Linux containers in a Linux VM, separate from macOS
([Docker VMM documentation](https://docs.docker.com/desktop/features/vmm/)).
Linux time namespaces affect monotonic/boot clocks, not CLOCK_REALTIME
([Linux man-pages](https://man7.org/linux/man-pages/man7/time_namespaces.7.html)).
Neither fact guarantees synchronization with the macOS wall clock.

## Clock map

| Timestamp | Producer / domain | Valid comparisons |
| --- | --- | --- |
| sample_time_ns | read_cgroup after counter reads, Linux application container | Cluster receiver wall clock |
| source_clock.wall_ns / monotonic_ns | Same application source handler | Local elapsed/discontinuity; same source across samples |
| cluster request / complete-body receipt | Application loopback HTTP receiver, same process/container/Linux kernel | Source wall clock; local transport duration |
| received_at_ns | macOS collector, after complete envelope body read, before decode | Host wall times only |
| host_admitted_at_ns / monotonic_ns | macOS validator, before scientific persistence | Host receipt and initialization/read ordering |
| host power/continuity checkpoints | macOS wall + monotonic + boot identity | Host continuity only |

`/clock-observation` requests `/telemetry` over loopback, reads the complete source
body, captures cluster wall/monotonic receipt, then envelopes the original bytes
and SHA256. Linux boot ID, time namespace inode and hostname must match the
source. The host captures its own receipt after the complete envelope arrives.
No source/host absolute comparison or monotonic-epoch comparison is permitted.
Timezone conversion is presentation only; integer nanoseconds remain unchanged.

## Causal and availability contract

`system-clock-observation-v2` requires:

- source <= cluster receipt, zero future tolerance; age <= existing2s bound;
- valid local cluster transport and host transport, each measured locally;
- source/instance/domain identity and increasing source timestamps;
- physical host response completion -> decode/validate -> host admission ->
  durable diagnostic -> scientific telemetry. Host admission cannot precede
  host receipt in either local wall or monotonic time;
- unchanged host wall/monotonic2s discontinuity and30s heartbeat-gap limits,
  AC/open-lid/owned assertion/boot/power-policy checks.

Signed host-minus-source differences are **NON_CAUSAL_DIAGNOSTIC_ONLY**. They
combine offset and transport delay; they are not calibrated absolute offsets.
No bound estimated from the probe becomes a tolerance or a conversion.
Rejected envelopes, source bytes, hashes, sequence, preceding accepted clocks,
cluster and host receipts remain isolated from scientific samples. Historical
v1 evidence remains verifiable as historical evidence, not reusable v2 input.

## Scientific timeline amendment

`host-admission-slots-cluster-causal-v2` explicitly uses the macOS timeline for
300s logical boundaries, workload scheduling, profile windows and read times.
A sample is assigned by host receipt in `(bucket_start,bucket_end]`, **not** by a
numerically compared VM timestamp. It must have passed admission before the
algorithm sees it. A complete bucket is available at the later of its nominal
end and its samples' host admission times. Samples after an end remain buffered
for the next bucket, rather than being lost or backdated.

CPU rate uses counter difference over source monotonic elapsed time for those
selected observations. Memory uses their actual working-set observations.
Coverage uses host receipt span: >=50samples over>=270s. No clock conversion,
interpolation, extension or clipping occurs. Physical counters retain their
source timestamps. Aggregate `host_receipt_start_ns`/`host_receipt_end_ns` explicitly name
host-receipt support bounds; actual source clocks are retained per raw sample. `source_span_seconds` is the separate
source-monotonic denominator.

Measured/shared bootstrap schemas become `measured-system-bootstrap-v2` and
`shared-measured-bootstrap-v2`. The24h/288nominal-slot, >=200paired and final96
complete rules remain. Raw bootstrap samples must belong to validated parent
accepted telemetry. No v1 artifact is silently upgraded. Materna/Google causal
protocols and `refresh-accounting-v1`, methods, scenarios, headroom and250ms
engineering threshold remain unchanged.

Operational latency measurements stay in real seconds using same-process
monotonic timers or same-host wall timestamps. Prometheus scrape timestamps
remain separate diagnostics and cannot supply profile bucket availability.

## Prospective bounded probe

`python -m dynapm.scripts.task37_clock_domain_probe --run` creates one fresh local
kind application, pinned environment, no `/work` requests, bootstrap, profiles,
controller or policy comparison. It observes for900real seconds at1s cadence,
with managed power/continuity monitoring and complete provenance/output hashes.
Pass requires >=800accepted observations, full duration, zero same-domain causal
or host-admission/continuity failures, unchanged Pod identity/no restarts, complete
hash validation and cleanup. This observation count checks collection feasibility,
not application performance. Offset direction/magnitude is not a pass criterion.
Report observed host-minus-source range/change and same-domain age distribution;
do not infer24h stability or new clock tolerances from15minutes.

A successful probe permits a separately authorized bootstrap-only retry, never
an automatic retry. No72h anchor or comparative experiment is authorized.

## Host endurance compatibility

The prior host-only observation remains labelled with original source and exact
original cache identity. `host-runtime-compatibility-v2` pins the unchanged
`ObservationClock.check_host` AST and2s constant instead of unrelated cluster
HTTP reception. Entire power monitor, observer acquisition (except its validation
helper), CLI, provenance/run-store/data-manifest code remain pinned. Changed host
checks or limits invalidate the certificate. Hardware/packages, boot/power policy
and original SUCCESS hashes must still match; generic scientific cache identity
is never relaxed.

## Completed V7C.6 validation

Disposition: **PASS**, bounded clock-path validation only. Source
`54c65bd80e79cd2e286b4bd61478e6617072f2f0` was clean throughout managed run
`2026-10-31T045418.835227Z-7363d15175a3-c3e3f52b`.
Experiment fingerprint:
`7363d15175a372fe1b9edfcff54604908003a8cbce38f3c7b669488a857a358e`.
Config SHA256:
`193516d1d6fc5ee7b07fb858ec456856b8f0320c12533fb9d75027bf94ff9282`.

896accepted observations span the901.003364334s observation period; zero
rejections. Source and receiver report the same Linux boot ID and time namespace;
the node boot ID also matches. Every retained response, source body, admission
order, context and all14output-file hashes were independently checked. A tampered
COPY is rejected with `output_hash_mismatch`; a claim-cache request is rejected.

- Cluster receipt minus source:0.204333–2.804959ms.
- Host receipt minus source:1.211577–8.004997ms, first1.211577ms,
  last1.856118ms, first-to-last change+0.644541ms. This conflates clock offset
  and transport delay; it is not an isolated estimate of oscillator drift.
- 186host continuity checkpoints; maximum absolute wall/monotonic discrepancy
  0.728125ms; maximum checkpoint gap5.096354250s. No recorded power, lid, boot,
  assertion or continuity failure. Caffeinate PID60782 for owner56639 was released.
- Zero workloads, bootstrap slots, profile initializations and comparisons.
- All82historical failed files and45V7C.5 files matched their stored inventories.
- Full suite: **676passed,0failed,1skipped**; compile/import/safe-CLI checks passed.

Output-manifest SHA256:
`fb9f44a6d350ffed28d86c06c655e94141dee25c5deb7273066e6abfa7d61cfb`.
Outputs remain under ignored `results/clock_probe/runs/<fingerprint>/<run_id>/`.
Independent validation is `results/clock_probe/v7c6-independent-validation.json`.

One earlier probe generation
`2026-10-31T044557.145357Z-c9a1a86a3f1f-ce507d39` failed at setup on
`isolated_harness_cluster_required`, before cluster creation or observations.
It remains FAILED and untouched. The probe naming/read-only-deployment correction
was tested and committed before the fresh successful generation. No bootstrap
retry occurred. A new bootstrap-only attempt may be separately authorized after
repeating host/resource preflight; this15minute probe does not prove24h uptime
or approve repeated claim-generating laptop trials.
