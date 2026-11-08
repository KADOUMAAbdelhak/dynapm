import hashlib,http.client,json
from pathlib import Path
import pytest
from dynapm.core.provenance import canonical_json,fingerprint
from dynapm.system_validation import service_generator as g
from dynapm.system_validation.service_transport import campaign_generator_config,generator_resources,validate_download
from dynapm.system_validation.bounded_v8 import cells,plan,offers
from dynapm.system_validation.estimation_design import frozen_spec

URL='http://application.test.svc.cluster.local:8080'
E=dict(request_id=0,offset_ns=0,memory_mib=96,iterations=30000,seed=2026110501)
class Reply:
 status=200
 def read(self):return json.dumps(dict(ok=True,iterations=30000,memory_mib=96)).encode()
class Conn:
 def __init__(self,*a,**kw):assert kw['timeout']==5
 def connect(self):pass
 def request(self,method,url,headers):assert method=='GET' and url=='/work?iterations=30000&memory_mib=96&seed=2026110501' and headers=={'Connection':'close'}
 def getresponse(self):return Reply()
 def close(self):pass

def test_all_frozen_offers_unchanged():
 for c in cells():
  p=plan('primary',sequence=c['sequence']);cfg=campaign_generator_config(p,'id',URL)
  assert [e for _,e in g.offers(cfg)]==list(offers(p))

def test_response_and_clock_contract():
 r=g.request(URL,E,'high12',0,connection_factory=Conn)
 assert r['success'] and r['retries']==0 and r['http_status']==200
 assert r['latency_ns']==r['completed_offset_ns'] and r['network_attempt_latency_ns']>=0
 assert r['sent_wall_ns']<=r['completed_wall_ns']
@pytest.mark.parametrize('stage',['connect','headers','body'])
def test_deadlines_preserve_stage(stage):
 class C(Conn):
  def connect(self):
   if stage=='connect':raise TimeoutError('connect')
  def getresponse(self):
   if stage=='headers':raise TimeoutError('headers')
   class R(Reply):
    def read(self):raise TimeoutError('body')
   return R()
 r=g.request(URL,E,'high12',0,connection_factory=C)
 assert r['outcome']=='request_timeout' and r['exception']['type']=='TimeoutError'
 assert r['failure_layer']==('CONNECTION_DEADLINE' if stage=='connect' else 'RESPONSE_DEADLINE_CAUSE_UNRESOLVED')

def test_reset_not_application_error():
 class C(Conn):
  def connect(self):raise ConnectionResetError(54,'reset')
 r=g.request(URL,E,'high12',0,connection_factory=C)
 assert r['outcome']=='transport_error' and r['exception']['errno']==54

def test_http_error_not_transport():
 class C(Conn):
  def getresponse(self):
   class R:status=503
   return R()
 r=g.request(URL,E,'high12',0,connection_factory=C)
 assert r['outcome']=='http_error' and r['http_status']==503

def test_external_endpoint_refused():
 with pytest.raises(ValueError):g.request('http://example.com',E,'high12',0,connection_factory=Conn)

def fixture(root):
 cfg=dict(run_id='unit',service_url=URL,warmup_seconds=0,lead_seconds=0,plan=dict(seed=1,segments=[[0,'low2']],measurement_seconds=1,warmup_phase='low2'))
 start=dict(origin_monotonic_ns=100)
 records=[]
 for phase,e in g.offers(cfg):
  done=100+e['offset_ns']+10
  records.append(dict(request_id=e['request_id'],offer=e,intended_phase=phase,retries=0,scheduled_monotonic_ns=100+e['offset_ns'],completed_wall_ns=done,exception=None,completed_monotonic_ns=done,completed_offset_ns=done-100,latency_ns=10,sent_offset_ns=e['offset_ns'],success=True,outcome='success'))
 (root/'START.json').write_text(canonical_json(start));(root/'requests.jsonl').write_text(''.join(canonical_json(x)+'\n' for x in records))
 d=dict(status='COMPLETE',run_id='unit',config_sha256=fingerprint(cfg),records=2,expected_records=2,start_sha256=g.sha(root/'START.json'),requests_sha256=g.sha(root/'requests.jsonl'))
 (root/'DONE.json').write_text(canonical_json(d));return cfg

def test_reconciliation_and_idempotent_read(tmp_path):
 cfg=fixture(tmp_path);a=validate_download(tmp_path,cfg);assert len(a[0])==2 and a==validate_download(tmp_path,cfg)

def test_tamper_rejected(tmp_path):
 cfg=fixture(tmp_path);(tmp_path/'requests.jsonl').write_text('corrupt')
 with pytest.raises(ValueError,match='hash'):validate_download(tmp_path,cfg)

