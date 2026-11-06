"""Compact, regenerable rejection evidence for the sealed cell-g raw acquisition."""
import hashlib

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from dynapm.core.provenance import file_sha256, read_json

SCHEMA = 'google2019-logical-rejection-audit-v1'
INTERVAL_FIELDS = {'rejected_duplicate_nominal_rows','exact_interval_surplus_rows',
                   'exact_duplicate_interval_groups'}


def logical_hash(table):
    """Hash typed, ordered rows in fixed-size Arrow IPC batches without pandas metadata."""
    table = table.replace_schema_metadata(None).combine_chunks()
    digest = hashlib.sha256(table.schema.serialize().to_pybytes())
    for batch in table.to_batches(max_chunksize=65536):
        columns = []
        for array in batch.columns:
            digest.update(pc.is_valid(array).to_numpy(zero_copy_only=False).astype('uint8').tobytes())
            if not pa.types.is_null(array.type):
                if pa.types.is_string(array.type) or pa.types.is_large_string(array.type):
                    neutral = ''
                elif pa.types.is_boolean(array.type):
                    neutral = False
                else:
                    neutral = 0
                array = pc.fill_null(array,pa.scalar(neutral,type=array.type))
            columns.append(array)
        encoded = pa.RecordBatch.from_arrays(columns,schema=table.schema).serialize()
        digest.update(len(encoded).to_bytes(8,'big'))
        digest.update(memoryview(encoded))
    return digest.hexdigest()


def rejection_record(accepted, rejected, *, partition, counts, conflicts, entities, binding, prior=None):
    from dynapm.experiments.google2019_availability_validation import duplicate_interval_counts

    if isinstance(rejected,pa.Table):
        table,frame = rejected,rejected.to_pandas()
    else:
        table,frame = pa.Table.from_pandas(rejected,preserve_index=False),rejected
    reasons = {str(k):int(v) for k,v in frame.exclusion_reason.value_counts().items()}
    if len(frame)!=counts['rejected_rows'] or reasons!=counts['exclusion_reasons']:
        raise ValueError('rejected_count_or_reason_mismatch')
    canonical = pq.read_table(accepted,columns=['collection_id','instance_index','timestamp_us',
        'source_start_time_us','source_end_time_us']).to_pandas()
    if len(canonical)!=counts['canonical_rows']:
        raise ValueError('accepted_rejection_binding_row_mismatch')
    return dict(schema=SCHEMA,cell='g',partition=partition,binding=binding,
        accepted_sha256=file_sha256(accepted),accepted_rows=len(canonical),
        rejected_rows=len(frame),exclusion_reasons=reasons,
        logical_rejected_sha256=logical_hash(table),logical_schema=str(table.schema.remove_metadata()),
        interval_counts=duplicate_interval_counts(canonical,frame),conflict_groups=conflicts,
        canonical_entities=entities,prior_parquet_sha256=prior)


def validate_record(path, accepted, counts, partition):
    record = read_json(path)
    intervals = record['interval_counts']
    duplicate = counts['exclusion_reasons'].get('duplicate_nominal_bucket',0)
    if (record['schema']!=SCHEMA or record['cell']!='g' or record['partition']!=partition
            or record['accepted_sha256']!=file_sha256(accepted)
            or record['accepted_rows']!=counts['canonical_rows']
            or record['rejected_rows']!=counts['rejected_rows']
            or record['exclusion_reasons']!=counts['exclusion_reasons']
            or set(intervals)!=INTERVAL_FIELDS or intervals['rejected_duplicate_nominal_rows']!=duplicate
            or any(type(n) is not int or not 0<=n<=duplicate for n in intervals.values())):
        raise ValueError('compact_rejection_audit_mismatch')
    return record
