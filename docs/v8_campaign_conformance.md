# V7E offline campaign conformance

The frozen study is identified by the SHA-256 of `design.json`,
`4374365b28d2c3ba9258a9610c190dbc70c6cdc373e86888162150c6aa825c5d`.
The accompanying Markdown has SHA-256
`696d685fa927ab6635621149d743781f8879b55137e952b89b5cdfc234923bdb`.
The offline loader requires both digests and the frozen source bindings.

## Conformance and remaining execution work

| Area | Verified offline | Production dependency |
|---|---|---|
| Matrix | Exactly 24 core and four mandatory secondary cells. Cell identity includes the ordered position, block, scenario, seed, method and duration. | Physical campaign worker |
| Shared input | Per-cell immutable bootstrap binding and common scenario/seed/config contract hash. Synthetic attempts use distinct cluster, Pod, application, profile, controller and telemetry identities. | Reconcile actual offered trace bytes, real runtime identities and all three qualified bootstrap artifacts |
| Order | Frozen sequence rechecked against independent counterbalance enumeration. Recovery cannot skip a failed cell or reorder a later one. | Persistent production campaign binding |
| Recovery | Exclusive journal lock, atomic publish, read-only event files, source/config/artifact/boot identity binding and hash-chain replay. | Verify real process/cluster disposition after interruption and manage reviewed boot transitions |
| Analysis | Scenario-specific run summaries, all replicate differences, paired t and fixed-60 Bonferroni intervals, point-estimate Pareto, churn and maintenance summaries. Secondary pairs are descriptive. | Independently validate physical raw-to-summary lineage, allocation integrals, clock evidence and full telemetry coverage |

The only new CLI entry point is a synthetic dry run. The existing calibration
runner accepts PW-6h on stable/periodic scenarios, acquires a separate bootstrap,
uses the legacy request/limit actuator and skips the terminal profile observation.
The reservation diagnostics exercise real bounded actuation with engineering
stimuli. Neither provides the frozen 48-hour V8 worker. Using those entry points
as a production V8 executor would be a scientific mismatch.

Before launch, build and audit the physical adapter that combines qualified
shared-history initialization, frozen per-cell seeds, exact offered-arrival
accounting, request drain, independent node enforcement, clock v2 and 576
physical buckets at 50 samples and 270 seconds of receipt span. The terminal
bucket must feed profile accounting without a post-horizon actuation. Bind
raw/output manifests and validate complete request/telemetry/actuation streams
before accepting summaries. Keep CPU requests equal to limits and memory limits
fixed at 1024 MiB while changing the memory reservation. Use acknowledged
requests and verified allocated reservations separately in resource integrals.
The legacy calibration percentile bootstrap estimator remains separate.

## Treatment-level recovery and calendar rules

A durable START is an active attempt until an explicit terminal event. A process
restart on the same boot replays the journal. It cannot create a replacement for
an unresolved START. In a physical adapter, reconcile the original worker and
cluster and preserve its artifacts before recording a terminal classification.
No interrupted partial exposure is stitched to a second run.

A valid complete terminal record advances exactly one cell. Application timeouts,
HTTP errors and overload drops stay in the offered-request denominator, including
requests offered before the endpoint whose outcomes arrive during drain.
Operational termination advances the ledger with censored evidence and undefined
full-horizon endpoints. A complete primary interval requires all three planned
paired differences. No extrapolation, favorable complete-case inference or
performance replacement is used. Degenerate data receive no zero-width CI.

A harness failure blocks the same cell. An eligible exogenous failure requires a
separate explicit replacement approval and a new attempt ID under the identical
cell and trace contract, with fresh runtime identities. The limit is two for the
whole campaign. Approval identifiers here are synthetic test inputs. A physical
launcher must require actual authorization. Exhaustion or an ineligible failure
leaves the campaign incomplete. Every failed attempt remains in the analysis
manifest. The ledger does not detect deleted suffixes without an independently
retained checkpoint. Archive the latest checkpoint receipt outside the working
journal and validate it when reopening. A corrupt entry or gap fails closed.

Pausing before a START leaves the cell pending and charges no replacement.
Multi-day gaps between treatments or blocks are allowed within the agreed
calendar budget. Recheck host readiness and identities, maintain the fixed order,
keep complete 48-hour exposures, and record elapsed calendar gaps and host
conditions. The current offline ledger rejects a changed boot identity. A real
planned reboot needs a reviewed between-cell host recertification transition
bound to the same campaign, which remains a production adapter requirement.

