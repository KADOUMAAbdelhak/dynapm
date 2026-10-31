"""Deterministic clock boundary tests; no Kubernetes or policy comparisons."""
import base64
import hashlib
import io
import json
from pathlib import Path

import pytest

from dynapm.core.provenance import read_json
from dynapm.system_validation.clock_observations import (
    ObservationClock,ClockRejected,MAX_CLOCK_DELTA_NS,receive_observation,validate_clock_evidence)

CONTEXT=dict(run_id='UNIT',experiment_fingerprint='f'*64,source_commit='c'*40)
NS=1_700_000_000_000_000_000
DOMAIN=dict(boot_id='UNIT_BOOT',time_namespace='UNIT_TIME_NS',hostname='UNIT')


def evidence(source=NS,receipt=None,**sample_fields):
    receipt=source+1_000_000 if receipt is None else receipt
    source_clock=sample_fields.pop('source_clock',dict(wall_ns=source,monotonic_ns=100))
    if isinstance(source_clock,dict):source_clock={**source_clock,'domain':DOMAIN}
    sample=dict(sample_time_ns=source,instance_id='UNIT',cpu_seconds=1.,source_clock=source_clock,**sample_fields)
    source_raw=json.dumps(sample).encode()
    raw=json.dumps(dict(schema_version='cluster-clock-envelope-v1',raw_payload_base64=base64.b64encode(source_raw).decode(),
        raw_payload_sha256=hashlib.sha256(source_raw).hexdigest(),cluster_received_at_ns=receipt,
        cluster_receipt_monotonic_ns=1_010_000_000,cluster_request_wall_ns=receipt-10_000_000,
        cluster_request_monotonic_ns=1_000_000_000,cluster_clock_domain=DOMAIN)).encode()
    return dict(raw_payload_base64=base64.b64encode(raw).decode(),raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
        request_wall_ns=receipt-10_000_000,request_monotonic_ns=1_000_000_000,
        received_at_ns=receipt,receipt_monotonic_ns=1_010_000_000)


@pytest.fixture
def store(tmp_path):
    (tmp_path/'outputs').mkdir()
    return ObservationClock(tmp_path,CONTEXT),io.StringIO()


def test_valid_exact_integer_nanoseconds_and_persistence(store):
    c,out=store
    sample=c.accept(evidence(NS+123),out)
    assert sample['sample_time_ns']==NS+123
    assert json.loads(out.getvalue())==sample
    assert c.rejections.read_text()==''
    c.finalize()
    assert validate_clock_evidence(c.root,CONTEXT)


@pytest.mark.parametrize('delta',[0,1,MAX_CLOCK_DELTA_NS])
def test_exact_boundary_is_accepted(store,delta):
    c,out=store
    assert c.accept(evidence(NS,NS+delta),out)['received_at_ns']==NS+delta


@pytest.mark.parametrize('delta,reason',[(-1,'source_ahead_of_cluster_receipt'),
    (MAX_CLOCK_DELTA_NS+1,'source_cluster_delta_exceeds_2s')])
def test_rejected_body_durable_and_never_scientific(store,delta,reason):
    c,out=store;obs=evidence(NS,NS+delta)
    with pytest.raises(ClockRejected,match=reason) as exc:c.accept(obs,out)
    assert out.getvalue()=='' and c.previous is None
    record=json.loads(c.rejections.read_text())
    assert record['raw_source_time_ns']==NS and record['raw_receipt_time_ns']==NS+delta
    assert record['receipt_minus_source_ns']==delta and record['sample_index']==1
    assert record['previous_accepted'] is None and record['observation']==obs
    assert 'clock_evidence_manifest_sha256=' in str(exc.value)
    assert validate_clock_evidence(c.root,CONTEXT)


@pytest.mark.parametrize('offset,reason',[(0,'duplicate_source_timestamp'),(-1,'out_of_order_source_timestamp')])
def test_order_rejections_retain_previous_and_accepted_only(store,offset,reason):
    c,out=store;c.accept(evidence(),out)
    with pytest.raises(ClockRejected,match=reason):c.accept(evidence(NS+offset),out)
    assert len(out.getvalue().splitlines())==1
    record=json.loads(c.rejections.read_text())
    assert record['previous_accepted']['sample_time_ns']==NS and record['sample_index']==2


@pytest.mark.parametrize('source',[float(NS),str(NS),True,None])
def test_no_float_string_boolean_or_missing_timestamp_conversion(store,source):
    c,out=store
    with pytest.raises(ClockRejected,match='integer_nanosecond'):c.accept(evidence(source,NS+1),out)
    assert not out.getvalue()


