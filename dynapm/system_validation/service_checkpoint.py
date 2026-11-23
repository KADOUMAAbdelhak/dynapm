"""Slot-atomic persistence for a prospective Service campaign; no live execution.

Campaign identity excludes the current host session. A new session must qualify
before begin(), while a completed slot is verified against its original session.

Amendment v3 (docs/primary_slot_replacement_amendment.md) adds only two explicit,
lock-held operations: an executor-only identity transition, after which every
earlier attempt is still verified against the identity it was sealed under, and
the approved replacement of a host-power-invalidated slot, which keeps the
invalid attempt in ``replaced_attempts``. Neither starts a treatment.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import shutil
import uuid

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, utc_now
from dynapm.system_validation.bounded_v8 import cells
from dynapm.system_validation import primary_slot_replacement as replacement

SCHEMA = 'v8-service-primary-checkpoint-v1'
STATUSES = {'PENDING', 'RUNNING', 'SEALED_VALID', 'SEALED_INVALID', 'INTERRUPTED'}
RESERVE = 20 * 2**30


def atomic_record(path, value, *, minimum_free=RESERVE):
    path = Path(path)
    payload = (canonical_json(value) + '\n').encode()
    if shutil.disk_usage(path.parent).free - len(payload) < minimum_free:
        raise ValueError('storage_reserve_checkpoint_write')
    temporary = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as sink:
            sink.write(payload)
            sink.flush()
            os.fsync(sink.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def campaign_lock(root):
    """Lock spans verification, execution, sealing and the checkpoint update."""
    root = Path(root)
    with (root / 'campaign.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('campaign_already_owned') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def new_checkpoint(identity):
    if identity.get('scope') not in ('AMENDED_V8_PRIMARY', 'DIAGNOSTIC_NON_CLAIM', 'DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'):
        raise ValueError('explicit_campaign_scope_required')
    return dict(schema=SCHEMA, identity=deepcopy(identity), identity_sha256=fingerprint(identity),
                revision=0, updated_at=utc_now(), slots=[dict(cell=c, status='PENDING',
                treatment_id=None, manifest=None, manifest_sha256=None, request_sha256=None,
                endpoint_sha256=None, continuity_sha256=None, started_at=None, ended_at=None)
                for c in cells()])


def _verify_history(root, state, identity):
    """Amendment v3: sealed executor-only identity transitions. Returns tid -> identity."""
    history = state.get('identity_history', [])
    if not isinstance(history, list):
        raise ValueError('campaign_identity_history_malformed')
    chain = [entry.get('identity') if isinstance(entry, dict) else None for entry in history] + [identity]
    sealed_under = {}
    for index, entry in enumerate(history):
        old, new = chain[index], chain[index+1]
        try:
            replacement.identity_difference(old, new)
        except ValueError as exc:
            raise ValueError('campaign_identity_transition_invalid') from exc
        if entry.get('identity_sha256') != fingerprint(old):
            raise ValueError('campaign_identity_transition_invalid')
        record_path = _evidence_path(root, entry.get('record'))
        if file_sha256(record_path) != entry.get('record_sha256'):
            raise ValueError('campaign_identity_transition_record_changed')
        record = json.loads(record_path.read_text())
        tids = entry.get('treatment_ids')
        if (record.get('schema') != replacement.TRANSITION_SCHEMA
                or record.get('from_identity_sha256') != fingerprint(old)
                or record.get('to_identity_sha256') != fingerprint(new)
                or not isinstance(tids, list) or record.get('treatment_ids') != tids):
            raise ValueError('campaign_identity_transition_record_mismatch')
        for tid in tids:
            if not isinstance(tid, str) or tid in sealed_under:
                raise ValueError('campaign_identity_transition_record_mismatch')
            sealed_under[tid] = old
    return sealed_under


def _verify_replaced(root, slot, record, identity):
    """Re-verify one replaced invalid attempt: sealed inventory, eligibility and approval."""
    if not isinstance(record, dict) or record.get('status') != 'SEALED_INVALID':
        raise ValueError('replaced_attempt_must_be_sealed_invalid')
    bound = dict(record, cell=slot['cell'])
    manifest = verify_slot(root, bound, identity)
    tid = record['treatment_id']
    failure = _evidence_path(root, replacement.failure_path(tid))
    digest = file_sha256(failure)
    invariant = replacement.require_eligible(manifest, json.loads(failure.read_text()), digest, tid)
    approval = _evidence_path(root, record.get('approval'))
    if file_sha256(approval) != record.get('approval_sha256'):
        raise ValueError('replacement_approval_changed')
    replacement.require_approval(json.loads(approval.read_text()), cell=slot['cell'], treatment_id=tid,
                                 manifest_sha256=record['manifest_sha256'], failure_sha256=digest,
                                 invariant=invariant)


def verify_checkpoint(root, state, identity):
    if (state.get('schema') != SCHEMA or state.get('identity') != identity
            or state.get('identity_sha256') != fingerprint(identity)
            or type(state.get('revision')) is not int or state['revision'] < 0):
        raise ValueError('campaign_identity_mismatch')
    slots = state.get('slots', [])
    if len(slots) != 18:
        raise ValueError('exact_18_slots_required')
    sealed_under = _verify_history(root, state, identity)
    pending_seen = False
    blocked = None
    treatment_ids = set()
    replaced_counts = []
    for slot, cell in zip(slots, cells(), strict=True):
        status = slot.get('status')
        if slot.get('cell') != cell or status not in STATUSES:
            raise ValueError('frozen_slot_or_status_mismatch')
        replaced = slot.get('replaced_attempts', [])
        if not isinstance(replaced, list):
            raise ValueError('replaced_attempts_malformed')
        if replaced and (pending_seen or blocked is not None):
            raise ValueError('noncontiguous_completed_prefix')
        replaced_counts.append(len(replaced))
        for record in replaced:
            ident = record.get('treatment_id') if isinstance(record, dict) else None
            if not ident or ident in treatment_ids or not record.get('started_at'):
                raise ValueError('missing_or_reused_treatment_identity')
            treatment_ids.add(ident)
            _verify_replaced(root, slot, record, sealed_under.get(ident, identity))
        if status == 'PENDING':
            if any(slot.get(k) is not None for k in ('treatment_id', 'manifest', 'manifest_sha256',
                    'request_sha256', 'endpoint_sha256', 'continuity_sha256', 'started_at', 'ended_at')):
                raise ValueError('pending_slot_has_attempt_evidence')
            pending_seen = True
            continue
        if pending_seen or blocked is not None:
            raise ValueError('noncontiguous_completed_prefix')
        ident = slot.get('treatment_id')
        if not ident or ident in treatment_ids or not slot.get('started_at'):
            raise ValueError('missing_or_reused_treatment_identity')
        treatment_ids.add(ident)
        if status in ('RUNNING', 'INTERRUPTED'):
            blocked = status
        elif status in ('SEALED_VALID', 'SEALED_INVALID'):
            verify_slot(root, slot, sealed_under.get(ident, identity))
            if status == 'SEALED_INVALID':
                blocked = status
    replacement.require_limits(replaced_counts)
    if not set(sealed_under) <= treatment_ids:
        raise ValueError('campaign_identity_transition_record_mismatch')
    attempts = Path(root) / 'attempts'
    if attempts.exists():
        for attempt in attempts.iterdir():
            if attempt.is_symlink() or not attempt.is_dir() or attempt.name not in treatment_ids:
                raise ValueError('unreferenced_attempt_requires_review')
    return state


def _evidence_path(root, relative):
    if not isinstance(relative, str):
        raise ValueError('missing_evidence_path')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('unsafe_evidence_path')
    root = Path(root).resolve()
    candidate = root / path
    if any(p.is_symlink() for p in [candidate, *candidate.parents] if p != root.parent):
        raise ValueError('linked_evidence_forbidden')
    if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
        raise ValueError('missing_or_external_evidence')
    return candidate


def verify_slot(root, slot, identity):
    if slot.get('manifest') != 'attempts/'+slot['treatment_id']+'/manifest.json':
        raise ValueError('slot_manifest_location_mismatch')
    manifest_path = _evidence_path(root, slot['manifest'])
    if file_sha256(manifest_path) != slot['manifest_sha256']:
        raise ValueError('slot_manifest_hash_mismatch')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('campaign_identity_sha256') != fingerprint(identity)
            or manifest.get('cell') != slot['cell']
            or manifest.get('treatment_id') != slot['treatment_id']
            or manifest.get('scope') != identity['scope']
            or manifest.get('status') != slot['status'] or not slot.get('ended_at')):
        raise ValueError('sealed_slot_binding_mismatch')
    files = manifest.get('files', {})
    if not files:
        raise ValueError('empty_sealed_inventory')
    for path, digest in files.items():
        if file_sha256(_evidence_path(root, path)) != digest:
            raise ValueError('sealed_slot_file_hash_mismatch')
    for name, field in [('requests', 'request_sha256'), ('endpoint', 'endpoint_sha256'),
                        ('continuity', 'continuity_sha256')]:
        path = manifest.get(name + '_path')
        if path not in files or files[path] != slot[field]:
            raise ValueError('required_slot_output_unbound')
    return manifest


def next_slot(root, state, identity):
    verify_checkpoint(root, state, identity)
    for slot in state['slots']:
        if slot['status'] in ('RUNNING', 'INTERRUPTED', 'SEALED_INVALID'):
            raise ValueError('interrupted_or_invalid_slot_requires_replacement_review')
        if slot['status'] == 'PENDING':
            return deepcopy(slot['cell'])
    return None


class Checkpoint:
    """Caller holds campaign_lock for the lifetime of this object."""
    def __init__(self, root, identity, *, resume=False):
        self.root = Path(root)
        self.path = self.root / 'checkpoint.json'
        self.identity = deepcopy(identity)
        if resume:
            self.state = json.loads(self.path.read_text())
            verify_checkpoint(self.root, self.state, self.identity)
            # A surviving RUNNING record means the previous launcher did not seal.
            # Never reconstruct an endpoint or resume the middle of that treatment.
            if any(slot['status'] == 'RUNNING' for slot in self.state['slots']):
                self.interrupt()
        else:
            if self.path.exists() or any(self.root.glob('attempts/*')):
                raise ValueError('existing_campaign_requires_explicit_resume')
            self.state = new_checkpoint(identity)
            atomic_record(self.path, self.state)

    def _commit(self, state):
        state['revision'] += 1
        state['updated_at'] = utc_now()
        verify_checkpoint(self.root, state, self.identity)
        atomic_record(self.path, state)
        self.state = state

    def begin(self, cell, treatment_id, session):
        if cell != next_slot(self.root, self.state, self.identity):
            raise ValueError('next_frozen_slot_required')
        diagnostic_only = (self.identity['scope'] == 'DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'
                           and session.get('status') == 'NON_QUALIFYING_DIAGNOSTIC_ADMISSION'
                           and session.get('claim_qualification_eligible') is False)
        if not session.get('preflight_sha256') or not (session.get('status') == 'PASS' or diagnostic_only):
            raise ValueError('fresh_host_session_preflight_required')
        state = deepcopy(self.state)
        state['slots'][cell['sequence']-1].update(status='RUNNING', treatment_id=treatment_id,
                                               started_at=utc_now(), session=deepcopy(session))
        self._commit(state)

    def interrupt(self):
        state = deepcopy(self.state)
        running = [s for s in state['slots'] if s['status'] == 'RUNNING']
        if len(running) != 1:
            raise ValueError('one_running_slot_required')
        running[0].update(status='INTERRUPTED', ended_at=utc_now())
        self._commit(state)

    def seal(self, sequence, manifest):
        state = deepcopy(self.state)
        slot = state['slots'][sequence-1]
        if slot['status'] != 'RUNNING':
            raise ValueError('only_running_slot_may_seal')
        path = _evidence_path(self.root, manifest)
        value = json.loads(path.read_text())
        if value.get('status') not in ('SEALED_VALID', 'SEALED_INVALID'):
            raise ValueError('terminal_validity_required')
        slot.update(status=value['status'], manifest=manifest, manifest_sha256=file_sha256(path),
                    ended_at=utc_now())
        for name, field in [('requests', 'request_sha256'), ('endpoint', 'endpoint_sha256'),
                            ('continuity', 'continuity_sha256')]:
            slot[field] = value['files'][value[name+'_path']]
        self._commit(state)


def _load(root, identity):
    path = Path(root) / 'checkpoint.json'
    state = json.loads(path.read_text())
    verify_checkpoint(root, state, identity)
    if any(slot['status'] in ('RUNNING', 'INTERRUPTED') for slot in state['slots']):
        raise ValueError('running_or_interrupted_slot_requires_review')
    return state


def _write_once(path, value):
    path = Path(path)
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        raise ValueError('immutable_record_exists:'+path.name)
    atomic_record(path, value)
    path.chmod(0o444)
    return file_sha256(path)


def transition_identity(root, old_identity, new_identity, *, reason):
    """Amendment v3. Caller holds campaign_lock. Executor-only identity change, sealed once.

    Every attempt sealed so far stays bound to the identity it was sealed under.
    """
    root = Path(root)
    state = _load(root, old_identity)
    replacement.identity_difference(old_identity, new_identity)
    sealed_under = _verify_history(root, state, old_identity)
    tids = [r['treatment_id'] for s in state['slots'] for r in s.get('replaced_attempts', [])]
    tids += [s['treatment_id'] for s in state['slots'] if s['treatment_id'] is not None]
    tids = [t for t in tids if t not in sealed_under]
    index = len(state.get('identity_history', [])) + 1
    relative = 'transitions/transition-%02d.json' % index
    record = dict(schema=replacement.TRANSITION_SCHEMA, from_identity_sha256=fingerprint(old_identity),
                  to_identity_sha256=fingerprint(new_identity), changed_fields=sorted(
                  replacement.identity_difference(old_identity, new_identity)),
                  treatment_ids=tids, reason=reason, recorded_at=utc_now())
    digest = _write_once(root/relative, record)
    new = deepcopy(state)
    new.setdefault('identity_history', []).append(dict(identity=deepcopy(old_identity),
        identity_sha256=fingerprint(old_identity), record=relative, record_sha256=digest,
        treatment_ids=tids, transitioned_at=record['recorded_at']))
    new.update(identity=deepcopy(new_identity), identity_sha256=fingerprint(new_identity),
               revision=state['revision']+1, updated_at=utc_now())
    verify_checkpoint(root, new, new_identity)
    atomic_record(root/'checkpoint.json', new)
    return new


def replace_invalid_slot(root, identity, sequence, approval):
    """Amendment v3. Caller holds campaign_lock. Returns an approved invalid slot to PENDING.

    The invalid attempt is kept, moved into ``replaced_attempts`` and re-verified on
    every later load. ``approval`` is a root-relative path to the sealed approval.
    """
    root = Path(root)
    state = _load(root, identity)
    if type(sequence) is not int or not 1 <= sequence <= 18:
        raise ValueError('valid_stop_slot_required')
    slot = state['slots'][sequence-1]
    if slot['status'] != 'SEALED_INVALID':
        raise ValueError('replacement_requires_sealed_invalid_slot')
    fields = ('treatment_id', 'manifest', 'manifest_sha256', 'request_sha256', 'endpoint_sha256',
              'continuity_sha256', 'started_at', 'ended_at')
    record = {k: slot[k] for k in fields}
    record.update(status='SEALED_INVALID', session=deepcopy(slot.get('session')), approval=approval,
                  approval_sha256=file_sha256(_evidence_path(root, approval)), replaced_at=utc_now())
    new = deepcopy(state)
    target = new['slots'][sequence-1]
    target.setdefault('replaced_attempts', []).append(record)
    target.pop('session', None)
    target.update(status='PENDING', **{k: None for k in fields})
    new.update(revision=state['revision']+1, updated_at=utc_now())
    verify_checkpoint(root, new, identity)
    atomic_record(root/'checkpoint.json', new)
    return new


def stop_after_seal(completed_this_session, sequence, *, max_slots=None, stop_after_slot=None):
    if max_slots is not None and (type(max_slots) is not int or max_slots < 1):
        raise ValueError('positive_max_slots_required')
    if stop_after_slot is not None and (type(stop_after_slot) is not int or not 1 <= stop_after_slot <= 18):
        raise ValueError('valid_stop_slot_required')
    return ((max_slots is not None and completed_this_session >= max_slots)
            or (stop_after_slot is not None and sequence >= stop_after_slot))
