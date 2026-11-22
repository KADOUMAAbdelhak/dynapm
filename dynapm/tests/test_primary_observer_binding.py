"""Offline regression tests for the primary executor x task49 observer binding.

No cluster, cooldown, generator, lifecycle, claim treatment or integration runs.
"""
import copy
import hashlib
from pathlib import Path
import subprocess

import pytest

from dynapm.core.provenance import file_sha256, read_json
from dynapm.system_validation import primary_observer_binding as b
from dynapm.system_validation import service_primary as sp

REPO = Path(__file__).resolve().parents[2]
ANCHOR = 1794336849060321000


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args],
                                   cwd=repo, text=True).strip()


def commit(repo, files, message):
    for path, text in files.items():
        target = repo/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', message)
    return git(repo, 'rev-parse', 'HEAD')


TREAT_V1 = '''def source_binding(repo, spec):
    return 'legacy'


def host_qualification(repo, spec):
    return 'legacy'


def treatment(x):
    return x * 2
'''
TREAT_BOUND = TREAT_V1.replace("return 'legacy'\n\n\ndef host", "return 'bound'\n\n\ndef host")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def lineage(tmp_path, monkeypatch):
    repo = tmp_path/'repo'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'exec')
    t = commit(repo, {'science.py': 'FROZEN = 1\n', 'host.py': 'GUARD = 1\n'}, 'transport')
    p = commit(repo, {'treat.py': TREAT_V1, 'exec.py': 'E = 1\n'}, 'primary')
    o = commit(repo, {'host.py': 'GUARD = 2\n', 'obs.py': 'O = 1\n'}, 'observer')
    h = commit(repo, {'treat.py': TREAT_BOUND, 'bind.py': 'B = 1\n'}, 'binding')
    monkeypatch.setattr(b, 'TRANSPORT', t)
    monkeypatch.setattr(b, 'PRIMARY_EXECUTOR', p)
    monkeypatch.setattr(b, 'OBSERVER_COMMIT', o)
    monkeypatch.setattr(b, 'OBSERVER_DELTA', {'host.py': 'M', 'obs.py': 'A'})
    monkeypatch.setattr(b, 'BINDING_DELTA', {'treat.py': 'M', 'bind.py': 'A'})
    monkeypatch.setattr(b, 'TREATMENT_MODULE', 'treat.py')
    spec = dict(executor_commit=h, executor_branch='exec',
                executor_files={'treat.py': sha(TREAT_V1), 'exec.py': sha('E = 1\n')},
                observer_files={'host.py': sha('GUARD = 2\n'), 'obs.py': sha('O = 1\n')},
                binding_files={'treat.py': sha(TREAT_BOUND), 'bind.py': sha('B = 1\n')})
    return repo, spec, h


def valid_spec(**extra):
    spec = dict(schema=b.SPEC_SCHEMA, primary_executor_commit=b.PRIMARY_EXECUTOR,
                observer_commit=b.OBSERVER_COMMIT, observer_amendment_path=b.OBSERVER_AMENDMENT_PATH,
                observer_amendment_sha256=b.OBSERVER_AMENDMENT_SHA256,
                host_amendment_path=b.QUALIFICATION_PATH, host_amendment_sha256=b.QUALIFICATION_SHA256,
                expected_boot_uuid=b.BOOT_UUID, scientific_source=b.SCIENTIFIC_SOURCE,
                qualified_transport=b.TRANSPORT, executor_commit='f'*40, executor_branch='v8c5-service-transport',
                executor_files={'x': 'y'}, observer_files={'x': 'y'}, binding_files={'x': 'y'})
    spec.update(extra)
    return spec


# --- valid binding -----------------------------------------------------------

def test_valid_binding_lineage_passes(lineage):
    repo, spec, head = lineage
    b.require_lineage(repo, spec, head)


def test_valid_spec_identities_pass():
    b.require_spec_identities(valid_spec())


def test_binding_only_admission_change_preserves_treatment_nodes():
    assert b.treatment_nodes(TREAT_V1) == b.treatment_nodes(TREAT_BOUND)


