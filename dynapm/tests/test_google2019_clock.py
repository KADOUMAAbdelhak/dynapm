import ast
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from dynapm.core.provenance import fingerprint,file_sha256,read_json
from dynapm.core.run_store import write_json
from dynapm.core.temporal import PeriodicGrid,METRICS
from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.data.google2019_clock import (STEP_US as S,CLOCK_VERSION,observation_frame,
    visible_observations,bootstrap_partition,bootstrap_thresholds_at_read,
    trailing_observations,forward_truth_observations,target_labels,refresh_eligible)
from dynapm.experiments.google2019_availability_validation import (timing_counts,
    duplicate_interval_counts,distribution_summary,protocol_v2,validate_protocol_v2,
    validate_clock_audit,SCHEMA)
from dynapm.experiments.google2019_protocol_validation import metadata_for_entity


def canonical(n=2400):
    b=np.arange(n,dtype=np.int64)*S
    return pd.DataFrame(dict(collection_id=np.ones(n,dtype=np.int64),instance_index=np.zeros(n,dtype=np.int64),
        timestamp_us=b,source_start_time_us=b,source_end_time_us=b+S,
        cpu_utilization=np.linspace(.1,2.1,n),memory_utilization=np.linspace(.2,1.5,n)))


def test_storage_labels_unchanged_and_explicit_closing_projection():
    raw=canonical();before=raw.copy();f=observation_frame(raw)
    pd.testing.assert_frame_equal(raw,before)
    assert np.array_equal(f.analysis_slot_close_us,raw.timestamp_us+S)
    assert f.attrs['resource_units']=='request_normalized_ratio'
    assert f.cpu_utilization.max()>1


def test_incomplete_measurement_is_invisible_to_read_state():
    raw=canonical(3);f=observation_frame(raw)
    assert visible_observations(f,S-1).empty
    assert visible_observations(f,S).analysis_slot_close_us.tolist()==[S]
    # Changing the active/future aggregate cannot alter a read of completed state.
    other=raw.copy();other.loc[other.source_end_time_us.gt(S),'cpu_utilization']=1e12
    pd.testing.assert_frame_equal(visible_observations(f,S),visible_observations(observation_frame(other),S))


