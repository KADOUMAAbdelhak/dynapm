# V7C.10 factual control-loop timing characterization

**COMPRESSION_MECHANISM_BLOCKED — current frozen production path.** No compression factor or candidate duration was selected.

The unmodified PW-6h consumer recommended 80m CPU and 64MiB. Kubernetes acknowledged the patch but refused the memory decrease below current charged usage (69,595,136 bytes versus target 67,108,864 bytes). CPU and memory remained at their old allocation; pending was exposed and the adjacent opportunity skipped. The run stopped at its predeclared 60-second bound. This is a right-censored path, not a 60-second enforcement observation or a zero/missing value to average away.

Three separate bounded engineering executions used unchanged 4rps, 30,000 iterations/request and a 32MiB persistent workset. Their explicit targets were 100–1000m CPU and 128–512MiB; they are not PW-6h policy outcomes, not comparisons, and not evidence that the 64MiB target works. They produced 33 enforced changes and six engineering no-ops, including individual CPU/memory increases/decreases and combined 1000m/512MiB → 100m/128MiB transitions.

## Empirical distributions

All values below are milliseconds. Quantiles describe finite engineering observations, not population tail guarantees. One additional production pending/enforcement path is right-censored beyond 60,000ms and is excluded from these finite quantiles.

| Component | n | Min | Median | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|
| Patch acknowledgement | 33 | 45.395 | 50.489 | 56.892 | 58.133 | 58.444 |
| Cgroup CPU | 27 | 85.148 | 93.409 | 108.694 | 119.588 | 122.633 |
| Cgroup memory | 27 | 87.102 | 93.723 | 110.350 | 119.588 | 122.633 |
| Decision to enforcement | 33 | 443.403 | 944.546 | 1272.762 | 1318.242 | 1327.340 |
| Old-request drain | 33 | 0.000 | 0.000 | 11.343 | 50.742 | 68.553 |
| Pending (finite paths) | 33 | 359.070 | 892.880 | 1200.608 | 1212.937 | 1216.826 |
| Pod CPU status | 27 | 353.171 | 902.141 | 1194.942 | 1207.090 | 1210.485 |
| Pod memory status | 27 | 353.171 | 767.491 | 1194.942 | 1207.090 | 1210.485 |
| 20-response window | 33 | 4775.116 | 4919.314 | 5018.844 | 5125.700 | 5174.366 |
| PW6 refresh component* | 39 | 0.617 | 0.808 | 1.947 | 2.936 | 3.467 |
| Recommendation | 39 | 0.009 | 0.028 | 0.081 | 0.126 | 0.141 |
| Telemetry completion | 901 | 2.726 | 12.828 | 47.403 | 143.304 | 239.706 |

*Refresh-component wall time is measured in the separate profile process on a disposable production PW-6h policy copy. It includes trailing-window selection, forecasting and field commit, but bypasses due/eligibility scheduling. Live profiles retain one initialization and zero runtime refreshes. A genuine six-hour scheduled refresh was not observed or accelerated.

First-observed status/enforcement times are upper bounds at roughly 0.2s polling plus real API/telemetry overhead. CPU and memory dimension counts omit unchanged dimensions. API acknowledgement is separate from enforcement.

## Worst paths and settling

The worst finite path was decision 11 in run 74c9dca4fd45: 100m/128MiB → 500m/256MiB. Decision-to-enforcement was 1.327340083s; patch acknowledgement 0.049589375s; cgroup CPU and memory first matched at 0.097345333s after submit; Pod status for both matched at 1.210484875s. Status convergence, rather than kernel-limit observation, dominated the finite pending path. The original 64MiB production shrink remained unresolved beyond 60s.

Old in-flight request drain reached 0.068553375s. The descriptive 20-response windows lasted 4.775115834–5.174366167s; all 660 responses succeeded and retained the expected work. This establishes mechanical drain/continued service and rechecked allocation/workset agreement, not statistical steady state. V7C.11 must predeclare settling criteria rather than treating these descriptive windows as an acceptance rule.

All 33 successful patches had an explicitly skipped adjacent pending opportunity; no overlapping patch was issued. Final matching Pod observations had no active resize condition, and Pod/cgroups were rechecked before the next target. The production failure had a visible, unresolved pending condition, not a hidden success.

## Host, initialization and provenance

All five managed attempts retained zero clock rejections, valid source/cluster and host-admission evidence, stable AC/open-lid/boot/policy observations and confirmed assertion release. Maximum recorded host wall/monotonic discrepancy was 0.000234666s and maximum guard gap 5.155706750s. Eight available before/after thermal snapshots recorded no thermal/performance warning; runtime-failed paths lack an after-snapshot and continuous thermal/frequency telemetry was not collected. Docker is empty after owned-cluster cleanup. No other acquisition, comparison or Google job was launched.

