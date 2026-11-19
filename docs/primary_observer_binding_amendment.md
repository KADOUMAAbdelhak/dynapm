# Primary executor x task49 observer binding amendment

Binding-only. No scientific method, workload, snapshot, target, treatment order,
endpoint, T0 policy, clock bound or power criterion changes.

Scientific source: fe3b870149a156e7fecb88741d51cfb5c1ed86d7 (unchanged).
Qualified transport: b3fd0d1fa095dbaa13c2b035624d6336b24d60ca (unchanged).

## Why

The task49 three-hour current-boot host qualification PASSED (certificate
SHA-256 594ba9a2a14145bc8bf28f5d3349953b9250cc437abf0f2bd12e547e12d07059,
sealed in evidence commit 697c734). The unchanged strict primary preflight then
stopped at `clean_exact_executor_commit_required`: the primary specification
pins executor 67bfd37 while the approved observer is 1b50282, a descendant that
modifies `v8_host_identity.py`. Neither the gate nor the specification was
bypassed. The legacy `host_qualification` gate also only understands the v1
neutral-witness certificate, not the v2 UUID certificate.

## Design

A new executor specification schema,
`v8-service-primary-executor-spec-v2-observer-binding`, is admitted by
`primary_observer_binding.py`. `service_primary.source_binding` and
`service_primary.host_qualification` dispatch on that schema; for every other
schema they behave exactly as at 67bfd37. These two admission functions are the
only code in `service_primary.py` that may differ from 67bfd37: every other
top-level node is required to be AST-identical (`treatment_code_changed`).

Four identities are bound and verified separately, each with its own failure:

| Identity | Value | Verified by |
|---|---|---|
| primary executor | 67bfd37 | ancestry; additions over b3fd0d1 hashed **at 67bfd37** equal the original `executor_files` |
| task49 observer | 1b50282 | ancestry; exact delta 67bfd37..1b50282 equals the approved six-file set, hashed at 1b50282 (`observer_files`) |
| observer amendment | e4cbb223... | on-disk file hash, blob in evidence commit 6004732, and its recorded observer/primary commits |
| current-boot qualification | 594ba9a2... | on-disk hash, blob in evidence commit 697c734, every file in its OUTPUT_MANIFEST, certificate identity fields, re-derived `qualification_inputs` (full raw UUID history) and pinned UUID-observer runtime vs 1b50282 |

The binding commit itself must be a clean HEAD on `v8c5-service-transport`,
equal to the spec's `executor_commit`, distinct from 67bfd37 and 1b50282, and
its delta over 1b50282 must be exactly the five binding files listed in
`BINDING_DELTA`, with hashes equal to `binding_files`. Any observer, executor,
scientific or other file change fails `binding_delta_not_binding_only`.

Current boot: exact `kern.bootsessionuuid` equality with
6C470F9C-9B15-4093-87C3-DDE6D713D7E6, and the full `kern.boottime` timeval
against the certificate's fixed anchor within the unchanged
MAX_CLOCK_DELTA_NS = 2 s bound. The power policy (`pmset -g custom`) must equal
the qualification guard's. Any mismatch fails `current_boot_incompatible:*` or
`endurance_power_policy_changed`.

## Why the three-hour observation is not repeated

The binding changes no file in the pinned UUID-observer runtime (verified by
`require_same_uuid_runtime(repo, 1b50282)` matching the certificate), the boot
UUID must still be the qualified one, and the power policy must be unchanged.
These are exactly the repeat conditions recorded in the task49 disposition.
A reboot, policy change or observer-runtime change still fails closed and would
require a new observation.

## Scope

`task50_primary_binding_preflight` runs source binding, host qualification and
the unchanged strict `preflight()` only. It never calls `campaign()` or
`treatment()`: no cooldown, cluster, generator, 75-minute lifecycle, claim
treatment or integration. The pending 18-slot checkpoint
(`results/v8c_r2/20261109-next-strict-ac/qualification-campaign/checkpoint.json`,
16c07107...) is verified byte-identical before and after. Because campaign
identity includes executor provenance, a later 75-minute qualification under
this binding uses a new campaign root; the old checkpoint stays as evidence.
