"""Binding-only amendment: primary Service executor lineage x approved task49 observer.

No scientific, workload, snapshot, target, treatment-order, endpoint or clock-rule
change. The amendment binds four identities separately and fails closed on each:

1. primary executor   67bfd37 (its exact additions over the qualified transport)
2. task49 observer    1b50282 (its exact delta over 67bfd37, unchanged at HEAD)
3. observer amendment e4cbb223... (sealed in evidence commit 6004732)
4. current-boot qualification 594ba9a2... (sealed in evidence commit 697c734)

and requires the exact qualified boot UUID on the current host. The three-hour
qualification is verified in place, never rewritten, and is not repeated: this
binding leaves the pinned observer runtime, boot UUID and power policy unchanged.
"""
import ast
import hashlib
from pathlib import Path
import subprocess

from dynapm.core.provenance import file_sha256, read_json
from dynapm.system_validation.v8_host_identity import (SCIENTIFIC_SOURCE, UUID_ENDURANCE_SCHEMA,
    qualification_inputs, read_boot, same_boot)
from dynapm.system_validation.host_power import command

SPEC_SCHEMA = 'v8-service-primary-executor-spec-v2-observer-binding'
CERTIFICATE_SCHEMA = 'v8-current-boot-host-qualification-v2-uuid'

TRANSPORT = 'b3fd0d1fa095dbaa13c2b035624d6336b24d60ca'
PRIMARY_EXECUTOR = '67bfd37ee72e0096e4dfec974fd145f7a347e6e0'
OBSERVER_COMMIT = '1b5028284d6868a3e3e3fc0d04f58710256054a9'
OBSERVER_AMENDMENT_PATH = 'results/v8c_r2/20261111-host-observer-amendment-v1/amendment.json'
OBSERVER_AMENDMENT_SHA256 = 'e4cbb223c76fce09c4ac7141ba89ff9dc1a8d73a457bc8909c962268859e8b74'
OBSERVER_EVIDENCE_COMMIT = '600473232847c015846bf4765f6005929e7d2377'
QUALIFICATION_PATH = 'results/v8c_r2/20261111-task49-current-boot-v1/current-boot-qualification.json'
QUALIFICATION_SHA256 = '594ba9a2a14145bc8bf28f5d3349953b9250cc437abf0f2bd12e547e12d07059'
QUALIFICATION_MANIFEST = 'results/v8c_r2/20261111-task49-current-boot-v1/OUTPUT_MANIFEST.json'
QUALIFICATION_EVIDENCE_COMMIT = '697c734c22ccfc8154dcd37744d475fdeb45cb3d'
BOOT_UUID = '6C470F9C-9B15-4093-87C3-DDE6D713D7E6'

# Exact approved observer delta over the primary executor (git name-status).
OBSERVER_DELTA = {
    'docs/host_observer_uuid_amendment.md': 'A',
    'dynapm/scripts/task49_host_uuid_observation.py': 'A',
    'dynapm/system_validation/uuid_host_observer.py': 'A',
    'dynapm/system_validation/v8_host_identity.py': 'M',
    'dynapm/tests/fixtures/host_boot_calendar_boundary.json': 'A',
    'dynapm/tests/test_uuid_host_observer.py': 'A',
}
# The only files this binding amendment may add or modify over the observer.
BINDING_DELTA = {
    'docs/primary_observer_binding_amendment.md': 'A',
    'dynapm/scripts/task50_primary_binding_preflight.py': 'A',
    'dynapm/system_validation/primary_observer_binding.py': 'A',
    'dynapm/system_validation/service_primary.py': 'M',
    'dynapm/tests/test_primary_observer_binding.py': 'A',
}
# Inside service_primary.py only these admission functions may differ from 67bfd37.
BINDING_FUNCTIONS = ('source_binding', 'host_qualification')
TREATMENT_MODULE = 'dynapm/system_validation/service_primary.py'


class BindingError(ValueError):
    pass


