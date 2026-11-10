"""Fail-closed evidence verification/binding only; never calls campaign/treatment."""
import ast,json,subprocess,shutil
from copy import deepcopy
from pathlib import Path
from dynapm.core.provenance import canonical_json,file_sha256,utc_now
from dynapm.system_validation.v8_host_identity import qualification_inputs,read_boot,same_boot
from dynapm.system_validation.host_power import ENDURANCE_SECONDS,MAX_HEARTBEAT_GAP_NS,power_state,command,TYPES
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.service_primary import preflight,stable_spec_hash,source_binding
from dynapm.system_validation.service_checkpoint import Checkpoint,next_slot

repo=Path.cwd();p=Path(__file__).resolve().parent
intent=json.loads((p/'intent.json').read_text());end=json.loads((p/'observation-terminal.json').read_text())
assert end['status']=='HOST_COMMAND_COMPLETE' and end['returncode']==0 and end['failure'] is None
assert end['elapsed_monotonic_seconds']>=ENDURANCE_SECONDS
log=(p/'host-observation.log').read_text().splitlines()
entries=[ast.literal_eval(l) for l in log if l.startswith("{'status':")]
assert entries[-1]['status']=='COMPLETE'
run=Path(entries[-1]['run_path']);inputs,guard=qualification_inputs(repo,run)
assert inputs['legacy_epoch']==intent['boot']['boot_epoch_seconds']
summary=json.loads((run/'outputs/endurance_summary.json').read_text())
continuity=json.loads((run/'outputs/host_continuity_summary.json').read_text())
rows=[json.loads(l) for l in (run/'outputs/host_continuity.jsonl').read_text().splitlines()]
assert all(r['kind']=='CHECKPOINT' for r in rows)
assert summary['elapsed_seconds']>=ENDURANCE_SECONDS and summary['requested_seconds']==ENDURANCE_SECONDS
assert guard['release_confirmed'] is True and guard['status']=='RELEASED' and guard['failure'] is None
assert guard['authorized_external_power_deficit'] is False
assert continuity['failure'] is None and continuity['checkpoints']==len(rows)
assert rows[-1]['monotonic_ns']-rows[0]['monotonic_ns']>=ENDURANCE_SECONDS*10**9
maxdrift=max(abs((r['wall_ns']-rows[0]['wall_ns'])-(r['monotonic_ns']-rows[0]['monotonic_ns'])) for r in rows)
gaps=[b['monotonic_ns']-a['monotonic_ns'] for a,b in zip(rows,rows[1:])]
assert maxdrift<=MAX_CLOCK_DELTA_NS and min(gaps)>=0 and max(gaps)<=MAX_HEARTBEAT_GAP_NS
assert maxdrift==continuity['maximum_absolute_drift_ns'] and max(gaps)==continuity['maximum_checkpoint_gap_ns']
for r in rows:
 power=r['power']
 assert power['ac_power'] and power['lid_open'] and not power['external_power_deficit_observed'] and not power['authorized_external_power_deficit']
 assert power['boot_epoch_seconds']==inputs['legacy_epoch']
 assert all(any(t in line for line in power['own_assertion_lines']) for t in TYPES)
