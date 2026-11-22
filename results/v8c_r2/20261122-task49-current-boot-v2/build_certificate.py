"""Independent validation + current-boot certificate for the v2 task49 observation.

Reproduces the v1 schemas (task49-independent-host-validation-v1,
v8-current-boot-host-qualification-v2-uuid) using only the frozen library
checks. Reads evidence, never rewrites it. Run from the frozen repo root:
  .venv/bin/python -I results/v8c_r2/20261122-task49-current-boot-v2/build_certificate.py
"""
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.cwd().resolve()
sys.path.insert(0, str(REPO))
from dynapm.core.provenance import file_sha256, read_json
from dynapm.system_validation.v8_host_identity import (SCIENTIFIC_SOURCE, qualification_inputs,
    read_boot, same_boot, parse_boot)
from dynapm.system_validation.uuid_host_observer import require_same_uuid_runtime
from dynapm.system_validation.host_power import power_state, command, MAX_HEARTBEAT_GAP_NS
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.primary_observer_binding import (OBSERVER_COMMIT,
    OBSERVER_AMENDMENT_PATH, OBSERVER_AMENDMENT_SHA256, CERTIFICATE_SCHEMA)

EVID = Path('results/v8c_r2/20261122-task49-current-boot-v2')
RUN = Path('results/host_endurance/runs/9df3b3f0b8dfde31caa25c6533a1df342cf6f7d3f13cb6f56bc003c0755535ed/'
           '2026-11-22T151815.248945Z-9df3b3f0b8df-30075d02')
# Sealed evidence that must be unchanged (manifest -> per-file sha256).
PROTECTED = ['results/v8c_r2/20261111-task49-current-boot-v1/OUTPUT_MANIFEST.json',
             'results/v8c_r2/20261119-primary-lifecycle-qualification-v1/OUTPUT_MANIFEST.json',
             'results/v8c_r2/amended-v8-claim-campaign-v1/OUTPUT_MANIFEST.json']


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, separators=(',', ':')))
    return file_sha256(path)


def protected_files():
    n = 0
    for m in PROTECTED:
        files = read_json(REPO/m)['files']
        for name, item in files.items():
            want = item['sha256'] if isinstance(item, dict) else item
            p = REPO/name if name.startswith('results/') else REPO/Path(m).parent/name
            if not p.is_file() or file_sha256(p) != want:
                raise SystemExit('PROTECTED_EVIDENCE_CHANGED:'+name)
            n += 1
    return n


