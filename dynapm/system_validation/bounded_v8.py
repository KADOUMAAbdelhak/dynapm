"""Frozen plans, measured reference lineage, and causal offline profile replay."""
import base64
import json
from pathlib import Path
import time

import pandas as pd

from dynapm.core.provenance import file_sha256, fingerprint, read_json
from dynapm.core.temporal import METRICS, trailing_observations
from dynapm.system_validation.adapter import aggregate_bucket
from dynapm.system_validation.clock_observations import validate_clock_evidence
from dynapm.system_validation.neutral_characterization import ARTIFACT, QUALIFICATION, qualification
from dynapm.system_validation.reservation_protocol import Target, reservation_recommendation
from dynapm.system_validation.shared_bootstrap import load_artifact
from dynapm.system_validation.trial_preparation import MeasuredBootstrap, MeasuredProfileAdapter

NS = 10**9
SLOT = 300
COOLDOWN = 900
WARMUP = 1800
DURATION = 1800
LIVE_DURATION = 12600
SEEDS = (2026110501, 2026110502, 2026110503)
METHODS = ('static', 'pw_12h', 'pw_3h')
CHECKPOINTS = {'periodic': 24300, 'abrupt_regime_shift': 97200}
PHASES = {'low2': (2, 32), 'low4': (4, 32), 'high12': (12, 96)}
REFERENCE = Target(1000, 512)
DONOR_SEED = 20251022
CONTRACT_PATH = 'configs/v8_bounded_operational_v1.json'
MEASURED = 'MEASURED_V8A'
FIXTURE = 'SYNTHETIC_V8A_FIXTURE'


def cells():
    rows = []
    for i, seed in enumerate(SEEDS):
        scenarios = tuple(CHECKPOINTS)
        for scenario in scenarios if i % 2 == 0 else scenarios[::-1]:
            order = METHODS if scenario == 'periodic' else (METHODS[0], METHODS[2], METHODS[1])
            for method in order[i:] + order[:i]:
                rows.append(dict(sequence=len(rows)+1, repetition=i+1, seed=seed, scenario=scenario, method=method))
    return rows


def contract():
    return dict(schema='v8-bounded-operational-v1', cooldown_seconds=COOLDOWN, warmup_seconds=WARMUP,
                measurement_seconds=DURATION, transition_slice_seconds=300, integration_seconds=LIVE_DURATION,
                integration_seed=DONOR_SEED, integration_refresh_seconds=10800,
                integration_shift_seconds=1800, donor_seed=DONOR_SEED,
                reference_resources=REFERENCE.resources(), donor_phases={k: list(v) for k,v in PHASES.items()},
                donor_buckets=6, bucket_seconds=SLOT, minimum_samples=50, minimum_receipt_span_seconds=270,
                slo_seconds=.25, iterations=30000, timeout_seconds=5, max_concurrency=32,
                checkpoints_seconds=CHECKPOINTS, cells=cells(),
                qualification_sha256=QUALIFICATION, bootstrap_sha256=ARTIFACT,
                reference_replay='tile six vectors in recorded order, reset at segment boundary',
                scope='checkpoint operational contrasts and one native live integration',
                resource_semantics='scheduler-reservation-actuation-v2',
                failure_taxonomy='reservation-outcome-observability-v1',
                practical_superiority='NOT_DEFINED', automatic_retries=0, maximum_replacements=2,
                fixed_program_seconds=(18+3)*(COOLDOWN+WARMUP+DURATION)+COOLDOWN+WARMUP+LIVE_DURATION)


RUNTIME_FILES = (
    'dynapm/system_validation/bounded_v8.py',
    'dynapm/system_validation/bounded_v8_metrics.py',
    'dynapm/system_validation/bounded_v8_runtime.py',
    'dynapm/scripts/task41_bounded_v8.py',
    'dynapm/system_validation/outcome_taxonomy.py',
    'dynapm/system_validation/v8_analysis.py',
    'dynapm/system_validation/v8_campaign.py',
    'dynapm/experiments/confirmatory_execution.py',
    'dynapm/methods/baselines_v2.py',
    'dynapm/core/temporal.py',
    'dynapm/core/accounting.py',
    'dynapm/system_validation/clock_observations.py',
    'dynapm/system_validation/reservation_protocol.py',
    'dynapm/system_validation/consumer.py',
    'harness/system/kind.yaml',
)