# --- each identity is verified separately and fails closed --------------------

@pytest.mark.parametrize('key,value,reason', [
    ('primary_executor_commit', 'a'*40, 'primary_executor_identity_mismatch'),
    ('observer_commit', 'a'*40, 'observer_identity_mismatch'),
    ('observer_amendment_sha256', '0'*64, 'observer_amendment_sha_mismatch'),
    ('observer_amendment_path', 'elsewhere.json', 'observer_amendment_path_mismatch'),
    ('host_amendment_sha256', '0'*64, 'current_boot_qualification_sha_mismatch'),
    ('host_amendment_path', 'elsewhere.json', 'current_boot_qualification_path_mismatch'),
    ('expected_boot_uuid', '00000000-0000-0000-0000-000000000000', 'expected_boot_uuid_mismatch'),
    ('scientific_source', 'a'*40, 'scientific_source_mismatch'),
    ('qualified_transport', 'a'*40, 'transport_identity_mismatch'),
    ('schema', 'v8-service-primary-executor-spec-v1', 'binding_spec_schema_required'),
])
def test_wrong_identity_fails_closed(key, value, reason):
    with pytest.raises(b.BindingError, match=reason):
        b.require_spec_identities(valid_spec(**{key: value}))


@pytest.mark.parametrize('key', ['primary_executor_commit', 'observer_commit', 'observer_amendment_sha256',
                                 'host_amendment_sha256', 'expected_boot_uuid', 'executor_files',
                                 'observer_files', 'binding_files', 'executor_commit'])
def test_missing_identity_fails_closed(key):
    spec = valid_spec()
    del spec[key]
    with pytest.raises(b.BindingError):
        b.require_spec_identities(spec)


@pytest.mark.parametrize('commit', [b.PRIMARY_EXECUTOR, b.OBSERVER_COMMIT])
def test_binding_requires_a_distinct_binding_commit(commit):
    with pytest.raises(b.BindingError, match='binding_commit_required'):
        b.require_spec_identities(valid_spec(executor_commit=commit))


def test_wrong_primary_executor_files_fail(lineage):
    repo, spec, head = lineage
    spec['executor_files']['exec.py'] = '0'*64
    with pytest.raises(b.BindingError, match='primary_executor_identity_mismatch'):
        b.require_lineage(repo, spec, head)


def test_wrong_observer_files_fail(lineage):
    repo, spec, head = lineage
    spec['observer_files']['obs.py'] = '0'*64
    with pytest.raises(b.BindingError, match='observer_identity_mismatch'):
        b.require_lineage(repo, spec, head)


def test_observer_modified_after_observer_commit_fails(lineage):
    repo, spec, _ = lineage
    head = commit(repo, {'obs.py': 'O = 2\n'}, 'tamper observer')
    with pytest.raises(b.BindingError, match='binding_delta_not_binding_only'):
        b.require_lineage(repo, spec, head)


def test_scientific_file_change_fails(lineage):
    repo, spec, _ = lineage
    head = commit(repo, {'science.py': 'FROZEN = 2\n'}, 'tamper science')
    with pytest.raises(b.BindingError, match='binding_delta_not_binding_only'):
        b.require_lineage(repo, spec, head)


def test_treatment_change_disguised_as_binding_fails(lineage, monkeypatch):
    repo, spec, _ = lineage
    changed = TREAT_BOUND.replace('x * 2', 'x * 3')
    head = commit(repo, {'treat.py': changed}, 'tamper treatment')
    spec['binding_files']['treat.py'] = sha(changed)
    with pytest.raises(b.BindingError, match='treatment_code_changed'):
        b.require_lineage(repo, spec, head)


def test_wrong_binding_file_hash_fails(lineage):
    repo, spec, head = lineage
    spec['binding_files']['bind.py'] = '0'*64
    with pytest.raises(b.BindingError, match='binding_files_mismatch'):
        b.require_lineage(repo, spec, head)


