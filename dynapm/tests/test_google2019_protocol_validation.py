import ast
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from dynapm.core.provenance import fingerprint, file_sha256
from dynapm.core.temporal import METRICS
from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.core.discretization import compute_thresholds, classify_value
from dynapm.core.forecasting import forecast_class_from_window, forecast_p95_from_window
from dynapm.core.ground_truth import derive_ground_truth_at_t
from dynapm.experiments.google2019_protocol_validation import (
    metadata_for_entity, selection_hash, select_cohort, freeze_selection_rule,
    cost_estimate, require_replication_ready, design_spec, validate_audit,
    PROTOCOL, STEP, SCHEMA)
from dynapm.core.run_store import write_json


def inputs(n=2400):
    ts=np.arange(n,dtype=np.int64)*STEP
    cpu=np.linspace(.1,2.1,n);mem=np.linspace(.2,1.2,n)
    return ts,cpu,mem,ts+STEP


def audit(n=2400,drop=()):
    ts,c,m,end=inputs(n);keep=~np.isin(np.arange(n),drop)
    return metadata_for_entity('e',1,0,ts[keep],c[keep],m[keep],end[keep],True)


def test_exact_grid_and_frozen_nominal_bootstrap_not_observed_rows():
    r=audit(drop=np.arange(200,400))
    assert r['bootstrap_cut_us']==720*STEP
    assert r['bootstrap_observations']==520
    assert r['bootstrap_coverage']==520/720
    assert r['rows_available_after_nominal_time']==2200
    assert r['max_availability_delay_seconds']==300


@pytest.mark.parametrize('bad',[np.array([0,STEP+1]),np.array([0,0]),np.array([STEP,0])])
def test_invalid_grid_rejected(bad):
    with pytest.raises(ValueError,match='timeline'):
        metadata_for_entity('e',1,0,bad,np.ones(2),np.ones(2),bad+STEP,True)


def test_metadata_matches_canonical_window_and_hourly_truth_density():
    ts,c,m,end=inputs();keep=np.ones(len(ts),bool);keep[[730,744,1000,1001]]=False
    r=metadata_for_entity('e',1,0,ts[keep],c[keep],m[keep],end[keep],True)
    index=pd.to_datetime(ts[keep],unit='us');frame=pd.DataFrame({METRICS[0]:c[keep],METRICS[1]:m[keep]},index=index)
    cut=pd.Timestamp(r['bootstrap_cut_us'],unit='us');stream=frame.index[frame.index>=cut]
    verified,info=compute_data_aware_evaluation_timestamps(frame,stream)
    assert r['globally_verifiable_origins']==len(verified)
    assert r['nominal_hourly_origins']==info['n_candidates']
    assert r['evaluation_origins_without_observation']==int((~verified.isin(frame.index)).sum())


def test_200_slot_gate_and_96_history_are_separate():
    r=audit(drop=[1000]);s=audit()
    assert r['window24_refresh_opportunities']==s['window24_refresh_opportunities']-1
    assert r['pw_refresh_opportunities']==s['pw_refresh_opportunities']-96
    # Sparse invalid slots are not interpolated and no observation is synthesized.
    assert r['observations']==s['observations']-1 and r['missing_slots']==1