| Failure during measurement | Fixed time consumed, including startup | Required disposition |
|---|---:|---|
| Hour 1 | 1h45m | Preserve partial evidence, classify cause, leave 48h endpoints undefined |
| Hour 24 | 24h45m | Same rule, with no extrapolation from half a run |
| Hour 47 | 47h45m | Same rule, with no near-complete exception |

Additional setup, cleanup and finalization time is charged as elapsed overhead.
A permitted replacement starts the same cell from scratch and adds the actual
failed exposure to the planned calendar. Any replacement or pause shifts all
subsequent wall-clock offsets without altering sequence positions. A planned
cell that cannot fit the remaining calendar stays pending or ends the campaign
as incomplete. Secondary cases are scheduled regardless of primary outcomes.

## Bootstrap slots and one-Mac calendar

Block 1 is verified by the existing qualification and artifact loader, including
lineage and 288 accepted buckets. Its artifact is
`51aad0e364d6f4774f8c51ab2cb7544eac87d7ebdb36e492eba648c014dffd2b`.
B2 and B3 have unbound artifact IDs. The offline slot definitions require the
stable reference workload, acquisition seed 20251022, 24h physical acquisition
and 45m startup. The acquisition slots precede all primary and secondary runs.

| Slot | Fixed start offset | Fixed end offset | Treatment seed |
|---|---:|---:|---:|
| B2 acquisition | 0d 00:00 | 1d 00:45 | 2026110502 |
| B3 acquisition | 1d 00:45 | 2d 01:30 | 2026110503 |

Offsets below include both acquisitions and each treatment's 45m startup.
Cumulative treatment time excludes acquisitions. Setup, teardown, request drain,
validation, pauses and replacements add elapsed time. A calendar start date
requires an actual host allocation.

| Cell | Block/artifact | Scenario | Method | Seed | Start offset | End offset | Cumulative treatment |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | qualified B1 | periodic | pw_12h | 2026110501 | 2d 01:30 | 4d 02:15 | 2d 00:45 |
| 2 | qualified B1 | periodic | pw_3h | 2026110501 | 4d 02:15 | 6d 03:00 | 4d 01:30 |
| 3 | qualified B1 | periodic | static | 2026110501 | 6d 03:00 | 8d 03:45 | 6d 02:15 |
| 4 | qualified B1 | periodic | full_rewrite | 2026110501 | 8d 03:45 | 10d 04:30 | 8d 03:00 |
| 5 | qualified B1 | abrupt_regime_shift | pw_3h | 2026110501 | 10d 04:30 | 12d 05:15 | 10d 03:45 |
| 6 | qualified B1 | abrupt_regime_shift | static | 2026110501 | 12d 05:15 | 14d 06:00 | 12d 04:30 |
| 7 | qualified B1 | abrupt_regime_shift | full_rewrite | 2026110501 | 14d 06:00 | 16d 06:45 | 14d 05:15 |
| 8 | qualified B1 | abrupt_regime_shift | pw_12h | 2026110501 | 16d 06:45 | 18d 07:30 | 16d 06:00 |
| 9 | B2 pending | abrupt_regime_shift | static | 2026110502 | 18d 07:30 | 20d 08:15 | 18d 06:45 |
| 10 | B2 pending | abrupt_regime_shift | full_rewrite | 2026110502 | 20d 08:15 | 22d 09:00 | 20d 07:30 |
| 11 | B2 pending | abrupt_regime_shift | pw_12h | 2026110502 | 22d 09:00 | 24d 09:45 | 22d 08:15 |
| 12 | B2 pending | abrupt_regime_shift | pw_3h | 2026110502 | 24d 09:45 | 26d 10:30 | 24d 09:00 |
| 13 | B2 pending | periodic | pw_3h | 2026110502 | 26d 10:30 | 28d 11:15 | 26d 09:45 |
| 14 | B2 pending | periodic | static | 2026110502 | 28d 11:15 | 30d 12:00 | 28d 10:30 |
| 15 | B2 pending | periodic | full_rewrite | 2026110502 | 30d 12:00 | 32d 12:45 | 30d 11:15 |
| 16 | B2 pending | periodic | pw_12h | 2026110502 | 32d 12:45 | 34d 13:30 | 32d 12:00 |
| 17 | B3 pending | periodic | static | 2026110503 | 34d 13:30 | 36d 14:15 | 34d 12:45 |
| 18 | B3 pending | periodic | full_rewrite | 2026110503 | 36d 14:15 | 38d 15:00 | 36d 13:30 |
| 19 | B3 pending | periodic | pw_12h | 2026110503 | 38d 15:00 | 40d 15:45 | 38d 14:15 |
| 20 | B3 pending | periodic | pw_3h | 2026110503 | 40d 15:45 | 42d 16:30 | 40d 15:00 |
| 21 | B3 pending | abrupt_regime_shift | full_rewrite | 2026110503 | 42d 16:30 | 44d 17:15 | 42d 15:45 |
| 22 | B3 pending | abrupt_regime_shift | pw_12h | 2026110503 | 44d 17:15 | 46d 18:00 | 44d 16:30 |
| 23 | B3 pending | abrupt_regime_shift | pw_3h | 2026110503 | 46d 18:00 | 48d 18:45 | 46d 17:15 |
| 24 | B3 pending | abrupt_regime_shift | static | 2026110503 | 48d 18:45 | 50d 19:30 | 48d 18:00 |
| 25 | qualified B1 | stable | static | 2026110501 | 50d 19:30 | 52d 20:15 | 50d 18:45 |
| 26 | qualified B1 | stable | pw_3h | 2026110501 | 52d 20:15 | 54d 21:00 | 52d 19:30 |
| 27 | qualified B1 | burst | pw_3h | 2026110501 | 54d 21:00 | 56d 21:45 | 54d 20:15 |
| 28 | qualified B1 | burst | static | 2026110501 | 56d 21:45 | 58d 22:30 | 56d 21:00 |