assert guard['power_settings']==intent['power_policy']==command(['/usr/bin/pmset','-g','custom'])
assert guard['power_settings'].count('lowpowermode         0')==2
witness=[json.loads(l) for l in (p/'boot-uuid-witness.jsonl').read_text().splitlines()]
assert all(w['boot']['boot_uuid']==intent['expected_boot_uuid'] for w in witness)
assert witness[0]['monotonic_ns']<=rows[0]['monotonic_ns'] and witness[-1]['monotonic_ns']>=rows[-1]['monotonic_ns']
wgaps=[b['monotonic_ns']-a['monotonic_ns'] for a,b in zip(witness,witness[1:])]
assert min(wgaps)>=0 and max(wgaps)<=MAX_HEARTBEAT_GAP_NS
wdrift=max(abs((w['wall_ns']-witness[0]['wall_ns'])-(w['monotonic_ns']-witness[0]['monotonic_ns'])) for w in witness)
assert wdrift<=MAX_CLOCK_DELTA_NS
current=read_boot();same_boot(intent['expected_boot_uuid'],current,legacy_epoch=inputs['legacy_epoch'])
old=repo/intent['old_host_amendment_path'];assert file_sha256(old)==intent['old_host_amendment_sha256']
previous=json.loads((p/'preserved-failed-attempt-inventory.json').read_text())
for path,item in previous.items():assert file_sha256(repo/path)==item['sha256'] and (repo/path).stat().st_size==item['bytes']
cp=repo/intent['checkpoint_path'];cpbytes=cp.read_bytes();state=json.loads(cpbytes)
assert file_sha256(cp)==intent['checkpoint_sha256'] and all(s['status']=='PENDING' for s in state['slots']) and len(state['slots'])==18
resumed=Checkpoint(cp.parent,state['identity'],resume=True);assert next_slot(cp.parent,resumed.state,state['identity'])['sequence']==1 and cp.read_bytes()==cpbytes
record=dict(schema_version='v8-current-boot-host-terminal-v1',status='PASS',recorded_at=utc_now(),boot_uuid=intent['expected_boot_uuid'],executor_commit=intent['executor_commit'],run_path=str(run.relative_to(repo)),qualification=inputs,elapsed_seconds=summary['elapsed_seconds'],checkpoints=len(rows),maximum_absolute_drift_ns=maxdrift,maximum_checkpoint_gap_ns=max(gaps),uuid_witness_count=len(witness),uuid_witness_maximum_gap_ns=max(wgaps),uuid_witness_maximum_drift_ns=wdrift,uuid_witness_sha256=file_sha256(p/'boot-uuid-witness.jsonl'),observer_terminal_sha256=file_sha256(p/'observation-terminal.json'),power_assertions_released=True,old_qualification_preserved=True,failed_attempt_preserved=True,all_18_pending=True,checkpoint_sha256=file_sha256(cp),primary_lifecycle_started=False,claim_started=False)
(p/'terminal.json').write_text(canonical_json(record)+'\n')
certificate=dict(schema_version='v8-current-boot-host-qualification-v1',status='PASS',boot_uuid=intent['expected_boot_uuid'],qualification=inputs,witnesses=[dict(path=str(p.relative_to(repo)),terminal_sha256=file_sha256(p/'terminal.json'),intent_sha256=file_sha256(p/'intent.json'),boot_uuid=intent['expected_boot_uuid'],kind='direct-current-boot-host-only-observation')],witness_mode='direct concurrent UUID readings across full three-hour host observation; no historical neutral-run UUID association',uuid_witness_sha256=file_sha256(p/'boot-uuid-witness.jsonl'),verification_script_sha256=file_sha256(Path(__file__)),observer_script_sha256=file_sha256(p/'observe-current-uuid.py'),executor_commit=intent['executor_commit'],frozen_scientific_source='fe3b870149a156e7fecb88741d51cfb5c1ed86d7',criteria_unchanged=True,required_seconds=ENDURANCE_SECONDS,clock_bound_ns=MAX_CLOCK_DELTA_NS,checkpoint_bound_ns=MAX_HEARTBEAT_GAP_NS,approval_basis='User authorized a fresh current-boot host qualification; unchanged criteria independently verified',previous_qualification_path=intent['old_host_amendment_path'],previous_qualification_sha256=intent['old_host_amendment_sha256'],previous_qualification_rewritten=False,primary_executor_qualified=False,claim_execution_authorized=False,recorded_at=utc_now())
cert=p/'current-boot-qualification.json';cert.write_text(canonical_json(certificate)+'\n')
original=repo/'results/v8c_r2/20261109-next-strict-ac/executor-spec.json';spec=json.loads(original.read_text());updated=deepcopy(spec);updated.update(host_amendment_path=str(cert.relative_to(repo)),host_amendment_sha256=file_sha256(cert))
assert stable_spec_hash(spec)==stable_spec_hash(updated)
assert {k for k in spec if spec[k]!=updated[k]}=={'host_amendment_path','host_amendment_sha256'}
new_spec=p/'executor-spec-current-boot.json';new_spec.write_text(canonical_json(updated)+'\n')
source_binding(repo,updated)
session,_,_,_=preflight(repo,p/'final-preflight',updated,18)
assert cp.read_bytes()==cpbytes
args=json.loads((original.parent/'commands.json').read_text())['start']
args[args.index('--spec')+1]=str(new_spec);args[args.index('--spec-sha256')+1]=file_sha256(new_spec)
args+=['--resume']
(p/'prepared-commands-current-boot.json').write_text(canonical_json(dict(status='PREPARED_ONLY_NOT_LAUNCHED',strict_ac_75_minute_qualification=args,claim_execution='NOT_AUTHORIZED',scope='DIAGNOSTIC_NON_CLAIM',expected_boot_uuid=intent['expected_boot_uuid']))+'\n')
verification=dict(status='CURRENT_BOOT_READY',qualification_sha256=file_sha256(cert),preflight_sha256=session['preflight_sha256'],executor_spec_sha256=file_sha256(new_spec),stable_campaign_spec_unchanged=True,checkpoint_sha256=file_sha256(cp),all_18_pending=True,old_qualification_preserved=True,failed_attempt_files_verified=len(previous),free_bytes=shutil.disk_usage(repo).free,executor_commit=intent['executor_commit'],source_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),primary_lifecycle_started=False,claim_started=False,integration_started=False,recorded_at=utc_now())
(p/'final-verification.json').write_text(canonical_json(verification)+'\n')
print(json.dumps(dict(qualification=certificate,verification=verification),indent=2))
