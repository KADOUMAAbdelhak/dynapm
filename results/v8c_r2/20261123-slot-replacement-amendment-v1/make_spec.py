"""Derive the amendment-v3 spec from the re-bound spec d741b746. Run from the frozen repo with PYTHONPATH=."""
import hashlib, json, subprocess, sys
from copy import deepcopy
from pathlib import Path
from dynapm.core.provenance import canonical_json, file_sha256
from dynapm.system_validation import primary_observer_binding as b

repo = Path.cwd()
out = Path(sys.argv[1])
src = repo/'results/v8c_r2/20261122-primary-rebinding-v1/executor-spec-rebound.json'
assert file_sha256(src) == 'd741b746c0ed13baf9fe2a058cc08c1370c0cbe31a0e59f403fe27bc89d17be9'
old = json.loads(src.read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
blob = lambda c, p: hashlib.sha256(subprocess.check_output(['git', 'show', c+':'+p], cwd=repo)).hexdigest()
spec = deepcopy(old)
spec.update(
    executor_commit=head,
    binding_files={p: blob(head, p) for p in b.BINDING_DELTA},
    supersedes_executor_spec_sha256=file_sha256(src),
    correction='Amendment v3: approved host-power slot replacement (checkpoint only); treatment unchanged; host qualification b0d91ebc unchanged',
)
changed = {k for k in spec if old.get(k) != spec[k]}
allowed = {'executor_commit', 'binding_files', 'supersedes_executor_spec_sha256', 'correction'}
assert changed <= allowed, changed - allowed
for k in ('executor_files', 'observer_files', 't0_policy', 'scientific_source', 'qualified_transport',
          'host_amendment_path', 'host_amendment_sha256', 'expected_boot_uuid',
          'physical_phases_seconds', 'storage_start_requirement_18_bytes', 'authorization'):
    assert spec[k] == old[k], k
assert not spec['claim_execution_authorized'] and not spec['strict_ac_qualification_satisfied']
out.write_text(canonical_json(spec)+'\n')
print(file_sha256(out), sorted(changed))
