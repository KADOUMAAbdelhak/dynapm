# V7C.3 host continuity and long-run execution

## Forensic conclusion: HOST_SLEEP_CONFIRMED

The replacement campaign `8a2f6f0d6b974f99a6651793e1fda8b8` failed during
warm-up at 2026-10-29 14:41:14 UTC (16:41:14 Helsinki, UTC+02).
The original evidence remains immutable. The scoped macOS log is preserved in
`results/host_forensics/v7c3-20261030/pmset_failure_window.txt` with an evidence
manifest. The original V7C.1 source-clock failure remains unproven; this conclusion
applies specifically to the V7C.2 host-continuity failure.

| Helsinki time on 2026-10-29 | macOS evidence |
|---|---|
|16:20:50|PID3128 caffeinate holds idle-system and system-sleep assertions.|
|16:32:16|Power state changes to battery.|
|16:35:06|Display turns off; caffeinate assertions are still listed.|
|16:35:11|Entering Sleep due to **Clamshell Sleep**, on battery; logged duration361s.|
|16:41:12|DarkWake from Deep Idle, `smc.sysState.Wake(0x70070000)`, on battery.|
|16:41:14|Run fails on wall-minus-monotonic elapsed discrepancy358.766629583s.|
|16:41:15|Caffeinate assertions released on client death.|

The sleep interval directly brackets the discontinuity. The difference between
the361s log entry and358.77s measured discrepancy is not an exact duration equality;
power-log timestamps include transition/notification timing and seconds resolution.
The sleep evidence suffices without attributing the failure to NTP. Unified
powerd/timed log access was denied by the OS, so no independent time-sync event
claim is made. There is no evidence of application SIGSTOP rather than host sleep.

The prior `caffeinate -i -s utility` wrapper did create assertions. It did not
override lid-close sleep; `-s` applies only on AC power (local caffeinate(8)). The
launch-record PID3127 was the utility PID; the assertion holder was PID3128.
Historical records are not rewritten. The new guard records both identities.

## Owned assertion and preflight

`ManagedPowerGuard` starts `/usr/bin/caffeinate -i -s -w <owner PID>` as its own
child, with no utility argument. It verifies **that child's** PID owns both
`PreventUserIdleSystemSleep` and `PreventSystemSleep` assertions before allowing
work. A different process's assertion is insufficient. Missing assertions, AC,
lid state or boot identity fail preflight. No global pmset settings are changed.
The PID watch releases assertions if the owner dies; ordinary exit/failure also
terminates only the owned child, waits, and verifies its assertions disappeared.
Start/end/types/PIDs, verification and release status are provenance-bound in
`power_guard.json`. Assertions are not a forced-sleep override.

## Independent continuity monitor

Schema `managed-macos-power-v1`: an independent thread records wall/monotonic
checkpoints every5s. Every30s it checks AC, open lid, boot identity, unchanged
power policy and owned assertion state. Diagnostic command timeouts are2s. A
checkpoint gap above30s fails rather than treating unobserved continuity as valid.
The wall-vs-monotonic2s invariant is unchanged, and the original collector's
`ObservationClock.check_host` remains active. Neither clock is repaired, rebased,
clamped or substituted. Monotonic epochs are never compared between hosts.

`host_continuity.jsonl` and its summary retain heartbeat/power/uptime information.
Failures are written before propagation to `host_continuity_failure.json`, with
run/source/fingerprint and a hash in the failure exception. During a blocked
collector, the thread still records/latches failures; the caller checks that
latch before further work. After a suspend, the run fails on resumption. No
assertion can promise that a user never closes the lid or forces sleep.

## Required three-hour non-claim endurance observation

From clean committed source:

```sh
.venv/bin/python -m dynapm.scripts.task35_host_endurance --observe --duration-seconds 10800
```

This uses managed provenance/output manifests with purpose **smoke**, no model,
policy, Kubernetes, application workload, bootstrap or scientific outcomes. It
requires three to six real hours; a five-minute check cannot satisfy the gate.
PASS requires the complete duration, continuous monitored checkpoints, no clock,
power/assertion/boot/policy failure, verified release, unchanged source/environment,
and validated output hashes. Failure records and incomplete directories are never
eligible. No automatic retry occurs.

Current inspected settings have AC idle sleep0 and display sleep0 (disabled).
Keep those settings unchanged during observation. A three-hour PASS establishes
observed stability under the recorded policy; it cannot claim to cross an infinite
disabled idle threshold or prove that assertions alone prevented sleep. Record
that limitation explicitly. No forced-sleep/lid-close test is performed.

