"""Amendment v3 operator: approved replacement of one host-power-invalidated primary slot.

Never starts a treatment. Without --apply it verifies everything and writes
nothing. With --apply, under the campaign lock, it seals an executor-only
identity transition (when the executor commit changed) and then returns the
approved slot to PENDING, keeping the invalid attempt. Run from the frozen repo:

  .venv/bin/python -m dynapm.scripts.task51_primary_slot_replacement \
      --spec SPEC --spec-sha256 H --root ROOT --sequence 9 \
      --approval replacements/slot-09-approval.json --approval-sha256 A [--apply]
"""
import argparse
import json
from pathlib import Path
import subprocess

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.system_validation import primary_observer_binding as observer_binding
from dynapm.system_validation import primary_slot_replacement as replacement
from dynapm.system_validation.service_checkpoint import (campaign_lock, replace_invalid_slot,
    transition_identity, verify_checkpoint)

SCOPE = 'AMENDED_V8_PRIMARY'


def campaign_identity(repo, spec, scope):
    """Exactly the identity expression of service_primary.campaign()."""
    from dynapm.system_validation.service_primary import (CONTRACT, SNAPSHOTS, source_binding,
        stable_spec_hash)
    provenance = source_binding(repo, spec)
    return dict(provenance, scope=scope, contract_sha256=CONTRACT, snapshot_sha256=SNAPSHOTS,
                spec_sha256=stable_spec_hash(spec), t0_policy=spec['t0_policy'],
                campaign_generation='v8-direct-service-primary-v1')


def plan(repo, root, spec, sequence, approval):
    """Verify every precondition; return (old identity, new identity, slot)."""
    if spec.get('schema') != observer_binding.SPEC_SCHEMA:
        raise ValueError('binding_spec_schema_required')
    state = json.loads((root/'checkpoint.json').read_text())
    old = state['identity']
    verify_checkpoint(root, state, old)
    if old.get('scope') != SCOPE:
        raise ValueError('claim_campaign_required')
    new = campaign_identity(repo, spec, SCOPE)
    if new != old:
        replacement.identity_difference(old, new)
        if subprocess.run(['git', 'merge-base', '--is-ancestor', old['executor_commit'], new['executor_commit']],
                          cwd=repo, capture_output=True).returncode != 0:
            raise ValueError('new_executor_must_descend_from_sealed_executor')
    slot = state['slots'][sequence-1]
    if slot['status'] != 'SEALED_INVALID':
        raise ValueError('replacement_requires_sealed_invalid_slot')
    if [s['status'] for s in state['slots'][:sequence-1]] != ['SEALED_VALID']*(sequence-1):
        raise ValueError('replacement_requires_valid_prefix')
    tid = slot['treatment_id']
    manifest = read_json(root/slot['manifest'])
    failure = root/replacement.failure_path(tid)
    invariant = replacement.require_eligible(manifest, read_json(failure), file_sha256(failure), tid)
    replacement.require_approval(read_json(root/approval), cell=slot['cell'], treatment_id=tid,
                                 manifest_sha256=slot['manifest_sha256'], failure_sha256=file_sha256(failure),
                                 invariant=invariant)
    return old, new, slot


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--spec-sha256', required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--sequence', type=int, required=True)
    p.add_argument('--approval', required=True, help='root-relative sealed approval path')
    p.add_argument('--approval-sha256', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    repo, root = Path.cwd(), a.root.resolve()
    if file_sha256(a.spec) != a.spec_sha256:
        raise ValueError('executor_spec_hash_mismatch')
    if Path(a.approval).is_absolute() or '..' in Path(a.approval).parts:
        raise ValueError('unsafe_evidence_path')
    if file_sha256(root/a.approval) != a.approval_sha256:
        raise ValueError('replacement_approval_hash_mismatch')
    spec = read_json(a.spec)
    with campaign_lock(root):
        old, new, slot = plan(repo, root, spec, a.sequence, a.approval)
        result = dict(sequence=a.sequence, invalid_treatment_id=slot['treatment_id'],
                      from_identity_sha256=fingerprint(old), to_identity_sha256=fingerprint(new),
                      transition_required=new != old, applied=False)
        if a.apply:
            if new != old:
                transition_identity(root, old, new, reason='amendment v3 executor for approved slot replacement')
            state = replace_invalid_slot(root, new, a.sequence, a.approval)
            result.update(applied=True, revision=state['revision'],
                          slot_status=state['slots'][a.sequence-1]['status'])
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
