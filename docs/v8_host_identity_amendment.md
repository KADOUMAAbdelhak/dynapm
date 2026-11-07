# V8C.3 host identity amendment

The frozen scientific source remains
`fe3b870149a156e7fecb88741d51cfb5c1ed86d7`.
All files present at that commit remain byte-identical. This amendment adds an
explicit execution harness, its host validator and regression tests. The original
launcher remains available under its original contract and source requirements.

Both legacy paths parse the integer `sec` member of `sysctl -n kern.boottime`.
Neither converts a float, reconstructs time from uptime nor parses a local date.
The endurance log stored only integer seconds. It did not store the full raw
timeval or a boot UUID. The sealed neutral-run campaign stores the UUID from
`sysctl -n kern.bootsessionuuid`.

Twelve reads over 22.3 seconds retained the same UUID and the same
raw timeval, `{ sec = 1793829797, usec = 37987 }`. The original qualified
integer epoch was 1793829796. Fluctuation during the short repeated-read window
was zero. The exact historical microsecond adjustment and its initiating process
cannot be reconstructed from the legacy log.

Apple's kernel calendar-setting implementation adjusts boot calendar time.
Consequently calendar boot time can change within one UUID boot session.
The defect is using integer calendar-time equality as reboot identity.
The evidence supports the same boot with changed calendar metadata. It does
not establish a Python rounding error.
[Kernel clock source](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/kern/clock.c)
[Kernel sysctl source](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c)

The amended validator requires exact UUID equality. To associate the legacy
qualification with a UUID, it verifies all three sealed neutral witnesses that
passed the original qualifier and recorded its exact integer boot epoch. A
separate hash-bound amendment pins their intent and terminal hashes and all
original qualification hashes. Original durations, checkpoints and guard history
remain intact.

Calendar metadata remains corroborating evidence. A legacy integer second
represents a timeval interval of one second. The validator computes distance
from that interval, then applies the existing two-second host-clock bound.
New guards retain full microseconds and compare against their initial full
timeval using that same existing bound. A different UUID always fails, even
with the same timestamp. Missing provenance, malformed values and materially
inconsistent calendar values fail closed. This adds no arbitrary one-second
acceptance tolerance. The original wall/monotonic two-second check and
thirty-second checkpoint-gap check remain inherited and unchanged, together
with AC, lid, adapter, policy and owned-assertion validation.

The versioned entrypoint is
`python -m dynapm.scripts.task45_v8_host_harness preflight`.
It requires an explicit original endurance path, amendment path and trusted
amendment SHA, exact expected harness commit and a new output record path.
Its `run` action retains the frozen primary plan and explicit live authorization.
It does not implement integration or automatic replacement.

Each new primary intent and manifest embeds both
`frozen_scientific_source` and `execution_harness_commit`, plus the amendment
SHA. Clock context records the actual execution harness commit. The old campaign
binding remains the scientific binding at the frozen source. Source checking
requires a clean committed tree, verifies every original file against the frozen
commit, and permits exactly the four named additive harness files. Any modified,
deleted or additional non-approved source fails closed.

No V8 treatment is executed by this amendment task.