def execution_contract(repo):
    return dict(contract(), runtime_sha256={p:file_sha256(Path(repo)/p) for p in RUNTIME_FILES})

def load_contract(repo):
    path = Path(repo)/CONTRACT_PATH
    if read_json(path) != execution_contract(repo):
        raise ValueError('bounded_contract_changed')
    return file_sha256(path)


def plan(mode, *, phase=None, sequence=None):
    if mode == 'reference' and phase in PHASES and sequence is None:
        seed, warm, segments, seconds = DONOR_SEED, phase, [(0, phase)], DURATION
        identity = dict(phase=phase)
    elif mode == 'primary' and type(sequence) is int and 1 <= sequence <= len(cells()) and phase is None:
        cell = cells()[sequence-1]
        seed, warm, seconds = cell['seed'], 'high12', DURATION
        segments = [(0, 'high12'), (900, 'low2')] if cell['scenario'] == 'periodic' else [(0, 'high12')]
        identity = dict(cell=cell)
    elif mode == 'integration' and phase is None and sequence is None:
        seed, warm, segments, seconds = DONOR_SEED, 'low4', [(0, 'low4'), (1800, 'high12')], LIVE_DURATION
        identity = dict(method='pw_3h', refresh_seconds=10800)
    else:
        raise ValueError('unplanned_bounded_v8_run')
    return dict(mode=mode, seed=seed, warmup_phase=warm, segments=[list(x) for x in segments],
                measurement_seconds=seconds, warmup_seconds=WARMUP, cooldown_seconds=COOLDOWN, **identity)


def offers(p):
    """Integer nanosecond open-loop schedule, relative to T0, including warm-up."""
    segments = [[-WARMUP, p['warmup_phase']], *p['segments']]
    ends = [s[0] for s in segments[1:]] + [p['measurement_seconds']]
    index = 0
    for (start, phase), end in zip(segments, ends):
        rps, mib = PHASES[phase]
        for i in range((end-start)*rps):
            yield dict(request_id=index, offset_ns=start*NS+i*NS//rps, memory_mib=mib,
                       iterations=30000, seed=p['seed'])
            index += 1


def rows(path):
    with Path(path).open() as handle:
        for line in handle:
            yield json.loads(line)


def inventory(root):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink():
            raise ValueError('linked_evidence_forbidden')
        if path.is_file() and path.relative_to(root).as_posix() not in ('terminal.json','SEALED'):
            result[str(path.relative_to(root))] = file_sha256(path)
    return result


def accepted_samples(root, context):
    validate_clock_evidence(root, context)
    out = Path(root)/'outputs'
    if (out/'clock_rejections.jsonl').stat().st_size:
        raise ValueError('clock_rejection_in_reference_or_treatment')
    previous = None
    for s, d in zip(rows(out/'telemetry.jsonl'), rows(out/'clock_observations.jsonl'), strict=True):
        evidence = d['observation']
        envelope = json.loads(base64.b64decode(evidence['raw_payload_base64']))
        source = json.loads(base64.b64decode(envelope['raw_payload_base64']))
        source.update(cluster_received_at_ns=envelope['cluster_received_at_ns'],
                      received_at_ns=evidence['received_at_ns'], host_admitted_at_ns=d['host_admitted_at_ns'],
                      host_admitted_monotonic_ns=d['host_admitted_monotonic_ns'],
                      host_receipt_monotonic_ns=evidence['receipt_monotonic_ns'], sample_index=d['sample_index'],
                      clock_schema=d['schema_version'], cluster_clock_domain=envelope['cluster_clock_domain'],
                      cluster_receipt_monotonic_ns=envelope['cluster_receipt_monotonic_ns'],
                      source_raw_payload_sha256=envelope['raw_payload_sha256'])
        sc = s['source_clock']
        if (source != s or sc['domain'] != s['cluster_clock_domain']
                or not 0 <= s['cluster_received_at_ns']-s['sample_time_ns'] <= 2*NS
                or not s['sample_time_ns'] <= sc['wall_ns'] <= s['cluster_received_at_ns']
                or sc['monotonic_ns'] > s['cluster_receipt_monotonic_ns']
                or not evidence['request_monotonic_ns'] <= s['host_receipt_monotonic_ns'] <= s['host_admitted_monotonic_ns']
                or s['received_at_ns'] > s['host_admitted_at_ns']):
            raise ValueError('raw_clock_admission_mismatch')
        if previous and (previous['instance_id'] != s['instance_id'] or previous['cluster_clock_domain'] != s['cluster_clock_domain']
                         or previous['source_clock']['monotonic_ns'] >= sc['monotonic_ns']
                         or previous['received_at_ns'] >= s['received_at_ns']
                         or previous['cpu_seconds'] > s['cpu_seconds']):
            raise ValueError('telemetry_identity_order_or_counter_reset')
        previous = s
        yield s


