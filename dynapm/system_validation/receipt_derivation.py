"""Outcome-blind receipt-time repair of an immutable, failed acquisition.

This offline path never changes a parent status or acquires telemetry. A trusted
external inventory is required because a FAILED run has no SUCCESS hash chain.
"""
import base64
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import shutil
import time

import pandas as pd

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.core.run_store import write_json
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.clock_observations import validate_clock_evidence, MAX_CLOCK_DELTA_NS
from dynapm.system_validation.trial_preparation import measured_bootstrap

VERSION = 'host-receipt-half-open-v1'
GENERATION = 'receipt-rebucket-generation-v1'
ARTIFACT = 'shared-measured-bootstrap-derived-v1'
STEP = 300 * 10**9
DAY = 288 * STEP
CODE = ('dynapm/system_validation/receipt_derivation.py', 'dynapm/system_validation/adapter.py',
        'dynapm/system_validation/trial_preparation.py', 'dynapm/system_validation/shared_bootstrap.py',
        'dynapm/system_validation/calibration_runner.py')


def bucket_end(receipt_ns, start_ns, end_ns):
    """Exact integer [start,end) membership; terminal receipts are excluded."""
    if any(type(v) is not int for v in (receipt_ns, start_ns, end_ns)):
        raise ValueError('integer_receipt_clocks_required')
    if start_ns % STEP or end_ns-start_ns != DAY:
        raise ValueError('fixed_24h_interval_required')
    if not start_ns <= receipt_ns < end_ns:
        return None
    return start_ns + ((receipt_ns-start_ns)//STEP+1)*STEP


def rebucket(samples, start, end):
    """Preserve complete accepted samples and input order; reject duplicate IDs."""
    result = {q: [] for q in range(start+STEP, end+1, STEP)}
    seen = set()
    for sample in samples:
        index = sample['sample_index']
        if index in seen:
            raise ValueError('duplicate_accepted_sample_index')
        seen.add(index)
        q = bucket_end(sample['received_at_ns'], start, end)
        if q is not None:
            result[q].append(deepcopy(sample))
    return [dict(role='MEASURED_CGROUP_SAMPLES', end_ns=q, samples=ss) for q, ss in result.items()]


def _rows(path):
    with Path(path).open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _inventory(root):
    root = Path(root)
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('derived_symlinks_forbidden')
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('derived_symlinks_forbidden')
    return {p.relative_to(root).as_posix(): file_sha256(p) for p in sorted(root.rglob('*')) if p.is_file()}


def _verify_inventory(root, expected):
    if not expected or _inventory(root) != expected:
        raise ValueError('derived_input_inventory_mismatch')


def _raw_checks(parent):
    m = read_json(parent/'manifest.json'); plan = read_json(parent/'outputs/plan.json')
    if (m['status'] != 'FAILED' or m['purpose'] != 'pilot' or m.get('allow_dirty') or
            m['experiment']['source']['dirty'] or
            m.get('error', {}).get('message') != 'future_or_outside_bootstrap_measurement' or
            not plan.get('bootstrap_only') or
            m['experiment']['config']['preprocessing']['mode'] != 'MEASURED_BOOTSTRAP_ONLY_V1'):
        raise ValueError('specific_failed_bootstrap_parent_required')
    for name, sha in m['metadata_sha256'].items():
        if file_sha256(parent/name) != sha:
            raise ValueError('parent_metadata_hash_mismatch')
    context = dict(run_id=m['run_id'], experiment_fingerprint=m['experiment_fingerprint'],
                   source_commit=m['experiment']['source']['commit'])
    validate_clock_evidence(parent, context)
    # This repair is intentionally narrower than a general rejection recovery.
    if list(_rows(parent/'outputs/clock_rejections.jsonl')):
        raise ValueError('rejected_observations_forbidden_in_receipt_repair')
    samples = list(_rows(parent/'outputs/telemetry.jsonl'))
    observations = list(_rows(parent/'outputs/clock_observations.jsonl'))
    if not samples or len(samples) != len(observations):
        raise ValueError('accepted_clock_telemetry_count_mismatch')
    previous = None
    for s, d in zip(samples, observations):
        e = d['observation']; env = json.loads(base64.b64decode(e['raw_payload_base64'], validate=True))
        source = json.loads(base64.b64decode(env['raw_payload_base64'], validate=True))
        # Reconstruct the admitted record from the exact original envelope/source.
        source.update(cluster_received_at_ns=env['cluster_received_at_ns'],
            received_at_ns=e['received_at_ns'], host_admitted_at_ns=d['host_admitted_at_ns'],
            host_admitted_monotonic_ns=d['host_admitted_monotonic_ns'],
            host_receipt_monotonic_ns=e['receipt_monotonic_ns'], sample_index=d['sample_index'],
            clock_schema=d['schema_version'], cluster_clock_domain=env['cluster_clock_domain'],
            cluster_receipt_monotonic_ns=env['cluster_receipt_monotonic_ns'],
            source_raw_payload_sha256=env['raw_payload_sha256'])
        if source != s or d['sample_index'] != s['sample_index']:
            raise ValueError('accepted_source_envelope_record_mismatch')
        delta = s['cluster_received_at_ns']-s['sample_time_ns']
        sc = s['source_clock']; domain = s['cluster_clock_domain']
        if (not 0 <= delta <= MAX_CLOCK_DELTA_NS or sc['domain'] != domain or
                not s['sample_time_ns'] <= sc['wall_ns'] <= s['cluster_received_at_ns'] or
                sc['monotonic_ns'] > s['cluster_receipt_monotonic_ns'] or
                not e['request_monotonic_ns'] <= e['receipt_monotonic_ns'] <= s['host_admitted_monotonic_ns'] or
                s['host_admitted_at_ns'] < s['received_at_ns']):
            raise ValueError('derived_causal_admission_violation')
        if previous and (s['sample_index'] <= previous['sample_index'] or
                s['received_at_ns'] <= previous['received_at_ns'] or
                sc['monotonic_ns'] <= previous['source_clock']['monotonic_ns'] or
                domain != previous['cluster_clock_domain']):
            raise ValueError('derived_observation_order_violation')
        elapsed=e['receipt_monotonic_ns']-e['request_monotonic_ns']
        cluster_elapsed=env['cluster_receipt_monotonic_ns']-env['cluster_request_monotonic_ns']
        if (not 0<=elapsed<=MAX_CLOCK_DELTA_NS or
                abs((e['received_at_ns']-e['request_wall_ns'])-elapsed)>MAX_CLOCK_DELTA_NS or
                not 0<=cluster_elapsed<=MAX_CLOCK_DELTA_NS or
                abs((env['cluster_received_at_ns']-env['cluster_request_wall_ns'])-cluster_elapsed)>MAX_CLOCK_DELTA_NS):
            raise ValueError('derived_transport_clock_violation')
        previous = s
    return m, plan, samples


def _host_checks(parent, m, start, end):
    guard = read_json(parent/'outputs/power_guard.json')
    summary = read_json(parent/'outputs/host_continuity_summary.json')
    failure = read_json(parent/'outputs/host_continuity_failure.json')
    hs = list(_rows(parent/'outputs/host_continuity.jsonl'))
    context = dict(run_id=m['run_id'], experiment_fingerprint=m['experiment_fingerprint'],
                   source_commit=m['experiment']['source']['commit'])
    if (not hs or guard['context'] != context or summary['context'] != context or
            failure.get('status') != 'NO_FAILURE' or guard.get('failure') or summary.get('failure') or
            not guard.get('ended_at') or not guard.get('release_confirmed') or
            summary['log_sha256'] != file_sha256(parent/'outputs/host_continuity.jsonl') or
            guard['continuity_log_sha256'] != summary['log_sha256'] or len(hs) != summary['checkpoints']):
        raise ValueError('derived_host_provenance_invalid')
    first = hs[0]; previous = None; powers = set(); boots = set(); deficits = 0
    for h in hs:
        p = h['power']; lines = ' '.join(p['own_assertion_lines'])
        gap = 0 if previous is None else h['monotonic_ns']-previous['monotonic_ns']
        drift = (h['wall_ns']-first['wall_ns'])-(h['monotonic_ns']-first['monotonic_ns'])
        if (h['context'] != context or not p['ac_power'] or not p['lid_open'] or
                h['assertion_pid'] != guard['assertion_pid'] or gap < 0 or gap > 30*10**9 or
                abs(drift) > MAX_CLOCK_DELTA_NS or not all(t in lines for t in guard['assertion_types'])):
            raise ValueError('derived_host_continuity_invalid')
        powers.add(p['power_settings_sha256']); boots.add(p['boot_epoch_seconds'])
        deficits += bool(p.get('external_power_deficit_observed'))
        previous = h
    if len(powers) != 1 or len(boots) != 1 or first['wall_ns'] > start or hs[-1]['wall_ns'] < end:
        raise ValueError('derived_host_interval_or_policy_invalid')
    return dict(checkpoints=len(hs), authorized_deficit_checkpoints=deficits,
        maximum_drift_ns=max(abs(h['wall_minus_monotonic_elapsed_ns']) for h in hs),
        maximum_gap_ns=max(h['checkpoint_gap_ns'] for h in hs), release_confirmed=True)


def reconstruct(parent, design):
    """Validate original raw evidence without invoking a collector or changing it."""
    parent = Path(parent); m, plan, samples = _raw_checks(parent)
    start = int(plan['bootstrap_start_seconds'])*10**9; end = int(plan['measurement_start_seconds'])*10**9
    available = pd.Timestamp(m['ended_at']).value
    if pd.Timestamp(m['started_at']).value > start or available < end:
        raise ValueError('parent_does_not_cover_interval')
    # Correct only membership; frozen physical resources/coverage and age stay fixed.
    for key in ('references', 'telemetry'):
        old = deepcopy(plan['design'][key]); new = deepcopy(design[key])
        if key == 'telemetry':
            old.pop('fence'); new.pop('fence')
        if old != new:
            raise ValueError('derivation_changed_frozen_requirements')
    host = _host_checks(parent, m, start, end)
    if len({s['instance_id'] for s in samples}) != 1 or any(s['oom_kills'] for s in samples):
        raise ValueError('derived_restart_or_oom')
    if any(s['cpu_limit_cores'] != 1 or s['memory_limit_bytes'] != 512*2**20 for s in samples):
        raise ValueError('derived_fixed_resources_required')
    for name in ('profiles', 'controller_commands'):
        if list(_rows(parent/f'outputs/{name}.jsonl')):
            raise ValueError('derived_policy_outcomes_forbidden')
    pods = list(_rows(parent/'outputs/decisions.jsonl'))
    if not pods or any(x.get('kind') != 'POD_OBSERVATION' or x.get('pod_uid') != plan['bootstrap_source_pod_uid'] for x in pods):
        raise ValueError('derived_pod_identity_or_decisions_invalid')
    for x in pods:
        for container in x['status']['containerStatuses']:
            if (container['restartCount'] != 0 or container.get('lastState') or
                    container.get('resources') != dict(limits=dict(cpu='1', memory='512Mi'), requests=dict(cpu='1', memory='512Mi'))):
                raise ValueError('derived_pod_restart_or_resource_change')
    ctrl = read_json(parent/'outputs/controller_status.json')
    if ctrl['pending'] is not None or any(ctrl['counters'].values()):
        raise ValueError('derived_controller_state_invalid')
    generator = read_json(parent/'outputs/generator_status.json')
    requests = list(_rows(parent/'outputs/requests.jsonl'))
    if not generator['complete'] or sorted(x['request_id'] for x in requests) != list(range(generator['offered'])):
        raise ValueError('derived_requests_not_reconciled')
    if any(x['error'] or not x['success'] or x['http_status'] != 200 for x in requests):
        raise ValueError('derived_application_request_errors')
    entries = rebucket(samples, start, end); coverage = []; failed = []
    for entry in entries:
        q = entry['end_ns']; ss = entry['samples']
        row = dict(end_ns=q, samples=len(ss), host_receipt_span_seconds=
            (ss[-1]['received_at_ns']-ss[0]['received_at_ns'])/1e9 if ss else 0)
        try:
            row['aggregate'] = aggregate_bucket(ss, q-STEP, q, design)
        except ValueError as exc:
            row['error'] = str(exc); failed.append(row)
        coverage.append(row)
    old = list(_rows(parent/'outputs/bootstrap_samples.jsonl'))
    old_slots = {}
    for entry in old:
        for sample in entry['samples']:
            old_slots.setdefault(sample['sample_index'], set()).add(entry['end_ns'])
    assigned = {s['sample_index']: e['end_ns'] for e in entries for s in e['samples']}
    report = dict(parent_status='FAILED', raw_samples=len(samples), retained_samples=len(assigned),
        excluded_before_start=sum(s['received_at_ns'] < start for s in samples),
        excluded_at_or_after_end=sum(s['received_at_ns'] >= end for s in samples),
        reassigned_observations=sum(any(q != assigned[i] for q in qs) for i, qs in old_slots.items() if i in assigned),
        original_duplicate_occurrences=sum(len(qs)-1 for qs in old_slots.values()),
        coverage=coverage, failed_buckets=failed, host=host, clock_rejections=0,
        unique_request_ids=len(requests), controller_complete=ctrl['complete'],
        controller_note='cleanup interrupted normal completion; zero counters and no pending resize',
        source_pod_uid=plan['bootstrap_source_pod_uid'],
        source_pod_observations=len(pods), source_pod_note='chronological POD_OBSERVATION records plus final runner UID check before exception',
        claim_eligibility='NOT_AUTOMATICALLY_CLAIM_ELIGIBLE', current_boot_endurance_qualified=False)
    if failed:
        return entries, report, None
    boot = measured_bootstrap(entries, start, end, available, design)
    if boot.accepted_slots != 288 or boot.missing_slots:
        raise ValueError('all_288_corrected_buckets_required')
    report.update(accepted_slots=288, missing_slots=0, evidence_sha256=boot.evidence_sha256)
    return entries, report, boot


def implementation_binding(repo):
    from dynapm.core.provenance import SourceProvenance
    source=SourceProvenance.capture(repo)
    if source.dirty:
        raise ValueError('clean_derivation_source_required')
    return dict(source_commit=source.commit, version=VERSION, code_sha256={p:file_sha256(Path(repo)/p) for p in CODE})


def create_generation(parent, store, design, *, expected_parent_inventory, implementation, allow_unit_fixture=False):
    """Write a new content-addressed generation; the failed parent is read-only."""
    parent = Path(parent); _verify_inventory(parent, expected_parent_inventory)
    unit=read_json(parent/'manifest.json')['experiment']['config'].get('analysis',{}).get('unit_test_fixture') is True
    if unit and not allow_unit_fixture:
        raise ValueError('unit_fixture_not_scientific_acquisition')
    if not unit and implementation != implementation_binding(Path(__file__).resolve().parents[2]):
        raise ValueError('derivation_implementation_binding_mismatch')
    entries, report, boot = reconstruct(parent, design)
    config = dict(version=VERSION, semantics='[start,end)', design=design, implementation=implementation)
    body = dict(schema_version=GENERATION, derived_at_ns=time.time_ns(), data_kind='UNIT_TEST_ONLY' if unit else 'MEASURED_24H_DERIVED_FROM_FAILED_ACQUISITION', parent_inventory=expected_parent_inventory,
        parent_run_id=read_json(parent/'manifest.json')['run_id'], derivation=config,
        derivation_sha256=fingerprint(config), report=report,
        corrected_sha256=fingerprint(entries), corrected_file_sha256=hashlib.sha256(''.join(canonical_json(e)+'\n' for e in entries).encode()).hexdigest(), status='PASS' if boot is not None else 'BLOCKED',
        label='Derived from failed acquisition: valid raw telemetry, incorrect original bucket assignment; correctness fix before comparative outcomes')
    identity = fingerprint(body); root = Path(store)/identity
    if root.exists():
        load_generation(root, identity, design); return root
    root.mkdir(parents=True)
    shutil.copytree(parent, root/'parent')
    with (root/'corrected.jsonl').open('x') as f:
        for entry in entries: f.write(canonical_json(entry)+'\n')
    write_json(root/'manifest.json', {**body, 'generation_sha256':identity})
    write_json(root/'COMPLETE',dict(generation_sha256=identity, manifest_sha256=file_sha256(root/'manifest.json')))
    _verify_inventory(parent, expected_parent_inventory)
    load_generation(root, identity, design)
    return root


def load_generation(root, expected_sha256, design):
    root = Path(root)
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('derived_symlinks_forbidden')
    if root.is_symlink() or {p.name for p in root.iterdir()} != {'parent','corrected.jsonl','manifest.json','COMPLETE'}:
        raise ValueError('derived_generation_inventory')
    m = read_json(root/'manifest.json'); body = {k:v for k,v in m.items() if k != 'generation_sha256'}
    if (m['schema_version'] != GENERATION or fingerprint(body) != expected_sha256 or m['generation_sha256'] != expected_sha256 or
            read_json(root/'COMPLETE') != dict(generation_sha256=expected_sha256,manifest_sha256=file_sha256(root/'manifest.json')) or
            fingerprint(m['derivation']) != m['derivation_sha256'] or m['derivation']['version'] != VERSION or m['derivation']['design'] != design):
        raise ValueError('derived_generation_hash_or_config')
    _verify_inventory(root/'parent', m['parent_inventory'])
    entries, report, boot = reconstruct(root/'parent', design)
    if file_sha256(root/'corrected.jsonl') != m['corrected_file_sha256'] or list(_rows(root/'corrected.jsonl')) != entries or fingerprint(entries) != m['corrected_sha256'] or report != m['report']:
        raise ValueError('derived_generation_reconstruction_mismatch')
    return m, boot


def create_derived_artifact(generation, store, expected_generation_sha256, design):
    gm, boot = load_generation(generation, expected_generation_sha256, design)
    if boot is None or gm['status'] != 'PASS':
        raise ValueError('incomplete_derived_generation')
    p = Path(generation)/'parent'; parent = read_json(p/'manifest.json'); plan = read_json(p/'outputs/plan.json')
    body = dict(schema_version=ARTIFACT, data_kind=gm['data_kind'],
        generation_sha256=expected_generation_sha256, generation_files=_inventory(generation),
        acquisition_start_ns=boot.start_ns, acquisition_end_ns=boot.end_ns,
        available_at_ns=max(time.time_ns(),gm['derived_at_ns']), acquisition_run_id=parent['run_id'],
        source_commit=parent['experiment']['source']['commit'], acquisition_fingerprint=parent['experiment_fingerprint'],
        source_instance_id=next(_rows(p/'outputs/telemetry.jsonl'))['instance_id'],
        source_pod_uid=plan['bootstrap_source_pod_uid'], accepted_slots=288,
        evidence_sha256=boot.evidence_sha256, label=gm['label'],
        claim_eligibility=gm['report']['claim_eligibility'], current_boot_endurance_qualified=False)
    identity = fingerprint(body); root = Path(store)/identity
    if not root.exists():
        root.mkdir(parents=True); shutil.copytree(generation, root/'generation')
        write_json(root/'manifest.json', {**body,'artifact_sha256':identity})
        write_json(root/'COMPLETE',dict(artifact_sha256=identity,manifest_sha256=file_sha256(root/'manifest.json')))
    load_derived_artifact(root, identity, design)
    return root


def load_derived_artifact(root, expected_sha256, design):
    root = Path(root)
    if any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('derived_symlinks_forbidden')
    if root.is_symlink() or {p.name for p in root.iterdir()} != {'generation','manifest.json','COMPLETE'}:
        raise ValueError('derived_artifact_inventory')
    m = read_json(root/'manifest.json'); body = {k:v for k,v in m.items() if k != 'artifact_sha256'}
    if (m['schema_version'] != ARTIFACT or fingerprint(body) != expected_sha256 or m['artifact_sha256'] != expected_sha256 or
            read_json(root/'COMPLETE') != dict(artifact_sha256=expected_sha256,manifest_sha256=file_sha256(root/'manifest.json'))):
        raise ValueError('derived_artifact_hash_mismatch')
    _verify_inventory(root/'generation', m['generation_files'])
    gm, boot = load_generation(root/'generation', m['generation_sha256'], design)
    if boot is None or gm['status'] != 'PASS' or m['evidence_sha256'] != boot.evidence_sha256:
        raise ValueError('derived_artifact_reconstruction')
    return m, boot
