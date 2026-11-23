"""Amendment v3: approved, outcome-blind replacement of a host-power-invalidated slot."""
import copy
import json
from pathlib import Path

import pytest

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint
from dynapm.system_validation import primary_slot_replacement as r
from dynapm.system_validation.bounded_v8 import cells
from dynapm.system_validation.service_checkpoint import (Checkpoint, next_slot, replace_invalid_slot,
    transition_identity, verify_checkpoint)

IDENTITY = dict(scope='AMENDED_V8_PRIMARY', scientific_source='frozen', executor_commit='old',
                contract_sha256='contract', snapshot_sha256='snapshot', spec_sha256='spec-old')
NEW = dict(IDENTITY, executor_commit='new', spec_sha256='spec-new')
SESSION = dict(status='PASS', preflight_sha256='session')
POWER = "mains_power_lost:Now drawing from 'Battery Power'"
REPO = Path(__file__).resolve().parents[2]


def seal(root, cp, sequence, identity=IDENTITY, *, invalid=None, metrics=None, tid=None):
    """Seal a fixture attempt; ``invalid`` is a host-continuity invariant or None (valid)."""
    cell = cells()[sequence-1]
    tid = tid or 'slot-%02d-%d' % (sequence, len(list((root/'attempts').glob('slot-%02d-*' % sequence)))
                                   if (root/'attempts').exists() else 0)
    cp.begin(cell, tid, SESSION)
    run = root/'attempts'/tid
    (run/'outputs').mkdir(parents=True)
    paths = {}
    for name in ('requests', 'endpoint', 'continuity'):
        path = run/'outputs'/(name+'.json')
        path.write_text(canonical_json(dict(cell=cell, name=name)))
        paths[name] = str(path.relative_to(root))
    manifest = dict(campaign_identity_sha256=fingerprint(identity), cell=cell, treatment_id=tid,
                    scope=identity['scope'], metrics=metrics if invalid else dict(ok=1))
    if invalid is None:
        manifest['status'] = 'SEALED_VALID'
    else:
        failure = run/'outputs'/r.FAILURE_NAME
        failure.write_text(canonical_json(dict(invariant=invalid, context=dict(run_id=tid, scope=identity['scope']))))
        digest = file_sha256(failure)
        manifest.update(status='SEALED_INVALID', failure=dict(category='HARNESS_MEASUREMENT_FAILURE',
            type='PowerGuardError', error='PowerGuardError("%s; host_continuity_failure_sha256=%s")' % (invalid, digest)))
        paths['failure'] = str(failure.relative_to(root))
    manifest['files'] = {p: file_sha256(root/p) for p in paths.values()}
    manifest.update({n+'_path': paths[n] for n in ('requests', 'endpoint', 'continuity')})
    path = run/'manifest.json'
    path.write_text(canonical_json(manifest))
    cp.seal(sequence, str(path.relative_to(root)))
    return tid


def approve(root, cp_state, position, **override):
    sequence = position
    slot = cp_state['slots'][sequence-1]
    tid = slot['treatment_id']
    failure = root/r.failure_path(tid)
    value = dict(schema=r.APPROVAL_SCHEMA, sequence=sequence, cell=slot['cell'], invalid_treatment_id=tid,
                 invalid_manifest_sha256=slot['manifest_sha256'], host_continuity_failure_sha256=file_sha256(failure),
                 invariant=r.invariant_class(json.loads(failure.read_text())['invariant']),
                 approved_by_user=True, user_approval_quote='Approve, implement', approved_at='2026-11-23T13:00:00Z')
    value.update(override)
    relative = 'replacements/slot-%02d-%s.json' % (sequence, tid)
    (root/'replacements').mkdir(exist_ok=True)
    (root/relative).write_text(canonical_json(value))
    return relative


@pytest.fixture
def halted(tmp_path):
    """Slots 1-2 valid, slot 3 invalidated by mains power loss (as campaign v2 slot 9)."""
    cp = Checkpoint(tmp_path, IDENTITY)
    seal(tmp_path, cp, 1)
    seal(tmp_path, cp, 2)
    seal(tmp_path, cp, 3, invalid=POWER)
    with pytest.raises(ValueError, match='replacement_review'):
        next_slot(tmp_path, cp.state, IDENTITY)
    return tmp_path, cp


