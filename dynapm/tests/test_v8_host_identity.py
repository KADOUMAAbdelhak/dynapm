"""Offline regressions for exact boot UUID and immutable V8 scientific lineage."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from dynapm.system_validation import v8_host_identity as h
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS

UUID = '59359FFE-05A4-4FBA-A5C2-457CFE8DF778'
OTHER = '12345678-1234-1234-1234-123456789ABC'
EPOCH = 1793829796
RAW = '{ sec = 1793829797, usec = 37987 } Thu Nov  5 00:03:17 2026\n'


def test_same_uuid_observed_second_boundary_uses_calendar_corroboration():
    current = h.parse_boot(UUID+'\n', RAW)
    assert current['boot_epoch_seconds'] == EPOCH+1
    assert h.same_boot(UUID, current, legacy_epoch=EPOCH) == 37988000
    assert h.same_boot(UUID, current, anchor_ns=EPOCH*10**9+914699000) == 123288000
    assert current['uuid_raw'] == UUID+'\n'
    assert current['timeval_raw'] == RAW


def test_exact_boot_identity_and_zero_calendar_difference():
    identity = h.parse_boot(UUID, RAW)
    assert h.same_boot(UUID, identity, anchor_ns=identity['boot_timeval_ns']) == 0


def test_other_boot_fails_even_with_identical_calendar_value():
    current = h.parse_boot(OTHER, RAW)
    with pytest.raises(ValueError, match='uuid_mismatch'):
        h.same_boot(UUID, current, legacy_epoch=EPOCH)


def test_material_calendar_change_fails_with_same_uuid():
    current = h.parse_boot(UUID, '{ sec = 1793829800, usec = 0 }')
    with pytest.raises(ValueError, match='calendar_discrepancy'):
        h.same_boot(UUID, current, legacy_epoch=EPOCH)
    current = h.parse_boot(UUID, RAW)
    with pytest.raises(ValueError, match='calendar_discrepancy'):
        h.same_boot(UUID, current, anchor_ns=current['boot_timeval_ns']-MAX_CLOCK_DELTA_NS-1)


@pytest.mark.parametrize('uuid_value,timeval', [
    ('', RAW), ('invalid', RAW), (UUID, ''), (UUID, '{ sec = 1, usec = 1000000 }'),
    (UUID, '{ sec = nan, usec = 0 }'), (None, RAW),
])
def test_malformed_os_boot_values_fail(uuid_value, timeval):
    with pytest.raises(ValueError):
        h.parse_boot(uuid_value, timeval)


def test_boot_change_between_os_reads_fails():
    values = iter([UUID, RAW, OTHER])
    with pytest.raises(ValueError, match='during_read'):
        h.read_boot(lambda args: next(values))


@pytest.mark.parametrize('value', [None, True, '1793829796', -1])
def test_malformed_legacy_anchor_fails(value):
    with pytest.raises(ValueError):
        h.same_boot(UUID, h.parse_boot(UUID, RAW), legacy_epoch=value)


def test_missing_or_tampered_amendment_fails(tmp_path):
    p = tmp_path/'amendment.json'
    p.write_text('{}')
    with pytest.raises(ValueError, match='hash_mismatch'):
        h.require_amended_endurance(tmp_path, tmp_path/'missing', p, '0'*64)
    with pytest.raises((FileNotFoundError, ValueError, KeyError)):
        h.require_amended_endurance(tmp_path, tmp_path/'missing', p, h.file_sha256(p))


@pytest.mark.parametrize('uuid_value,timeval,passes', [
    (UUID, RAW, True),
    (OTHER, RAW, False),
    (UUID, '{ sec = 1793829800, usec = 0 }', False),
])
def test_power_guard_keeps_uuid_and_material_calendar_checks(monkeypatch, uuid_value, timeval, passes):
    current = h.parse_boot(uuid_value, timeval)
    monkeypatch.setattr(h, 'power_state', lambda *a, **k: dict(
        boot_epoch_seconds=current['boot_epoch_seconds'], ac_power=True, lid_open=True))
    guard = h.UUIDPowerGuard(Path('/unused'), {})
    guard.process = SimpleNamespace(pid=88, poll=lambda: None)
    guard.state = dict(power_settings='settings', boot_timeval_anchor_ns=EPOCH*10**9+914699000)
    guard.cached = dict(boot_uuid=UUID)
    def read(args):
        if args[-1] == 'kern.bootsessionuuid':
            return uuid_value
        if args[-1] == 'kern.boottime':
            return timeval
        if args[-1] == 'custom':
            return 'settings'
        return ' pid 88(caffeinate): PreventUserIdleSystemSleep\n pid 88(caffeinate): PreventSystemSleep\n'
    guard.read = read
    if passes:
        assert guard._snapshot()['boot_uuid'] == UUID
    else:
        with pytest.raises(ValueError):
            guard._snapshot()


def test_harness_only_allows_additions_not_frozen_file_edits(tmp_path, monkeypatch):
    repo = tmp_path/'repo'
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('init','-b','dynapm')
    (repo/'science.txt').write_text('frozen')
    git('add','.')
    git('-c','user.name=UNIT','-c','user.email=unit@example.invalid','commit','-m','base')
    base = git('rev-parse','HEAD')
    monkeypatch.setattr(h,'SCIENTIFIC_SOURCE',base)
    for name in h.ADDITIONS:
        path=repo/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('UNIT = 1\n')
    git('add','.')
    git('-c','user.name=UNIT','-c','user.email=unit@example.invalid','commit','-m','harness')
    proof=h.harness_source(repo)
    assert proof['frozen_scientific_source']==base
    assert proof['execution_harness_commit']==git('rev-parse','HEAD')
    (repo/'science.txt').write_text('changed')
    git('add','.')
    git('-c','user.name=UNIT','-c','user.email=unit@example.invalid','commit','-m','invalid')
    with pytest.raises(ValueError,match='scientific_source_changed'):
        h.harness_source(repo)


def test_primary_execution_keeps_frozen_transport_and_policy_calls():
    """The new manifest provenance is the only execution-path delta."""
    import ast
    import inspect
    from dynapm.scripts.task41_bounded_v8 import run_one
    from dynapm.scripts.task45_v8_host_harness import run_primary
    expected = inspect.getsource(run_one)
    expected = expected.replace('def run_one(', 'def run_primary(')
    expected = expected.replace('    require_endurance(repo,args.host_endurance_run)',
        "    provenance = harness_source(repo)\n    require_amended_endurance(repo,args.host_endurance_run,args.amendment,args.amendment_sha256)")
    expected = expected.replace('campaign = identity(repo,root,contract_sha,design)',
        'campaign = scientific_binding(repo,root,contract_sha,design)')
    expected = expected.replace('replacement=replacement)',
        'replacement=replacement, harness_provenance=dict(provenance,\n                  host_identity_amendment_sha256=args.amendment_sha256))')
    expected = expected.replace("source_commit=campaign['source_commit'],experiment_fingerprint",
        "source_commit=provenance['execution_harness_commit'],frozen_scientific_source=SCIENTIFIC_SOURCE,experiment_fingerprint")
    expected = expected.replace('with ManagedPowerGuard(run,context)', 'with UUIDPowerGuard(run,context)')
    expected = expected.replace("clean_source(repo)!=campaign['source_commit']",
        "clean_source(repo)!=provenance['execution_harness_commit']")
    assert ast.dump(ast.parse(inspect.getsource(run_primary)), include_attributes=False) == ast.dump(ast.parse(expected), include_attributes=False)
