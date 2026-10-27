import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from dynapm.core.provenance import fingerprint,file_sha256
from dynapm.core.run_store import write_json
from dynapm.experiments.google2019_requests import prepare_request_history,KEYS
from dynapm.experiments.google2019_local_canonical import (canonical_partition,source_hashes,
    require_corrected_generation,SCHEMA,NORMALIZATION,process_partition)
from dynapm.experiments.google2019_streaming_execute import build_request_index,causal_request_lookup


def events():
    return pd.DataFrame(dict(collection_id=[1]*6,instance_index=[0]*6,time=[0,0,10,10,20,30],
        request_cpu=[2.,2.,3.,4.,5.,0.],request_memory=[4.,4.,6.,8.,10.,0.]))


def usage():
    return pd.DataFrame(dict(collection_id=[1]*4,instance_index=[0]*4,collection_type=[1]*4,
        start_time=[5,15,25,300000025],end_time=[10,19,29,300000030],
        average_cpu=[1.,2.,3.,4.],average_memory=[2.,4.,6.,8.]))


def test_identical_duplicates_collapse_and_conflicts_excluded():
    clean,bad,latest,audit=prepare_request_history(events())
    assert clean.time.tolist()==[0,20]
    assert bad.time.tolist()==[10] and bad.distinct_request_pairs.tolist()==[2]
    assert audit['identical_duplicate_copies']==1 and audit['invalid_request_event_rows']==1
    assert audit['ambiguous_groups']==1 and not clean.duplicated(KEYS).any()


def test_production_index_falls_back_to_earlier_positive_unambiguous_request(tmp_path):
    p=tmp_path/'events.parquet';events().to_parquet(p,index=False)
    index=build_request_index(p)
    assert causal_request_lookup(index,1,0,15)==(2.,4.,0)
    assert causal_request_lookup(index,1,0,10)==(2.,4.,0)
    assert causal_request_lookup(index,1,0,25)==(5.,10.,20)
    assert causal_request_lookup(index,1,0,-1) is None


def test_canonical_fallback_not_row_deletion_and_no_ambiguous_request():
    history,bad,latest,audit=prepare_request_history(events())
    canonical,entities,rejected,counts=canonical_partition(usage(),history,latest)
    # Duplicate bucket max-end rule keeps t=25; fallback t=15 itself is retained
    # when considered alone, rather than deleting every conflict-affected row.
    one,_,_,c=canonical_partition(usage().iloc[[1]],history,latest)
    assert len(one)==1 and one.request_event_time_us.iloc[0]==0
    assert one.used_earlier_request.iloc[0] and one.cpu_utilization.iloc[0]==1
    assert not canonical.request_event_time_us.isin(bad.time).any()
    assert counts['requires_ambiguity_fallback_raw']==1 and counts['successful_fallback_raw']==1
    assert len(usage())==len(canonical)+len(rejected)


def test_ambiguous_without_earlier_history_is_invalid():
    e=events().iloc[[2,3]];history,bad,latest,a=prepare_request_history(e)
    canonical,entities,rejected,c=canonical_partition(usage().iloc[[1]],history,latest)
    assert canonical.empty and c['no_earlier_valid_request_raw']==1
    assert rejected.exclusion_reason.tolist()==['missing_unambiguous_positive_request']


def test_future_requests_do_not_affect_current_content():
    e=events();history,bad,latest,a=prepare_request_history(e)
    original=canonical_partition(usage().iloc[[0]],history,latest)[0]
    e.loc[e.time.gt(5),'request_cpu']=100000.;e.loc[e.time.gt(5),'request_memory']=200000.
    h,b,l,a=prepare_request_history(e)
    pd.testing.assert_frame_equal(original,canonical_partition(usage().iloc[[0]],h,l)[0])


def test_optimized_hash_is_exact_frozen_json():
    h,b,l,a=prepare_request_history(events());from dynapm.experiments.google2019_local_canonical import join_partition
    f=join_partition(usage(),h,l)
    for row,sha in zip(f.to_dict('records'),source_hashes(f)):
        raw={k:row[k] for k in ['collection_id','instance_index','collection_type','start_time','end_time','average_cpu','average_memory','request_cpu','request_event_time','request_memory']}
        raw['request_event_time']=int(raw['request_event_time'])
        raw.update(cell='e',usage_source_table='google.com:google-cluster-data.clusterdata_2019_e.instance_usage',
            request_source_table='google.com:google-cluster-data.clusterdata_2019_e.instance_events')
        assert fingerprint(raw)==sha