Long calibration requires an explicit compatible-host-runtime completed managed endurance
run via `--host-endurance-run <run directory>`; missing/incomplete/unversioned or
tampered evidence is rejected before workload execution. Another72h anchor is
not authorized by completing this runtime-hardening task.

## Physical and OS operating contract

- Keep the laptop lid open throughout; clamshell sleep caused the observed failure.
- Keep AC connected. Thirty-second power checks replace reliance on infrequent
  diagnostic snapshots; they cannot stop instantaneous forced suspend.
- Display-only sleep is permissible if the host remains awake. No display-sleep
  assertion or global display-setting change is required by the guard.
- Reserve the machine for comparative trials. A personal actively used laptop
  is not currently an accepted dedicated multi-day V8 host.
- Record/check maintenance windows and local OS update/restart settings before
  a run. Assertions do not block a forced update, restart, logout or shutdown.
  Do not assume update settings are controlled when unavailable; never initiate
  a network update check as part of provenance collection.
- Detaching a process from its terminal is not proof it survives user logout.
  Keep the session intact. SIGTERM/normal failure should clean up; a hard kill
  drops the PID-watched assertion but leaves an INCOMPLETE run, never SUCCESS.
- A reboot changes boot identity and interrupts provenance. Never resume the
  old generation; preserve it and inspect before any separately authorized retry.
- Leave time synchronization enabled. Record local diagnostics; any discontinuity
  fails the unchanged causal guard, rather than increasing tolerance.

## Alternative always-on host

Prefer a dedicated always-on machine for V7/V8 if AC/lid/session and maintenance
conditions cannot be operationally assured here. No host offers an absolute
uptime guarantee; fail-closed execution and immutable failed attempts remain
required. Migration requires a supported OS power/continuity adapter, new
hardware/environment fingerprints, pinned Kubernetes harness smoke, remeasured
controller/enforcement timings, new real bootstrap collection and fresh system
calibration/precision planning. Never transfer Mac timings as measurements of
another machine. Methods, scenarios, controller and estimation endpoints remain
unchanged by this hardening.


## V7C.4 validated boundary and host contract

The host-only run `2026-10-30T135116.779346Z-91d2fda4555f-98babc9b`
completed on2026-10-30 at18:51 Helsinki. Independent validation records
10800.100598792 real elapsed seconds,2152 checkpoints, maximum absolute
wall/monotonic discrepancy92.965167ms and maximum checkpoint gap5.137944834s.
AC/open lid, boot identity and owned assertions were maintained; PID25250's
assertions for owner25200 were released. Output-manifest SHA256:
`530ca9d3919c918147b80514fa6fab2dfcac71cc789fe4cfacedff2a2987254b`.
The original observation remains labelled with source
`2f0d15709266b587f1911afa64679e607690de6d`; no result was relabelled.

The operating contract requires AC, open lid, verified run-owned assertions,
fail-closed monitoring, recorded hardware/environment fingerprint, **no concurrent
heavy jobs**, and a controlled reboot/update/session maintenance window. Operator
reservation and background-process diagnostics are required for comparative
trials. The guard cannot attest that a laptop is dedicated or prohibit deliberate
lid closure, logout, shutdown or a forced update. No such settings were changed.

A host-safety observation is not a scientific-result cache. Its original SUCCESS,
manifest and outputs are checked against its ORIGINAL experiment identity.
`host-runtime-compatibility-v1` additionally compares pinned Git objects for the
power guard, causal clock guard, observer CLI, generic provenance/run store and
dataset-manifest code. The entire observer module is compared by AST except its
validation-only `require_endurance` helper (never called by observation acquisition).
Hardware/packages, boot identity and recorded power policy must still match.
Missing source objects or changed relevant runtime fail closed. This permits an
unrelated shared-bootstrap implementation commit without pretending the old
observation ran from new source. Generic scientific cache checks still require
exact source/experiment identity; they were not changed.

Current suitability: conditional development/probes on this guarded Mac; **no72h
anchor is authorized**; repeated claim-generating V8 is not approved on this
unreserved interactive laptop. Prefer dedicated always-on owned/institutional
hardware if physical/session controls cannot be sustained. An engineering starting
budget is8logical CPUs,16GiB host RAM, enough memory for the existing~8GiB Docker
allocation, local SSD and>=20GiB free reserve beyond expected outputs. These are
planning budgets, not validated minimum performance. Migration requires a new
hardware/package fingerprint and supported OS power adapter, pinned kind/Kubernetes
smoke, controller/enforcement timing checks, fresh measured bootstrap and fresh
system calibration/precision planning. Do not transfer Mac timing measurements.
