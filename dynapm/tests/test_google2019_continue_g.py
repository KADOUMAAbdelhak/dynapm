import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dynapm.core.provenance import file_sha256
from dynapm.core.run_store import write_json
from dynapm.scripts import task43_google2019_continue_g as continuation


def example(path, pid=186):
    for name,rows in [('canonical_usage',2),('rejected_rows',1)]:
        (path/name).mkdir()
        pq.write_table(pa.table({'v':list(range(rows))}),path/name/f'part_{pid:03d}.parquet')
    (path/'partition_diagnostics').mkdir()
    write_json(path/'partition_diagnostics'/f'{pid:03d}.json',
        dict(partition=pid,canonical_rows=2,rejected_rows=1,raw_usage_rows=3,exclusion_reasons={'fixture':1}))
    return {'passed':True}


def test_resume_preserves_interrupted_attempt_and_reuses_sealed_shard(tmp_path):
    inputs = {'partition':186,'source':'fixture'}
    def interrupt(path):
        (path/'retained').write_text('partial bytes')
        raise OSError('interrupted')
    with pytest.raises(OSError,match='interrupted'):
        continuation.publish_shard(tmp_path,inputs,interrupt)
    failed = tmp_path/'attempts/186-001/retained'
    before = file_sha256(failed)
    seal = continuation.publish_shard(tmp_path,inputs,example)
    assert seal['counts']['raw_usage_rows']==3
    assert file_sha256(failed)==before
    def forbidden(_):
        pytest.fail('recomputed a sealed shard')
    assert continuation.publish_shard(tmp_path,inputs,forbidden)==seal
    with pytest.raises(ValueError,match='shard_seal_changed'):
        continuation.publish_shard(tmp_path,dict(inputs,source='other'),forbidden)
    assert continuation.contiguous([186],186)==187
    with pytest.raises(ValueError,match='noncontiguous'):
        continuation.contiguous([186,188],186)


def test_promotes_verified_seal_after_interrupt_before_rename(tmp_path,monkeypatch):
    inputs = {'partition':186}
    rename = continuation.os.rename
    def fail(*args):
        raise OSError('before rename')
    monkeypatch.setattr(continuation.os,'rename',fail)
    with pytest.raises(OSError,match='before rename'):
        continuation.publish_shard(tmp_path,inputs,example)
    assert (tmp_path/'attempts/186-001/SHARD.json').is_file()
    monkeypatch.setattr(continuation.os,'rename',rename)
    def forbidden(_):
        pytest.fail('recomputed an atomically sealed attempt')
    assert continuation.publish_shard(tmp_path,inputs,forbidden)['validation']=={'passed':True}


def test_storage_refusal_does_not_open_partial_state(tmp_path,monkeypatch):
    root = tmp_path/continuation.ROOT
    root.mkdir(parents=True)
    monkeypatch.setattr(continuation.shutil,'disk_usage',lambda _:type('D',(),{'free':39*2**30})())
    with pytest.raises(ValueError,match='requires_40_GiB_free'):
        continuation.run(tmp_path,execute=True)
    assert list(root.iterdir())==[]


def test_legacy_phase_refuses_to_discard_verified_shards(tmp_path):
    from dynapm.scripts.task42_google2019_cell_g import phase
    original = tmp_path/'.canonical.partial/partition_diagnostics'
    original.mkdir(parents=True)
    record = original/'185.json'
    record.write_text('preserved')
    with pytest.raises(ValueError,match='use_offline_continuation'):
        phase(tmp_path,'canonical',{},lambda _:pytest.fail('legacy replay'))
    assert record.read_text()=='preserved'


def test_real_shard_processing_does_not_consume_original_scratch(tmp_path):
    from dynapm.tests.test_google2019_local_canonical import events,usage
    source = tmp_path/'old'
    (source/'work/events').mkdir(parents=True)
    (source/'work/usage').mkdir()
    pid = 1000003%256
    event_file = source/'work/events'/f'raw_{pid:03d}.parquet'
    usage_file = source/'work/usage'/f'raw_{pid:03d}.parquet'
    events().to_parquet(event_file,index=False)
    usage().to_parquet(usage_file,index=False)
    expected = [file_sha256(f) for f in (event_file,usage_file)]
    work = tmp_path/'out'
    work.mkdir()
    result = continuation.publish_shard(work,{'partition':pid},lambda out:continuation.create_shard(out,source,pid))
    assert result['validation']['ambiguous_requests_selected']==0
    assert result['counts']['raw_usage_rows']==len(usage())
    assert [file_sha256(f) for f in (event_file,usage_file)]==expected
