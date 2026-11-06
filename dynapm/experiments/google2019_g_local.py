"""Local phases for a sealed Google acquisition, reusing the cell-e algorithms."""
from collections import Counter

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.experiments.google2019_availability_validation import SCHEMA as AUDIT_SCHEMA, audit_partition
from dynapm.experiments.google2019_local_canonical import (NORMALIZATION, PARTITIONS, SCHEMA, disk_guard,
    partition_usage, process_partition, require_corrected_generation, validate_local)
from dynapm.experiments.google2019_protocol_validation import select_cohort
from dynapm.experiments.google2019_requests import KEYS, PAIR, REQUEST_RULE, prepare_request_history
from dynapm.system_validation.v8_campaign import publish_record


class Progress:
    def update(self, **values):
        if 'stage' in values:
            print(values, flush=True)


def inventory(root):
    artifacts = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('linked_artifact')
        if p.is_file():
            artifacts.append(dict(path=p.relative_to(root).as_posix(),size_bytes=p.stat().st_size,
                                  sha256=file_sha256(p)))
    return artifacts


def canonicalize(out, cell, raw, files, source_commit):
    events = pa.concat_tables([pq.read_table(p,columns=KEYS+PAIR) for p in files['events']]).to_pandas()
    if len(events)!=raw['events']['rows']:
        raise ValueError('request_event_rows_do_not_reconcile')
    clean,bad,latest,request_counts = prepare_request_history(events)
    del events
    for name,table in [('request_history',clean),('ambiguous_requests',bad),('positive_event_times',latest)]:
        table.to_parquet(out/f'{name}.parquet',compression='zstd',index=False)
    (out/'partition_diagnostics').mkdir()
    progress = Progress()
    n = partition_usage(files['usage'],out/'work',PARTITIONS,progress)
    if n!=raw['usage']['rows']:
        raise ValueError('usage_partition_rows_do_not_reconcile')
    total = Counter()
    reasons = Counter()
    for p in sorted((out/'work').glob('raw_*.parquet')):
        counts = process_partition((p,out/'request_history.parquet',out/'positive_event_times.parquet',
                                    out,int(p.stem.split('_')[1])),cell=cell)
        reasons.update(counts.pop('exclusion_reasons'))
        counts.pop('partition')
        total.update(counts)
    (out/'work').rmdir()
    if n!=total['canonical_rows']+total['rejected_rows'] or sum(reasons.values())!=total['rejected_rows']:
        raise ValueError('canonical_and_rejected_rows_do_not_reconcile')
    entities = pd.concat([pq.read_table(p).to_pandas() for p in sorted((out/'entities').glob('*.parquet'))],
                         ignore_index=True)
    if entities.empty or entities.duplicated(['cell','collection_id','instance_index']).any():
        raise ValueError('canonical_entities_empty_or_partition_split')
    entities = entities.sort_values(['cell','collection_id','instance_index']).reset_index(drop=True)
    entities.to_parquet(out/'entity_manifest.parquet',compression='zstd',index=False)
    validation = validate_local(out,clean,bad,latest,progress,cell=cell)
    if validation['canonical_rows_verified']!=total['canonical_rows']:
        raise ValueError('canonical_validation_row_mismatch')
    artifacts = inventory(out)
    for entry in artifacts:
        if entry['path'].endswith('.parquet'):
            entry['rows'] = pq.ParquetFile(out/entry['path']).metadata.num_rows
    parts = [a for a in artifacts if a['path'].startswith('canonical_usage/')]
    manifest = dict(schema_version=SCHEMA,normalization_version=NORMALIZATION,cell=cell,status='VERIFIED',
        source_commit=source_commit,raw_lineage_sha256=fingerprint(raw),request_rule=REQUEST_RULE,partitions=PARTITIONS,
        output_row_count=total['canonical_rows'],entity_count=len(entities),
        acquisition_eligible_entities=int(entities.eligible.sum()),canonical_dataset_sha256=fingerprint(parts),
        entity_manifest_sha256=file_sha256(out/'entity_manifest.parquet'),artifacts=artifacts,validation=validation,
        diagnostics=dict(total,exclusion_reasons=dict(reasons),request_history=request_counts))
    publish_record(out/'manifest.json',manifest)
    publish_record(out/'SUCCESS',dict(manifest_sha256=file_sha256(out/'manifest.json')))
    return manifest


def availability(out, cell, generation, protocol):
    parent = require_corrected_generation(generation)
    entities = pq.read_table(generation/'entity_manifest.parquet').to_pandas().set_index(['collection_id','instance_index'])
    rows = []
    timing = Counter()
    max_gap = 0
    for p in sorted((generation/'canonical_usage').glob('*.parquet')):
        metadata,counts,_ = audit_partition(cell,generation,p,entities)
        max_gap = max(max_gap,counts.pop('maximum_interval_gap_us'))
        timing.update(counts)
        rows.extend(metadata)
    table = pd.DataFrame(rows).sort_values(['cell','collection_id','instance_index']).reset_index(drop=True)
    if (timing['rows']!=parent['output_row_count'] or len(table)!=parent['entity_count']
            or table.duplicated(['cell','collection_id','instance_index']).any()
            or any(timing[k] for k in ('ambiguous_rows','overlapping_interval_pairs','canonical_duplicate_rows'))
            or table.availability_contract_blocked.any() or table.bootstrap_rows_ending_after_cut.any()
            or table.bootstrap_rows_ending_after_stream_anchor.any()):
        raise ValueError('availability_contract_blocked')
    table.to_parquet(out/'entity_eligibility.parquet',compression='zstd',index=False)
    summary = dict(disposition='AVAILABILITY_CONTRACT_READY',timing=dict(timing,maximum_interval_gap_us=max_gap),
        canonical_entities=len(table),eligible_entities=int(table.nominal_protocol_eligible.sum()),
        incomplete_bootstrap_rows=0,incomplete_rows_at_stream_anchor=0,policy_outcomes_computed=False)
    manifest = dict(schema_version=AUDIT_SCHEMA,cell=cell,**protocol,summary=summary,
        canonical_sha256=parent['canonical_dataset_sha256'],
        canonical_parent_manifest_sha256=file_sha256(generation/'manifest.json'),artifacts=inventory(out))
    publish_record(out/'manifest.json',manifest)
    publish_record(out/'SUCCESS',dict(manifest_sha256=file_sha256(out/'manifest.json')))
    return manifest


def freeze_cohort(out, cell, canonical_sha, eligibility, protocol, rule):
    table = pq.read_table(eligibility).to_pandas()
    if not table.cell.eq(cell).all() or rule['maximum_entities_per_cell']!=1000:
        raise ValueError('held_out_cohort_scope_mismatch')
    selected = select_cohort(table,rule).to_dict('records')
    if not selected or len(selected)!=min(1000,int(table.nominal_protocol_eligible.sum())):
        raise ValueError('empty_or_unreconciled_held_out_cohort')
    result = dict(schema_version='google2019-availability-cohort-v2',role='HELD_OUT_STAGE_B',cell=cell,
        canonical_sha256=canonical_sha,protocol_fingerprint=protocol['protocol_fingerprint'],
        clock_contract_sha256=protocol['clock_contract_sha256'],cohort_rule_sha256=fingerprint(rule),
        entities=selected)
    publish_record(out/'g_cohort.json',result)
    return dict(cohort_size=len(selected),member_records_sha256=fingerprint(selected))