def test_broken_lineage_fails(lineage, monkeypatch):
    repo, spec, head = lineage
    git(repo, 'checkout', '-q', '--orphan', 'other')
    other = commit(repo, {'z.py': 'Z = 1\n'}, 'unrelated')
    with pytest.raises(b.BindingError, match='executor_observer_lineage_broken'):
        b.require_lineage(repo, spec, other)


def test_unclean_or_wrong_head_fails(lineage, monkeypatch):
    repo, spec, head = lineage
    monkeypatch.setattr(b, 'require_spec_identities', lambda spec: None)
    (repo/'stray.txt').write_text('dirty')
    with pytest.raises(b.BindingError, match='clean_exact_executor_commit_required'):
        b.source_binding(repo, spec)
    (repo/'stray.txt').unlink()
    with pytest.raises(b.BindingError, match='clean_exact_executor_commit_required'):
        b.source_binding(repo, dict(spec, executor_branch='other'))
    with pytest.raises(b.BindingError, match='clean_exact_executor_commit_required'):
        b.source_binding(repo, dict(spec, executor_commit='0'*40))


# --- certificate and current boot --------------------------------------------

def certificate(**extra):
    cert = dict(schema_version=b.CERTIFICATE_SCHEMA, status='PASS', observer_commit=b.OBSERVER_COMMIT,
                observer_amendment_sha256=b.OBSERVER_AMENDMENT_SHA256, scientific_source=b.SCIENTIFIC_SOURCE,
                boot_uuid=b.BOOT_UUID, boot_timeval_anchor_ns=ANCHOR,
                qualification=dict(boot_uuid=b.BOOT_UUID, original_uuid_recorded=True,
                                   boot_timeval_anchor_ns=ANCHOR),
                runtime_compatibility=dict(observation_source_commit=b.OBSERVER_COMMIT))
    cert.update(extra)
    return cert


