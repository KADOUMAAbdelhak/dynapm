"""Synthetic UNIT data only; these tests are NOT a measured-bootstrap demonstration."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dynapm.core.provenance import canonical_json, read_json
from dynapm.system_validation.design import frozen_design
from dynapm.system_validation.trial_preparation import (
    current_draft, draft_spec, measured_bootstrap, MeasuredProfileAdapter,
    isolated_trial_plan, conditional_precision_plan, preparation_report,
)

ROOT=Path(__file__).resolve().parents[2]
START=pd.Timestamp('2026-01-01T00:00Z').value
STEP=300*10**9
END=START+288*STEP


def unit_evidence():
    out=[]
    for slot in range(288):
        b=START+slot*STEP
        samples=[dict(sample_time_ns=b+i*5*10**9,received_at_ns=b+i*5*10**9,
            instance_id='UNIT_FIXTURE_ONLY',cpu_seconds=(slot*300+i*5)*.01,
            memory_working_set_bytes=40*2**20) for i in range(60)]
        out.append(dict(role='MEASURED_CGROUP_SAMPLES',end_ns=b+STEP,samples=samples))
    return out


@pytest.fixture(scope='module')
def design():return frozen_design(ROOT)


@pytest.fixture(scope='module')
def evidence():return unit_evidence()


def test_draft_is_explicitly_unfrozen_and_execution_disabled():
    d=current_draft(ROOT)
    assert d==draft_spec(ROOT) and d['status']=='BLOCKED' and not d['frozen']
    assert not d['comparative_execution_enabled'] and not d['calibration_execution_enabled']
    assert all(x is None for x in d['precision']['targets'].values())
    assert d['operational_contract']['acceptable_slo_harm'] is None


def test_no_parameter_or_workload_tuning(design):
    d=current_draft(ROOT)
    for k in ['consumer','references','workload','scenarios','kubernetes','methods']:assert d[k]==design[k]
    assert d['bootstrap']['duration_seconds']==86400
    assert d['engineering_plan']['measurement_seconds']==172800


def test_unit_bootstrap_fixed_slots_causal_thresholds_and_initialization(evidence,design):
    b=measured_bootstrap(evidence,START,END,END,design)
    assert b.accepted_slots==288 and b.missing_slots==0
    assert b.frame.index[0].value==START+STEP and b.frame.index[-1].value==END
    a=MeasuredProfileAdapter('pw_6h',b,design,planned_streaming_slots=576)
    r=a.snapshot()
    assert r['scope']=='MEASURED_BOOTSTRAP_DEVELOPMENT_NOT_CLAIM'
    assert r['accounting']['n_initialization_events']==1 and r['accounting']['n_refresh_events']==0
    assert r['profile']['dynamic']['predicted_cpu_p95_next_24h']==pytest.approx(1.)
    assert isinstance(canonical_json(r),str)
    assert r['bootstrap_evidence_sha256']==b.evidence_sha256


@pytest.mark.parametrize('bad_end',[END-STEP,END+STEP])
def test_shortened_or_extended_bootstrap_rejected(evidence,design,bad_end):
    with pytest.raises(ValueError,match='fixed_24h'):measured_bootstrap(evidence,START,bad_end,bad_end,design)


def test_bootstrap_unavailable_before_its_end(evidence,design):
    with pytest.raises(ValueError):measured_bootstrap(evidence,START,END,END-1,design)


def test_future_receipt_and_future_slot_never_initialize(evidence,design):
    records=deepcopy(evidence);records[-1]['samples'][0]['received_at_ns']=END+1
    with pytest.raises(ValueError,match='future'):measured_bootstrap(records,START,END,END,design)
    records=deepcopy(evidence);records[-1]['end_ns']=END+STEP
    with pytest.raises(ValueError,match='outside'):measured_bootstrap(records,START,END,END+STEP,design)


def test_warmup_sample_cannot_enter_bootstrap(evidence,design):
    records=deepcopy(evidence);records[0]['samples'][0]['sample_time_ns']=START-1
    with pytest.raises(ValueError,match='outside'):measured_bootstrap(records,START,END,END,design)


def test_identical_duplicate_slot_rejected(evidence,design):
    with pytest.raises(ValueError,match='duplicate'):measured_bootstrap(evidence+[evidence[0]],START,END,END,design)


def test_synthetic_role_cannot_be_loaded_as_measured(evidence,design):
    records=deepcopy(evidence);records[0]['role']='SYNTHETIC_SMOKE_FIXTURE'
    with pytest.raises(ValueError,match='measured_raw'):measured_bootstrap(records,START,END,END,design)


def test_no_filling_and_density_boundary(evidence,design):
    b=measured_bootstrap(evidence[88:],START,END,END,design)
    assert b.accepted_slots==200 and b.missing_slots==88
    assert b.frame.iloc[:88].isna().all().all()
    with pytest.raises(ValueError,match='200_paired'):measured_bootstrap(evidence[89:],START,END,END,design)


def test_last96_complete_gate_preserved(evidence,design):
    records=evidence[:-1]
    with pytest.raises(ValueError,match='last_96'):measured_bootstrap(records,START,END,END,design)


def test_bootstrap_hash_deterministic_and_sample_tampering_detectable(evidence,design):
    a=measured_bootstrap(evidence,START,END,END,design)
    assert measured_bootstrap(list(reversed(evidence)),START,END,END,design).evidence_sha256==a.evidence_sha256
    changed=deepcopy(evidence);changed[0]['samples'][0]['memory_working_set_bytes']+=1
    assert measured_bootstrap(changed,START,END,END,design).evidence_sha256!=a.evidence_sha256


def test_observations_after_initialization_do_not_change_bootstrap(evidence,design):
    b=measured_bootstrap(evidence,START,END,END,design)
    first=MeasuredProfileAdapter('pw_6h',b,design,planned_streaming_slots=576).snapshot()['profile']
    future=deepcopy(evidence[-1])
    future['end_ns']+=STEP
    for sample in future['samples']:
        sample['sample_time_ns']+=STEP;sample['received_at_ns']+=STEP;sample['cpu_seconds']*=1e12
    later_stream=list(evidence)+[future]
    assert later_stream[-1]['end_ns']>b.end_ns
    second=MeasuredProfileAdapter('pw_6h',b,design,planned_streaming_slots=576).snapshot()['profile']
    assert first==second


@pytest.mark.parametrize('bad',['nan','reset','restart'])
def test_corrupted_telemetry_not_a_bootstrap(evidence,design,bad):
    records=deepcopy(evidence)
    if bad=='nan':records[10]['samples'][5]['cpu_seconds']=float('nan')
    if bad=='reset':
        for sample in records[10]['samples']:sample['cpu_seconds']-=30
    if bad=='restart':
        for sample in records[10]['samples']:sample['instance_id']='changed'
    with pytest.raises(ValueError):measured_bootstrap(records,START,END,END,design)


def test_calibration_plan_one_method_no_outcome_inputs():
    s=current_draft(ROOT);p=isolated_trial_plan(s,3,calibration=True)
    assert len(p)==6 and {r['method'] for r in p}=={'pw_6h'}
    assert {r['scenario'] for r in p}=={'stable','periodic'}
    assert all(r['recreate'] and not r['reuse_bootstrap'] for r in p)
    assert p==isolated_trial_plan(s,3,calibration=True)
    assert preparation_report(ROOT)['minimum_serial_hours']==436.5


def test_comparative_plan_balanced_but_not_execution():
    s=current_draft(ROOT);p=isolated_trial_plan(s,5,calibration=False)
    assert len(p)==100 and all(r['minimum_wall_seconds']>=72*3600 for r in p)
    for scenario in s['scenarios']:
        first=[next(r['method'] for r in p if r['scenario']==scenario and r['block']==block) for block in range(5)]
        assert set(first)==set(s['methods'])
    assert not s['comparative_execution_enabled']


def test_precision_is_not_significance_search_and_never_auto_freezes():
    wide=conditional_precision_plan([1.,2.,3.],10.,100)
    tight=conditional_precision_plan([1.,2.,3.],1.,100)
    assert wide['status']=='CONDITIONAL_PLANNING_ESTIMATE_NOT_FROZEN'
    assert tight['required_n'] is None or tight['required_n']>=wide['required_n']
    impossible=conditional_precision_plan([1.,2.,3.],.001,5)
    assert impossible['status']=='INFEASIBLE_WITHIN_CAP' and impossible['required_n'] is None


def test_zero_variance_not_proof_of_precision():
    p=conditional_precision_plan([0.,0.,0.],.01,10)
    assert p['status'].startswith('BLOCKED_ZERO_VARIANCE') and p['required_n'] is None


@pytest.mark.parametrize('values,width,cap',[([1.,2.],.1,10),([1.,2.,float('nan')],.1,10),([1.,2.,3.],0.,10),([1.,2.,3.],.1,2)])
def test_missing_precision_evidence_rejected(values,width,cap):
    with pytest.raises(ValueError):conditional_precision_plan(values,width,cap)


def test_preparation_report_cannot_claim_real_bootstrap_or_variance():
    r=preparation_report(ROOT)
    assert not r['real_bootstrap_demonstrated'] and r['calibration_runs_completed']==0
    assert r['calibration_variance'] is None and r['frozen_repetitions'] is None