def test_partial_interval_actual_availability_and_nominal_admission():
    raw=canonical(2);raw.loc[0,'source_start_time_us']=S//5;raw.loc[0,'source_end_time_us']=S*3//5
    f=observation_frame(raw)
    assert visible_observations(f,S*3//5).empty
    assert len(visible_observations(f,S))==1
    assert f.source_start_time_us.iloc[0]==S//5


def test_bootstrap_exact_nominal_split_and_complete_thresholds():
    f=observation_frame(canonical());boot,stream,info=bootstrap_partition(f)
    assert info['bootstrap_cut_us']==721*S and info['stream_anchor_us']==721*S
    assert len(boot)==720 and int(boot.source_end_time_us.max())<=info['stream_anchor_us']
    thresholds=bootstrap_thresholds_at_read(f,info['stream_anchor_us'])
    assert thresholds['cpu_utilization']['p95']==np.percentile(boot.cpu_utilization,95)


def test_bootstrap_thresholds_not_available_before_freeze():
    f=observation_frame(canonical());_,_,i=bootstrap_partition(f)
    with pytest.raises(ValueError,match='not_frozen'):bootstrap_thresholds_at_read(f,i['stream_anchor_us']-1)


def test_future_and_streaming_values_cannot_change_bootstrap_thresholds():
    raw=canonical();f=observation_frame(raw);_,_,i=bootstrap_partition(f)
    original=bootstrap_thresholds_at_read(f,i['stream_anchor_us'])
    raw.loc[raw.timestamp_us.ge(720*S),['cpu_utilization','memory_utilization']]=1e9
    assert bootstrap_thresholds_at_read(observation_frame(raw),i['stream_anchor_us'])==original


def test_bootstrap_cannot_use_incomplete_aggregate_even_if_frame_tampered():
    f=observation_frame(canonical());f.loc[f.index[0],'source_end_time_us']=2000*S
    with pytest.raises(ValueError,match='incomplete_bootstrap'):bootstrap_partition(f)


def test_trailing_exact_288_slots_cover_physical_previous_24h():
    f=observation_frame(canonical());r=1000*S;w=trailing_observations(f,r)
    assert len(w)==288
    assert w.analysis_slot_close_us.iloc[0]==r-287*S and w.analysis_slot_close_us.iloc[-1]==r
    assert w.source_start_time_us.min()==r-288*S and w.source_end_time_us.max()==r
    assert (w.source_end_time_us<=r).all()


def test_forward_exact_288_targets_cover_physical_next_24h():
    f=observation_frame(canonical());r=1000*S
    targets=target_labels(r)
    assert len(targets)==288 and targets[0]==r+S and targets[-1]==r+288*S and r not in targets
    w=forward_truth_observations(f,r,r+288*S)
    assert np.array_equal(w.analysis_slot_close_us,targets)
    assert w.source_start_time_us.min()==r and w.source_end_time_us.max()==r+288*S


def test_verification_cannot_read_future_aggregate_or_complete_early():
    f=observation_frame(canonical());r=1000*S
    with pytest.raises(ValueError,match='not_elapsed'):forward_truth_observations(f,r,r+288*S-1)
    f.loc[f.index[1000+287],'source_end_time_us']=r+288*S+1
    w=forward_truth_observations(f,r,r+288*S)
    assert len(w)==287 and (w.source_end_time_us<=r+288*S).all()


def test_missing_slots_never_imputed_200_slot_density_boundary():
    raw=canonical();r=1000*S
    # Remove 88 targets: exactly 200 remain. The full target horizon still fits.
    raw=raw.drop(index=np.arange(1000,1088));f=observation_frame(raw)
    assert len(forward_truth_observations(f,r,r+288*S))==200
    f=observation_frame(raw.drop(index=1088))
    with pytest.raises(ValueError,match='insufficient_forward'):forward_truth_observations(f,r,r+288*S)


def test_periodic_vs_full_rewrite_content_gate_preserved_after_gap():
    f=observation_frame(canonical().drop(index=999));r=1001*S
    assert len(trailing_observations(f,r))>=200
    assert refresh_eligible(f,r,periodic=False)
    assert not refresh_eligible(f,r,periodic=True)
    assert refresh_eligible(f,1096*S,periodic=True)


def test_pending_periodic_grid_preserved_when_aggregate_unavailable():
    f=observation_frame(canonical().drop(index=799));anchor=721*S
    grid=PeriodicGrid(pd.Timestamp(anchor,unit='us'),6)
    due=anchor+72*S
    assert grid.pop_due(pd.Timestamp(due,unit='us'),eligible=False) is None
    actual=900*S
    assert refresh_eligible(f,actual)
    assert grid.pop_due(pd.Timestamp(actual,unit='us'),eligible=True)==pd.Timestamp(anchor+144*S,unit='us')


def test_missing_observation_at_hourly_read_keeps_nominal_clock():
    raw=canonical().drop(index=732);f=observation_frame(raw)
    boot,stream,i=bootstrap_partition(f)
    data=f[['cpu_utilization','memory_utilization']].rename(columns=dict(zip(['cpu_utilization','memory_utilization'],METRICS)))
    reads,_=compute_data_aware_evaluation_timestamps(data,stream.index)
    t=pd.Timestamp(733*S,unit='us')
    assert t in reads and t not in f.index
    assert (trailing_observations(f,733*S).source_end_time_us<=733*S).all()


@pytest.mark.parametrize('kind',['cross','zero','duplicate','mixed_entities'])
def test_ambiguous_interval_semantics_rejected(kind):
    f=canonical(3)
    if kind=='cross':f.loc[0,'source_end_time_us']=S+1
    if kind=='zero':f.loc[0,'source_end_time_us']=0
    if kind=='duplicate':f=pd.concat([f,f.iloc[[0]]],ignore_index=True)
    if kind=='mixed_entities':f.loc[2,'collection_id']=2
    with pytest.raises(ValueError):observation_frame(f)


def test_raw_start_label_frame_cannot_satisfy_clock_interface():
    with pytest.raises(ValueError,match='clock_frame'):visible_observations(canonical(),1000*S)


def test_timing_statistics_and_duplicate_interval_reconciliation():
    f=canonical(3);f.loc[0,'source_start_time_us']=S//2;f.loc[2,'source_end_time_us']=3*S-1
    c,h=timing_counts(f)
    assert c['exact_300s']==1 and c['partial_lt_300s']==2 and c['end_off_grid']==1
    assert c['ambiguous_rows']==0 and c['overlapping_interval_pairs']==0
    d=pd.DataFrame(dict(collection_id=[1,1],instance_index=[0,0],start_time=[0,0],end_time=[S,S],exclusion_reason=['duplicate_nominal_bucket']*2))
    c=duplicate_interval_counts(canonical(3),d)
    assert c==dict(rejected_duplicate_nominal_rows=2,exact_interval_surplus_rows=2,exact_duplicate_interval_groups=1)


def test_histogram_quantiles_match_expanded_values():
    h={1000000:2,5000000:3,9000000:1};s=distribution_summary(h);a=np.array([1,1,5,5,5,9])
    assert s['p50_seconds']==np.quantile(a,.5) and s['p95_seconds']==np.quantile(a,.95)


def test_global_translation_preserves_eligibility_thresholds_and_targets():
    raw=canonical().drop(index=[500,731,732]);f=observation_frame(raw)
    a=metadata_for_entity('e',1,0,raw.timestamp_us,raw.cpu_utilization,raw.memory_utilization,raw.source_end_time_us,True)
    b=metadata_for_entity('e',1,0,f.analysis_slot_close_us,f.cpu_utilization,f.memory_utilization,f.source_end_time_us,True)
    for key in ['bootstrap_observations','window24_refresh_opportunities','pw_refresh_opportunities','nominal_hourly_origins','globally_verifiable_origins','p3_nominal_ticks','p6_nominal_ticks','p12_nominal_ticks']:
        assert a[key]==b[key]
    assert not b['availability_contract_blocked'] and a['availability_contract_blocked']
    assert b['stream_anchor_us']==a['stream_anchor_us']+S
    for key in a:
        if '_threshold_' in key:assert a[key]==b[key]


def test_new_protocol_fingerprint_and_inherited_questions_unchanged():
    repo=Path(__file__).resolve().parents[2];parent=read_json(repo/'configs/google_clusterdata_2019_replication_protocol_v1.json')
    new=protocol_v2(repo);info=validate_protocol_v2(repo)
    assert info['protocol_fingerprint']!=fingerprint(parent)
    assert new['inherited_from_v3_unchanged']==parent['inherited_from_v3_unchanged']
    assert new['adaptation']==parent['adaptation']
    assert new['clock_contract']['horizon_slots']==288


def test_clock_audit_tampering_rejected(tmp_path):
    (tmp_path/'data').write_bytes(b'checked')
    write_json(tmp_path/'manifest.json',dict(schema_version=SCHEMA,artifacts=[dict(path='data',sha256=file_sha256(tmp_path/'data'))]))
    write_json(tmp_path/'SUCCESS',dict(manifest_sha256=file_sha256(tmp_path/'manifest.json')))
    validate_clock_audit(tmp_path)
    (tmp_path/'data').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='output_hash'):validate_clock_audit(tmp_path)


