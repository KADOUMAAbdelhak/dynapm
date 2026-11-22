# task49 current-boot qualification (v2, boot 26051F76)

The three-hour host qualification on the current boot PASSED. The Mac was shut down after the v1-boot campaign halted, which invalidated boot 6C470F9C, so this is a fresh, prospective observation, not a reuse of any earlier interval.

- Observer: task49 at approved commit 1b50282 (unchanged runtime; observer amendment e4cbb223… unchanged).
- Run: `results/host_endurance/runs/9df3b3f0…/2026-11-22T151815.248945Z-9df3b3f0b8df-30075d02`, 15:18:15–18:18:15 UTC, returncode 0, status COMPLETE.
- Elapsed 10800.125 s; independently reconstructed checkpoint span 10800.091 s; 2139 checkpoints, all with boot UUID 26051F76-7B84-4CBD-A25D-1418E39980A2.
- Max wall/monotonic drift 157.0 ms; max checkpoint gap 5.157 s; max boot-calendar discrepancy 103.4 ms. Unchanged limits: 2 s clock/calendar, 30 s gap.
- AC power and lid open at every checkpoint; battery 100% throughout; both owned caffeinate assertions released (release_confirmed true); no failure recorded.
- Current host after the run: same boot UUID, AC, lid open, pmset policy identical to the run's recorded policy; 43.4 GB free.
- 330 files of earlier sealed evidence (v1 qualification, 75-min lifecycle, halted campaign v1) verified unchanged.

Qualification SHA-256: see OUTPUT_MANIFEST.json (`qualification_sha256`).

Binding status: the sealed primary binding (commit 4c1326c) pins boot 6C470F9C and the v1 certificate, so it correctly rejects this certificate (`current_boot_qualification_identity_mismatch`). The certificate passes `require_certificate` when the boot UUID constant is the new one. Next required step: a binding-only re-binding amendment that changes only the qualification path/SHA/evidence commit and boot UUID, followed by strict preflight and a new 75-minute Step B. No lifecycle, claim treatment or integration was started; the campaign v1 remains HALTED and v2 has not started.

`build_certificate.py` in this directory is the exact builder that produced the validation, terminal and certificate files.
