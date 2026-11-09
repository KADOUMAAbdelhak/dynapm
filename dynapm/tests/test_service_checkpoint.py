import copy
import json
from pathlib import Path
import pytest
from dynapm.core.provenance import canonical_json, file_sha256, fingerprint
from dynapm.system_validation.bounded_v8 import cells, plan, offers
from dynapm.system_validation.service_transport import campaign_generator_config
from dynapm.system_validation.service_generator import offers as generator_offers
from dynapm.system_validation.service_checkpoint import (
    Checkpoint, atomic_record, campaign_lock, new_checkpoint, next_slot,
    verify_checkpoint, stop_after_seal)

IDENTITY = dict(scope='AMENDED_V8_PRIMARY', scientific_source='frozen', executor_commit='new',
                contract_sha256='contract', snapshot_sha256='snapshot', amendment_sha256='amendment')
SESSION = dict(status='PASS', preflight_sha256='session-one')


def seal_fixture(root, checkpoint, sequence, *, valid=True):
    cell = cells()[sequence-1]
    ident = 'slot-'+str(sequence)
    checkpoint.begin(cell, ident, SESSION)
    directory = root/'attempts'/ident
    directory.mkdir(parents=True)
    paths = {}
    for name in ('requests', 'endpoint', 'continuity'):
        path = directory/(name+'.json')
        path.write_text(canonical_json(dict(fixture=True, cell=cell, name=name)))
        paths[name] = str(path.relative_to(root))
    manifest = dict(campaign_identity_sha256=fingerprint(IDENTITY), cell=cell,
                    treatment_id=ident, scope=IDENTITY['scope'],
                    status='SEALED_VALID' if valid else 'SEALED_INVALID',
                    files={path:file_sha256(root/path) for path in paths.values()},
                    **{name+'_path':path for name,path in paths.items()})
    path = directory/'manifest.json'
    path.write_text(canonical_json(manifest))
    checkpoint.seal(sequence, str(path.relative_to(root)))
    return path


