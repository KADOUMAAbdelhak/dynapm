# Step B v2: 75-minute strict-AC primary lifecycle qualification (re-bound executor) — PASS

Executor 738139b (re-bound to boot 26051F76), spec d741b746, scope DIAGNOSTIC_NON_CLAIM, slot 1 (static/periodic/rep 1).
Started 2026-11-22T19:49:15Z, finished 21:05:23Z, exit 0. Slot SEALED_VALID; cleanup deleted the cluster.

- Strict AC/power: guard RELEASED, no failure, 900 checkpoints, max drift 84099709 ns, max gap 5178568834 ns; boot 26051F76-7B84-4CBD-A25D-1418E39980A2.
- Buckets validated: [300, 600, 900, 1200, 1500, 1800].
- Requests: 34200 scheduled = expected, 0 missing, 0 duplicates; independent reconstruction equals endpoint metrics in primary/transition/follow-up.
- Enforcement: 70m ENFORCED at T0; 13 enforcement rows.
- Storage: slot 58716429 / 150994944 B; generator 26890452 / 67108864 B; minimum free 39647178752 B (> 22 GiB buffer).
- Checkpoint/resume: verified; resume selects slot 2 without changing checkpoint bytes. Slots 2-18 PENDING. 48 manifest files, 0 mismatches.
- Application: 0 restarts, ready at end. Primary-window outcomes (measured, not gates): {'connection_deadline': 2471, 'connection_refusal': 813, 'overload_drop': 4771, 'response_deadline': 387, 'success': 4158}.

Qualification record primary-qualification.json (SHA-256 8a87c578b4c44883da39d9ead7d9ac8ef7f9ada71b9f20addfafdd2a53b5e18b) passes the campaign() claim-admission checks and the task48 spec-hash and evidence-inventory checks.
Protected pending checkpoint 16c07107 unchanged. No claim treatment or integration started. Campaign v2 prepared only (prepared-step-c-command.json): 3-slot blocks, free >= 31 GB gate per block; requires explicit user go-ahead.