The three completed engineering executions began with identical artifact history/dynamic-field hashes and thresholds, one initialization and zero live refreshes. Pod/application/profile/controller/collector identities were fresh, initial work CPU counters zero, and initial resources 1 CPU/512MiB. Worker ASTs are identical across those source versions after normalizing the stop-signal path; timing/workload semantics did not change. The artifact, its qualification record and original failed bootstrap parent remain byte-identical.

The first two engineering executions completed physically but remain managed FAILED: the first omitted resources.json from its output declaration; the second left STOP_LOAD outside the allowed root inventory. Separate trusted inventories and independent reconstruction bind their diagnostic timing data; no failed run was relabelled or promoted into a managed result cache. The third execution has a valid managed SUCCESS and passed check_cache/output-hash validation. A prior initialization-RPC timeout and prelaunch descriptor error are also retained.

| Run ID | Fingerprint | Managed status / role |
|---|---|---|
| `2026-11-03T054931.607903Z-31f77a06d745-78db2348` | `31f77a06d7451fc994c995ce19244047c7ee17215e7c2ddc8bb0a0287bae17d0` | FAILED: setup-only initialization timeout |
| `2026-11-03T055519.903830Z-ad2267fadb05-f17684b7` | `ad2267fadb05bb028dcae0982884ca284b408641f155e752adff005a01b827e3` | FAILED: production resize right-censored |
| `2026-11-03T060252.967930Z-63f68834d8b6-46e2a452` | `63f68834d8b6afe41222a04d7799d4550218d65174c54b698a8552ee43da2b25` | FAILED: completed engineering; bookkeeping failure |
| `2026-11-03T061027.782339Z-74c9dca4fd45-c9d18e48` | `74c9dca4fd459ea7591cf46b11034554c41befe5f0560c05646393c6463099a2` | FAILED: completed engineering; bookkeeping failure |
| `2026-11-03T061829.410183Z-d88e3c0a76d5-e4d656d5` | `d88e3c0a76d5453f1b40050cc6eeeeac13d4eb056b2dad5fafddcad621308ffc` | SUCCESS: completed engineering; cache validated |

## Constraints for V7C.11

1. 64MiB recommendation is blocked below current charged memory usage; no finite unconditional memory convergence bound established.
2. resolve/explicitly handle resize admissibility before any compression validation; no masking deferred state, overlap, backdating or silently raising the frozen floor.
3. future admissible resource targets limited to independently validated range; successful engineering paths used 100-1000m CPU and 128-512MiB, not 80m/64MiB.
4. prospectively bound observation+maintenance+recommendation+API/enforcement+drain+settling plus scheduling and polling uncertainty; observed maxima are not guarantees.
5. keep one actuation in flight and make pending/skip visible at every opportunity; acceptance limits must be frozen before validation outcomes.
6. unchanged V8 requires complete host-time 300s buckets, >=50 samples and >=270s physical receipt span; direct logical-clock acceleration is not implemented or validated.
7. retain zero future tolerance, <=2s same-domain source age, physical host admission order, <=2s host clock discrepancy and <=30s guard checkpoint gaps.
8. retain 4rps, 30000 iterations, same seed/workset and fresh isolated state; no scaling workload to make resizes pass.
9. prospectively define application settling criteria and windows, genuine PW6 scheduler/mapping tests and faithful treatment accounting before compressed validation.

The state-dependent memory-admissibility condition is not a latency-only problem. No finite slot-duration choice is justified for a target that the kubelet cannot currently admit. This observation is scoped to this instrumented setup: diagnostic telemetry is more frequent than the frozen five-second sampling cadence, and whether reducing diagnostic overhead would prevent the failure was not tested. Do not generalize this as universal Kubernetes failure or tune the observer/consumer after the fact to manufacture a passing compression result.

## Validation records

Full tests: **718 passed, 1 skipped**. No frozen V8 config, policy, workload, consumer or scientific clock implementation changed. Instrumentation/storage fixes are separate commits; this document records factual findings.

Independent record: `results/neutral_characterization/v7c10-validation.json`

SHA-256: `499552a7c7c05823c95bd276fa00695427319acb91806b06442601bf49d6f1c2`

Supplement: `results/neutral_characterization/v7c10-supplement.json`; `VALIDATION_COMPLETE` binds both records and the independent validator.

**V7C.10 STATUS: BLOCKED**
