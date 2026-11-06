"""Exact-session Storage Read with atomic, independently checkable Arrow chunks."""
import base64
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile

import pyarrow.parquet as pq

from dynapm.core.provenance import file_sha256, read_json
from dynapm.experiments.google2019_local_canonical import disk_guard
from dynapm.experiments.google2019_storage_read import temp_table_from_job, verify_storage_read_zero_spend
from dynapm.system_validation.v8_campaign import publish_record


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stream_inventory(root, stream):
    """Only atomic chunk directories constitute offsets. Orphan temp dirs do not."""
    chunks = []
    offset = 0
    for path in sorted(root.glob('chunk-*')):
        meta = read_json(path/'receipt.json')
        parquet = path/'rows.parquet'
        if (meta['stream'] != stream or meta['start'] != offset or meta['rows'] <= 0
                or path.name != f'chunk-{offset:020d}'
                or pq.ParquetFile(parquet).metadata.num_rows != meta['rows']
                or file_sha256(parquet) != meta['sha256']):
            raise ValueError('storage_read_chunk_gap_identity_or_hash')
        chunks.append(dict(meta,path=parquet.relative_to(root.parent).as_posix()))
        offset += meta['rows']
    return offset, chunks


def write_chunk(root, stream, offset, table, *, guard=disk_guard):
    guard(root, max(table.nbytes, 256*2**20))
    with tempfile.TemporaryDirectory(prefix='.uncommitted-',dir=root) as temp:
        stage = Path(temp)/'chunk'
        stage.mkdir()
        path = stage/'rows.parquet'
        pq.write_table(table,path,compression='zstd')
        with path.open('rb') as handle:
            os.fsync(handle.fileno())
        path.chmod(0o444)
        publish_record(stage/'receipt.json',dict(stream=stream,start=offset,rows=table.num_rows,sha256=file_sha256(path)))
        os.rename(stage,root/f'chunk-{offset:020d}')
        sync_directory(root)


def download_stream(root, stream, read, *, guard=disk_guard):
    root.mkdir(exist_ok=True)
    offset,chunks = stream_inventory(root,stream)
    done = root/'COMPLETE'
    if not done.exists():
        for table in read(stream,offset):
            if table.num_rows:
                write_chunk(root,stream,offset,table,guard=guard)
                offset += table.num_rows
        publish_record(done,dict(stream=stream,rows=offset))
        offset,chunks = stream_inventory(root,stream)
    if read_json(done) != dict(stream=stream,rows=offset):
        raise ValueError('storage_read_stream_completion_mismatch')
    return chunks


def completed_download(root):
    """Recover fully committed local results even after the server table expires."""
    checkpoint = root/'session.json'
    if not checkpoint.is_file():
        return None
    record = read_json(checkpoint)
    streams = record['streams']
    if not streams or len(set(streams))!=len(streams):
        raise ValueError('storage_read_session_streams_changed')
    if not all((root/f'stream-{i:03d}'/'COMPLETE').is_file() for i in range(len(streams))):
        return None
    chunks = []
    for index,stream in enumerate(streams):
        folder = root/f'stream-{index:03d}'
        offset,parts = stream_inventory(folder,stream)
        if read_json(folder/'COMPLETE')!=dict(stream=stream,rows=offset):
            raise ValueError('storage_read_stream_completion_mismatch')
        chunks.extend(parts)
    rows = sum(c['rows'] for c in chunks)
    if rows!=record['result']['expected_rows']:
        raise ValueError('storage_read_result_row_mismatch')
    return dict(result=record['result'],session_sha256=file_sha256(checkpoint),rows=rows,chunks=chunks)


def download_result(job, table, root, project, *, credentials, max_streams=8):
    """Reuse the serialized ReadSession. Expiration blocks without rescanning."""
    import pyarrow as pa
    from google.cloud import bigquery_storage_v1 as storage

    root.mkdir(exist_ok=True)
    temp = temp_table_from_job(job)
    if not temp.is_anonymous_temp or temp.project!=project:
        raise ValueError('job_requires_owned_anonymous_result')
    verify_storage_read_zero_spend(project,temp)
    if table.created is None or table.etag is None or table.num_rows is None:
        raise ValueError('missing_anonymous_result_identity')
    identity = dict(job_id=job.job_id,table=temp.resource_name,created=table.created.isoformat(),
                    etag=table.etag,expected_rows=int(table.num_rows))
    client = storage.BigQueryReadClient(credentials=credentials)
    checkpoint = root/'session.json'
    if checkpoint.exists():
        record = read_json(checkpoint)
        if record['result'] != identity:
            raise ValueError('storage_read_result_identity_changed')
        session = storage.types.ReadSession.deserialize(base64.b64decode(record['session'],validate=True))
    else:
        if any(root.iterdir()):
            raise ValueError('storage_read_session_missing')
        requested = storage.types.ReadSession(table=temp.resource_name,data_format=storage.types.DataFormat.ARROW)
        session = client.create_read_session(parent=f'projects/{project}',read_session=requested,
                                             max_stream_count=max_streams)
        if not session.streams:
            raise ValueError('storage_read_empty_session')
        record = dict(result=identity,session=base64.b64encode(storage.types.ReadSession.serialize(session)).decode(),
                      streams=[s.name for s in session.streams])
        publish_record(checkpoint,record)
    streams = [s.name for s in session.streams]
    if (session.table != temp.resource_name or streams != record['streams'] or not streams
            or len(set(streams)) != len(streams)):
        raise ValueError('storage_read_session_streams_changed')

    def read(name,offset):
        if session.expire_time is not None and session.expire_time<=datetime.now(timezone.utc):
            raise ValueError('storage_read_original_session_expired_no_rescan')
        for page in client.read_rows(name,offset=offset).rows(session).pages:
            arrow = page.to_arrow()
            yield arrow if isinstance(arrow,pa.Table) else pa.Table.from_batches([arrow])

    for index,stream in enumerate(streams):
        download_stream(root/f'stream-{index:03d}',stream,read)
    return completed_download(root)
