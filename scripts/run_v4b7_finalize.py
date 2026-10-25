#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import pyarrow.parquet as pq
from dynapm.core.provenance import canonical_json, file_sha256, read_json, utc_now
from dynapm.experiments.google2019_acquisition import GIB, cumulative_executed_bytes, load_byte_ledger
from dynapm.experiments.google2019_streaming import read_checkpoint, write_checkpoint
from dynapm.experiments.google2019_streaming_execute import (
    cell_canonical_dir, measure_path_gib, query_output_path, validate_cell_artifacts,
)
from dynapm.experiments.google2019_v4b7_recover_e import (
    CAP_BYTES, CELL, CONSERVATIVE_MONTHLY_BEFORE_RETRY, EVENTS_BYTES,
    FAILED_E_USAGE_BYTES, RECORD_JSON, USAGE_PARQUET, USAGE_TEMPLATE,
)

print('validate start', flush=True)
v = validate_cell_artifacts('e')
print('validation', v, flush=True)
if not v['passed']:
    raise SystemExit(f'validation_failed:{v["findings"]}')

manifest = read_json(cell_canonical_dir('e') / 'manifest.json')
cp = read_checkpoint('e') or {}
q = (cp.get('queries') or {}).get(f'{CELL}:{USAGE_TEMPLATE}') or {}
job_id = q.get('job_id') or '464ac735-9748-46cc-ad23-f9094b4fcc36'
executed = FAILED_E_USAGE_BYTES
for e in load_byte_ledger().get('executed_entries') or []:
    if e.get('job_id') == job_id:
        executed = int(e['executed_bytes'])
usage_rows = int(pq.ParquetFile(USAGE_PARQUET).metadata.num_rows)
write_checkpoint('e', {
    **cp,
    'stage': 'validated',
    'validation': v,
    'canonical_manifest': manifest,
    'v4b7_usage_download': {
        'job_id': job_id,
        'execution_bytes': executed,
        'usage_parquet_rows': usage_rows,
        'canonical_rows': v['canonical_rows'],
    },
})
google_side = CONSERVATIVE_MONTHLY_BEFORE_RETRY + executed
record = {
    'schema_version': 'google2019-v4b7-recovery-record-v1',
    'gate': 'V4B.7',
    'disposition': 'CELL_E_ACQUIRED',
    'blocker': None,
    'billing_enabled': False,
    'cell_g_queried': False,
    'method_outcomes_computed': False,
    'retry_query': {
        'job_id': job_id,
        'execution_bytes': executed,
        'execution_gib': round(executed / GIB, 6),
        'rows_downloaded': usage_rows,
        'query_sha256': q.get('query_sha256'),
    },
    'google_side_processed_bytes': {
        'events': EVENTS_BYTES,
        'failed_e_usage_v4b6': FAILED_E_USAGE_BYTES,
        'retry_e_usage_v4b7': executed,
        'cumulative': google_side,
        'cumulative_gib': round(google_side / GIB, 6),
        'cap_gib': 900,
        'remaining_cap_gib': round((CAP_BYTES - google_side) / GIB, 6),
    },
    'local_ledger_bytes': cumulative_executed_bytes(),
    'local_ledger_gib': round(cumulative_executed_bytes() / GIB, 6),
    'canonical': {
        'rows': manifest.get('row_count'),
        'entities': manifest.get('entity_count'),
        'eligible_entities': manifest.get('eligible_entity_count'),
        'artifacts': manifest.get('artifacts'),
    },
    'validation': v,
    'disk_gib': {
        'events': round(measure_path_gib(query_output_path('e', '21_events_minimal.sql')), 6),
        'usage': round(measure_path_gib(USAGE_PARQUET), 6),
        'canonical': round(measure_path_gib(cell_canonical_dir('e')), 6),
    },
    'next_gate_note': 'Cell g deferred this month; remaining cap insufficient for full g pair after retry.',
    'recorded_at': utc_now(),
}
RECORD_JSON.write_text(canonical_json(record) + '\n')
Path('logs/v4b7_result.json').write_text(canonical_json(record) + '\n')
print('DONE', file_sha256(RECORD_JSON), flush=True)
print('usage_rows', usage_rows, 'canonical', manifest.get('row_count'), 'eligible', manifest.get('eligible_entity_count'), flush=True)
