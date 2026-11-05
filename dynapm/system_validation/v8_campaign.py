"""Offline V7D campaign planning and durable treatment-level orchestration."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import re
import tempfile

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.system_validation.outcome_taxonomy import HARNESS

DESIGN_PATH = 'results/prospective_v8/V7D-2026-11-05-v1/design.json'
DESIGN_SHA = '4374365b28d2c3ba9258a9610c190dbc70c6cdc373e86888162150c6aa825c5d'
METHODS = ('pw_12h', 'pw_3h', 'static', 'full_rewrite')
SCENARIOS = ('periodic', 'abrupt_regime_shift')
BLOCKS = tuple(f'block{i:04d}' for i in (1, 2, 3))
SEEDS = dict(zip(BLOCKS, (2026110501, 2026110502, 2026110503)))
ARTIFACT_1 = '51aad0e364d6f4774f8c51ab2cb7544eac87d7ebdb36e492eba648c014dffd2b'
QUALIFICATION_1 = 'b0e4e3c1dcaf87de424cb6bb070341da4fc69ad96b63558bf910255807775a93'
DURATION = 172800
STARTUP = 2700
ACQUISITION = 89100
REPLACEMENTS = 2
SCOPE = 'SYNTHETIC_OFFLINE_ONLY'
CONFIG_HASHES = {
    'configs/system_trials_v8_estimation_v2.json': 'd33f4010b3131cb6fee5fbfa77fc421f82e9ae6a709f216e3d72daf0f0ec718f',
    'configs/system_resource_actuation_v2.json': '2dcf52db918816eda1139a92b3643fa5b09b2430bf53b1d019fd1ac4b5b858ca',
    'dynapm/system_validation/outcome_taxonomy.py': '0a1ebad090d20e2ae9ab299c791232f643bdaddd649292eb72673c8f330a432d',
}


def expected_sequence():
    rows = []
    for i, block in enumerate(BLOCKS):
        scenarios = SCENARIOS if i % 2 == 0 else SCENARIOS[::-1]
        for scenario in scenarios:
            shift = i + (scenario == 'abrupt_regime_shift')
            for method in METHODS[shift:] + METHODS[:shift]:
                rows.append((block, scenario, method, 'CORE'))
    rows.extend((BLOCKS[0], scenario, method, 'MANDATORY_SECONDARY') for scenario, method in (
        ('stable', 'static'), ('stable', 'pw_3h'), ('burst', 'pw_3h'), ('burst', 'static')))
    return [dict(sequence=i, bootstrap_block=b, scenario=s, method=m, stage=stage,
                 workload_seed=SEEDS[b], measurement_seconds=DURATION, startup_seconds=STARTUP)
            for i, (b, s, m, stage) in enumerate(rows, 1)]


def load_design(repo):
    path = Path(repo) / DESIGN_PATH
    if file_sha256(path) != DESIGN_SHA:
        raise ValueError('frozen_design_digest_mismatch')
    design = read_json(path)
    if file_sha256(path.with_name('V7D-design.md')) != '696d685fa927ab6635621149d743781f8879b55137e952b89b5cdfc234923bdb':
        raise ValueError('frozen_report_digest_mismatch')
    if (design['sequence'] != expected_sequence() or design['execution_enabled'] is not False
            or design['maximum_infrastructure_replacement_attempts'] != REPLACEMENTS):
        raise ValueError('frozen_design_contract_mismatch')
    return design


def configuration(repo, design):
    """Bind the actual workload shape and mechanics inputs used by the plan."""
    if design != load_design(repo):
        raise ValueError('frozen_design_required')
    root = Path(repo)
    for path, digest in design['source_hashes'].items():
        if file_sha256(root / path) != digest:
            raise ValueError(f'frozen_source_binding_changed:{path}')
    return dict(CONFIG_HASHES)


def acquisition_slots():
    return [dict(block=b, status='AWAITING_SEPARATE_ACQUISITION_AND_QUALIFICATION',
                 artifact_sha256=None, qualification_sha256=None, scenario='stable',
                 bootstrap_workload_seed=20251022, treatment_workload_seed=SEEDS[b],
                 startup_seconds=STARTUP, acquisition_seconds=86400, slots=288,
                 bucket_seconds=300, minimum_samples=50, minimum_span_seconds=270,
                 acquisition_enabled=False)
            for b in BLOCKS[1:]]


def calendar(design):
    if design['sequence'] != expected_sequence():
        raise ValueError('frozen_sequence_required')
    offset = 2 * ACQUISITION
    treatment_elapsed = 0
    rows = []
    for cell in design['sequence']:
        end = offset + STARTUP + DURATION
        treatment_elapsed += STARTUP + DURATION
        artifact = ARTIFACT_1 if cell['bootstrap_block'] == BLOCKS[0] else None
        rows.append(dict(cell, artifact_sha256=artifact, start_offset_seconds=offset,
                         measurement_start_offset_seconds=offset + STARTUP,
                         end_offset_seconds=end, cumulative_treatment_seconds=treatment_elapsed))
        offset = end
    return rows


def cell_binding(cell, artifact, config):
    return dict(cell=cell, bootstrap=artifact, config_sha256=fingerprint(config),
                trace_contract_sha256=fingerprint(dict(
                    scenario=cell['scenario'], seed=cell['workload_seed'],
                    duration_seconds=DURATION, startup_seconds=STARTUP, config=config)))


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def synthetic_header(repo, *, source_commit, boot_identity, host_identity):
    design = load_design(repo)
    artifacts = {BLOCKS[0]: dict(artifact_sha256=ARTIFACT_1, qualification_sha256=QUALIFICATION_1)}
    for b in BLOCKS[1:]:
        artifacts[b] = dict(artifact_sha256=fingerprint({'synthetic_slot': b}),
                            qualification_sha256=None, synthetic=True)
    return dict(schema='v8-campaign-ledger-v1', scope=SCOPE, design_sha256=DESIGN_SHA,
                source_commit=source_commit, boot_identity=boot_identity, host_identity=host_identity,
                configuration=configuration(repo, design), artifacts=artifacts)


def publish_record(path, value):
    """Publish a fully written record exactly once, including directory durability."""
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o444)
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Campaign:
    """Append-only dry-run ledger. Reopen requires an independently supplied header.

    Each journal entry is the authoritative checkpoint. A START with no terminal
    record remains active after interruption and cannot launch a duplicate.
    """

    def __init__(self, root, header, *, create=False, checkpoint=None):
        self.root = Path(root)
        self.header = deepcopy(header)
        if (header.get('scope') != SCOPE or header.get('design_sha256') != DESIGN_SHA
                or not re.fullmatch('[0-9a-f]{40}', header.get('source_commit', ''))
                or not header.get('boot_identity') or not header.get('host_identity')):
            raise ValueError('synthetic_campaign_identity_required')
        if header.get('configuration') != CONFIG_HASHES:
            raise ValueError('resume_frozen_configuration_required')
        artifacts = header.get('artifacts', {})
        if set(artifacts) != set(BLOCKS) or artifacts[BLOCKS[0]] != dict(
                artifact_sha256=ARTIFACT_1, qualification_sha256=QUALIFICATION_1):
            raise ValueError('invalid_bootstrap_binding')
        for block in BLOCKS[1:]:
            if artifacts[block] != dict(artifact_sha256=fingerprint({'synthetic_slot': block}),
                                         qualification_sha256=None, synthetic=True):
                raise ValueError('synthetic_bootstrap_placeholder_required')
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            publish_record(self.root / 'campaign.json', header)
        with self._locked():
            _, count, _ = self._replay()
            if checkpoint is not None:
                index, digest = checkpoint
                if (type(index) is not int or not 1 <= index <= count or
                        read_json(self.root / f'{index:06d}.event.json')['sha256'] != digest):
                    raise ValueError('checkpoint_missing_or_changed')

    @contextmanager
    def _locked(self):
        if self.root.is_symlink() or (self.root / 'campaign.json').is_symlink():
            raise ValueError('linked_campaign_path')
        with (self.root / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if read_json(self.root / 'campaign.json') != self.header:
                raise ValueError('resume_source_config_host_boot_or_artifact_mismatch')
            yield

    def _replay(self):
        state = dict(next_sequence=1, active=None, completed=[], failures=[],
                     approved=None, replacements_used=0, identities=set(), attempts=[])
        previous = fingerprint(self.header)
        records = sorted(self.root.glob('*.event.json'))
        for index, path in enumerate(records, 1):
            if path.name != f'{index:06d}.event.json' or path.is_symlink():
                raise ValueError('journal_gap_or_link')
            row = read_json(path)
            if row['index'] != index or row['previous_sha256'] != previous:
                raise ValueError('journal_chain_mismatch')
            body = {k: v for k, v in row.items() if k != 'sha256'}
            if row['sha256'] != fingerprint(body) or path.read_text() != canonical_json(row):
                raise ValueError('journal_record_hash_mismatch')
            self._apply(state, row['kind'], row['payload'])
            previous = row['sha256']
        return state, len(records), previous

    def _apply(self, state, kind, data):
        sequence = state['next_sequence']
        if sequence > 28 or data['sequence'] != sequence:
            raise ValueError('next_frozen_cell_required')
        cell = expected_sequence()[sequence - 1]
        active = state['active']
        last = state['failures'][-1] if state['failures'] else None
        needs_replacement = last is not None and last['sequence'] == sequence
        if kind == 'APPROVE_REPLACEMENT':
            if (active or not needs_replacement or state['approved'] or not last['exogenous']
                    or state['replacements_used'] >= REPLACEMENTS
                    or data['failed_attempt_id'] != last['attempt_id']
                    or not data['approval_id'].strip() or not data['reviewer'].strip()):
                raise ValueError('replacement_not_eligible')
            state['approved'] = data
            return
        if kind == 'START':
            if active or needs_replacement != bool(state['approved']):
                raise ValueError('active_attempt_or_explicit_replacement_required')
            binding = cell_binding(cell, self.header['artifacts'][cell['bootstrap_block']], self.header['configuration'])
            if (data['binding'] != binding or data['source_commit'] != self.header['source_commit']
                    or data['campaign_sha256'] != fingerprint(self.header)):
                raise ValueError('attempt_binding_mismatch')
            if data['replacement_for'] != (last['attempt_id'] if needs_replacement else None):
                raise ValueError('replacement_parent_mismatch')
            ids = data['runtime_identities']
            if (set(ids) != {'cluster', 'pod', 'application', 'profile', 'controller', 'telemetry'}
                    or any(not isinstance(x, str) or not x for x in ids.values())
                    or len(set(ids.values())) != len(ids) or set(ids.values()) & state['identities']
                    or not isinstance(data['attempt_id'], str) or not data['attempt_id']
                    or any(x['attempt_id'] == data['attempt_id'] for x in state['attempts'])):
                raise ValueError('fresh_runtime_and_attempt_identities_required')
            state['identities'].update(ids.values())
            state['attempts'].append(data)
            state['active'] = data
            if needs_replacement:
                state['replacements_used'] += 1
            state['approved'] = None
            return
        if kind != 'TERMINAL' or not active or data['attempt_id'] != active['attempt_id']:
            raise ValueError('active_attempt_required')
        if data['binding_sha256'] != fingerprint(active) or not _sha(data['evidence_sha256']):
            raise ValueError('terminal_evidence_binding_required')
        elapsed = data['measurement_elapsed_seconds']
        if type(elapsed) is not int or not 0 <= elapsed <= DURATION:
            raise ValueError('invalid_measurement_exposure')
        status = data['status']
        if status == 'COMPLETE':
            from dynapm.system_validation.v8_analysis import validate_summary
            validate_summary(data['endpoints'])
            if elapsed != DURATION or data['failure_kind'] is not None or data['exogenous']:
                raise ValueError('full_horizon_required')
        elif status == 'OPERATIONAL_CENSORED':
            if (elapsed >= DURATION or data['exogenous'] or data['endpoints'] is not None
                    or data['failure_kind'] not in {'resize_watchdog', 'operational_shutdown'}):
                raise ValueError('invalid_operational_censoring')
        elif status == 'HARNESS_FAILED':
            if (data['failure_kind'] not in HARNESS or data['endpoints'] is not None
                    or type(data['exogenous']) is not bool):
                raise ValueError('invalid_harness_failure')
        else:
            raise ValueError('invalid_terminal_status')
        state['active'] = None
        if status == 'HARNESS_FAILED':
            state['failures'].append(data)
        else:
            state['completed'].append(data)
            state['next_sequence'] += 1

    def checkpoint(self):
        with self._locked():
            _, count, digest = self._replay()
        return (count, digest) if count else None

    def state(self):
        with self._locked():
            state, _, _ = self._replay()
        state.pop('identities')
        return state

    def record(self, kind, payload):
        with self._locked():
            state, count, previous = self._replay()
            self._apply(state, kind, payload)
            row = dict(index=count + 1, previous_sha256=previous, kind=kind, payload=payload)
            row['sha256'] = fingerprint(row)
            publish_record(self.root / f'{count + 1:06d}.event.json', row)
        return row['sha256']
