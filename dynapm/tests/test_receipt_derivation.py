"""Offline synthetic regression evidence, never physical acquisition/reset proof."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from dynapm.core.provenance import canonical_json, fingerprint, file_sha256, read_json
from dynapm.core.run_store import write_json
from dynapm.system_validation.adapter import aggregate_bucket, receipt_bucket_samples
from dynapm.system_validation.receipt_derivation import (
    STEP, DAY, VERSION, bucket_end, rebucket, reconstruct, create_generation,
    load_generation, create_derived_artifact, _inventory)
from dynapm.system_validation.shared_bootstrap import load_artifact, freeze_blocks
from dynapm.tests.test_shared_bootstrap import acquisition
from dynapm.tests.test_provenance import inputs
from dynapm.tests.test_system_trial_preparation import START, END, unit_evidence


@pytest.mark.parametrize('delta,expected',[
    (-1,None),(0,STEP),(STEP-1,STEP),(STEP,2*STEP),
    (STEP+12_000_000,2*STEP),(DAY-1,DAY),(DAY,None),(DAY+1,None)])
def test_exact_half_open_integer_boundaries(delta,expected):
    assert bucket_end(START+delta,START,END)==(START+expected if expected is not None else None)


def test_partition_determinism_no_duplicates_loss_and_no_clock_rewrites():
    times=[START-1,START,START+STEP-1,START+STEP,START+STEP+4_000_000,END-1,END,END+1]
    ss=[dict(sample_index=i,received_at_ns=t,sample_time_ns=t+123,host_admitted_at_ns=t+999) for i,t in enumerate(times)]
    before=deepcopy(ss);first=rebucket(ss,START,END)
    assert ss==before and first==rebucket(ss,START,END)
    flattened=[s for e in first for s in e['samples']]
    assert flattened==ss[1:6] and len({s['sample_index'] for s in flattened})==5
    assert first[0]['samples']==ss[1:3] and first[1]['samples']==ss[3:5]
    with pytest.raises(ValueError,match='duplicate'):rebucket(ss+[ss[1]],START,END)


def test_collector_persists_only_the_same_samples_that_are_aggregated():
    ss=unit_evidence()[0]['samples'];boundary=deepcopy(ss[-1]);boundary['received_at_ns']=START+STEP
    selected=receipt_bucket_samples(ss+[boundary],START,START+STEP)
    assert selected==ss and receipt_bucket_samples([boundary],START+STEP,START+2*STEP)==[boundary]


def test_half_open_still_requires_original_causal_and_admission_semantics():
    from dynapm.system_validation.estimation_design import frozen_spec
    d=frozen_spec(Path(__file__).parents[2]);ss=unit_evidence()[0]['samples']
    ss[0]['received_at_ns']=START;ss[0]['host_admitted_at_ns']=START
    assert aggregate_bucket(ss,START,START+STEP,d)['real_samples']==60
    ss[0]['host_admitted_at_ns']=START-1
    with pytest.raises(ValueError,match='admission'):aggregate_bucket(ss,START,START+STEP,d)
    ss[0]['host_admitted_at_ns']=START;ss[0]['cluster_received_at_ns']=ss[0]['sample_time_ns']-1
    with pytest.raises(ValueError,match='admission'):aggregate_bucket(ss,START,START+STEP,d)


def populate_failed_parent(parent,d):
    """Explicit UNIT_TEST_ONLY, internally consistent immutable clock-envelope bytes."""
    out=parent/'outputs';m=read_json(parent/'manifest.json');m.update(status='FAILED',error={'message':'future_or_outside_bootstrap_measurement'})
    write_json(parent/'manifest.json',m)
    context=dict(run_id=m['run_id'],experiment_fingerprint=m['experiment_fingerprint'],source_commit=m['experiment']['source']['commit'])
    domain=dict(boot_id='UNIT_LINUX_BOOT',hostname='application',time_namespace='UNIT_TIME_NS')
    samples=[];diags=[]
    for i,s in enumerate(s for e in unit_evidence() for s in e['samples']):
        s.update(cpu_limit_cores=1.,memory_limit_bytes=512*2**20,oom_kills=0)
        s['source_clock'].update(domain=domain,wall_ns=s['sample_time_ns'],pid=1)
        source=deepcopy(s)
        for k in ['received_at_ns','host_admitted_at_ns','cluster_received_at_ns','clock_schema']:source.pop(k)
        env=dict(schema_version='cluster-clock-envelope-v1',raw_payload_base64=base64.b64encode(canonical_json(source).encode()).decode(),
            raw_payload_sha256=fingerprint(source),cluster_received_at_ns=s['sample_time_ns'],
            cluster_receipt_monotonic_ns=s['source_clock']['monotonic_ns'],
            cluster_request_monotonic_ns=s['source_clock']['monotonic_ns'],cluster_request_wall_ns=s['sample_time_ns'],cluster_clock_domain=domain)
        # fingerprint uses canonical JSON; exactly these bytes are retained.
        raw=canonical_json(env).encode()
        e=dict(raw_payload_base64=base64.b64encode(raw).decode(),raw_payload_sha256=fingerprint(env),
            received_at_ns=s['received_at_ns'],receipt_monotonic_ns=s['source_clock']['monotonic_ns'],
            request_monotonic_ns=s['source_clock']['monotonic_ns'],request_wall_ns=s['received_at_ns'])
        s.update(sample_index=i+1,host_receipt_monotonic_ns=e['receipt_monotonic_ns'],host_admitted_monotonic_ns=e['receipt_monotonic_ns'],
            cluster_clock_domain=domain,cluster_receipt_monotonic_ns=env['cluster_receipt_monotonic_ns'],source_raw_payload_sha256=env['raw_payload_sha256'])
        samples.append(s);diags.append(dict(schema_version='system-clock-observation-v2',context=context,observation=e,
            sample_index=i+1,host_admitted_at_ns=s['host_admitted_at_ns'],host_admitted_monotonic_ns=s['host_admitted_monotonic_ns']))
    original=[dict(role='MEASURED_CGROUP_SAMPLES',end_ns=START+(i+1)*STEP,samples=samples[i*60:(i+1)*60+1]) for i in range(288)]
    (out/'bootstrap_samples.jsonl').write_text(''.join(canonical_json(x)+'\n' for x in original))
    for name,records in [('telemetry',samples),('clock_observations',diags),('clock_rejections',[]),('profiles',[]),('controller_commands',[])]:
        (out/f'{name}.jsonl').write_text(''.join(canonical_json(x)+'\n' for x in records))
    body=dict(schema_version='system-clock-observation-v2',context=context,observations_sha256=file_sha256(out/'clock_observations.jsonl'),rejections_sha256=file_sha256(out/'clock_rejections.jsonl'))
    write_json(out/'clock_evidence_manifest.json',{**body,'manifest_sha256':fingerprint(body)})
    host=[]
    for wall in range(START,END+1,30*10**9):
        host.append(dict(context=context,wall_ns=wall,monotonic_ns=wall-START,checkpoint_gap_ns=30*10**9 if host else 0,
            wall_minus_monotonic_elapsed_ns=0,assertion_pid=12,power=dict(ac_power=True,lid_open=True,boot_epoch_seconds=123,
                own_assertion_lines=['PreventSystemSleep PreventUserIdleSystemSleep'],power_settings_sha256='UNIT_POLICY')))
    (out/'host_continuity.jsonl').write_text(''.join(canonical_json(x)+'\n' for x in host));sha=file_sha256(out/'host_continuity.jsonl')
    write_json(out/'power_guard.json',dict(context=context,status='FAILED',failure=None,ended_at=m['ended_at'],release_confirmed=True,
        continuity_log_sha256=sha,assertion_pid=12,assertion_types=['PreventSystemSleep','PreventUserIdleSystemSleep']))
    write_json(out/'host_continuity_summary.json',dict(context=context,failure=None,log_sha256=sha,checkpoints=len(host)))
    write_json(out/'host_continuity_failure.json',dict(status='NO_FAILURE'))
    write_json(out/'controller_status.json',dict(counters={'recommendations':0},pending=None,complete=False))
    write_json(out/'generator_status.json',dict(complete=True,offered=1))
    (out/'requests.jsonl').write_text(canonical_json(dict(request_id=0,error=None,success=True,http_status=200))+'\n')
    pod=dict(kind='POD_OBSERVATION',pod_uid='UNIT_SOURCE_POD',status=dict(containerStatuses=[dict(restartCount=0,lastState={},resources=dict(limits=dict(cpu='1',memory='512Mi'),requests=dict(cpu='1',memory='512Mi')))]))
    (out/'decisions.jsonl').write_text(canonical_json(pod)+'\n')


def test_derived_generation_parent_immutability_independent_load_and_tamper(acquisition):
    parent,d,tmp=acquisition;populate_failed_parent(parent,d);before=_inventory(parent)
    entries,report,b=reconstruct(parent,d)
    assert b.accepted_slots==288 and not report['failed_buckets']
    with pytest.raises(ValueError,match='unit_fixture'):
        create_generation(parent,tmp/'production',d,expected_parent_inventory=before,implementation={})
    g=create_generation(parent,tmp/'derived',d,expected_parent_inventory=before,implementation={'version':VERSION},allow_unit_fixture=True)
    assert _inventory(parent)==before and read_json(parent/'manifest.json')['status']=='FAILED'
    assert load_generation(g,g.name,d)[1].frame.equals(b.frame)
    a=create_derived_artifact(g,tmp/'artifacts',g.name,d);assert load_artifact(a,a.name,d)[1].frame.equals(b.frame)
    with pytest.raises(ValueError,match='unit_artifact'):freeze_blocks([(a,a.name)],d,common_stable_prehistory=True)
    with pytest.raises(ValueError,match='hash'):load_artifact(a,'0'*64,d)
    for target in ['corrected.jsonl','parent/outputs/telemetry.jsonl','parent/outputs/clock_observations.jsonl','manifest.json']:
        copy=tmp/('tamper-'+target.replace('/','-'));shutil.copytree(g,copy)
        with (copy/target).open('a') as f:f.write(' ')
        with pytest.raises(ValueError):load_generation(copy,g.name,d)
    with (a/'generation/corrected.jsonl').open('a') as f:f.write(' ')
    with pytest.raises(ValueError):load_artifact(a,a.name,d)
    assert _inventory(parent)==before

    incomplete=tmp/'incomplete-parent';shutil.copytree(parent,incomplete)
    out=incomplete/'outputs'
    for name in ('telemetry','clock_observations'):
        lines=(out/f'{name}.jsonl').read_text().splitlines()[20:]
        (out/f'{name}.jsonl').write_text('\n'.join(lines)+'\n')
    cm=read_json(out/'clock_evidence_manifest.json')
    cm['observations_sha256']=file_sha256(out/'clock_observations.jsonl')
    cm['manifest_sha256']=fingerprint({k:v for k,v in cm.items() if k!='manifest_sha256'})
    write_json(out/'clock_evidence_manifest.json',cm)
    _,rr,bb=reconstruct(incomplete,d)
    assert bb is None and len(rr['failed_buckets'])==1 and rr['failed_buckets'][0]['end_ns']==START+STEP
    blocked=create_generation(incomplete,tmp/'blocked',d,expected_parent_inventory=_inventory(incomplete),implementation={},allow_unit_fixture=True)
    with pytest.raises(ValueError,match='incomplete_derived'):create_derived_artifact(blocked,tmp/'blocked-artifact',blocked.name,d)