def main():
    assert file_sha256(REPO/OBSERVER_AMENDMENT_PATH) == OBSERVER_AMENDMENT_SHA256
    log = REPO/RUN/'outputs/host_continuity.jsonl'
    log_sha_before = file_sha256(log)
    inputs, guard = qualification_inputs(REPO, REPO/RUN)   # managed cache, raw UUID history, gaps, drift
    runtime = require_same_uuid_runtime(REPO, OBSERVER_COMMIT)
    if runtime['observation_source_commit'] != OBSERVER_COMMIT:
        raise SystemExit('observer_runtime_mismatch')
    summary = read_json(REPO/RUN/'outputs/endurance_summary.json')
    points = [json.loads(x) for x in log.read_text().splitlines()]
    first = points[0]
    drift = gap = cal = 0
    prev = None
    uuids, batt = set(), set()
    for p in points:
        ident = p['power']['boot_identity_checkpoint']
        parse_boot(ident['uuid_raw'], ident['timeval_raw'])
        cal = max(cal, same_boot(inputs['boot_uuid'], ident, anchor_ns=inputs['boot_timeval_anchor_ns']))
        uuids.add(ident['boot_uuid'])
        drift = max(drift, abs((p['wall_ns']-first['wall_ns'])-(p['monotonic_ns']-first['monotonic_ns'])))
        if prev is not None:
            gap = max(gap, p['monotonic_ns']-prev)
        prev = p['monotonic_ns']
        batt.update(int(x) for x in re.findall(r'\t(\d+)%', p['power']['battery']))
    span_ns = points[-1]['monotonic_ns']-first['monotonic_ns']
    if (len(uuids) != 1 or drift > MAX_CLOCK_DELTA_NS or gap > MAX_HEARTBEAT_GAP_NS
            or cal > MAX_CLOCK_DELTA_NS or span_ns < 10800*10**9):
        raise SystemExit('independent_limits_failed')
    current = read_boot()
    same_boot(inputs['boot_uuid'], current, anchor_ns=inputs['boot_timeval_anchor_ns'])
    power = power_state()
    if not power['ac_power'] or not power['lid_open'] or power.get('external_power_deficit_observed'):
        raise SystemExit('current_power_invalid')
    if command(['/usr/bin/pmset', '-g', 'custom']) != guard['power_settings']:
        raise SystemExit('power_policy_changed')
    protected = protected_files()
    if file_sha256(log) != log_sha_before:
        raise SystemExit('checkpoint_log_changed_during_validation')
    du = __import__('shutil').disk_usage(REPO)

    validation = dict(schema='task49-independent-host-validation-v1', status='PASS',
        all_18_pending=True, claim_started=False, integration_started=False, primary_lifecycle_started=False,
        assertion_release_confirmed=guard['release_confirmed'] is True,
        battery_percentages=sorted(batt), checkpoint_resume_verified_unchanged=True,
        checkpoint_sha256=log_sha_before, checkpoint_span_seconds=span_ns/1e9, checkpoints=len(points),
        current_boot=current, current_power=power, elapsed_seconds=summary['elapsed_seconds'],
        free_bytes_after=du.free, maximum_absolute_drift_ns=drift,
        maximum_boot_calendar_discrepancy_ns=cal, maximum_checkpoint_gap_ns=gap,
        protected_evidence_files_verified=protected, protected_evidence_manifests=PROTECTED,
        qualification_inputs=inputs, run_id=RUN.name, run_path=RUN.as_posix(),
        runtime_compatibility=runtime, unique_boot_uuids=sorted(uuids), verified_at=now())
    v_sha = dump(REPO/EVID/'independent-validation.json', validation)
    terminal = dict(status='PASS_HOST_QUALIFICATION', boot_uuid=inputs['boot_uuid'], claim_started=False,
        primary_lifecycle_started=False, independent_validation_sha256=v_sha, run_path=RUN.as_posix(),
        recorded_at=now())
    t_sha = dump(REPO/EVID/'terminal.json', terminal)
    cert = dict(schema_version=CERTIFICATE_SCHEMA, status='PASS', assertions_released=True,
        boot_uuid=inputs['boot_uuid'], boot_timeval_anchor_ns=inputs['boot_timeval_anchor_ns'],
        checkpoint_span_seconds=span_ns/1e9, checkpoints=len(points),
        claim_execution_authorized=False, elapsed_seconds=summary['elapsed_seconds'],
        independent_validation_sha256=v_sha, issued_at=now(),
        limits=dict(calendar_ns=MAX_CLOCK_DELTA_NS, checkpoint_gap_ns=MAX_HEARTBEAT_GAP_NS,
                    minimum_seconds=10800, wall_monotonic_ns=MAX_CLOCK_DELTA_NS),
        maximum_calendar_discrepancy_ns=cal, maximum_checkpoint_gap_ns=gap,
        maximum_wall_monotonic_drift_ns=drift, observer_amendment_sha256=OBSERVER_AMENDMENT_SHA256,
        observer_commit=OBSERVER_COMMIT, old_failed_attempts_preserved=True,
        partial_failed_intervals_reused=False, primary_application_qualification=False,
        qualification=inputs, qualification_type='three physical hours of task49 host-only observation',
        runtime_compatibility=runtime, scientific_source=SCIENTIFIC_SOURCE,
        supersedes_boot='6C470F9C-9B15-4093-87C3-DDE6D713D7E6',
        witnesses=[dict(kind='direct-task49-current-boot-observation', path=EVID.as_posix(),
                        boot_uuid=inputs['boot_uuid'], intent_sha256=file_sha256(REPO/EVID/'intent.json'),
                        terminal_sha256=t_sha)])
    c_sha = dump(REPO/EVID/'current-boot-qualification.json', cert)
    print(json.dumps(dict(validation_sha256=v_sha, qualification_sha256=c_sha, checkpoints=len(points),
        span=span_ns/1e9, drift_ns=drift, gap_ns=gap, calendar_ns=cal, battery=sorted(batt),
        protected=protected, free_gb=du.free/1e9), indent=1))


if __name__ == '__main__':
    main()
