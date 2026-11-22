"""Derive the re-bound v2 spec from the sealed observer-binding spec. Run from the frozen repo."""
import hashlib, json, subprocess, sys
from copy import deepcopy
from pathlib import Path
from dynapm.core.provenance import canonical_json, file_sha256
from dynapm.system_validation import primary_observer_binding as b

repo = Path.cwd()
out = Path(sys.argv[1])
src = repo/'results/v8c_r2/20261119-primary-binding-v1/executor-spec-observer-binding.json'
assert file_sha256(src) == 'f5d78b95c764ad785017822345b8b919e1b3cd806ac5a73c7747225610ee5e09'
old = json.loads(src.read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
blob = lambda c, p: hashlib.sha256(subprocess.check_output(['git', 'show', c+':'+p], cwd=repo)).hexdigest()
spec = deepcopy(old)
spec.update(
    executor_commit=head,
    binding_files={p: blob(head, p) for p in b.BINDING_DELTA},
    host_amendment_path=b.QUALIFICATION_PATH,
    host_amendment_sha256=b.QUALIFICATION_SHA256,
    host_qualification_evidence_commit=b.QUALIFICATION_EVIDENCE_COMMIT,
    expected_boot_uuid=b.BOOT_UUID,
    supersedes_executor_spec_sha256=file_sha256(src),
    correction='Re-bind to current-boot certificate b0d91ebc (boot 26051F76) after reboot; binding constants only; treatment unchanged',
)
changed = {k for k in spec if old.get(k) != spec[k]}
allowed = {'executor_commit', 'binding_files', 'host_amendment_path', 'host_amendment_sha256',
           'host_qualification_evidence_commit', 'expected_boot_uuid', 'supersedes_executor_spec_sha256', 'correction'}
assert changed <= allowed, changed - allowed
for k in ('executor_files', 'observer_files', 't0_policy', 'scientific_source', 'qualified_transport',
          'physical_phases_seconds', 'storage_start_requirement_18_bytes', 'authorization'):
    assert spec[k] == old[k], k
assert not spec['claim_execution_authorized'] and not spec['strict_ac_qualification_satisfied']
out.write_text(canonical_json(spec)+'\n')
print(file_sha256(out), sorted(changed))