def test_deterministic_regeneration_content_and_file_hashes(tmp_path):
    first=prepare_request_history(events());second=prepare_request_history(events().sample(frac=1,random_state=7))
    a=canonical_partition(usage(),first[0],first[2])[0]
    b=canonical_partition(usage().sample(frac=1,random_state=9),second[0],second[2])[0]
    pd.testing.assert_frame_equal(a,b)
    for name,frame in [('a',a),('b',b)]:frame.to_parquet(tmp_path/f'{name}.parquet',compression='zstd',row_group_size=100000,index=False)
    assert file_sha256(tmp_path/'a.parquet')==file_sha256(tmp_path/'b.parquet')


def test_same_max_end_duplicate_tie_uses_frozen_source_hash():
    h,b,l,a=prepare_request_history(events());raw=pd.concat([usage().iloc[[2]],usage().iloc[[2]].assign(average_cpu=7.)],ignore_index=True)
    canonical,_,rejected,c=canonical_partition(raw,h,l)
    from dynapm.experiments.google2019_local_canonical import join_partition
    expected=min(source_hashes(join_partition(raw,h,l)))
    assert len(canonical)==1 and canonical.source_row_sha256.iloc[0]==expected
    assert c['exclusion_reasons']['duplicate_nominal_bucket']==1


def test_old_generation_refused_and_tampering_rejected(tmp_path):
    old=tmp_path/'old';old.mkdir();write_json(old/'manifest.json',{'schema_version':'google2019-streaming-canonical-v1'})
    with pytest.raises(ValueError,match='old_or_unsupported'):require_corrected_generation(old)
    new=tmp_path/'new';new.mkdir();(new/'data').write_bytes(b'checked')
    write_json(new/'manifest.json',dict(schema_version=SCHEMA,normalization_version=NORMALIZATION,status='VERIFIED',
        artifacts=[dict(path='data',sha256=file_sha256(new/'data'))]))
    write_json(new/'SUCCESS',dict(manifest_sha256=file_sha256(new/'manifest.json')))
    assert require_corrected_generation(new)['status']=='VERIFIED'
    (new/'data').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='hash_mismatch'):require_corrected_generation(new)


def test_exhaustive_local_validator_with_bounded_fixture(tmp_path):
    from dynapm.experiments.google2019_local_canonical import validate_local
    h,b,l,a=prepare_request_history(events())
    c,e,r,d=canonical_partition(usage(),h,l)
    (tmp_path/'canonical_usage').mkdir()
    c.to_parquet(tmp_path/'canonical_usage/part_000.parquet',index=False)
    e.to_parquet(tmp_path/'entity_manifest.parquet',index=False)
    class Status:
        def update(self,**kwargs):pass
    result=validate_local(tmp_path,h,b,l,Status())
    assert result['passed'] and result['canonical_rows_verified']==len(c)
    assert result['ambiguous_requests_selected']==0 and result['every_row_latest_request_verified']


def test_randomized_frozen_json_hash_equivalence():
    from dynapm.experiments.google2019_local_canonical import join_partition
    h,b,l,a=prepare_request_history(events());f=join_partition(pd.concat([usage()]*25,ignore_index=True),h,l)
    rng=np.random.default_rng(5)
    f['average_cpu']=rng.normal(size=len(f));f['average_memory']=rng.uniform(size=len(f))*1e-9
    f.loc[0,'average_cpu']=-0.0
    for row,sha in zip(f.to_dict('records'),source_hashes(f)):
        raw={k:row[k] for k in ['collection_id','instance_index','collection_type','start_time','end_time','average_cpu','average_memory','request_cpu','request_event_time','request_memory']}
        raw['request_event_time']=int(raw['request_event_time'])
        raw.update(cell='e',usage_source_table='google.com:google-cluster-data.clusterdata_2019_e.instance_usage',request_source_table='google.com:google-cluster-data.clusterdata_2019_e.instance_events')
        assert fingerprint(raw)==sha


def test_producer_is_local_only():
    import ast
    import dynapm.experiments.google2019_local_canonical as module
    source=Path(module.__file__).read_text();tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):assert not (node.module or '').startswith(('google.cloud','google.auth'))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ['query','get_job','create_read_session','read_rows']
