# Step B: 75-minute strict-AC primary lifecycle qualification — PASS

Executor 4c1326c (observer-bound), spec f5d78b95, scope DIAGNOSTIC_NON_CLAIM, slot 1 (static/periodic/rep 1).
Started 2026-11-19T11:00:10Z, finished 12:16:23Z, exit 0. Slot SEALED_VALID; cleanup deleted the cluster.

- Strict AC/power: guard RELEASED, no failure, 902 checkpoints, max drift 97011084 ns, max gap 5169466875 ns; boot 6C470F9C-9B15-4093-87C3-DDE6D713D7E6.
- Buckets validated: [300, 600, 900, 1200, 1500, 1800].
- Requests: 34200 scheduled = expected, 0 missing, 0 duplicates; independent reconstruction equals endpoint metrics in primary/transition/follow-up.
- Enforcement: 70m / 64 MiB ENFORCED at T0 (1.142 s), verified at every bucket.
- Telemetry complete; 0 clock rejections. Node/host request hashes match.
- Storage: slot 58801720 / 150994944 B; generator 26902079 / 67108864 B; minimum free 27479580672 B (> 22 GiB buffer).
- Checkpoint/resume: verified; resume selects slot 2 without changing checkpoint bytes. Slots 2-18 PENDING.
- Application: 0 restarts, ready at end. Primary-window outcomes (measured, not gates): {'connection_deadline': 2597, 'connection_refusal': 810, 'overload_drop': 4762, 'response_deadline': 503, 'success': 3928}.

Qualification record primary-qualification.json (SHA-256 b57c08ab395d7ddc3c20a2e74b09522e8d45fcc36ec755759100e144570b93a2) passes task48 and campaign() claim-admission checks.
Old pending 18-slot checkpoint 16c07107 unchanged. No claim treatment or integration started; Step C prepared only.