def test_approved_power_loss_slot_returns_to_same_cell_and_keeps_attempt(halted):
    root, cp = halted
    old_tid = cp.state['slots'][2]['treatment_id']
    state = replace_invalid_slot(root, IDENTITY, 3, approve(root, cp.state, 3))
    slot = state['slots'][2]
    assert slot['status'] == 'PENDING' and slot['treatment_id'] is None
    assert [a['treatment_id'] for a in slot['replaced_attempts']] == [old_tid]
    assert (root/'attempts'/old_tid/'manifest.json').is_file()
    resumed = Checkpoint(root, IDENTITY, resume=True)
    assert next_slot(root, resumed.state, IDENTITY) == cells()[2]
    seal(root, resumed, 3, tid='slot-03-replacement')
    again = Checkpoint(root, IDENTITY, resume=True)
    assert [s['status'] for s in again.state['slots'][:3]] == ['SEALED_VALID']*3
    assert next_slot(root, again.state, IDENTITY) == cells()[3]


@pytest.mark.parametrize('invariant', ['host_sleep_or_clock_discontinuity', 'host_continuity_heartbeat_gap',
    'host_boot_identity_changed', 'host_power_policy_changed', 'owned_power_assertion_missing',
    'host_continuity_monitor_exited', 'storage_reserve_checkpoint_write'])
def test_non_power_failures_are_never_replaceable(tmp_path, invariant):
    cp = Checkpoint(tmp_path, IDENTITY)
    seal(tmp_path, cp, 1, invalid=invariant)
    with pytest.raises(ValueError, match='invariant_not_replaceable'):
        replace_invalid_slot(tmp_path, IDENTITY, 1, approve(tmp_path, cp.state, 1, invariant=invariant))


