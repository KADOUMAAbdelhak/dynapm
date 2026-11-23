# Slot replacement amendment v3: implementation and preflight

## What changed
- Executor commit **ce03b3d** on v8c5-service-transport (pushed). It adds the approved host-power slot replacement (docs/primary_slot_replacement_amendment.md).
- The treatment module is AST-identical outside the admission functions.
- The binding delta over observer 1b50282 equals the extended BINDING_DELTA.
- Spec executor-spec-v3.json (sha 89072590…) is derived from d741b746 by make_spec.py. It changes only executor_commit, binding_files, supersedes and correction.
- The campaign v2 identity transition 09563a1c… → 062fd115… changes exactly executor_commit and spec_sha256 (identity-transition-check.json).

## Evidence and tests
- Focused tests: 118 passed. They include a real-evidence test showing that v2 slot 9 (mains_power_lost, metrics null) is eligible and that slots 1–8 are valid.
- Full suite: 972 passed, 3 skipped, 53 errors. All the errors are the pre-existing Google modules, because data/google2019 is absent from the frozen repo.
- Retained runtime evidence of slot 9, taken before deleting its cluster: amended-v8-claim-campaign-v2/slot-09-retained/RETAINED_MANIFEST.json (sha b5cac631b669…; node copy, kubectl state/events, kind logs, docker inspect). The sealed attempt directory is untouched.
- Pinned images are intact.
- The task50 strict preflight first returned BLOCKED engine_not_isolated, because the retained slot 9 cluster was still present. After retention and deletion, it returned **PASS** (strict-preflight-result.json).

## Blockers
- Slot 9 is not replaced yet. That needs the user's explicit per-slot approval (rule 5).
- Step B v3 (~75 min, AC, same boot 26051F76) is required, because qualification 8a87c578 is bound to 738139b.

## Next actionable step
User approval for slot 9's replacement and a time for Step B v3 (prepared-step-b-command.json, not authorized).
