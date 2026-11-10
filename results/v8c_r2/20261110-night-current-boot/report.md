# Current-boot host qualification: BLOCKED

The newly authorized night observation ran on unchanged source 67bfd37 with boot UUID 6C470F9C-9B15-4093-87C3-DDE6D713D7E6. It stopped after 7424.602 monotonic seconds (about 2h03m45s), before the required 10800 seconds. The historical daytime attempt remains separately failed and unchanged.

At 23:00:08 Helsinki time, the original ManagedPowerGuard reported host_boot_identity_changed. The concurrent witness recorded the same UUID in all 1476 readings. Near failure, kern.boottime changed from { sec = 1794336848, usec = 986377 } to { sec = 1794336849, usec = 60321 }: a 73.944 ms calendar change crossing a whole-second boundary. The legacy observer compares integer tv_sec, so it misclassified this as a boot change. The shift from the initial intent timestamp was 575.123 ms. The OS reason for the calendar adjustment was not independently established.

Offline reconstruction reproduces rejection by the legacy ManagedPowerGuard, acceptance of the same recorded UUID/timeval by the existing approved UUIDPowerGuard under its unchanged 2-second bound, and rejection of a different UUID. The exact 67bfd37 three-hour observer still uses ManagedPowerGuard; the amended primary executor uses UUIDPowerGuard. No source or qualification criteria were changed, and the failed run was not relabeled.

Recorded host checkpoints: 1476. Maximum wall/monotonic drift: 302.825375 ms. Maximum heartbeat gap: 5.111952209 s. All recorded checkpoints showed AC/lid valid and no external-power deficit. Both owned assertions were released. Docker and all three pinned image identities passed start preflight. Storage remained ample at final inspection (30.98 GiB).

The original 18-slot checkpoint was independently resumed read-only and remains byte-for-byte unchanged with all 18 PENDING. The previous approved qualification and the 17-file daytime failed-attempt inventory verified unchanged. No 75-minute lifecycle, claim treatment or integration started. No new qualification certificate was issued. Focused offline tests: 103 passed.

A prospective host-observer correction must align boot identity with the already-approved UUID semantics while retaining strict AC/lid/policy/assertion and 2-second/30-second continuity criteria. Then a fresh complete three-hour observation is required; neither failed interval counts toward it. No additional long run was started.
