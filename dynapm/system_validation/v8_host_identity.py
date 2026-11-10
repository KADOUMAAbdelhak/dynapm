"""Versioned host UUID guards and evidence; no scientific treatment changes."""
from pathlib import Path
import re
import subprocess
import threading
import uuid

from dynapm.core.provenance import (canonical_json, experiment_from_dict, file_sha256,
                                    read_json, SourceProvenance)
from dynapm.core.run_store import check_cache
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.host_certificate import require_same_host_runtime
from dynapm.system_validation.host_power import (
    ManagedPowerGuard, PowerGuardError, command, power_state, own_assertions,
    ENDURANCE_SECONDS, SCHEMA, MAX_HEARTBEAT_GAP_NS,
)

UUID_ENDURANCE_SCHEMA = 'host-endurance-v2-uuid'

SCIENTIFIC_SOURCE = 'fe3b870149a156e7fecb88741d51cfb5c1ed86d7'
ADDITIONS = (
    'dynapm/system_validation/v8_host_identity.py',
    'dynapm/scripts/task45_v8_host_harness.py',
    'dynapm/tests/test_v8_host_identity.py',
    'docs/v8_host_identity_amendment.md',
)


def harness_source(repo):
    """Exact frozen tree plus only these committed harness additions."""
    import subprocess
    repo = Path(repo)
    current = SourceProvenance.capture(repo)
    if current.dirty or current.branch != 'dynapm':
        raise ValueError('clean_committed_dynapm_harness_required')
    subprocess.run(['git', 'merge-base', '--is-ancestor', SCIENTIFIC_SOURCE, current.commit],
                   cwd=repo, check=True, capture_output=True)
    changes = subprocess.check_output(
        ['git', 'diff', '--name-status', SCIENTIFIC_SOURCE, current.commit], cwd=repo, text=True)
    actual = {}
    for row in changes.splitlines():
        status, path = row.split('\t')
        if status != 'A' or path not in ADDITIONS:
            raise ValueError('frozen_scientific_source_changed')
        actual[path] = file_sha256(repo/path)
    if set(actual) != set(ADDITIONS):
        raise ValueError('incomplete_host_harness_commit')
    return dict(frozen_scientific_source=SCIENTIFIC_SOURCE,
                execution_harness_commit=current.commit, harness_files=actual)


def parse_boot(uuid_raw, timeval_raw):
    if not isinstance(uuid_raw, str) or not isinstance(timeval_raw, str):
        raise ValueError('malformed_boot_identity')
    value = uuid_raw.strip()
    try:
        parsed = str(uuid.UUID(value)).upper()
    except (ValueError, AttributeError) as exc:
        raise ValueError('malformed_boot_uuid') from exc
    if parsed != value.upper():
        raise ValueError('noncanonical_boot_uuid')
    match = re.match(r'^\{ sec = (\d+), usec = (\d+) \}', timeval_raw)
    if not match or int(match[2]) >= 1000000:
        raise ValueError('malformed_boot_timeval')
    return dict(boot_uuid=parsed, boot_timeval_ns=int(match[1])*10**9+int(match[2])*1000,
                boot_epoch_seconds=int(match[1]), uuid_raw=uuid_raw, timeval_raw=timeval_raw)


def read_boot(read=command):
    before = read(['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid'])
    timeval = read(['/usr/sbin/sysctl', '-n', 'kern.boottime'])
    after = read(['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid'])
    if before != after:
        raise ValueError('boot_changed_during_read')
    return parse_boot(before, timeval)