def test_owner_restart_refuses_to_overwrite(tmp_path):
 (tmp_path/'OWNER').write_text('old')
 with pytest.raises(FileExistsError):g.run(dict(run_id='other'),tmp_path)
 assert (tmp_path/'OWNER').read_text()=='old'

def test_export_failure_preserves_completed_files(tmp_path,monkeypatch):
 from dynapm.system_validation.service_transport import export_records
 from types import SimpleNamespace
 cfg=fixture(tmp_path);before=(tmp_path/'requests.jsonl').read_bytes()
 # Every complete local file exists: no data retrieval or workload submission is performed.
 monkeypatch.setattr('subprocess.run',lambda *a,**kw:pytest.fail('should not retrieve existing files'))
 export_records(SimpleNamespace(cwd=tmp_path,env={}), 'node','/durable',tmp_path)
 assert before==(tmp_path/'requests.jsonl').read_bytes()

def test_no_port_forward_dependency():
 import inspect
 from dynapm.system_validation import service_transport
 source=inspect.getsource(service_transport)
 assert "'port-forward'" not in source and 'free_port(' not in source

def test_old_new_mixing_refused():
 from dynapm.system_validation.service_transport import require_new_campaign_rows
 rows=[dict(scope='AMENDED_V8_PRIMARY',campaign_generation='v8-direct-service-v1',amendment_sha256='seal',implementation_commit='commit',cell=c,status='COMPLETE') for c in cells()]
 assert require_new_campaign_rows(rows,'seal','commit')
 rows[0]['scope']='MEASURED_V8A'
 with pytest.raises(ValueError,match='mixing'):require_new_campaign_rows(rows,'seal','commit')
 with pytest.raises(ValueError,match='18'):require_new_campaign_rows(rows[8:],'seal','commit')

def test_metric_arithmetic_preserved_with_disaggregation():
 from dynapm.system_validation.service_transport import endpoint_metrics
 from dynapm.system_validation.bounded_v8_metrics import request_metrics
 p=plan('primary',sequence=1);records=[]
 for event in offers(p):
  records.append(dict(request_id=event['request_id'],offer=event,sent_offset_ns=event['offset_ns'],completed_offset_ns=event['offset_ns']+10_000_000,success=True,outcome='success',http_status=200))
 old=request_metrics(p,records);new=endpoint_metrics(p,records)
 for name,metrics in old.items():
  for key,value in metrics.items():assert new[name][key]==value
 assert new['primary']['service_transport_errors']==0

def test_interrupted_export_resumes_without_losing_sealed_rows(tmp_path,monkeypatch):
 from types import SimpleNamespace
 import subprocess
 from dynapm.system_validation.service_transport import export_records
 source=tmp_path/'node';source.mkdir();cfg=fixture(source);saved={p.name:p.read_bytes() for p in source.iterdir()}
 dest=tmp_path/'host';calls=[];fail=[True]
 def copy(args,stdout,**kw):
  name=args[-1].rsplit('/',1)[-1];calls.append(name)
  if name=='START.json' and fail[0]:fail[0]=False;raise subprocess.TimeoutExpired(args,60)
  stdout.write(saved[name]);return SimpleNamespace(returncode=0,stderr=b'')
 monkeypatch.setattr(subprocess,'run',copy)
 commands=SimpleNamespace(cwd=tmp_path,env={})
 with pytest.raises(subprocess.TimeoutExpired):export_records(commands,'node','/durable',dest)
 assert (dest/'DONE.json').read_bytes()==saved['DONE.json'] and (source/'requests.jsonl').read_bytes()==saved['requests.jsonl']
 export_records(commands,'node','/durable',dest)
 assert len(validate_download(dest,cfg)[0])==2 and calls.count('DONE.json')==1

def test_interrupted_generator_is_not_full_window(tmp_path):
 cfg=fixture(tmp_path);d=json.loads((tmp_path/'DONE.json').read_text());d['status']='INTERRUPTED';(tmp_path/'DONE.json').write_text(canonical_json(d))
 with pytest.raises(ValueError,match='completion'):validate_download(tmp_path,cfg)

def test_duplicate_rows_refused_even_with_consistent_file_hash(tmp_path):
 cfg=fixture(tmp_path);rows=(tmp_path/'requests.jsonl').read_text().splitlines();(tmp_path/'requests.jsonl').write_text(rows[0]+'\n'+rows[0]+'\n')
 d=json.loads((tmp_path/'DONE.json').read_text());d['requests_sha256']=g.sha(tmp_path/'requests.jsonl');(tmp_path/'DONE.json').write_text(canonical_json(d))
 with pytest.raises(ValueError,match='offer'):validate_download(tmp_path,cfg)
