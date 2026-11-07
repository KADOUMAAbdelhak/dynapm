"""V8 host identity amendment. Frozen acquisition and scientific files stay intact."""
from pathlib import Path
import re
import uuid

from dynapm.core.provenance import (canonical_json, experiment_from_dict, file_sha256,
                                    read_json, SourceProvenance)
from dynapm.core.run_store import check_cache
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.host_certificate import require_same_host_runtime
from dynapm.system_validation.host_power import (
    ManagedPowerGuard, PowerGuardError, command, power_state, own_assertions,
    ENDURANCE_SECONDS, SCHEMA,
)

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
    def _snapshot(self):
        if self.process is None or self.process.poll() is not None:
            raise PowerGuardError('power_assertion_process_exited')
        state = power_state(self.read, allow_external_power_deficit=self.allow_external_power_deficit)
        try:
            identity = read_boot(self.read)
            if state['boot_epoch_seconds'] != identity['boot_epoch_seconds']:
                raise ValueError('inconsistent_boot_snapshot')
            if self.cached:
                same_boot(self.cached['boot_uuid'], identity,
                          anchor_ns=self.state['boot_timeval_anchor_ns'])
            else:
                self.state['boot_timeval_anchor_ns'] = identity['boot_timeval_ns']
        except ValueError as exc:
            raise PowerGuardError(str(exc)) from exc
        settings = self.read(['/usr/bin/pmset', '-g', 'custom'])
        if settings != self.state['power_settings']:
            raise PowerGuardError('host_power_policy_changed')
        from dynapm.core.provenance import fingerprint
        state['power_settings_sha256'] = fingerprint(settings)
        state['own_assertion_lines'] = own_assertions(
            self.read(['/usr/bin/pmset', '-g', 'assertions']), self.process.pid)
        return dict(state, **{k:v for k,v in identity.items() if k != 'boot_epoch_seconds'})


def qualification_inputs(repo, run_path):
    """Verify the original endurance evidence without rewriting its history."""
    repo = Path(repo).resolve()
    root = Path(run_path).resolve()
    if not root.is_relative_to(repo/'results/host_endurance/runs'):
        raise ValueError('managed_host_endurance_path_required')
    manifest = read_json(root/'manifest.json')
    exp = experiment_from_dict(manifest['experiment'])
    require_same_host_runtime(repo, exp.source.commit)
    decision = check_cache(root, exp, 'smoke')
    if not decision.reusable:
        raise ValueError('host_endurance_invalid:'+','.join(decision.reasons))
    summary = read_json(root/'outputs/endurance_summary.json')
    guard = read_json(root/'outputs/power_guard.json')
    if (summary.get('schema_version') != 'host-endurance-v1'
            or summary.get('elapsed_seconds', 0) < ENDURANCE_SECONDS
            or summary.get('requested_seconds', 0) < ENDURANCE_SECONDS
            or summary.get('comparisons') != 0 or summary.get('profile_initializations') != 0
            or guard.get('schema_version') != SCHEMA or not guard.get('release_confirmed')
            or guard.get('failure') is not None or guard.get('status') != 'RELEASED'):
        raise ValueError('host_endurance_incomplete')
    import json
    points = [json.loads(line) for line in (root/'outputs/host_continuity.jsonl').read_text().splitlines()]
    if not points:
        raise ValueError('missing_qualification_checkpoints')
    epochs = {p['power']['boot_epoch_seconds'] for p in points}
    if len(epochs) != 1 or type(next(iter(epochs))) is not int:
        raise ValueError('inconsistent_qualification_boot_metadata')
    names = ('manifest.json', 'output_manifest.json', 'SUCCESS', 'outputs/power_guard.json',
             'outputs/endurance_summary.json', 'outputs/host_continuity.jsonl')
    return dict(path=root.relative_to(repo).as_posix(),
                hashes={n:file_sha256(root/n) for n in names},
                legacy_epoch=next(iter(epochs)), original_uuid_recorded=False), guard


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
