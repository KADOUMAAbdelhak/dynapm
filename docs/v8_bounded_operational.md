# Bounded Kubernetes operational validation v1

The [execution contract](../configs/v8_bounded_operational_v1.json) fixes the eighteen-cell order, request schedules, the three neutral donor phases and the separate native PW-3h integration run. The contract is checked against the runner and its bound dependencies before use. The previous V7D campaign has a separate launcher and evidence directory.

## Offline inspection

```sh
python -m dynapm.scripts.task41_bounded_v8 plan
python -m pytest dynapm/tests/test_bounded_v8.py
```

The plan prints the complete physical schedules and the execution-contract SHA-256. The tests use synthetic vectors and mocked enforcement solely for verification. The measured loader requires sealed neutral attempts with original clock and resource evidence.

## Gates for a separately authorised live phase

- Use clean committed `dynapm` source, the qualified block #1, current-boot endurance evidence and strict AC, lid and host continuity guards. Verify exclusive local Docker/kind access, the cached pinned images and CLI hashes, and at least 24 GiB free. The launcher creates a fresh cluster and records Pod, container, controller, profile and telemetry identities.
- Authorise each neutral `run --mode reference --phase low2|low4|high12` separately with `--authorize-live` and `--host-endurance-run`. Each session runs at CPU 1 and 512 MiB reservation with a fixed 1024 MiB memory limit and retains six physical receipt-time buckets from its 30-minute measurement window.
- After the three successful donors, `compile` freezes the library, logical histories, six profile states, quantized targets and maintenance evidence. It prints the six scenario/contrast labels and the SHA-256 of the bundle seal. Review that digest before supplying it to `run --mode primary --sequence N --snapshot-sha256 HASH`. Equal-target contrasts retain their frozen cells and cannot identify downstream target effects at those checkpoints.
- The separate `run --mode integration` uses fresh PW-3h state and live telemetry. It admits physical buckets and records the native T+3h profile commit, recommendation, actuation evidence and later request outcomes. A confirmed no-op completes the run with the integration objective unmet.
- `analyze --snapshot-sha256 HASH` checks the immutable attempts and bundle, returns every run and paired difference, and marks undefined endpoints and contrasts. Inference uses physical runs. It reports pointwise paired-t intervals for nondegenerate complete triples. Results are conditional on block #1 and the chosen checkpoint in each scenario.

## Time and failure handling

The 30h30m is scheduled cooldown, warm-up and exposure. Cluster setup and teardown, final request drain and any authorised infrastructure replacements add time. The primary window follows offered request timestamps. It retains terminal outcomes for requests offered before its end and reports throughput from completions within the window. Controller-enforced allocation uses Kubernetes and node cgroup evidence independently of application diagnostics. The 5-minute transition and 25-minute follow-up slices are descriptive.

Application timeouts, errors and overload are counted in the offered-request denominator. An incomplete or unverifiable exposure has an undefined full-window endpoint. An unresolved resize is right-censored. The runner preserves each issued attempt and will neither repeat a successful cell nor reorder the frozen sequence. A maximum of two separately reviewed exogenous primary replacements can use the identical cell, seed and snapshot. A torn attempt stops further execution. The `recover` path requires same-boot source and campaign identity, a reviewed evidence record, and confirmation that the owned cluster is absent. A mismatched attempt index requires explicit reconciliation.

The new launcher needs physical preflight verification for its node-side clock and cgroup transport. Offline checks cannot establish current host conditions or the six measured target comparisons.