def boot(uuid=b.BOOT_UUID, ns=ANCHOR):
    return dict(boot_uuid=uuid, boot_timeval_ns=ns, boot_epoch_seconds=ns//10**9)


def test_valid_certificate_and_current_boot_pass():
    cert = b.require_certificate(certificate())
    assert b.require_current_boot(cert, boot(ns=ANCHOR+700_000_000)) == 700_000_000


@pytest.mark.parametrize('key,value', [
    ('status', 'FAIL'), ('observer_commit', 'a'*40), ('observer_amendment_sha256', '0'*64),
    ('boot_uuid', '00000000-0000-0000-0000-000000000000'), ('schema_version', 'v8-current-boot-host-qualification-v1'),
    ('scientific_source', 'a'*40)])
def test_wrong_certificate_identity_fails(key, value):
    with pytest.raises(b.BindingError, match='current_boot_qualification_identity_mismatch'):
        b.require_certificate(certificate(**{key: value}))


def test_malformed_certificate_fails():
    cert = certificate()
    del cert['qualification']
    with pytest.raises(b.BindingError, match='malformed_current_boot_qualification'):
        b.require_certificate(cert)


@pytest.mark.parametrize('current', [
    boot(uuid='00000000-0000-0000-0000-000000000000'),   # rebooted
    boot(ns=ANCHOR+2_000_000_001),                         # calendar beyond unchanged 2 s bound
    dict(boot_uuid=b.BOOT_UUID),                           # malformed reading
])
def test_incompatible_current_boot_fails_closed(current):
    with pytest.raises(b.BindingError, match='current_boot_incompatible'):
        b.require_current_boot(certificate(), current)


# --- service_primary dispatch: v1 unchanged, v2 routed -------------------------

def test_v2_spec_routes_both_admission_gates(monkeypatch):
    calls = []
    monkeypatch.setattr(b, 'host_qualification', lambda repo, spec: calls.append('host') or 'boot')
    assert sp.host_qualification(REPO, valid_spec()) == 'boot'
    assert calls == ['host']


def test_v1_spec_still_requires_exact_primary_head(monkeypatch):
    spec = dict(executor_commit=b.PRIMARY_EXECUTOR, executor_branch='v8c5-service-transport')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if head == b.PRIMARY_EXECUTOR:
        pytest.skip('checkout is the primary executor itself')
    with pytest.raises(ValueError, match='clean_exact_executor_commit_required'):
        sp.source_binding(REPO, spec)


# --- real repository evidence (skipped when objects/evidence are absent) -------

def _have(*commits):
    return all(subprocess.run(['git', 'cat-file', '-e', c+'^{commit}'], cwd=REPO,
                              capture_output=True).returncode == 0 for c in commits)


@pytest.mark.skipif(not _have(b.PRIMARY_EXECUTOR, b.OBSERVER_COMMIT), reason='lineage objects absent')
def test_real_observer_delta_is_the_approved_one():
    assert b.name_status(REPO, b.PRIMARY_EXECUTOR, b.OBSERVER_COMMIT) == b.OBSERVER_DELTA


@pytest.mark.skipif(not _have(b.PRIMARY_EXECUTOR), reason='primary executor object absent')
def test_real_treatment_module_is_unchanged_outside_admission():
    old = subprocess.check_output(['git', 'show', b.PRIMARY_EXECUTOR+':'+b.TREATMENT_MODULE], cwd=REPO, text=True)
    new = (REPO/b.TREATMENT_MODULE).read_text()
    assert b.treatment_nodes(old) == b.treatment_nodes(new)


@pytest.mark.skipif(not (REPO/b.QUALIFICATION_PATH).is_file(), reason='sealed qualification absent')
def test_real_qualification_and_amendment_are_unrewritten():
    assert file_sha256(REPO/b.QUALIFICATION_PATH) == b.QUALIFICATION_SHA256
    assert file_sha256(REPO/b.OBSERVER_AMENDMENT_PATH) == b.OBSERVER_AMENDMENT_SHA256
    b.require_certificate(read_json(REPO/b.QUALIFICATION_PATH))
    if _have(b.QUALIFICATION_EVIDENCE_COMMIT, b.OBSERVER_EVIDENCE_COMMIT):
        b.require_observer_amendment(REPO)


@pytest.mark.skipif(not (REPO/b.QUALIFICATION_PATH).is_file(), reason='sealed qualification absent')
def test_real_qualification_rejects_a_different_boot_without_new_observation():
    cert = read_json(REPO/b.QUALIFICATION_PATH)
    with pytest.raises(b.BindingError, match='current_boot_incompatible'):
        b.require_current_boot(cert, boot(uuid='00000000-0000-0000-0000-000000000000',
                                          ns=cert['boot_timeval_anchor_ns']))
    assert b.require_current_boot(cert, boot(ns=cert['boot_timeval_anchor_ns'])) == 0


SUPERSEDED_PATH = REPO/'results/v8c_r2/20261111-task49-current-boot-v1/current-boot-qualification.json'


@pytest.mark.skipif(not SUPERSEDED_PATH.is_file(), reason='superseded qualification absent')
def test_superseded_pre_reboot_qualification_is_rejected():
    old = read_json(SUPERSEDED_PATH)
    assert file_sha256(SUPERSEDED_PATH) == b.SUPERSEDED_QUALIFICATION_SHA256
    assert old['boot_uuid'] == b.SUPERSEDED_BOOT_UUID != b.BOOT_UUID
    with pytest.raises(b.BindingError, match='current_boot_qualification_identity_mismatch'):
        b.require_certificate(old)


@pytest.mark.skipif(not (REPO/b.QUALIFICATION_PATH).is_file(), reason='sealed qualification absent')
def test_rebound_qualification_rejects_the_pre_reboot_boot():
    cert = read_json(REPO/b.QUALIFICATION_PATH)
    with pytest.raises(b.BindingError, match='current_boot_incompatible'):
        b.require_current_boot(cert, boot(uuid=b.SUPERSEDED_BOOT_UUID, ns=cert['boot_timeval_anchor_ns']))
