# Primary slot replacement amendment (v3)

Status: **approved by the user ("Approve, implement", 2026-11-23)** for
implementation. Each replacement still needs its own sealed approval (rule 5).
It changes no scientific, workload, snapshot, target, treatment-order, endpoint
or clock rule.

## Why

Campaign v2 (`results/v8c_r2/amended-v8-claim-campaign-v2/claim-campaign`)
sealed slots 1–8 `SEALED_VALID`. Slot 9 (`static`, `abrupt_regime_shift`,
repetition 2, seed 2026110502, attempt `slot-09-6cefd2f6…`) was sealed
`SEALED_INVALID` at 2026-11-23T09:19:35Z:

- failure `HARNESS_MEASUREMENT_FAILURE` / `PowerGuardError`
  `mains_power_lost` (host switched to battery at 100 %);
- `host_continuity_failure.json` sha `8773591d…`; `metrics: null`, so no
  endpoint was accepted and no outcome of the treatment was observed;
- the boot (26051F76) and power policy did not change; AC was restored.

`docs/v8_service_primary.md` says invalid attempts "remain sealed and halt
execution" and that there is "no … automatic replacement". This amendment adds
one narrow, explicitly approved, outcome-blind replacement path. It does not make
replacement automatic.

## Rule

A sealed invalid slot may be replaced only if **all** of the following hold.

1. **Host-continuity cause only.** Its manifest failure is
   `HARNESS_MEASUREMENT_FAILURE` with type `PowerGuardError`. It has a sealed
   `host_continuity_failure.json` bound in the sealed inventory and in the error
   text. Its invariant must be one of `mains_power_lost`,
   `external_adapter_disconnected`,
   `external_power_insufficient_battery_draining` or `lid_closed`. Every other
   failure still halts for review exactly as today. That includes sleep, clock
   and heartbeat discontinuity, boot change, power-policy change, assertion or
   monitor loss, and any resource-enforcement, readiness, storage or cleanup
   failure.
2. **Outcome-blind.** The invalid manifest has `metrics: null` and no accepted
   endpoint. A slot that reached an accepted endpoint is never replaceable.
3. **Same cell, same position.** The replacement runs the identical frozen cell
   (method, scenario, seed, repetition, sequence) as the next slot. The frozen
   order is unchanged; slot 10 cannot start before slot 9 is `SEALED_VALID`.
4. **Bounded.** At most one replacement per cell and at most two per campaign.
   Exceeding either limit halts the campaign for review.
5. **Explicit per-slot approval.** Each replacement needs a sealed
   `replacement-approval.json` that names the slot, the invalid attempt id, its
   manifest sha and its failure sha, and quotes the user's approval. The
   approval is committed to an evidence branch before execution.
6. **Same host qualification.** The existing current-boot qualification
   (b0d91ebc…, boot 26051F76) and all preflight gates apply unchanged.

The failed attempt is never deleted or rewritten. It stays under `attempts/`,
the checkpoint records it in the slot's `replaced_attempts` list, and
`verify_checkpoint` re-verifies its sealed inventory on every resume. The paper
and campaign report must state the number of replaced attempts, their cells,
causes and times.

## Retained evidence of the failed attempt

The executor deliberately left slot 9's cluster
(`dynapm-v7b-calibration-v8r2-03a88f4ff7`) running (`cleanup.json`:
`deleted: false, node_copy_preserved: true`). Before the cluster is deleted:

- export `/var/local/dynapm-v8c5/<attempt>` from the control-plane node;
- export `kubectl get all,events -A -o json` and the kind logs;
- store all of these in a sibling `slot-09-retained/` directory with a manifest.

The sealed attempt directory itself is not touched.

## Code change (executor amendment v3, implemented)

The treatment stays AST-identical: `service_primary.py` changes only inside
`source_binding` and `host_qualification`, as before.

| File | Change |
|---|---|
| `dynapm/system_validation/service_checkpoint.py` | `verify_checkpoint` re-verifies the `replaced_attempts` (sealed inventory, eligibility, approval, limits) and the `identity_history`. `replace_invalid_slot()` moves the invalid record into `replaced_attempts` and returns the slot to `PENDING`. `transition_identity()` seals an executor-only identity change; each earlier attempt stays bound to the identity it was sealed under. `next_slot` is unchanged. |
| `dynapm/system_validation/primary_slot_replacement.py` (new) | Pure eligibility checks for rules 1–5. |
| `dynapm/scripts/task51_primary_slot_replacement.py` (new) | Dry run by default. With `--apply`, under the campaign lock, it seals the transition and applies the replacement. It never starts a treatment. |
| `dynapm/system_validation/primary_observer_binding.py` | `BINDING_DELTA` is extended by exactly these files. |
| `docs/primary_slot_replacement_amendment.md`, tests | New files. |

**Identity continuity.** Campaign identity includes `executor_commit` and
`spec_sha256`, so any new commit changes it. The checkpoint gains a single
sealed identity transition, 738139b → the new commit. It is accepted only if
the two identities differ solely in `executor_commit`, `spec_sha256` and the
binding-file hashes. Each sealed slot is verified against the identity recorded
when it was sealed.

## Required re-qualification (cost)

- New executor commit → new executor spec (only the binding fields change) →
  **new Step B lifecycle qualification** (~75 min on AC, diagnostic scope, own
  root, same boot). The current Step B (8a87c578…) is bound to 738139b and
  cannot be reused.
- The 3-hour host qualification is **not** repeated, as long as the Mac does not
  reboot and the power policy is unchanged.

## Execution order after approval

1. Implement the change and its tests; run the focused and full suites.
2. Commit the amendment, build the rebound spec and run the task50 strict preflight.
3. Retain slot 9's cluster evidence, then delete the cluster.
4. Run Step B v3 (~75 min, AC throughout).
5. Seal the slot 9 replacement approval and apply it with task51.
6. Resume v2: replacement slot 9, then 10–18, in user-sized blocks of 1–3 slots
   (~76 min each), on AC for the whole block.

Remaining primary work: about 10 slots (~12.7 h), plus Step B (~1.3 h).
For comparison, a fresh v3 campaign is 18 slots (~23 h) plus Step B.

## Not changed

- No pooling with campaign v1 or with old port-forward V8 results.
- None of the withdrawn claims return.
- No treatment, endpoint, snapshot, clock or storage rule changes.
- No result is submitted without explicit approval.
