import importlib.util
from pathlib import Path
import io,json,urllib.error
import pytest
p=Path(__file__).parents[1]/'system_validation/transport_observability.py'
if not p.is_file():p=Path(__file__).with_name('transport_observability.py')
s=importlib.util.spec_from_file_location('v8c4_transport_observability',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
EVENT=dict(request_id=1,iterations=30000,memory_mib=96,seed=2026110501,offset_ns=0)
class Response:
    status=200
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self):return self.body

def test_identical_success_request_and_deadline():
    seen=[]
    def open(url,timeout):seen.append((url,timeout));return Response(json.dumps(dict(ok=True,iterations=30000,memory_mib=96)).encode())
    r=m.request_once('http://127.0.0.1:9999',EVENT,0,opener=open)
    assert r['success'] and seen==[('http://127.0.0.1:9999/work?iterations=30000&memory_mib=96&seed=2026110501',5)]
    assert r['attempt']==1
@pytest.mark.parametrize('exc',[ConnectionResetError(54,'reset'),ConnectionRefusedError(61,'refused'),urllib.error.URLError(ConnectionRefusedError(61,'refused'))])
def test_transport_never_application(exc):
    def open(*a,**kw):raise exc
    r=m.request_once('http://127.0.0.1',EVENT,0,opener=open)
    assert r['outcome']=='transport_error' and r['failure_layer']=='HARNESS_TRANSPORT' and r['exception_chain']
    assert m.require_transport_observable([r])=='HARNESS_FAILED'
@pytest.mark.parametrize('exc',[TimeoutError('timeout'),urllib.error.URLError(TimeoutError('timeout'))])
def test_timeout_cannot_be_attributed_to_application(exc):
    def open(*a,**kw):raise exc
    r=m.request_once('http://127.0.0.1',EVENT,0,opener=open)
    assert r['outcome']=='request_timeout' and r['failure_layer']=='UNATTRIBUTED_TIMEOUT'
    assert m.require_transport_observable([r])=='INDETERMINATE'
def test_explicit_http_error_is_response():
    def open(*a,**kw):raise urllib.error.HTTPError('http://127.0.0.1',503,'busy',{},io.BytesIO())
    r=m.request_once('http://127.0.0.1',EVENT,0,opener=open)
    assert r['outcome']=='http_error' and r['http_status']==503
    assert m.require_transport_observable([r])=='VALID'
def test_bad_body_is_preserved_application_response():
    r=m.request_once('http://127.0.0.1',EVENT,0,opener=lambda *a,**kw:Response(b'bad json'))
    assert r['outcome']=='application_error' and r['http_status']==200 and r['exception_chain']
def test_warning_alone_is_not_invalidation():
    assert m.require_transport_observable([],stream_creation_failures=1)=='VALID_WITH_TRANSPORT_WARNINGS'
    assert m.require_transport_observable([dict(outcome='request_timeout')],stream_creation_failures=1)=='INDETERMINATE'
    assert m.require_transport_observable([],lost_connection=True)=='HARNESS_FAILED'
def test_live_exit_precedes_cleanup_and_no_restart():
    class P:
        pid=123
        def poll(self):return -9
    records=[];p=m.ProcessObserver(P(),records.append,clock=lambda:10);p.begin_cleanup();p.poll()
    assert [r['event'] for r in records]==['PROCESS_STARTED','PROCESS_EXIT_OBSERVED','CLEANUP_REQUESTED']
    assert records[1]['signal']==9 and not records[1]['cleanup_requested']
def test_time_and_stream_categories():
    line='E1108 08:37:56.548540   48258 portforward.go:357] error creating error stream'
    assert m.glog_timestamp(line,year=2026,timezone='Europe/Helsinki')==pytest.approx(1794119876.548540)
    assert m.portforward_kind(line)=='error_stream_creation'
    assert m.glog_timestamp('error: lost connection to pod',year=2026,timezone='Europe/Helsinki') is None

def test_supervision_fails_before_bucket_deadline_and_keeps_exit_code():
    class Guard:
        def raise_if_failed(self):pass
    class P:
        pid=1
        def poll(self):return 1
    records=[];observer=m.ProcessObserver(P(),records.append)
    with pytest.raises(m.TransportFailure,match='returncode=1'):
        m.supervised_wait(10**30,Guard(),observer,sleep=lambda x:pytest.fail('should not wait for bucket boundary'))
    assert records[-1]['event']=='PROCESS_EXIT_OBSERVED'

def test_supervision_checks_short_intervals_without_deadline_fabrication():
    class Guard:
        def raise_if_failed(self):pass
    class P:
        pid=1
        def poll(self):return None
    now=[0];delays=[]
    def sleep(s):delays.append(s);now[0]+=int(s*1e9)
    observer=m.ProcessObserver(P(),lambda x:None,clock=lambda:now[0])
    m.supervised_wait(1_000_000_000,Guard(),observer,clock=lambda:now[0],sleep=sleep)
    assert now[0]==1_000_000_000 and delays==[.25]*4


def test_truncated_http_body_is_transport_failure_not_application_error():
    import http.client
    class BrokenResponse(Response):
        def read(self):raise http.client.IncompleteRead(b"partial",10)
    r=m.request_once("http://127.0.0.1",EVENT,0,opener=lambda *a,**kw:BrokenResponse(b""))
    assert r["outcome"]=="transport_error" and r["failure_stage"]=="read_body"
    assert r["http_status"]==200 and r["exception_chain"][0]["type"]=="IncompleteRead"