The fixed program is 58d 22h30m. With two largest-attempt reserves it is
63 days before additional elapsed overhead. The 70-day envelope is proposed.

## Storage projection and guard

The projection uses preserved neutral evidence. The 24h parent held 352,800
request rows averaging 212 bytes, clock envelopes averaging 3,946 bytes, accepted
telemetry averaging 1,436 bytes and host checkpoints averaging 2,899 bytes.
Independent node records from V7C.13 averaged 1,978 bytes. The estimate budgets
512 bytes per offered request, 6 KiB per envelope/accepted pair, 2.25 KiB per
1 Hz node record, 3 KiB per host checkpoint and 128 MiB for other outputs.
These are planning assumptions and require verification against the final writer.

| Scenario | Nominal 48h offers | Projected output per treatment |
|---|---:|---:|
| Stable | 691,200 | 1.13 GiB |
| Periodic | 1,191,600 | 1.37 GiB |
| Burst | 883,200 | 1.23 GiB |
| Abrupt | 1,382,400 | 1.46 GiB |

Projected total is 39.82 GiB including two acquisitions and their artifacts,
before failed attempts. The measured volume had roughly 38 GiB free. The
proposed conservative launch guard is 112 GiB free, comprising 84 GiB for 28
successful treatments at 3 GiB each, 2 GiB for the acquisitions/artifacts, 6 GiB
for two replacement slots and a 20 GiB free floor. This operational storage
allowance does not change N, duration or scientific coverage. Recompute the
remaining budget before each start and monitor the free floor and writer growth
throughout physical execution. A separate destination must be checked on its
actual filesystem, including temporary staging space. The existing space can
cover the two bootstrap acquisitions in isolation, subject to their own guard.

Retain raw request outcomes, original clocks and telemetry, node/Pod/patch
observations, coverage and host guards, provenance, failed attempts and all
artifact inventories. Budget the data uncompressed. Only remove owned ephemeral
clusters or verified disposable scratch after evidence is safely published.
Archival relocation requires verified hashes and a recoverable index before
any deletion. Preserve prior evidence and every authoritative copy referenced
by the campaign. No automatic pruning of claim-relevant streams is permitted.

## Gates

Before acquiring B2/B3, separately authorize the two stable bootstrap-only
slots and verify current-boot endurance, AC/open lid, controlled local host,
source/config/images, disk and exclusive execution. Qualify full 24h coverage,
causal clocks, host/cleanup and exact immutable bytes. Require distinct parent
runs and source instances, nonoverlapping acquisition windows and independently
verified artifacts. Lock the first qualifying acquisition for each planned slot
before any comparative outcome. No content-based backfill or substitution.

Before V8 launch, bind the three qualified artifacts to the full campaign,
complete the continuous worker and physical evidence integration described
above, validate raw storage growth and make sufficient space available, establish
the controlled host/calendar, and obtain separate execution authorization.
The current review is BLOCKED for production conformance. The synthetic ledger,
calendar and estimator are available for offline use.
