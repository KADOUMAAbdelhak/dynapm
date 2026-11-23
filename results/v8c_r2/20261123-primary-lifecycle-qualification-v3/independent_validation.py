"""Independent validation of Step B v3 (reproduces v1 schema). Run from the frozen repo with PYTHONPATH=."""
import json, shutil, sys
from collections import Counter
from pathlib import Path
from dynapm.core.provenance import canonical_json, file_sha256, read_json, utc_now
from dynapm.system_validation.service_checkpoint import verify_checkpoint, next_slot
from dynapm.system_validation.service_primary import stable_spec_hash, RESERVE
L = Path(sys.argv[1]); root = L/'qualification-campaign'
spec = read_json('results/v8c_r2/20261123-slot-replacement-amendment-v1/executor-spec-v3.json')
cp = root/'checkpoint.json'; before = file_sha256(cp); state = read_json(cp)
ident = state['identity']
assert ident['executor_commit'] == spec['executor_commit'] and ident['spec_sha256'] == stable_spec_hash(spec)
assert ident['expected_boot_uuid'] == spec['expected_boot_uuid'] and ident['scope'] == 'DIAGNOSTIC_NON_CLAIM'
verify_checkpoint(root, state, ident)
slot = state['slots'][0]; run = (root/slot['manifest']).parent; out = run/'outputs'
man = read_json(run/'manifest.json')
mism = [p for p, d in man['files'].items() if file_sha256(root/p) != d]
nxt = next_slot(root, state, ident)
reqs = [json.loads(l) for l in (out/'generator/requests.jsonl').read_text().splitlines()]
ref = [r for r in reqs if r['outcome'] == 'transport_error' and (r.get('exception') or {}).get('type') == 'ConnectionRefusedError']
offs = [r['offer']['offset_ns']//10**9 for r in ref]
app = read_json(out/'application-terminal.json')['status']
cs = app['containerStatuses'][0]
prot = 'results/v8c_r2/20261109-next-strict-ac/qualification-campaign/checkpoint.json'
free = shutil.disk_usage('.').free
rec = dict(schema='v8-primary-lifecycle-independent-validation-v1', slot_status=slot['status'], cell=slot['cell'],
    checkpoint_verified=True, manifest_files=len(man['files']), manifest_mismatches=mism,
    other_slots=dict(Counter(s['status'] for s in state['slots'][1:])), records=len(reqs),
    unique_offers=len({r['offer']['offset_ns'] for r in reqs}), refusal_count=len(ref),
    refusal_offset_seconds_range=[min(offs), max(offs)] if offs else [],
    enforcement_rows=len((out/'enforcement.jsonl').read_text().splitlines()),
    app_ready=bool(cs.get('ready')), app_restart_count=cs['restartCount'],
    app_last_state=[] if not cs.get('lastState') else [cs['lastState']],
    resume_next_sequence=nxt['sequence'], resume_left_bytes_unchanged=file_sha256(cp) == before,
    protected_checkpoint_unchanged=file_sha256(prot) == '16c07107b4063037c922ea766398c72e526a4d68f4e931f184a5c0264ad07ce6',
    free_bytes_now=free, storage_reserve_preserved=free > RESERVE, recorded_at=utc_now())
assert not mism and rec['resume_left_bytes_unchanged'] and rec['protected_checkpoint_unchanged'] and rec['app_ready']
(L/'independent-validation.json').write_text(canonical_json(rec)+'\n')
print(json.dumps({k: v for k, v in rec.items() if k != 'cell'}))
