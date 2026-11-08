"""Opt-in transport attribution amendment. Does not modify frozen V8 execution."""
from __future__ import annotations
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

SCHEMA = 'v8-transport-observability-v1'


def exception_record(exc):
    """Retain the actual reason/errno rather than calling connection loss application error."""
    chain=[]; seen=set(); current=exc
    while isinstance(current,BaseException) and id(current) not in seen:
        seen.add(id(current))
        chain.append(dict(type=type(current).__name__,message=str(current),errno=getattr(current,'errno',None)))
        reason=getattr(current,'reason',None)
        current=reason if isinstance(reason,BaseException) else current.__cause__
    return chain


def request_once(url,event,origin,*,opener=None,clock=time.monotonic_ns,timeout=5):
    """Same request, work, deadline and success contract; separately record transport failures."""
    opener=opener or urllib.request.urlopen
    sent=clock()-origin; status=None; stage='connect_or_headers'; failure=None; layer=None; raw=None
    outcome='success'
    try:
        query=f"iterations={event['iterations']}&memory_mib={event['memory_mib']}&seed={event['seed']}"
        with opener(url+'/work?'+query,timeout=timeout) as response:
            status=response.status; stage='read_body'; raw=response.read(); stage='decode_body'
            body=json.loads(raw)
            if status!=200 or not isinstance(body,dict) or body.get('ok') is not True or body.get('iterations')!=event['iterations'] or body.get('memory_mib')!=event['memory_mib']:
                outcome='application_error'; layer='APPLICATION_RESPONSE'
    except urllib.error.HTTPError as exc:
        status=exc.code;outcome='http_error';layer='APPLICATION_HTTP_RESPONSE';failure=exception_record(exc);exc.close()
    except (OSError,ValueError,http.client.HTTPException) as exc:
        failure=exception_record(exc)
        if any(x['type'] in ('TimeoutError','socket.timeout') for x in failure):
            outcome='request_timeout';layer='UNATTRIBUTED_TIMEOUT'
        elif stage=='decode_body':
            outcome='application_error';layer='APPLICATION_RESPONSE'
        else:
            outcome='transport_error';layer='HARNESS_TRANSPORT'
    completed=clock()-origin
    return dict(schema=SCHEMA,request_id=event['request_id'],offer=event,sent_offset_ns=sent,
        completed_offset_ns=completed,success=outcome=='success',outcome=outcome,http_status=status,
        failure_layer=layer,failure_stage=stage if failure else None,exception_chain=failure,
        response_bytes=len(raw) if raw is not None else None,attempt=1)


def portforward_kind(line):
    if 'error creating error stream' in line:return 'error_stream_creation'
    if 'error creating forwarding stream' in line:return 'data_stream_creation'
    if 'connection reset by peer' in line:return 'connection_reset'
    if 'broken pipe' in line:return 'broken_pipe'
    if 'lost connection to pod' in line:return 'lost_connection_to_pod'
    if 'Unhandled Error' in line:return 'other_warning'
    return None


def glog_timestamp(line,*,year,timezone):
    m=re.match(r'[IWEF](\d{2})(\d{2}) (\d{2}:\d{2}:\d{2}\.\d+)',line)
    if not m:return None
    return datetime.fromisoformat(f'{year}-{m[1]}-{m[2]}T{m[3]}').replace(tzinfo=ZoneInfo(timezone)).timestamp()


class ProcessObserver:
    """Record actual poll status promptly; never restart or label a live-scope exit as cleanup."""
    def __init__(self,process,emit,*,clock=time.monotonic_ns):
        self.process=process;self.emit=emit;self.clock=clock;self.exited=False;self.cleanup=False
        emit(dict(event='PROCESS_STARTED',pid=process.pid,monotonic_ns=clock()))
    def poll(self):
        status=self.process.poll()
        if status is not None and not self.exited:
            self.exited=True
            self.emit(dict(event='PROCESS_EXIT_OBSERVED',pid=self.process.pid,returncode=status,
                signal=-status if status<0 else None,monotonic_ns=self.clock(),cleanup_requested=self.cleanup))
        return status
    def begin_cleanup(self):
        # Poll first: an already dead transport must never be relabelled as deliberate teardown.
        self.poll();self.cleanup=True
        self.emit(dict(event='CLEANUP_REQUESTED',pid=self.process.pid,monotonic_ns=self.clock()))


def require_transport_observable(records,*,stream_creation_failures=0,lost_connection=False):
    """Fail closed for definite transport loss. Warning counts alone do not reject a run."""
    if lost_connection or any(r.get('failure_layer')=='HARNESS_TRANSPORT' for r in records):
        return 'HARNESS_FAILED'
    uncertain=any(r.get('outcome') in ('request_timeout','application_error') and
        r.get('failure_layer') not in ('APPLICATION_RESPONSE','APPLICATION_HTTP_RESPONSE') for r in records)
    if uncertain and stream_creation_failures:
        return 'INDETERMINATE'
    if uncertain:return 'INDETERMINATE'
    return 'VALID_WITH_TRANSPORT_WARNINGS' if stream_creation_failures else 'VALID'


class TransportFailure(RuntimeError):
    pass


def supervised_wait(deadline_ns,guard,observer,*,clock=time.monotonic_ns,sleep=time.sleep):
    """Opt-in replacement for a wait that formerly noticed worker death only at 300 s."""
    while True:
        guard.raise_if_failed()
        code=observer.poll()
        if code is not None and not observer.cleanup:
            raise TransportFailure(f'workload_port_forward_exited:returncode={code}')
        remaining=(deadline_ns-clock())/1e9
        if remaining<=0:return
        sleep(min(.25,remaining))