def test_observed_outcome_is_never_replaceable(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    seal(tmp_path, cp, 1, invalid=POWER, metrics=dict(sla=0.5))
    with pytest.raises(ValueError, match='observed_outcome'):
        replace_invalid_slot(tmp_path, IDENTITY, 1, approve(tmp_path, cp.state, 1))


@pytest.mark.parametrize('override,reason', [
    (dict(approved_by_user=False), 'explicit_user_approval_required'),
    (dict(user_approval_quote=''), 'explicit_user_approval_required'),
    (dict(invalid_treatment_id='other'), 'invalid_treatment_id'),
    (dict(invalid_manifest_sha256='0'*64), 'invalid_manifest_sha256'),
    (dict(host_continuity_failure_sha256='0'*64), 'host_continuity_failure_sha256'),
    (dict(sequence=4), 'sequence'),
    (dict(schema='other'), 'schema'),
])
def test_approval_must_name_exactly_this_attempt(halted, override, reason):
    root, cp = halted
    with pytest.raises(ValueError, match=reason):
        replace_invalid_slot(root, IDENTITY, 3, approve(root, cp.state, 3, **override))


def test_valid_slot_cannot_be_replaced(halted):
    root, cp = halted
    with pytest.raises(ValueError, match='sealed_invalid_slot'):
        replace_invalid_slot(root, IDENTITY, 2, approve(root, cp.state, 3))


def test_replaced_attempt_and_approval_are_reverified_on_resume(halted):
    root, cp = halted
    old_tid = cp.state['slots'][2]['treatment_id']
    approval = approve(root, cp.state, 3)
    replace_invalid_slot(root, IDENTITY, 3, approval)
    endpoint = root/'attempts'/old_tid/'outputs/endpoint.json'
    original = endpoint.read_bytes()
    endpoint.write_text('rewritten')
    with pytest.raises(ValueError, match='file_hash'):
        Checkpoint(root, IDENTITY, resume=True)
    endpoint.write_bytes(original)
    (root/approval).write_text('{}')
    with pytest.raises(ValueError, match='replacement_approval_changed'):
        Checkpoint(root, IDENTITY, resume=True)


def test_one_replacement_per_slot(halted):
    root, cp = halted
    replace_invalid_slot(root, IDENTITY, 3, approve(root, cp.state, 3))
    resumed = Checkpoint(root, IDENTITY, resume=True)
    seal(root, resumed, 3, invalid=POWER, tid='slot-03-second')
    with pytest.raises(ValueError, match='limit_per_slot'):
        replace_invalid_slot(root, IDENTITY, 3, approve(root, resumed.state, 3))


def test_two_replacements_per_campaign(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    for sequence in (1, 2):
        seal(tmp_path, cp, sequence, invalid=POWER)
        replace_invalid_slot(tmp_path, IDENTITY, sequence, approve(tmp_path, cp.state, sequence))
        cp = Checkpoint(tmp_path, IDENTITY, resume=True)
        seal(tmp_path, cp, sequence, tid='slot-%02d-valid' % sequence)
    seal(tmp_path, cp, 3, invalid=POWER)
    with pytest.raises(ValueError, match='limit_per_campaign'):
        replace_invalid_slot(tmp_path, IDENTITY, 3, approve(tmp_path, cp.state, 3))


def test_executor_only_transition_keeps_earlier_seals_bound_to_their_identity(halted):
    root, cp = halted
    state = transition_identity(root, IDENTITY, NEW, reason='test')
    assert state['identity'] == NEW and state['identity_history'][0]['identity'] == IDENTITY
    with pytest.raises(ValueError, match='identity_mismatch'):
        Checkpoint(root, IDENTITY, resume=True)
    state = replace_invalid_slot(root, NEW, 3, approve(root, cp.state, 3))
    resumed = Checkpoint(root, NEW, resume=True)
    seal(root, resumed, 3, NEW, tid='slot-03-new-executor')
    final = Checkpoint(root, NEW, resume=True)
    assert next_slot(root, final.state, NEW) == cells()[3]
    record = json.loads((root/'transitions/transition-01.json').read_text())
    assert record['changed_fields'] == ['executor_commit', 'spec_sha256']
    assert len(record['treatment_ids']) == 3


@pytest.mark.parametrize('field', ['scope', 'scientific_source', 'contract_sha256', 'snapshot_sha256'])
def test_transition_cannot_change_scientific_identity(halted, field):
    root, _ = halted
    with pytest.raises(ValueError, match='executor_only'):
        transition_identity(root, IDENTITY, dict(NEW, **{field: 'changed'}), reason='test')


def test_transition_requires_a_change(halted):
    root, _ = halted
    with pytest.raises(ValueError, match='executor_only'):
        transition_identity(root, IDENTITY, copy.deepcopy(IDENTITY), reason='test')


def test_tampered_transition_record_or_history_fails_closed(halted):
    root, _ = halted
    transition_identity(root, IDENTITY, NEW, reason='test')
    record = root/'transitions/transition-01.json'
    original = record.read_bytes()
    record.chmod(0o644)
    record.write_text('{}')
    with pytest.raises(ValueError, match='transition_record_changed'):
        Checkpoint(root, NEW, resume=True)
    record.write_bytes(original)
    state = json.loads((root/'checkpoint.json').read_text())
    state['identity_history'][0]['treatment_ids'].pop()
    with pytest.raises(ValueError, match='transition'):
        verify_checkpoint(root, state, NEW)


def test_transition_refuses_running_or_interrupted_slot(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    cp.begin(cells()[0], 'slot-01-running', SESSION)
    with pytest.raises(ValueError, match='running_or_interrupted'):
        transition_identity(tmp_path, IDENTITY, NEW, reason='test')


def test_operator_identity_matches_campaign(monkeypatch, tmp_path):
    from dynapm.scripts import task51_primary_slot_replacement as task51
    from dynapm.system_validation import service_primary as sp
    captured = {}

    class Stop(Exception):
        pass

    def capture(root, identity, resume=False):
        captured['identity'] = identity
        raise Stop
    monkeypatch.setattr(sp, 'source_binding', lambda repo, spec: dict(executor_commit='h', scientific_source='s'))
    monkeypatch.setattr(sp, 'Checkpoint', capture)
    spec = dict(t0_policy='FROZEN_T0_INCLUDES_ENFORCEMENT_TRANSITION', power_mode='STRICT_AC')
    with pytest.raises(Stop):
        sp.campaign(tmp_path, tmp_path/'root', spec, 'DIAGNOSTIC_NON_CLAIM')
    assert task51.campaign_identity(tmp_path, spec, 'DIAGNOSTIC_NON_CLAIM') == captured['identity']


V2 = REPO/'results/v8c_r2/amended-v8-claim-campaign-v2/claim-campaign'


@pytest.mark.skipif(not (V2/'checkpoint.json').is_file(), reason='campaign v2 evidence absent')
def test_real_v2_slot_9_is_eligible_and_slots_1_to_8_are_not_replaceable():
    state = json.loads((V2/'checkpoint.json').read_text())
    verify_checkpoint(V2, state, state['identity'])
    slot = state['slots'][8]
    if slot['status'] != 'SEALED_INVALID':
        pytest.skip('slot 9 already replaced')
    tid = slot['treatment_id']
    failure = V2/r.failure_path(tid)
    manifest = json.loads((V2/slot['manifest']).read_text())
    assert r.require_eligible(manifest, json.loads(failure.read_text()), file_sha256(failure), tid) == 'mains_power_lost'
    assert [s['status'] for s in state['slots'][:8]] == ['SEALED_VALID']*8