def test_second_or_microsecond_units_not_silently_converted(store):
    c,out=store
    with pytest.raises(ClockRejected,match='exceeds_2s'):c.accept(evidence(NS//1000,NS),out)


def test_receipt_is_after_complete_body_before_json_decode():
    stage=[]
    class Reply:
        def __enter__(self):stage.append('enter');return self
        def read(self):stage.append('body_complete');return b'{"sample_time_ns":1}'
        def __exit__(self,*args):stage.append('close')
    def wall():stage.append('wall');return 10
    def mono():stage.append('mono');return 11
    e=receive_observation('unit',opener=lambda *a,**k:Reply(),wall_ns=wall,monotonic_ns=mono)
    assert stage==['wall','mono','enter','body_complete','wall','mono','close']
    assert base64.b64decode(e['raw_payload_base64'])==b'{"sample_time_ns":1}'


def test_transport_wall_step_is_rejected(store):
    c,out=store;e=evidence();e['request_wall_ns']-=MAX_CLOCK_DELTA_NS+1
    with pytest.raises(ClockRejected,match='transport_wall_clock_discontinuity'):c.accept(e,out)


def test_host_clock_discontinuity_is_durable(store):
    c,out=store;c.check_host(NS,1)
    with pytest.raises(ClockRejected,match='host_sleep_or_clock_discontinuity'):
        c.check_host(NS+MAX_CLOCK_DELTA_NS+2,2)
    assert validate_clock_evidence(c.root,CONTEXT)
    assert not out.getvalue()


def test_container_clock_step_uses_same_source_monotonic_epoch(store):
    c,out=store
    c.accept(evidence(source_clock=dict(wall_ns=NS,monotonic_ns=100)),out)
    e=evidence(NS+10_000_000_000,source_clock=dict(wall_ns=NS+10_000_000_000,monotonic_ns=101))
    with pytest.raises(ClockRejected,match='source_wall_monotonic_discontinuity'):c.accept(e,out)
    assert len(out.getvalue().splitlines())==1


def test_tampered_failure_or_context_is_rejected(store):
    c,out=store
    with pytest.raises(ClockRejected):c.accept(evidence(NS,NS-1),out)
    with pytest.raises(ValueError,match='provenance'):validate_clock_evidence(c.root,{**CONTEXT,'run_id':'OTHER'})
    with c.rejections.open('a') as f:f.write(' ')
    with pytest.raises(ValueError,match='hash'):validate_clock_evidence(c.root,CONTEXT)


def test_failure_digest_bound_into_managed_failed_manifest(store):
    """RunSession.fail persists exception text, binding this evidence digest even on failure."""
    from dynapm.core.run_store import RunSession
    c,out=store
    try:c.accept(evidence(NS,NS-1),out)
    except ClockRejected as error:
        session=object.__new__(RunSession);session.path=c.root
        # Use an actual dataclass manifest shape without running an experiment.
        from dynapm.core.run_store import RunManifest
        session.manifest=RunManifest('UNIT','f'*64,{},'smoke',False,False,'INCOMPLETE','unit',[],str(c.root),[],{})
        session.fail(error)
    manifest=read_json(c.root/'manifest.json')
    assert manifest['status']=='FAILED' and 'clock_evidence_manifest_sha256=' in manifest['error']['message']
    assert not (c.root/'SUCCESS').exists() and (c.root/'FAILED').exists()


def test_runner_declares_clock_outputs_and_uses_single_receipt_path():
    from dynapm.system_validation.calibration_runner import output_specs
    paths={s.path for s in output_specs()}
    assert {'outputs/clock_rejections.jsonl','outputs/clock_observations.jsonl','outputs/clock_evidence_manifest.json'}<=paths
    source=(Path(__file__).parents[1]/'system_validation/calibration_runner.py').read_text()
    assert "observation=receive_observation(app+'/clock-observation')" in source
    assert "sample=clock.accept(observation,raw)" in source
    import ast
    tree=ast.parse(source)
    reception=next(node for node in ast.walk(tree) if isinstance(node,ast.Try) and any(
        isinstance(stmt,ast.Assign) and isinstance(stmt.value,ast.Call)
        and isinstance(stmt.value.func,ast.Name) and stmt.value.func.id=='receive_observation'
        for stmt in node.body))
    assert any(isinstance(child,ast.Call) and isinstance(child.func,ast.Attribute) and child.func.attr=='accept'
        for stmt in reception.orelse for child in ast.walk(stmt))


def test_evidence_io_error_aborts_before_scientific_write(store,monkeypatch):
    from dynapm.system_validation import clock_observations as module
    c,out=store
    def fail(*args):raise OSError('UNIT full disk')
    monkeypatch.setattr(module,'_append',fail)
    with pytest.raises(OSError,match='full disk'):c.accept(evidence(),out)
    assert not out.getvalue() and c.previous is None


def test_invalid_source_clock_fields_preserved(store):
    c,out=store
    with pytest.raises(ClockRejected,match='invalid_source_clock_diagnostics'):
        c.accept(evidence(source_clock={'wall_ns':float(NS),'monotonic_ns':100}),out)
    assert validate_clock_evidence(c.root,CONTEXT) and not out.getvalue()


def test_nonfinite_json_preserves_raw_bytes_not_nan_object(store):
    c,out=store;e=evidence();raw=b'{"sample_time_ns":NaN}'
    e['raw_payload_base64']=base64.b64encode(raw).decode()
    e['raw_payload_sha256']=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ClockRejected,match='invalid_telemetry_json'):c.accept(e,out)
    assert validate_clock_evidence(c.root,CONTEXT) and not out.getvalue()


def rewrite_envelope(e,**changes):
    env=json.loads(base64.b64decode(e['raw_payload_base64']));env.update(changes)
    raw=json.dumps(env).encode()
    return {**e,'raw_payload_base64':base64.b64encode(raw).decode(),'raw_payload_sha256':hashlib.sha256(raw).hexdigest()}


def test_cross_domain_host_behind_source_is_not_causal_failure(store):
    c,out=store;e=evidence()
    e['received_at_ns']=NS-4_309_552;e['request_wall_ns']=e['received_at_ns']-10_000_000
    s=c.accept(e,out)
    assert s['sample_time_ns']>s['received_at_ns']
    assert s['sample_time_ns']<=s['cluster_received_at_ns']
    c.finalize();assert validate_clock_evidence(c.root,CONTEXT)
    d=json.loads(c.observations.read_text())
    assert d['cross_domain_delta_role']=='NON_CAUSAL_DIAGNOSTIC_ONLY'
    assert d['receipt_minus_source_ns']==-4_309_552


def test_source_after_cluster_receipt_rejected_despite_later_host(store):
    c,out=store;e=rewrite_envelope(evidence(),cluster_received_at_ns=NS-1)
    with pytest.raises(ClockRejected,match='source_ahead_of_cluster_receipt'):c.accept(e,out)
    assert not out.getvalue();assert validate_clock_evidence(c.root,CONTEXT)


def test_no_admission_before_physical_host_receipt(store,monkeypatch):
    import dynapm.system_validation.clock_observations as module
    c,out=store;e=evidence();monkeypatch.setattr(module.time,'monotonic_ns',lambda:e['receipt_monotonic_ns']-1)
    with pytest.raises(ClockRejected,match='admission_before_host_receipt'):c.accept(e,out)
    assert not out.getvalue()


def test_success_admission_order_recorded_before_persistence(store):
    c,out=store;s=c.accept(evidence(),out)
    assert s['host_admitted_monotonic_ns']>=1_010_000_000
    assert s['host_admitted_at_ns']>=s['received_at_ns']
    assert json.loads(out.getvalue())==s


def test_different_linux_time_namespace_rejected(store):
    c,out=store;e=rewrite_envelope(evidence(),cluster_clock_domain={**DOMAIN,'time_namespace':'OTHER'})
    with pytest.raises(ClockRejected,match='cluster_clock_domain_mismatch'):c.accept(e,out)
    assert not out.getvalue()


def test_legacy_bare_sample_cannot_satisfy_new_contract(store):
    c,out=store;raw=b'{"sample_time_ns":1700000000000000000}'
    e=evidence();e.update(raw_payload_base64=base64.b64encode(raw).decode(),raw_payload_sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ClockRejected,match='cluster_clock_envelope_required'):c.accept(e,out)
    assert not out.getvalue()


def test_complete_source_response_precedes_cluster_receipt(monkeypatch):
    from dynapm.system_validation import application_instrumented as app
    stages=[]
    class Response:
        def __enter__(self):return self
        def read(self):stages.append('complete_source');return b'raw-source'
        def __exit__(self,*args):pass
    monkeypatch.setattr(app.urllib.request,'urlopen',lambda *a,**k:Response())
    monkeypatch.setattr(app,'clock_domain',lambda:DOMAIN)
    monkeypatch.setattr(app.time,'time_ns',lambda:stages.append('cluster_wall') or 1)
    monkeypatch.setattr(app.time,'monotonic_ns',lambda:stages.append('cluster_mono') or 2)
    e=app.receive_in_cluster('unit')
    assert stages==['cluster_wall','cluster_mono','complete_source','cluster_wall','cluster_mono']
    assert e['cluster_clock_domain']==DOMAIN
    assert base64.b64decode(e['raw_payload_base64'])==b'raw-source'


def test_host_sleep_guard_unchanged_with_cross_domain_skew(store):
    c,out=store;e=evidence();e['received_at_ns']=NS-1;e['request_wall_ns']=NS-10_000_001
    c.accept(e,out);c.check_host(NS,10)
    with pytest.raises(ClockRejected,match='host_sleep_or_clock_discontinuity'):c.check_host(NS+MAX_CLOCK_DELTA_NS+11,20)
    assert len(out.getvalue().splitlines())==1
