"""Derive the v2 binding spec from the sealed task49 host-only spec. Run from the frozen repo."""
import hashlib, json, subprocess, sys
from copy import deepcopy
from pathlib import Path
from dynapm.core.provenance import canonical_json, file_sha256
from dynapm.system_validation import primary_observer_binding as b

repo = Path.cwd()
out = Path(sys.argv[1])
src = repo/'results/v8c_r2/20261111-task49-current-boot-v1/executor-spec-current-host-only.json'
assert file_sha256(src) == 'f97a99e42eca820bfe89b1569faf19528e854566a2c0bb514f8938b35adf62e8'
old = json.loads(src.read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
blob = lambda c, p: hashlib.sha256(subprocess.check_output(['git', 'show', c+':'+p], cwd=repo)).hexdigest()
spec = deepcopy(old)
spec.update(
    schema=b.SPEC_SCHEMA,
    executor_commit=head,
    executor_branch='v8c5-service-transport',
    primary_executor_commit=b.PRIMARY_EXECUTOR,
    observer_commit=b.OBSERVER_COMMIT,
    observer_files={p: blob(b.OBSERVER_COMMIT, p) for p in b.OBSERVER_DELTA},
    observer_amendment_path=b.OBSERVER_AMENDMENT_PATH,
    observer_amendment_sha256=b.OBSERVER_AMENDMENT_SHA256,
    observer_evidence_commit=b.OBSERVER_EVIDENCE_COMMIT,
    host_qualification_evidence_commit=b.QUALIFICATION_EVIDENCE_COMMIT,
    binding_files={p: blob(head, p) for p in b.BINDING_DELTA},
    expected_boot_uuid=b.BOOT_UUID,
    supersedes_executor_spec_sha256=file_sha256(src),
    authorization='PLAN ONLY: binding-only amendment; strict preflight only; no lifecycle, claim or integration authorized',
    correction='Bind primary executor 67bfd37 lineage to approved task49 observer 1b50282 and current-boot certificate 594ba9a2; treatment unchanged',
)
# Unchanged scientific/treatment fields must carry over byte-for-byte.
changed = {k for k in spec if old.get(k) != spec[k]}
allowed = {'schema', 'executor_commit', 'primary_executor_commit', 'observer_commit', 'observer_files',
           'observer_amendment_path', 'observer_amendment_sha256', 'observer_evidence_commit',
           'host_qualification_evidence_commit', 'binding_files', 'expected_boot_uuid',
           'supersedes_executor_spec_sha256', 'authorization', 'correction'}
assert changed <= allowed, changed - allowed
assert spec['executor_files'] == old['executor_files'] and spec['t0_policy'] == old['t0_policy']
assert not spec['claim_execution_authorized'] and not spec['strict_ac_qualification_satisfied']
out.write_text(canonical_json(spec)+'\n')
print(file_sha256(out), sorted(changed))