def test_clock_audit_has_no_policy_or_cloud_execution():
    import dynapm.experiments.google2019_availability_validation as module
    tree=ast.parse(Path(module.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith(('google.cloud','dynapm.methods','dynapm.eval.runner'))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ['query','get_job','create_read_session','read_rows','step']


def test_evaluation_and_one_step_history_exclude_the_active_measurement():
    raw=canonical();f=observation_frame(raw);r=1000*S
    before=trailing_observations(f,r)
    # This interval starts at the read and completes one slot later.
    raw.loc[1000,['cpu_utilization','memory_utilization']]=1e12
    other=observation_frame(raw)
    pd.testing.assert_frame_equal(before,trailing_observations(other,r))
    history=visible_observations(other,r)
    assert r+S not in history.analysis_slot_close_us.to_numpy()
    assert (history.source_end_time_us<=r).all()


def test_completed_metadata_parquet_hash_is_deterministic(tmp_path):
    f=observation_frame(canonical())
    rows=[]
    for _ in range(2):rows.append(metadata_for_entity('e',1,0,f.analysis_slot_close_us,f.cpu_utilization,f.memory_utilization,f.source_end_time_us,True))
    assert rows[0]==rows[1]
    for i,row in enumerate(rows):pd.DataFrame([row]).to_parquet(tmp_path/f'{i}.parquet',compression='zstd',index=False)
    assert file_sha256(tmp_path/'0.parquet')==file_sha256(tmp_path/'1.parquet')