def test_exact_matrix_and_initial_slot(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    assert [s['cell'] for s in cp.state['slots']] == cells()
    assert len(cp.state['slots']) == 18
    assert next_slot(tmp_path, cp.state, IDENTITY) == cells()[0]


def test_two_sealed_resume_at_three_with_new_host_session(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    seal_fixture(tmp_path, cp, 1)
    seal_fixture(tmp_path, cp, 2)
    previous = (tmp_path/'checkpoint.json').read_bytes()
    resumed = Checkpoint(tmp_path, IDENTITY, resume=True)
    assert (tmp_path/'checkpoint.json').read_bytes() == previous
    assert next_slot(tmp_path, resumed.state, IDENTITY) == cells()[2]
    resumed.begin(cells()[2], 'new-cluster-new-runtime', dict(status='PASS', preflight_sha256='new-boot-qualified-session'))
    assert resumed.state['slots'][0]['status'] == 'SEALED_VALID'
    assert resumed.state['slots'][2]['session']['preflight_sha256'] == 'new-boot-qualified-session'


def test_explicit_resume_and_identity_required(tmp_path):
    Checkpoint(tmp_path, IDENTITY)
    with pytest.raises(ValueError, match='explicit_resume'):Checkpoint(tmp_path, IDENTITY)
    with pytest.raises(ValueError, match='identity'):Checkpoint(tmp_path, dict(IDENTITY, snapshot_sha256='other'), resume=True)


def test_tampered_manifest_and_payload_fail_closed(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    p = seal_fixture(tmp_path, cp, 1)
    original = p.read_bytes()
    p.write_text('{}')
    with pytest.raises(ValueError, match='manifest_hash'):Checkpoint(tmp_path, IDENTITY, resume=True)
    p.write_bytes(original)
    (p.parent/'requests.json').write_text('changed')
    with pytest.raises(ValueError, match='file_hash'):Checkpoint(tmp_path, IDENTITY, resume=True)


def test_missing_prefix_with_later_sealed_fails(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    seal_fixture(tmp_path, cp, 1)
    seal_fixture(tmp_path, cp, 2)
    state = copy.deepcopy(cp.state)
    state['slots'][0] = new_checkpoint(IDENTITY)['slots'][0]
    with pytest.raises(ValueError, match='noncontiguous'):verify_checkpoint(tmp_path, state, IDENTITY)


@pytest.mark.parametrize('interrupt', [False, True])
def test_midrun_interruption_requires_review_and_never_reruns(tmp_path, interrupt):
    cp = Checkpoint(tmp_path, IDENTITY)
    cp.begin(cells()[0], 'partial', SESSION)
    marker = tmp_path/'partial-evidence';marker.write_bytes(b'preserve')
    if interrupt:cp.interrupt()
    resumed = Checkpoint(tmp_path, IDENTITY, resume=True)
    assert resumed.state['slots'][0]['status'] == 'INTERRUPTED'
    with pytest.raises(ValueError, match='review'):next_slot(tmp_path, resumed.state, IDENTITY)
    with pytest.raises(ValueError, match='review'):resumed.begin(cells()[0], 'replacement', SESSION)
    assert marker.read_bytes() == b'preserve'


def test_invalid_slot_stops_advancement(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    seal_fixture(tmp_path, cp, 1, valid=False)
    with pytest.raises(ValueError, match='review'):next_slot(tmp_path, cp.state, IDENTITY)


def test_order_and_session_gate(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    with pytest.raises(ValueError, match='next_frozen'):cp.begin(cells()[1], 'skip', SESSION)
    with pytest.raises(ValueError, match='preflight'):cp.begin(cells()[0], 'first', dict(status='FAIL'))
    assert cp.state['slots'][0]['status'] == 'PENDING'


def test_intentional_stop_after_seal():
    assert not stop_after_seal(2, 2, max_slots=3)
    assert stop_after_seal(3, 3, max_slots=3)
    assert stop_after_seal(1, 8, stop_after_slot=8)
    with pytest.raises(ValueError):stop_after_seal(0, 0, max_slots=0)


def test_campaign_lock_refuses_concurrent_launcher(tmp_path):
    with campaign_lock(tmp_path):
        with pytest.raises(ValueError, match='already_owned'):
            with campaign_lock(tmp_path):pass


def test_reserve_failure_preserves_old_checkpoint(tmp_path, monkeypatch):
    from types import SimpleNamespace
    cp = Checkpoint(tmp_path, IDENTITY)
    before = cp.path.read_bytes()
    monkeypatch.setattr('dynapm.system_validation.service_checkpoint.shutil.disk_usage', lambda _:SimpleNamespace(free=20*2**30))
    with pytest.raises(ValueError, match='reserve'):cp.begin(cells()[0], 'run', SESSION)
    assert cp.path.read_bytes() == before and cp.state['slots'][0]['status'] == 'PENDING'


def test_frozen_offsets_partition_warmup_and_primary_exactly():
    for sequence in range(1,19):
        p = plan('primary', sequence=sequence)
        cfg = campaign_generator_config(p, 'fixture', 'http://application.test.svc.cluster.local:8080')
        generated = list(generator_offers(cfg))
        assert [offer for phase,offer in generated] == list(offers(p))
        warm = [(phase,x) for phase,x in generated if x['offset_ns'] < 0]
        primary = [(phase,x) for phase,x in generated if x['offset_ns'] >= 0]
        assert len(warm) == 21600 and warm[0][1]['offset_ns'] == -1800*10**9
        assert primary[0][1]['offset_ns'] == 0
        assert all(x['offset_ns'] < 1800*10**9 for _,x in primary)
        if p['cell']['scenario'] == 'periodic':
            assert sum(phase=='high12' for phase,x in primary) == 10800
            assert sum(phase=='low2' for phase,x in primary) == 1800
            assert next(x['offset_ns'] for phase,x in primary if phase=='low2') == 900*10**9
        else:
            assert len(primary) == 21600 and {phase for phase,x in primary} == {'high12'}


def test_diagnostic_identity_cannot_resume_claim_checkpoint(tmp_path):
    Checkpoint(tmp_path, IDENTITY)
    with pytest.raises(ValueError, match='identity'):
        Checkpoint(tmp_path, dict(IDENTITY, scope='DIAGNOSTIC_NON_CLAIM'), resume=True)


def test_valid_slot_cannot_be_rerun_or_resealed(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    path = seal_fixture(tmp_path, cp, 1)
    with pytest.raises(ValueError, match='next_frozen'):
        cp.begin(cells()[0], 'rerun', SESSION)
    with pytest.raises(ValueError, match='only_running'):
        cp.seal(1, str(path.relative_to(tmp_path)))
    assert cp.state['slots'][0]['status'] == 'SEALED_VALID'


def test_missing_bound_continuity_and_external_paths_refused(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    path = seal_fixture(tmp_path, cp, 1)
    manifest = json.loads(path.read_text())
    manifest['continuity_path'] = '../external'
    path.write_text(canonical_json(manifest))
    state = copy.deepcopy(cp.state)
    state['slots'][0]['manifest_sha256'] = file_sha256(path)
    with pytest.raises(ValueError, match='unbound'):
        verify_checkpoint(tmp_path, state, IDENTITY)
    path.unlink()
    with pytest.raises(ValueError, match='missing'):
        Checkpoint(tmp_path, IDENTITY, resume=True)


def test_rolled_back_checkpoint_cannot_hide_completed_attempt(tmp_path):
    cp = Checkpoint(tmp_path, IDENTITY)
    original = cp.path.read_bytes()
    seal_fixture(tmp_path, cp, 1)
    cp.path.write_bytes(original)
    with pytest.raises(ValueError, match='unreferenced_attempt'):
        Checkpoint(tmp_path, IDENTITY, resume=True)


def test_unreferenced_partial_attempt_requires_review(tmp_path):
    Checkpoint(tmp_path, IDENTITY)
    (tmp_path/'attempts'/'orphan').mkdir(parents=True)
    with pytest.raises(ValueError, match='unreferenced_attempt'):
        Checkpoint(tmp_path, IDENTITY, resume=True)
