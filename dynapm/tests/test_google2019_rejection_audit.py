import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dynapm.core.provenance import file_sha256
from dynapm.experiments.google2019_availability_validation import audit_partition
from dynapm.experiments.google2019_local_canonical import write_bounded_parquet
from dynapm.experiments.google2019_rejection_audit import logical_hash, rejection_record, validate_record
from dynapm.scripts import task43_google2019_continue_g as resume
from dynapm.scripts import task44_google2019_compact_g as compact
from dynapm.tests.test_google2019_local_canonical import events, usage


def test_logical_hash_ignores_batch_and_null_storage_but_detects_content():
    schema = pa.schema([('id',pa.int64()),('text',pa.large_string())])
    table = pa.Table.from_pylist([{'id':1,'text':None},{'id':2,'text':'ab'}],schema=schema)
    rechunked = pa.concat_tables([table.slice(0,1),table.slice(1)])
    assert logical_hash(table)==logical_hash(rechunked)
    assert logical_hash(table)!=logical_hash(table.take(pa.array([1,0])))
    assert logical_hash(table)!=logical_hash(table.set_column(1,'text',pa.array(['','ab'],type=pa.large_string())))


def test_full_and_compact_real_shard_have_same_canonical_and_clock(tmp_path):
    old = tmp_path/'source'
    (old/'work/events').mkdir(parents=True)
    (old/'work/usage').mkdir()
    pid = 1000003%256
    part = f'part_{pid:03d}.parquet'
    events().to_parquet(old/'work/events'/f'raw_{pid:03d}.parquet',index=False)
    usage().to_parquet(old/'work/usage'/f'raw_{pid:03d}.parquet',index=False)
    source_digests = {p:file_sha256(p) for p in old.rglob('*.parquet')}
    full,small = tmp_path/'full',tmp_path/'compact'
    full.mkdir();small.mkdir()
    resume.create_shard(full,old,pid)
    resume.create_shard(small,old,pid,compact_binding={'fixture':True})
    for p,h in source_digests.items():
        assert file_sha256(p)==h
    accepted = 'canonical_usage/'+part
    assert pq.read_table(full/accepted).equals(pq.read_table(small/accepted),check_metadata=True)
    full_counts = resume.reconcile_shard(full,pid)
    assert resume.reconcile_shard(small,pid)==full_counts
    record = validate_record(small/'rejection_audit'/f'{pid:03d}.json',small/accepted,full_counts,pid)
    assert record['logical_rejected_sha256']==logical_hash(pq.read_table(full/'rejected_rows'/part))
    ent = pq.read_table(full/'entities'/part).to_pandas().set_index(['collection_id','instance_index'])
    assert audit_partition('g',full,full/accepted,ent)==audit_partition('g',small,small/accepted,ent)


def test_retirement_requires_matching_replacement_and_is_idempotent(tmp_path):
    old,work = tmp_path/'old',tmp_path/'work'
    (old/'rejected_rows').mkdir(parents=True)
    (work/'historical-audits').mkdir(parents=True)
    source = old/'rejected_rows/part_000.parquet'
    source.write_bytes(b'preserved input')
    entry = dict(path='rejected_rows/part_000.parquet',size_bytes=source.stat().st_size,sha256=file_sha256(source))
    binding = dict(raw_receipts={'events':'a','usage':'b'})
    replacement = work/'historical-audits/000.json'
    replacement.write_text('replacement')
    result = compact.retire(old,work,entry,binding)
    assert not source.exists()
    assert compact.retire(old,work,entry,binding)==result
    assert compact.retired_paths(old,work,{entry['path']:entry},binding)=={entry['path']}
    replacement.write_text('tampered')
    with pytest.raises(ValueError,match='retirement_evidence'):
        compact.retired_paths(old,work,{entry['path']:entry},binding)
    with pytest.raises(ValueError,match='not_authorized'):
        compact.replacement_path(work,'canonical_usage/part_000.parquet')