def same_boot(expected_uuid, current, *, legacy_epoch=None, anchor_ns=None):
    if parse_boot(expected_uuid, '{ sec = 1, usec = 0 }')['boot_uuid'] != current['boot_uuid']:
        raise ValueError('host_boot_uuid_mismatch')
    if (legacy_epoch is None) == (anchor_ns is None):
        raise ValueError('exactly_one_boot_calendar_anchor_required')
    now = current['boot_timeval_ns']
    if legacy_epoch is not None:
        if type(legacy_epoch) is not int or legacy_epoch < 0:
            raise ValueError('malformed_legacy_boot_epoch')
        # Legacy logs retained only tv_sec. Its unknown timeval lies in this bin.
        low, high = legacy_epoch*10**9, (legacy_epoch+1)*10**9-1000
        discrepancy = max(low-now, now-high, 0)
    else:
        if type(anchor_ns) is not int or anchor_ns < 0:
            raise ValueError('malformed_boot_timeval_anchor')
        discrepancy = abs(now-anchor_ns)
    # Corroboration uses the existing 2 s host clock bound, never a new +/-1 s rule.
    if discrepancy > MAX_CLOCK_DELTA_NS:
        raise ValueError('material_boot_calendar_discrepancy')
    return discrepancy


class UUIDPowerGuard(ManagedPowerGuard):
    """Keep all original clock, gap, AC, lid, policy and owned-assertion checks."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = threading.RLock()

    def _snapshot(self):
        if self.process is None or self.process.poll() is not None:
            raise PowerGuardError('power_assertion_process_exited')
        state = power_state(self.read, allow_external_power_deficit=self.allow_external_power_deficit)
        try:
            identity = read_boot(self.read)
            # The calendar may cross an integer-second boundary between OS reads.
            # Corroborate its resolution bin with the existing 2 s bound.
            same_boot(identity['boot_uuid'], identity, legacy_epoch=state['boot_epoch_seconds'])
            if self.cached:
                same_boot(self.cached['boot_uuid'], identity,
                          anchor_ns=self.state['boot_timeval_anchor_ns'])
            else:
                self.state['boot_timeval_anchor_ns'] = identity['boot_timeval_ns']
                self.state['boot_uuid_anchor'] = identity['boot_uuid']
        except ValueError as exc:
            raise PowerGuardError(str(exc)) from exc
        settings = self.read(['/usr/bin/pmset', '-g', 'custom'])
        if settings != self.state['power_settings']:
            raise PowerGuardError('host_power_policy_changed')
        from dynapm.core.provenance import fingerprint
        state['power_settings_sha256'] = fingerprint(settings)
        state['own_assertion_lines'] = own_assertions(
            self.read(['/usr/bin/pmset', '-g', 'assertions']), self.process.pid)
        return dict(state, boot_identity_checkpoint=identity,
                    **{k:v for k,v in identity.items() if k != 'boot_epoch_seconds'})


    def checkpoint(self, *, wall_ns=None, mono_ns=None, force_power=False):
        with self.lock:
            # UUID/timeval are checked at EVERY existing 5 s checkpoint, even while
            # expensive AC/lid/policy/assertion diagnostics retain their 30 s cadence.
            self.raise_if_failed()
            try:
                identity = read_boot(self.read)
                same_boot(self.cached['boot_uuid'], identity,
                          anchor_ns=self.state['boot_timeval_anchor_ns'])
            except (ValueError, OSError, subprocess.SubprocessError, KeyError) as exc:
                self._fail(str(exc), dict(boot_identity=locals().get('identity')))
            self.cached['boot_identity_checkpoint'] = identity
            return super().checkpoint(wall_ns=wall_ns, mono_ns=mono_ns, force_power=force_power)


def endurance_boot_metadata(summary, guard, points):
    """Validate v2 raw UUID history; v1 stays identifiable as historical evidence."""
    if not points:
        raise ValueError('missing_qualification_checkpoints')
    if summary['schema_version'] == 'host-endurance-v1':
        epochs = {p['power']['boot_epoch_seconds'] for p in points}
        if len(epochs) != 1 or type(next(iter(epochs))) is not int:
            raise ValueError('inconsistent_qualification_boot_metadata')
        return dict(legacy_epoch=next(iter(epochs)), original_uuid_recorded=False)
    if summary['schema_version'] != UUID_ENDURANCE_SCHEMA:
        raise ValueError('unknown_host_endurance_schema')
    anchor = guard.get('boot_timeval_anchor_ns')
    uuid_value = guard.get('boot_uuid_anchor')
    if summary.get('boot_uuid') != uuid_value or summary.get('boot_timeval_anchor_ns') != anchor:
        raise ValueError('qualification_boot_anchor_mismatch')
    if type(anchor) is not int or anchor < 0 or not uuid_value:
        raise ValueError('missing_qualification_boot_anchor')
    try:
        first = points[0]
        previous = None
        for point in points:
            if point['kind'] != 'CHECKPOINT':
                raise ValueError('noncheckpoint_qualification_record')
            power = point['power']
            identity = power['boot_identity_checkpoint']
            parsed = parse_boot(identity['uuid_raw'], identity['timeval_raw'])
            if parsed != identity or power['boot_uuid'] != parsed['boot_uuid']:
                raise ValueError('qualification_raw_boot_identity_mismatch')
            same_boot(uuid_value, parsed, anchor_ns=anchor)
            if (not power['ac_power'] or not power['lid_open']
                    or power.get('external_power_deficit_observed')
                    or power.get('authorized_external_power_deficit')):
                raise ValueError('qualification_power_invalid')
            wall, mono = point['wall_ns'], point['monotonic_ns']
            drift = (wall-first['wall_ns'])-(mono-first['monotonic_ns'])
            if abs(drift) > MAX_CLOCK_DELTA_NS:
                raise ValueError('qualification_clock_discontinuity')
            if previous is not None and not 0 <= mono-previous <= MAX_HEARTBEAT_GAP_NS:
                raise ValueError('qualification_checkpoint_gap')
            previous = mono
        if points[-1]['monotonic_ns']-first['monotonic_ns'] < ENDURANCE_SECONDS*10**9:
            raise ValueError('qualification_history_incomplete')
    except (KeyError, TypeError) as exc:
        raise ValueError('malformed_qualification_history') from exc
    return dict(legacy_epoch=points[0]['power']['boot_epoch_seconds'],
                original_uuid_recorded=True, boot_uuid=uuid_value,
                boot_timeval_anchor_ns=anchor)


def qualification_inputs(repo, run_path):
    """Verify the original endurance evidence without rewriting its history."""
    repo = Path(repo).resolve()
    root = Path(run_path).resolve()
    if not root.is_relative_to(repo/'results/host_endurance/runs'):
        raise ValueError('managed_host_endurance_path_required')
    manifest = read_json(root/'manifest.json')
    exp = experiment_from_dict(manifest['experiment'])
    schema = read_json(root/'outputs/endurance_summary.json').get('schema_version')
    if schema == UUID_ENDURANCE_SCHEMA:
        from dynapm.system_validation.uuid_host_observer import require_same_uuid_runtime
        require_same_uuid_runtime(repo, exp.source.commit)
    else:
        require_same_host_runtime(repo, exp.source.commit)
    decision = check_cache(root, exp, 'smoke')
    if not decision.reusable:
        raise ValueError('host_endurance_invalid:'+','.join(decision.reasons))
    summary = read_json(root/'outputs/endurance_summary.json')
    guard = read_json(root/'outputs/power_guard.json')
    if (summary.get('schema_version') not in ('host-endurance-v1', UUID_ENDURANCE_SCHEMA)
            or summary.get('elapsed_seconds', 0) < ENDURANCE_SECONDS
            or summary.get('requested_seconds', 0) < ENDURANCE_SECONDS
            or summary.get('comparisons') != 0 or summary.get('profile_initializations') != 0
            or guard.get('schema_version') != SCHEMA or not guard.get('release_confirmed')
            or guard.get('failure') is not None or guard.get('status') != 'RELEASED'):
        raise ValueError('host_endurance_incomplete')
    import json
    points = [json.loads(line) for line in (root/'outputs/host_continuity.jsonl').read_text().splitlines()]
    boot_metadata = endurance_boot_metadata(summary, guard, points)
    names = ('manifest.json', 'output_manifest.json', 'SUCCESS', 'outputs/power_guard.json',
             'outputs/endurance_summary.json', 'outputs/host_continuity.jsonl')
    return dict(path=root.relative_to(repo).as_posix(),
                hashes={n:file_sha256(root/n) for n in names},
                **boot_metadata), guard


def qualification_amendment(repo, run_path, witness_paths):
    """UUID association is witnessed by sealed neutral runs, never invented as an old field."""
    repo = Path(repo)
    inputs, _ = qualification_inputs(repo, run_path)
    from dynapm.scripts.task41_bounded_v8 import completed_attempts
    all_attempts = completed_attempts(repo/'results/bounded_v8/campaign-v1')
    neutral = [(p,i,t) for p,i,t in all_attempts if i['plan']['mode']=='reference']
    if len(neutral) != 3 or set(map(str, witness_paths)) != {str(p) for p,i,t in neutral}:
        raise ValueError('three_exact_neutral_boot_witnesses_required')
    witnesses = []
    for path, intent, terminal in neutral:
        if terminal['status'] != 'COMPLETE' or intent['campaign']['source_commit'] != SCIENTIFIC_SOURCE:
            raise ValueError('invalid_neutral_boot_witness')
        guard = read_json(path/'outputs/power_guard.json')
        if guard['status'] != 'RELEASED' or guard['failure'] is not None or not guard['release_confirmed']:
            raise ValueError('invalid_neutral_boot_guard')
        import json
        epochs = {json.loads(line)['power']['boot_epoch_seconds']
                  for line in (path/'outputs/host_continuity.jsonl').read_text().splitlines()}
        if epochs != {inputs['legacy_epoch']}:
            raise ValueError('witness_does_not_match_original_qualification_epoch')
        witnesses.append(dict(path=path.relative_to(repo).as_posix(),
                              terminal_sha256=file_sha256(path/'terminal.json'),
                              intent_sha256=file_sha256(path/'intent.json'),
                              boot_uuid=intent['campaign']['boot_identity']))
    uuids = {x['boot_uuid'] for x in witnesses}
    if len(uuids) != 1:
        raise ValueError('conflicting_boot_uuid_witnesses')
    provenance = harness_source(repo)
    return dict(schema_version='v8-host-identity-amendment-v1', qualification=inputs,
                frozen_scientific_source=SCIENTIFIC_SOURCE,
                execution_harness_commit=provenance['execution_harness_commit'],
                boot_uuid=next(iter(uuids)), witnesses=witnesses,
                legacy_uuid_association='sealed neutral campaign that passed original exact-epoch qualification',
                clock_bound_ns=MAX_CLOCK_DELTA_NS, original_history_rewritten=False)


def require_amended_endurance(repo, run_path, amendment_path, expected_sha):
    if not expected_sha or file_sha256(amendment_path) != expected_sha:
        raise ValueError('host_amendment_hash_mismatch')
    amendment = read_json(amendment_path)
    if (not isinstance(amendment, dict)
            or amendment.get('schema_version') != 'v8-host-identity-amendment-v1'
            or not isinstance(amendment.get('witnesses'), list)
            or len(amendment['witnesses']) != 3):
        raise ValueError('malformed_host_identity_amendment')
    witnesses = [Path(repo)/x['path'] for x in amendment['witnesses']]
    expected = qualification_amendment(repo, run_path, witnesses)
    if canonical_json(amendment) != canonical_json(expected):
        raise ValueError('host_amendment_provenance_mismatch')
    current = read_boot()
    same_boot(amendment['boot_uuid'], current, legacy_epoch=amendment['qualification']['legacy_epoch'])
    _, guard = qualification_inputs(repo, run_path)
    if command(['/usr/bin/pmset', '-g', 'custom']) != guard['power_settings']:
        raise ValueError('host_endurance_power_policy_mismatch')
    return current