def _git(repo, *args, text=True):
    try:
        return subprocess.check_output(['git', *args], cwd=repo, text=text, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise BindingError('git_object_unavailable:'+' '.join(args)) from exc


def _ancestor(repo, older, newer):
    return subprocess.run(['git', 'merge-base', '--is-ancestor', older, newer], cwd=repo,
                          capture_output=True).returncode == 0


def blob_sha256(repo, commit, path):
    return hashlib.sha256(_git(repo, 'show', commit+':'+path, text=False)).hexdigest()


def name_status(repo, old, new):
    rows = {}
    for line in _git(repo, 'diff', '--no-renames', '--name-status', old, new).splitlines():
        status, path = line.split('\t')
        rows[path] = status
    return rows


def treatment_nodes(source, excluded=BINDING_FUNCTIONS):
    """Every top-level node of the treatment module except the named admission functions."""
    tree = ast.parse(source)
    return [ast.dump(node, include_attributes=False) for node in tree.body
            if not (isinstance(node, ast.FunctionDef) and node.name in excluded)]


def require_spec_identities(spec):
    """Each identity is bound and checked separately, so failures are attributable."""
    if not isinstance(spec, dict) or spec.get('schema') != SPEC_SCHEMA:
        raise BindingError('binding_spec_schema_required')
    checks = (
        ('primary_executor_commit', PRIMARY_EXECUTOR, 'primary_executor_identity_mismatch'),
        ('observer_commit', OBSERVER_COMMIT, 'observer_identity_mismatch'),
        ('observer_amendment_path', OBSERVER_AMENDMENT_PATH, 'observer_amendment_path_mismatch'),
        ('observer_amendment_sha256', OBSERVER_AMENDMENT_SHA256, 'observer_amendment_sha_mismatch'),
        ('host_amendment_path', QUALIFICATION_PATH, 'current_boot_qualification_path_mismatch'),
        ('host_amendment_sha256', QUALIFICATION_SHA256, 'current_boot_qualification_sha_mismatch'),
        ('expected_boot_uuid', BOOT_UUID, 'expected_boot_uuid_mismatch'),
        ('scientific_source', SCIENTIFIC_SOURCE, 'scientific_source_mismatch'),
        ('qualified_transport', TRANSPORT, 'transport_identity_mismatch'),
    )
    for key, expected, reason in checks:
        if spec.get(key) != expected:
            raise BindingError(reason)
    for key in ('executor_commit', 'executor_branch', 'executor_files', 'observer_files', 'binding_files'):
        if not spec.get(key):
            raise BindingError('binding_spec_field_missing:'+key)
    if spec['executor_commit'] in (PRIMARY_EXECUTOR, OBSERVER_COMMIT):
        raise BindingError('binding_commit_required')


def require_lineage(repo, spec, head):
    """Transport -> primary executor -> observer -> binding commit, each delta exact."""
    repo = Path(repo)
    for older, newer in ((TRANSPORT, PRIMARY_EXECUTOR), (PRIMARY_EXECUTOR, OBSERVER_COMMIT),
                         (OBSERVER_COMMIT, head)):
        if not _ancestor(repo, older, newer):
            raise BindingError('executor_observer_lineage_broken')
    # 1. Primary executor identity: its original additions, hashed at 67bfd37 itself.
    primary = name_status(repo, TRANSPORT, PRIMARY_EXECUTOR)
    if (any(s != 'A' for s in primary.values())
            or {p: blob_sha256(repo, PRIMARY_EXECUTOR, p) for p in primary} != spec['executor_files']):
        raise BindingError('primary_executor_identity_mismatch')
    # 2. Observer identity: the exact approved delta, hashed at 1b50282.
    observer = name_status(repo, PRIMARY_EXECUTOR, OBSERVER_COMMIT)
    if (observer != OBSERVER_DELTA
            or {p: blob_sha256(repo, OBSERVER_COMMIT, p) for p in observer} != spec['observer_files']):
        raise BindingError('observer_identity_mismatch')
    # 3. Binding-only delta: nothing else (observer, executor, scientific) may change.
    binding = name_status(repo, OBSERVER_COMMIT, head)
    if binding != BINDING_DELTA:
        raise BindingError('binding_delta_not_binding_only')
    if {p: blob_sha256(repo, head, p) for p in binding} != spec['binding_files']:
        raise BindingError('binding_files_mismatch')
    # 4. Treatment behaviour: every non-admission node is AST-identical to 67bfd37.
    old = _git(repo, 'show', PRIMARY_EXECUTOR+':'+TREATMENT_MODULE)
    new = _git(repo, 'show', head+':'+TREATMENT_MODULE)
    if treatment_nodes(old) != treatment_nodes(new):
        raise BindingError('treatment_code_changed')


def require_observer_amendment(repo):
    repo = Path(repo)
    path = repo/OBSERVER_AMENDMENT_PATH
    if not path.is_file() or file_sha256(path) != OBSERVER_AMENDMENT_SHA256:
        raise BindingError('observer_amendment_sha_mismatch')
    if blob_sha256(repo, OBSERVER_EVIDENCE_COMMIT, OBSERVER_AMENDMENT_PATH) != OBSERVER_AMENDMENT_SHA256:
        raise BindingError('observer_amendment_evidence_commit_mismatch')
    amendment = read_json(path)
    if (amendment.get('observer_amendment_commit') != OBSERVER_COMMIT
            or amendment.get('previous_primary_harness') != PRIMARY_EXECUTOR
            or amendment.get('observer_schema') != UUID_ENDURANCE_SCHEMA):
        raise BindingError('observer_amendment_identity_mismatch')
    return amendment


def require_certificate(certificate):
    """Pure checks on the sealed three-hour certificate; it is read, never rewritten."""
    try:
        qualification = certificate['qualification']
        ok = (certificate['schema_version'] == CERTIFICATE_SCHEMA
              and certificate['status'] == 'PASS'
              and certificate['observer_commit'] == OBSERVER_COMMIT
              and certificate['observer_amendment_sha256'] == OBSERVER_AMENDMENT_SHA256
              and certificate['scientific_source'] == SCIENTIFIC_SOURCE
              and certificate['boot_uuid'] == BOOT_UUID
              and qualification['boot_uuid'] == BOOT_UUID
              and qualification['original_uuid_recorded'] is True
              and qualification['boot_timeval_anchor_ns'] == certificate['boot_timeval_anchor_ns']
              and certificate['runtime_compatibility']['observation_source_commit'] == OBSERVER_COMMIT)
    except (KeyError, TypeError) as exc:
        raise BindingError('malformed_current_boot_qualification') from exc
    if not ok:
        raise BindingError('current_boot_qualification_identity_mismatch')
    return certificate


def require_current_boot(certificate, current):
    """Exact UUID; full timeval against the fixed anchor with the unchanged 2 s bound."""
    try:
        discrepancy = same_boot(BOOT_UUID, current, anchor_ns=certificate['boot_timeval_anchor_ns'])
    except (ValueError, KeyError, TypeError) as exc:
        raise BindingError('current_boot_incompatible:'+str(exc)) from exc
    return discrepancy


def require_qualification(repo, read=read_boot, policy=command):
    repo = Path(repo)
    path = repo/QUALIFICATION_PATH
    if not path.is_file() or file_sha256(path) != QUALIFICATION_SHA256:
        raise BindingError('current_boot_qualification_sha_mismatch')
    if blob_sha256(repo, QUALIFICATION_EVIDENCE_COMMIT, QUALIFICATION_PATH) != QUALIFICATION_SHA256:
        raise BindingError('current_boot_qualification_evidence_commit_mismatch')
    manifest = read_json(repo/QUALIFICATION_MANIFEST)
    if manifest.get('qualification_sha256') != QUALIFICATION_SHA256 or not manifest.get('files'):
        raise BindingError('qualification_manifest_mismatch')
    for name, item in manifest['files'].items():
        candidate = (repo/name).resolve()
        if (Path(name).is_absolute() or not candidate.is_relative_to(repo.resolve())
                or not candidate.is_file() or file_sha256(candidate) != item['sha256']):
            raise BindingError('qualification_evidence_changed:'+name)
    certificate = require_certificate(read_json(path))
    from dynapm.system_validation.uuid_host_observer import require_same_uuid_runtime
    if require_same_uuid_runtime(repo, OBSERVER_COMMIT) != certificate['runtime_compatibility']:
        raise BindingError('observer_runtime_changed')
    inputs, guard = qualification_inputs(repo, repo/certificate['qualification']['path'])
    if inputs != certificate['qualification']:
        raise BindingError('endurance_evidence_changed')
    current = read()
    discrepancy = require_current_boot(certificate, current)
    if policy(['/usr/bin/pmset', '-g', 'custom']) != guard['power_settings']:
        raise BindingError('endurance_power_policy_changed')
    return dict(current, boot_calendar_discrepancy_ns=discrepancy)


def source_binding(repo, spec):
    """Executor/observer provenance for a v2 spec. Called from service_primary."""
    repo = Path(repo)
    require_spec_identities(spec)
    head = _git(repo, 'rev-parse', 'HEAD').strip()
    if (head != spec['executor_commit'] or _git(repo, 'status', '--porcelain').strip()
            or _git(repo, 'branch', '--show-current').strip() != spec['executor_branch']):
        raise BindingError('clean_exact_executor_commit_required')
    require_lineage(repo, spec, head)
    require_observer_amendment(repo)
    return dict(primary_executor_commit=PRIMARY_EXECUTOR, observer_commit=OBSERVER_COMMIT,
                observer_amendment_sha256=OBSERVER_AMENDMENT_SHA256,
                host_qualification_sha256=QUALIFICATION_SHA256, expected_boot_uuid=BOOT_UUID,
                binding_schema=SPEC_SCHEMA)


def host_qualification(repo, spec):
    require_spec_identities(spec)
    return require_qualification(repo)