def reference_library(paths, design, contract_sha):
    """Rebuild donor vectors from sealed neutral runs, never from supplied aggregates."""
    from dynapm.system_validation.bounded_v8_metrics import request_metrics

    donors = {}
    instances = set()
    for root in map(Path, paths):
        terminal = read_json(root/'terminal.json')
        manifest = read_json(root/'manifest.json')
        phase = manifest['plan']['phase']
        if (read_json(root/'SEALED')!={'terminal_sha256':file_sha256(root/'terminal.json')}
                or terminal['measurement_origin_wall_ns']!=manifest['origin_wall_ns']
                or terminal['status'] != 'COMPLETE' or terminal['files'] != inventory(root)
                or manifest['scope'] != MEASURED or manifest['contract_sha256'] != contract_sha
                or manifest['plan'] != plan('reference', phase=phase) or phase in donors
                or manifest['reference_resources'] != REFERENCE.resources()
                or terminal['measurement_seconds'] != DURATION or terminal['actuations']):
            raise ValueError('unqualified_reference_run')
        from dynapm.system_validation.outcome_taxonomy import control_enforcement
        checks = list(rows(root/'outputs/enforcement.jsonl'))
        if len(checks)!=7 or any('event' in x or x['target']!=vars(REFERENCE) or not control_enforcement(
                x['pod'],x['node'],REFERENCE,pod_uid=manifest['runtime']['pod_uid'],
                generation=x['pod']['metadata']['generation'],ack_ns=0,
                pod_received_ns=x['receipt_monotonic_ns'],now_ns=x['node']['end_monotonic_ns'])['complete'] for x in checks):
            raise ValueError('neutral_requested_and_allocated_resources_unverified')
        guard = read_json(root/'outputs/power_guard.json')
        if guard['status'] != 'RELEASED' or not guard['release_confirmed'] or guard['failure'] is not None:
            raise ValueError('invalid_donor_host_guard')
        request_metrics(manifest['plan'], rows(root/'outputs/requests.jsonl'))
        samples = list(accepted_samples(root, manifest['clock_context']))
        identity = manifest['runtime']['container']
        if identity in instances or {s['instance_id'] for s in samples} != {identity}:
            raise ValueError('reference_runtime_reuse_or_mismatch')
        instances.add(identity)
        if any(s['cpu_limit_cores'] != 1 or s['memory_limit_bytes'] != 1024*2**20
               or s['oom_kills'] or s['memory_swap_bytes'] for s in samples):
            raise ValueError('reference_enforced_resources_changed')
        start = terminal['measurement_origin_wall_ns']
        buckets = [aggregate_bucket(samples, start+i*SLOT*NS, start+(i+1)*SLOT*NS, design)
                   for i in range(6)]
        donors[phase] = dict(phase=phase, run_id=manifest['run_id'], instance_id=identity,
                            manifest_sha256=file_sha256(root/'manifest.json'),
                            terminal_sha256=file_sha256(root/'terminal.json'),
                            raw_sha256=terminal['files']['outputs/telemetry.jsonl'], buckets=buckets)
    if set(donors) != set(PHASES):
        raise ValueError('three_measured_donor_phases_required')
    return dict(scope=MEASURED, contract_sha256=contract_sha, donors=donors)


