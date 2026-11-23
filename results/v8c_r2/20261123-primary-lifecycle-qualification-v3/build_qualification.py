"""Independent reconstruction of the Step B lifecycle and its claim-gate qualification record."""
import json,sys
from collections import Counter
from pathlib import Path
from dynapm.core.provenance import canonical_json,file_sha256,read_json,utc_now
from dynapm.system_validation.bounded_v8 import plan,offers
from dynapm.system_validation.service_primary import stable_spec_hash,SLOT_BUDGET,GENERATOR_BUDGET,RESERVE
NS=10**9
L=Path(sys.argv[1]);repo=Path.cwd()
spec_path=Path('results/v8c_r2/20261123-slot-replacement-amendment-v1/executor-spec-v3.json');spec=read_json(spec_path)
root=L/'qualification-campaign';state=read_json(root/'checkpoint.json');slot=state['slots'][0]
run=(root/slot['manifest']).parent;out=run/'outputs';e=read_json(out/'endpoint.json')
assert slot['status']=='SEALED_VALID' and e['status']=='SEALED_VALID' and state['identity']['scope']=='DIAGNOSTIC_NON_CLAIM'
assert state['identity']['executor_commit']==spec['executor_commit']
reqs=[json.loads(l) for l in (out/'generator/requests.jsonl').read_text().splitlines()]
planned=list(offers(plan('primary',sequence=1)))
assert len(reqs)==len(planned)==e['request_reconciliation']['expected'] and len({r['offer']['offset_ns'] for r in reqs})==len(reqs)
def cls(r):
    if r['outcome']=='transport_error' and (r.get('exception') or {}).get('type')=='ConnectionRefusedError':return 'connection_refusal'
    if r.get('failure_layer')=='CONNECTION_DEADLINE':return 'connection_deadline'
    if r['outcome']=='request_timeout':return 'response_deadline'
    return r['outcome']
recon={}
for name,(lo,hi) in {'primary':(0,1800),'transition':(0,300),'followup':(300,1800)}.items():
    c=[r for r in reqs if lo*NS<=r['offer']['offset_ns']<hi*NS];k=Counter(map(cls,c))
    recon[name]=dict(scheduled_offers=len(c),sent_attempts=sum(r['sent_offset_ns'] is not None for r in c),failure_class_counts=dict(k))
    m=e['metrics'][name]
    assert recon[name]['scheduled_offers']==m['scheduled_offers'] and recon[name]['sent_attempts']==m['sent_attempts'] and dict(k)==m['failure_class_counts'],name
assert Counter(r['outcome'] for r in reqs)==Counter(e['request_reconciliation']['outcomes'])
buckets=[json.loads(p.read_text()) for p in out.glob('*.event.json')];offsets=sorted(b['offset_seconds'] for b in buckets if b['event']=='BUCKET_VALIDATED')
assert offsets==[300,600,900,1200,1500,1800]
act=e['actuations'];assert len(act)==1 and act[0]['status']=='ENFORCED'
snap=read_json(out/'snapshot-binding.json');assert snap['target']['cpu_millicores']==act[0]['cpu_millicores'] if 'cpu_millicores' in snap['target'] else True
guard=read_json(out/'power_guard.json');cont=read_json(out/'host_continuity_summary.json')
assert guard['status']=='RELEASED' and guard['failure'] is None and guard['release_confirmed'] and not guard['authorized_external_power_deficit'] and cont['failure'] is None
clean=read_json(out/'cleanup.json');assert clean['deleted'] and not clean['node_copy_preserved']
assert file_sha256(out/'generator/requests.jsonl')==e['node_host_sha256']==slot['request_sha256']
life=[json.loads(l) for l in (out/'lifecycle.jsonl').read_text().splitlines()]
slot_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file());gen_bytes=(out/'generator/requests.jsonl').stat().st_size
min_free=min(x['free_bytes'] for x in life)
assert slot_bytes<=SLOT_BUDGET and gen_bytes<=GENERATOR_BUDGET and min_free>22*2**30
evidence=[p for p in sorted(root.rglob('*')) if p.is_file() and p.name!='campaign.lock']+[L/'independent-validation.json',L/'intent.json',L/'launcher-terminal.json',L/'lifecycle-execution.log']
record=dict(schema='v8-primary-service-qualification-v1',status='PASS',scope='DIAGNOSTIC_NON_CLAIM',qualification_mode='STRICT_AC_PRIMARY_LIFECYCLE',
 claim_qualification_eligible=True,full_lifecycle_verified=True,storage_certified=True,
 executor_commit=spec['executor_commit'],campaign_spec_sha256=stable_spec_hash(spec),executor_spec_sha256=file_sha256(spec_path),
 boot_uuid=slot['session']['boot']['boot_uuid'],host_qualification_sha256=slot['session']['host_qualification_sha256'],
 cell=slot['cell'],phases_seconds=[900,1800,1800],buckets_validated=offsets,request_reconstruction=recon,
 records=len(reqs),missing=0,duplicates=0,actuation=act[0],
 power=dict(checkpoints=cont['checkpoints'],maximum_absolute_drift_ns=cont['maximum_absolute_drift_ns'],maximum_checkpoint_gap_ns=cont['maximum_checkpoint_gap_ns']),
 storage=dict(slot_bytes=slot_bytes,slot_budget=SLOT_BUDGET,generator_bytes=gen_bytes,generator_budget=GENERATOR_BUDGET,minimum_observed_free_bytes=min_free,operational_buffer=22*2**30,absolute_reserve=RESERVE),
 cleanup=clean,application_restarts=read_json(out/'application-terminal.json')['status']['containerStatuses'][0]['restartCount'],
 outcomes_note='Deadlines, refusals and cap drops are measured outcomes; not validity gates',
 claim_execution_authorized=False,files={str(p.relative_to(L)):file_sha256(p) for p in evidence},recorded_at=utc_now())
(L/'primary-qualification.json').write_text(canonical_json(record)+'\n')
print(file_sha256(L/'primary-qualification.json'),json.dumps(record['storage']),len(record['files']))
