"""Slot replacement amendment (v3): outcome-blind, explicitly approved, host-power only.

Pure checks, no I/O. A sealed invalid primary slot may be replaced only when the
power guard stopped it for a host-power invariant before any outcome was
accepted, the user approved that exact attempt, and the per-slot / per-campaign
limits hold. The invalid attempt is never rewritten; the checkpoint keeps it in
``replaced_attempts`` and re-verifies it on every resume. Any other failure still
halts the campaign for review. See docs/primary_slot_replacement_amendment.md.
"""

APPROVAL_SCHEMA = 'v8-primary-slot-replacement-approval-v1'
TRANSITION_SCHEMA = 'v8-primary-campaign-identity-transition-v1'
# Host-power invariants raised by host_power.power_state / PowerGuard. Clock,
# heartbeat, boot, policy, assertion and monitor failures are deliberately absent.
ELIGIBLE_INVARIANTS = ('mains_power_lost', 'external_adapter_disconnected',
                       'external_power_insufficient_battery_draining', 'lid_closed')
MAX_PER_SLOT = 1
MAX_PER_CAMPAIGN = 2
# An identity transition may change only the executor commit and the spec hash.
TRANSITION_FIELDS = frozenset({'executor_commit', 'spec_sha256'})
FAILURE_NAME = 'host_continuity_failure.json'


class ReplacementError(ValueError):
    pass


def invariant_class(invariant):
    """Leading invariant name (text before the first ':' or ';')."""
    if not isinstance(invariant, str) or not invariant:
        raise ReplacementError('host_continuity_invariant_missing')
    return invariant.split(';', 1)[0].split(':', 1)[0].strip()


def failure_path(treatment_id):
    return 'attempts/'+treatment_id+'/outputs/'+FAILURE_NAME


def require_eligible(manifest, failure, failure_sha256, treatment_id):
    """Rules 1-2: sealed invalid, no observed outcome, host-power invariant, bound evidence."""
    if not isinstance(manifest, dict) or not isinstance(failure, dict):
        raise ReplacementError('malformed_invalid_attempt')
    if manifest.get('status') != 'SEALED_INVALID' or manifest.get('treatment_id') != treatment_id:
        raise ReplacementError('replacement_requires_sealed_invalid_attempt')
    if manifest.get('metrics') is not None:
        raise ReplacementError('replacement_forbidden_after_observed_outcome')
    reason = manifest.get('failure') or {}
    if reason.get('category') != 'HARNESS_MEASUREMENT_FAILURE' or reason.get('type') != 'PowerGuardError':
        raise ReplacementError('replacement_requires_host_power_failure')
    path = failure_path(treatment_id)
    if (manifest.get('files', {}).get(path) != failure_sha256
            or 'host_continuity_failure_sha256='+failure_sha256 not in str(reason.get('error', ''))):
        raise ReplacementError('host_continuity_failure_unbound')
    context = failure.get('context') or {}
    if context.get('run_id') != treatment_id or context.get('scope') != manifest.get('scope'):
        raise ReplacementError('host_continuity_failure_context_mismatch')
    name = invariant_class(failure.get('invariant'))
    if name not in ELIGIBLE_INVARIANTS:
        raise ReplacementError('invariant_not_replaceable:'+name)
    if name not in str(reason.get('error', '')):
        raise ReplacementError('host_continuity_failure_unbound')
    return name


def require_approval(approval, *, cell, treatment_id, manifest_sha256, failure_sha256, invariant):
    """Rule 5: the user approved exactly this attempt of exactly this cell."""
    if not isinstance(approval, dict):
        raise ReplacementError('malformed_replacement_approval')
    expected = dict(schema=APPROVAL_SCHEMA, sequence=cell['sequence'], cell=cell,
                    invalid_treatment_id=treatment_id, invalid_manifest_sha256=manifest_sha256,
                    host_continuity_failure_sha256=failure_sha256, invariant=invariant)
    for key, value in expected.items():
        if approval.get(key) != value:
            raise ReplacementError('replacement_approval_mismatch:'+key)
    if (approval.get('approved_by_user') is not True or not approval.get('user_approval_quote')
            or not approval.get('approved_at')):
        raise ReplacementError('explicit_user_approval_required')
    return approval


def require_limits(per_slot_counts):
    """Rule 4: at most one replacement per cell and two per campaign."""
    if any(n > MAX_PER_SLOT for n in per_slot_counts):
        raise ReplacementError('replacement_limit_per_slot_exceeded')
    if sum(per_slot_counts) > MAX_PER_CAMPAIGN:
        raise ReplacementError('replacement_limit_per_campaign_exceeded')


def identity_difference(old, new):
    """Keys that differ; a transition must change something and only TRANSITION_FIELDS."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ReplacementError('malformed_identity_transition')
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    if not changed or not changed <= TRANSITION_FIELDS:
        raise ReplacementError('identity_transition_not_executor_only:'+','.join(sorted(changed)))
    return changed