def logical_history(scenario, library):
    checkpoint = CHECKPOINTS[scenario]
    previous = None
    index = 0
    history = []
    for start in range(0, checkpoint, SLOT):
        if scenario == 'periodic':
            phase = 'low2' if start % 25200 < 12600 else 'high12'
        else:
            phase = 'low4' if start < 86400 else 'high12'
        if phase != previous:
            index = 0
        donor = library['donors'][phase]
        if len(donor['buckets']) != 6:
            raise ValueError('six_donor_vectors_required')
        bucket = donor['buckets'][index]
        history.append(dict(logical_end_seconds=start+SLOT, available_logical_seconds=start+SLOT,
                            cpu_percent=bucket['cpu_percent'], memory_percent=bucket['memory_percent'],
                            donor_run_id=donor['run_id'], donor_raw_sha256=donor['raw_sha256'],
                            donor_manifest_sha256=donor['manifest_sha256'], donor_phase=phase,
                            donor_bucket_index=index, donor_bucket_sha256=fingerprint(bucket)))
        previous = phase
        index = (index+1) % 6
    return history


def new_profile(method, bootstrap, design, origin_ns, slots):
    frame = bootstrap.frame.copy(deep=True)
    frame.index = pd.date_range(end=pd.Timestamp(origin_ns,tz='UTC'), periods=288, freq='5min')
    view = MeasuredBootstrap(frame, origin_ns-86400*NS, origin_ns, bootstrap.accepted_slots,
                             bootstrap.missing_slots, bootstrap.evidence_sha256)
    return MeasuredProfileAdapter(method, view, design, planned_streaming_slots=slots)


def compile_snapshots(library, bootstrap, design):
    """Pure replay inputs and state identities. Timing evidence is stored separately."""
    histories, snapshots, costs = {}, [], []
    for scenario in CHECKPOINTS:
        history = histories[scenario] = logical_history(scenario, library)
        for method in METHODS:
            begin, cpu = time.perf_counter_ns(), time.thread_time_ns()
            adapter = new_profile(method, bootstrap, design, 0, len(history))
            init = dict(wall_ns=time.perf_counter_ns()-begin, cpu_ns=time.thread_time_ns()-cpu)
            steps = []
            for record in history:
                q = record['logical_end_seconds']
                if record['available_logical_seconds'] > q:
                    raise ValueError('future_replay_input')
                stamp = pd.Timestamp(q*NS,tz='UTC')
                begin, cpu = time.perf_counter_ns(), time.thread_time_ns()
                before = adapter.policy.accounting_metrics()['n_refresh_events']
                adapter.history.loc[stamp] = [record['cpu_percent'], record['memory_percent']]
                adapter.policy.step(stamp, *(trailing_observations(adapter.history[m], stamp, 24) for m in METRICS))
                steps.append(dict(logical_end_seconds=q, wall_ns=time.perf_counter_ns()-begin,
                                  cpu_ns=time.thread_time_ns()-cpu,
                                  committed=adapter.policy.accounting_metrics()['n_refresh_events']>before))
            profile = adapter.policy.profile.to_json()
            target = reservation_recommendation(profile, design)
            snapshots.append(dict(method=method, scenario=scenario, logical_history_sha256=fingerprint(history),
                                  profile=profile, cpu_millicores=target.cpu_millicores,
                                  memory_request_mib=target.memory_request_mib, target=target.resources(),
                                  maintenance_counts=adapter.policy.accounting_metrics(),
                                  refreshes=[event.to_dict() for event in adapter.policy.accounting.refresh_events]))
            costs.append(dict(method=method, scenario=scenario, initialization=init, steps=steps))
    result = dict(scope=library['scope'], contract_sha256=library['contract_sha256'],
                  library_sha256=fingerprint(library), bootstrap_sha256=ARTIFACT,
                  qualification_sha256=QUALIFICATION, bootstrap_evidence_sha256=bootstrap.evidence_sha256,
                  snapshots=snapshots, histories=histories)
    result['structural_targets'] = structural_targets(snapshots)
    return result, costs


def structural_targets(snapshots):
    lookup = {(r['scenario'],r['method']):r['target'] for r in snapshots}
    return [dict(scenario=s, left=a, right=b, status='STRUCTURAL_EQUAL_TARGET' if lookup[s,a] == lookup[s,b]
                 else 'DISTINCT_TARGET') for s in CHECKPOINTS for a,b in
            (('static','pw_12h'),('static','pw_3h'),('pw_12h','pw_3h'))]


def qualified_bootstrap(repo, design):
    path, _ = qualification(repo)
    _, bootstrap = load_artifact(path, ARTIFACT, design)
    return bootstrap
