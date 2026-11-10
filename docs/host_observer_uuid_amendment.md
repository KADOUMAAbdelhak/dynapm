# Prospective three-hour host observer amendment

Previous executor source: 67bfd37ee72e0096e4dfec974fd145f7a347e6e0.
Scientific design source: fe3b870149a156e7fecb88741d51cfb5c1ed86d7.
No scientific method, workload, snapshot, target, treatment order, or endpoint changes.

The failed night observation recorded the same boot UUID while kern.boottime
crossed from { sec = 1794336848, usec = 986377 } to
{ sec = 1794336849, usec = 60321 }. The calendar moved 73.944 ms across an integer
boundary. ManagedPowerGuard compared tv_sec integers and falsely reported a
reboot. Its failed record and the earlier lid/sleep failure remain unchanged.
Neither partial interval counts toward a qualification.

The prospective uuid_host_observer uses UUIDPowerGuard, whose primary identity is exact
kern.bootsessionuuid equality. Every existing five-second host checkpoint now
reads UUID/timeval through the UUID-before/timeval/UUID-after bracket. UUID change,
malformed/unavailable identity, or a material calendar discrepancy fails closed
on that observation. The raw strings and normalized values are retained in each
checkpoint. This is sampled detection, not a claim of continuous OS monitoring.

The full timeval is corroborating metadata against the initial fixed anchor
using the already approved MAX_CLOCK_DELTA_NS = 2,000,000,000 ns. Independent
power-state and identity reads may cross a second boundary; their agreement uses
the existing legacy-resolution-bin calculation and the same bound. No new
plus/minus-one-second tolerance is introduced. Calendar comparisons use the
fixed origin, not a rolling anchor that could conceal cumulative drift.

Strict AC/adapter, no corroborated battery deficit, open-lid observability,
unchanged power policy, both owned assertion types, assertion cleanup, the
2-second wall/monotonic bound and 30-second heartbeat-gap bound remain inherited
from ManagedPowerGuard. Power diagnostics keep their 30-second cadence. The
physical observation remains 10,800--21,600 seconds; the default is three hours.
No short test or historical partial observation can satisfy that duration.

Acquisition/summary schema is host-endurance-v2-uuid; inputs and dataset identity
are versioned so old records cannot be relabeled. The validator checks raw UUID
history, fixed calendar anchor, physical coverage and clock/power invariants;
it no longer demands a single integer calendar epoch for v2. Legacy v1 stays
identifiable and immutable. Versioned UUID runtime compatibility pins the UUID guard module
as well as the observer and original host/clock dependencies. Old acquisition
runtime identities are not silently reused.

Implementation and prospective amendment are sealed before a new observation.
This task runs offline tests only. No qualification is issued. The previous
primary executor remains bound to 67bfd37; adopting the new observer certificate
for a later 75-minute lifecycle requires explicit prospective executor provenance
binding. This amendment does not authorize any claim campaign or integration.

Next observation command (run only from the sealed amendment commit):

    .venv/bin/python -m dynapm.scripts.task49_host_uuid_observation \
      --repo /Users/fgtek002/dynapm-v8c-frozen \
      --observe --duration-seconds 10800

The legacy task35 observer, host_endurance.py, host_certificate.py and frozen
calibration config remain byte-identical to 67bfd37. The new task49 entry point
is deliberate: task35 is not authorized for the new UUID-based qualification.
Identity and inherited checkpoint operations share a reentrant lock so main and
background checkpoints cannot overwrite each other's identity samples.