def test_forward_horizon_elapsed_and_origin_excluded():
    # Removing last origin's observation leaves its future density unchanged.
    r=audit();last_eval=((2400-289-720)//12)*12+720
    q=audit(drop=[last_eval])
    assert q['globally_verifiable_origins']==r['globally_verifiable_origins']
    assert q['evaluation_origins_without_observation']==1


def test_bootstrap_thresholds_future_invariance_and_no_clipping():
    ts,c,m,end=inputs();r=metadata_for_entity('e',1,0,ts,c,m,end,True)
    cut=r['bootstrap_cut_us'];c[ts>=cut]=1e12;m[ts>=cut]=1e9
    q=metadata_for_entity('e',1,0,ts,c,m,end,True)
    assert r==q
    expected=np.percentile(inputs()[1][:720],95)
    assert q['cpu_threshold_p95']==expected


def test_threshold_class_mean_and_profile_p95_contract_synthetic_only():
    ts,c,m,end=inputs();f=pd.DataFrame({METRICS[0]:c,METRICS[1]:m},index=pd.to_datetime(ts,unit='us'))
    th=compute_thresholds(f.iloc[:720],METRICS[0]);mh=compute_thresholds(f.iloc[:720],METRICS[1])
    assert th['p20']==np.percentile(c[:720],20)
    w=c[721:1009]
    gt=derive_ground_truth_at_t(f,f.index[720],cpu_thresholds=th,mem_thresholds=mh)
    assert gt['cpu_class']==classify_value(w.mean(),th)==forecast_class_from_window(w,th)
    assert gt['p95_cpu_next_24h']==forecast_p95_from_window(w)==np.quantile(w,.95)
    assert forecast_p95_from_window([1.,2.,3.])==2.9  # values >1 retained


def test_acquisition_and_protocol_exclusion_codes_without_outcomes():
    r=audit(n=300)
    assert 'insufficient_bootstrap_history' in r['protocol_exclusion_reasons']
    assert 'insufficient_globally_verifiable_evaluation_origins' in r['protocol_exclusion_reasons']
    assert not r['nominal_protocol_eligible']


def test_selection_invariant_to_values_outcomes_order_and_cell_stratified():
    rows=[dict(cell=cell,collection_id=i,instance_index=0,nominal_protocol_eligible=i!=99,
        cpu_threshold_p95=float(i),method_accuracy=0.,volatility=float(i)) for cell in ['e','g'] for i in range(100)]
    table=pd.DataFrame(rows);rule=dict(mode='lowest_sha256_per_cell',maximum_entities_per_cell=20)
    a=select_cohort(table,rule)
    table['cpu_threshold_p95']=1e9;table['method_accuracy']=1.;table['volatility']=-1
    b=select_cohort(table.sample(frac=1,random_state=4),rule)
    pd.testing.assert_frame_equal(a,b)
    assert a.groupby('cell').size().to_dict()=={'e':20,'g':20}
    assert selection_hash('e',7,0)!=selection_hash('g',7,0)


def test_resource_rule_keeps_all_when_feasible_and_bounded_when_not():
    r=audit(n=8000)
    tiny=pd.DataFrame([r]);small=freeze_selection_rule(tiny)
    assert small['mode']=='all_protocol_eligible'
    big=pd.DataFrame([dict(r,collection_id=i) for i in range(30000)])
    rule=freeze_selection_rule(big)
    assert rule['mode']=='lowest_sha256_per_cell' and rule['maximum_entities_per_cell']==1000
    assert len(select_cohort(big,rule))==1000
    assert cost_estimate(big)['method_entity_runs']==150000


def test_no_v5_until_g_and_availability_validated():
    record=dict(disposition='PROTOCOL_REQUIRES_CORRECTION',cohort_rule_sha256='same')
    with pytest.raises(ValueError,match='cell_g'):require_replication_ready({'e':record})
    with pytest.raises(ValueError,match='protocol_requires'):require_replication_ready({'e':record,'g':record})
    record=dict(disposition='PROTOCOL_READY',cohort_rule_sha256='same')
    require_replication_ready({'e':record,'g':record})


def test_audit_hashes_deterministic_and_tampering_rejected(tmp_path):
    a=pd.DataFrame([audit()]);b=pd.DataFrame([audit()])
    for name,f in [('a',a),('b',b)]:f.to_parquet(tmp_path/f'{name}.parquet',index=False,compression='zstd')
    assert file_sha256(tmp_path/'a.parquet')==file_sha256(tmp_path/'b.parquet')
    assert fingerprint(design_spec())==fingerprint(design_spec())
    write_json(tmp_path/'manifest.json',dict(schema_version=SCHEMA,artifacts=[dict(path='a.parquet',sha256=file_sha256(tmp_path/'a.parquet'))]))
    write_json(tmp_path/'SUCCESS',dict(manifest_sha256=file_sha256(tmp_path/'manifest.json')))
    validate_audit(tmp_path)
    (tmp_path/'a.parquet').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='output_hash'):validate_audit(tmp_path)


def test_frozen_protocol_and_no_policy_cloud_or_outcome_entry_points():
    from dynapm.experiments.replication_corpus import frozen_hashes
    import dynapm.experiments.google2019_protocol_validation as module
    assert frozen_hashes()['protocol_fingerprint']==PROTOCOL
    tree=ast.parse(Path(module.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith(('google.cloud','dynapm.methods','dynapm.eval.runner','dynapm.experiments.confirmatory_execution'))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ['query','get_job','create_read_session','read_rows','step']


def test_bootstrap_availability_cut_and_stream_anchor_are_distinct():
    ts,c,m,end=inputs();end[719]=ts[720]+STEP
    r=metadata_for_entity('e',1,0,ts,c,m,end,True)
    assert r['bootstrap_rows_ending_after_cut']==1
    assert r['bootstrap_rows_ending_after_stream_anchor']==1
    keep=np.arange(len(ts))!=720
    q=metadata_for_entity('e',1,0,ts[keep],c[keep],m[keep],end[keep],True)
    assert q['bootstrap_rows_ending_after_cut']==1
    assert q['bootstrap_rows_ending_after_stream_anchor']==0
