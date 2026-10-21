"""Synthetic provenance/cache tests; no scientific evaluation or training."""
from dataclasses import asdict, replace
from enum import Enum
import importlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from dynapm.core.provenance import (canonical_json, fingerprint, file_sha256, read_json,
    SourceProvenance, EnvironmentProvenance, DataConfig, ModelConfig, PolicyConfig,
    ExperimentConfigProvenance, ExperimentManifest, CohortManifest, CohortEntity,
    dataset_from_dict, cohort_from_dict, experiment_from_dict, prepare_experiment,
    PROVENANCE_SCHEMA, OUTPUT_SCHEMA)
from dynapm.core.run_store import (RunSession, RunPurpose, OutputSpec,
    build_output_manifest, check_cache, load_verified_output, write_json)
from dynapm.data.manifests import build_dataset_manifest, check_dataset, materna_manifest, materna_cohort


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)


@pytest.fixture
def inputs(tmp_path):
    repo = tmp_path/'repo'
    (repo/'dynapm').mkdir(parents=True)
    (repo/'dynapm/model.py').write_text('x = 1\n')
    (repo/'.gitignore').write_text('results/\n')
    git(repo, 'init', '-b', 'dynapm')
    git(repo, 'add', '.')
    git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    raw = tmp_path/'raw'
    (raw/'Trace-A').mkdir(parents=True)
    for i in (1, 2):
        (raw/'Trace-A'/f'{i}.csv').write_text(f'x\n{i}\n')
    dataset = build_dataset_manifest(raw, dataset_id='fixture', source_name='synthetic',
        trace_names=('Trace-A',), schema_identity='fixture-schema-v1')
    cohort = CohortManifest('fixture', dataset.sha256, 'fixture-filter-v1', {'minimum_observations': 1},
        tuple(CohortEntity('Trace-A', str(i), True, None, 1) for i in (1, 2)), 'metadata-only-time')
    config = ExperimentConfigProvenance(DataConfig('fixture', minimum_observations=1), ModelConfig(),
        (PolicyConfig('periodic_predictor_6h_v2', periodic_interval_hours=6),))
    exp, env = prepare_experiment(repo, raw, config, dataset, cohort, {'model': 42, 'bootstrap': 42})
    return repo, raw, exp, env


def completed(tmp_path, inputs, purpose='smoke', **kwargs):
    repo, raw, exp, env = inputs
    with RunSession(tmp_path/'results', exp, env, repo=repo, dataset_root=raw, purpose=purpose,
        required_outputs=[OutputSpec('outputs/result.json', 'synthetic-integrity-fixture')], **kwargs) as session:
        write_json(session.path/'outputs/result.json', {'fixture': [1, 2, 3]})
        session.complete()
    return session


def test_stable_serialization_and_explicit_types(inputs):
    class Choice(str, Enum):
        A = 'a'
    a = {'z': [Path('settings/model.json'), Choice.A], 'a': 1}
    b = {'a': 1, 'z': ['settings/model.json', 'a']}
    assert canonical_json(a) == canonical_json(b)
    assert fingerprint(a) == fingerprint(b)
    _, _, exp, _ = inputs
    assert experiment_from_dict(json.loads(canonical_json(exp))).fingerprint == exp.fingerprint
    assert canonical_json(exp.config) == canonical_json(exp.config)
    with pytest.raises(TypeError):
        canonical_json(object())
    with pytest.raises(TypeError):
        canonical_json({1: 'not a JSON key'})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_numbers_rejected(value):
    with pytest.raises(ValueError):
        canonical_json({'x': value})


@pytest.mark.parametrize('change', ['period', 'trees', 'protocol', 'accounting', 'seed', 'preprocessing',
                                    'feature', 'cadence', 'target', 'statistics', 'source_commit'])
def test_every_scientific_dimension_changes_fingerprint(inputs, change):
    _, _, exp, _ = inputs
    changed = exp
    if change == 'period':
        changed = replace(exp, config=replace(exp.config, policies=(replace(exp.config.policies[0], periodic_interval_hours=3),)))
    elif change == 'trees':
        changed = replace(exp, config=replace(exp.config, model=replace(exp.config.model, n_estimators=201)))
    elif change == 'protocol':
        changed = replace(exp, protocol_version='different-protocol')
    elif change == 'accounting':
        changed = replace(exp, accounting_schema='different-accounting')
    elif change == 'seed':
        changed = replace(exp, seeds={'model': 100})
    elif change == 'preprocessing':
        changed = replace(exp, config=replace(exp.config, preprocessing={'missingness': 'different'}))
    elif change == 'feature':
        changed = replace(exp, config=replace(exp.config, model=replace(exp.config.model, feature_specification={'lags': [2]})))
    elif change == 'cadence':
        changed = replace(exp, config=replace(exp.config, data=replace(exp.config.data, evaluation_cadence_seconds=21600)))
    elif change == 'target':
        changed = replace(exp, config=replace(exp.config, model=replace(exp.config.model, targets=('CPU usage [%]',))))
    elif change == 'statistics':
        changed = replace(exp, config=replace(exp.config, statistics=replace(exp.config.statistics, confidence_level=.99)))
    else:
        changed = replace(exp, source=replace(exp.source, commit='f'*40))
    assert changed.fingerprint != exp.fingerprint


def test_dataset_relocation_generation_time_and_byte_change(inputs, tmp_path):
    _, raw, exp, _ = inputs
    other = tmp_path/'another-location'
    shutil.copytree(raw, other)
    def manifest(root):
        return build_dataset_manifest(root, dataset_id='fixture', source_name='synthetic',
            trace_names=('Trace-A',), schema_identity='fixture-schema-v1')
    relocated = manifest(other)
    assert relocated.generated_at != exp.dataset.generated_at
    assert relocated.sha256 == exp.dataset.sha256
    assert replace(exp, dataset=relocated).fingerprint == exp.fingerprint
    (other/'Trace-A/1.csv').write_text('x\n9\n')
    changed = manifest(other)
    assert changed.sha256 != exp.dataset.sha256
    changed_cohort = replace(exp.cohort, dataset_manifest_sha256=changed.sha256)
    assert replace(exp, dataset=changed, cohort=changed_cohort).fingerprint != exp.fingerprint
    with pytest.raises(ValueError, match='dataset_mismatch'):
        check_dataset(other, exp.dataset)
    (raw/'Trace-A/3.csv').write_text('x\n3\n')
    with pytest.raises(ValueError, match='dataset_mismatch'):
        check_dataset(raw, exp.dataset)


def test_cohort_removal_changes_identity(inputs):
    _, _, exp, _ = inputs
    cohort = replace(exp.cohort, entities=exp.cohort.entities[:1])
    assert cohort.sha256 != exp.cohort.sha256
    assert replace(exp, cohort=cohort).fingerprint != exp.fingerprint


def test_dirty_source_tracked_and_untracked_identity(inputs):
    repo, _, exp, _ = inputs
    assert not exp.source.dirty
    (repo/'dynapm/model.py').write_text('x = 2\n')
    src = SourceProvenance.capture(repo)
    assert src.dirty and src.tracked_diff_sha256 and src.scientific_diff_sha256
    assert replace(exp, source=src).fingerprint != exp.fingerprint
    (repo/'dynapm/new.py').write_text('new = 1\n')
    new = SourceProvenance.capture(repo)
    assert [f.path for f in new.untracked_scientific_files] == ['dynapm/new.py']
    assert replace(exp, source=new).fingerprint != replace(exp, source=src).fingerprint
    assert SourceProvenance.capture(repo).identity() == new.identity()


def test_source_checkout_relocation_and_branch_metadata(inputs, tmp_path):
    repo, _, exp, _ = inputs
    other = tmp_path/'clone'
    subprocess.run(['git', 'clone', '-q', str(repo), str(other)], check=True)
    assert SourceProvenance.capture(other).identity() == exp.source.identity()
    assert replace(exp, source=replace(exp.source, branch='different-label')).fingerprint == exp.fingerprint


def test_hostname_and_output_root_do_not_affect_fingerprint(inputs, tmp_path):
    _, _, exp, env = inputs
    other = replace(env, execution=dict(env.execution, hostname='other-host'))
    assert other.scientific == env.scientific
    assert replace(exp, scientific_environment=other.scientific).fingerprint == exp.fingerprint
    a = completed(tmp_path, inputs)
    b = completed(tmp_path/'elsewhere', inputs)
    assert a.manifest.experiment_fingerprint == b.manifest.experiment_fingerprint
    assert a.manifest.run_id != b.manifest.run_id
    relocated = tmp_path/'moved-run'
    shutil.copytree(a.path, relocated)
    assert check_cache(relocated, exp, 'smoke').reusable


@pytest.mark.parametrize('path', ['/absolute/location', 'C:\\machine\\input'])
def test_absolute_configuration_paths_rejected(inputs, path):
    _, _, exp, _ = inputs
    with pytest.raises(ValueError, match='absolute filesystem'):
        replace(exp.config, preprocessing={'input': path}).sha256


def test_output_manifest_is_deterministic(tmp_path):
    (tmp_path/'outputs').mkdir(); (tmp_path/'logs').mkdir()
    write_json(tmp_path/'outputs/a.json', {'a': 1})
    (tmp_path/'outputs/b.csv').write_text('x\n1\n2\n')
    a = OutputSpec('outputs/a.json', 'fixture')
    b = OutputSpec('outputs/b.csv', 'fixture-table')
    first = build_output_manifest(tmp_path, [a, b])
    second = build_output_manifest(tmp_path, [b, a])
    assert first.sha256 == second.sha256
    assert first.files[1].row_count == 2
    assert first.files[1].table_schema == ('x',)


@pytest.mark.parametrize('tamper', ['missing_success', 'json_byte', 'missing_output', 'extra_output',
    'unsupported_manifest', 'unsupported_output_schema', 'metadata', 'marker', 'legacy_json'])
def test_cache_rejects_incomplete_corrupt_and_legacy_runs(inputs, tmp_path, tamper):
    session = completed(tmp_path, inputs)
    root, exp = session.path, inputs[2]
    assert check_cache(root, exp, 'smoke').reusable
    if tamper == 'missing_success':
        (root/'SUCCESS').unlink()
    elif tamper == 'json_byte':
        (root/'outputs/result.json').write_text('{"fixture":[1,2,4]}')
    elif tamper == 'missing_output':
        (root/'outputs/result.json').unlink()
    elif tamper == 'extra_output':
        (root/'outputs/unlisted.txt').write_text('not declared')
    elif tamper == 'unsupported_manifest':
        data = read_json(root/'manifest.json'); data['schema_version'] = 'future'
        write_json(root/'manifest.json', data)
    elif tamper == 'unsupported_output_schema':
        data = read_json(root/'output_manifest.json'); data['schema_version'] = 'future'
        write_json(root/'output_manifest.json', data)
    elif tamper == 'metadata':
        data = read_json(root/'config.json'); data['model']['n_estimators'] += 1
        write_json(root/'config.json', data)
    elif tamper == 'marker':
        write_json(root/'SUCCESS', {'manifest_sha256': 'f'*64})
    else:
        (root/'manifest.json').unlink()
        write_json(root/'old_result.json', {'total_updates': 4})
    verdict = check_cache(root, exp, 'smoke')
    assert not verdict.reusable
    if tamper in ['json_byte', 'missing_output', 'extra_output']:
        assert 'output_hash_mismatch' in verdict.reasons
    if tamper == 'missing_success':
        assert 'incomplete_run' in verdict.reasons
    if tamper in ['unsupported_manifest', 'unsupported_output_schema']:
        assert 'unsupported_manifest_schema' in verdict.reasons


@pytest.mark.parametrize('dimension,reason', [('config', 'config_mismatch'), ('protocol', 'protocol_mismatch'),
    ('accounting', 'accounting_schema_mismatch'), ('environment', 'environment_mismatch'),
    ('source', 'source_commit_mismatch'), ('cohort', 'cohort_mismatch'), ('seed', 'seed_mismatch')])
def test_compatibility_dimensions_have_explicit_reasons(inputs, tmp_path, dimension, reason):
    session = completed(tmp_path, inputs)
    exp = inputs[2]
    if dimension == 'config':
        expected = replace(exp, config=replace(exp.config, model=replace(exp.config.model, n_estimators=123)))
    elif dimension == 'protocol':
        expected = replace(exp, protocol_version='future')
    elif dimension == 'accounting':
        expected = replace(exp, accounting_schema='future')
    elif dimension == 'source':
        expected = replace(exp, source=replace(exp.source, commit='f'*40))
    elif dimension == 'cohort':
        expected = replace(exp, cohort=replace(exp.cohort, entities=exp.cohort.entities[:1]))
    elif dimension == 'seed':
        expected = replace(exp, seeds={'model': 7})
    else:
        environment = json.loads(canonical_json(exp.scientific_environment))
        environment['packages']['numpy'] = 'different-version'
        expected = replace(exp, scientific_environment=environment)
    assert reason in check_cache(session.path, expected, 'smoke').reasons


def test_pilot_and_smoke_cannot_supply_claim_cache(inputs, tmp_path):
    for purpose in ('pilot', 'smoke'):
        run = completed(tmp_path/purpose, inputs, purpose)
        assert not run.manifest.claim_eligible
        decision = check_cache(run.path, inputs[2], 'claim')
        assert not decision.reusable and 'run_purpose_mismatch' in decision.reasons
    claim = completed(tmp_path/'claim', inputs, 'claim')
    assert claim.manifest.claim_eligible
    assert check_cache(claim.path, inputs[2], 'claim').reusable


def test_dirty_claim_requires_override_and_remains_noncanonical(inputs, tmp_path):
    repo, raw, exp, env = inputs
    (repo/'dynapm/model.py').write_text('x = 3\n')
    exp = replace(exp, source=SourceProvenance.capture(repo))
    dirty = (repo, raw, exp, env)
    with pytest.raises(ValueError, match='dirty_source'):
        completed(tmp_path/'blocked', dirty, 'claim')
    run = completed(tmp_path/'development', dirty, 'claim', allow_dirty=True)
    assert not run.manifest.claim_eligible and run.manifest.allow_dirty
    assert 'dirty_source' in check_cache(run.path, exp, 'claim').reasons
    assert check_cache(completed(tmp_path/'smoke', dirty).path, exp, 'smoke').reusable


def test_failed_and_partial_runs_never_succeed(inputs, tmp_path):
    repo, raw, exp, env = inputs
    session = RunSession(tmp_path/'results', exp, env, repo=repo, dataset_root=raw, purpose='smoke',
        required_outputs=[OutputSpec('outputs/missing.json', 'required')])
    with pytest.raises(ValueError, match='inventory'):
        with session:
            session.complete()
    assert (session.path/'FAILED').is_file() and not (session.path/'SUCCESS').exists()
    assert read_json(session.path/'manifest.json')['error']['type'] == 'ValueError'
    assert not check_cache(session.path, exp, 'smoke').reusable


def test_source_or_dataset_change_during_run_prevents_completion(inputs, tmp_path):
    repo, raw, exp, env = inputs
    for kind in ['source', 'dataset']:
        session = RunSession(tmp_path/kind, exp, env, repo=repo, dataset_root=raw, purpose='smoke',
            required_outputs=[OutputSpec('outputs/result.json', 'required')])
        with pytest.raises(ValueError):
            with session:
                write_json(session.path/'outputs/result.json', {'fixture': True})
                if kind == 'source':
                    (repo/'dynapm/model.py').write_text('changed\n')
                else:
                    (raw/'Trace-A/1.csv').write_text('changed\n')
                session.complete()
        assert not (session.path/'SUCCESS').exists()
        if kind == 'source':
            (repo/'dynapm/model.py').write_text('x = 1\n')


def test_verified_output_cannot_escape_inventory(inputs, tmp_path):
    run = completed(tmp_path, inputs)
    assert load_verified_output(run.path, inputs[2], 'smoke', 'outputs/result.json').is_file()
    with pytest.raises(ValueError, match='output_not_in_manifest'):
        load_verified_output(run.path, inputs[2], 'smoke', 'config.json')
    (run.path/'outputs/result.json').unlink()
    (run.path/'outputs/result.json').symlink_to(tmp_path/'outside')
    assert not check_cache(run.path, inputs[2], 'smoke').reusable


def test_package_resolution_failure_is_loud(monkeypatch):
    from dynapm.core import provenance
    def missing(name):
        raise provenance.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(provenance.metadata, 'version', missing)
    with pytest.raises(RuntimeError, match='required scientific package unresolved'):
        EnvironmentProvenance.capture()


@pytest.mark.parametrize('script', ['task04_full_corpus_predictor', 'task04_ground_truth',
    'task04_ground_truth_stats', 'task15_full_corpus', 'task18_paper_packaging',
    'run_bootstrap_characterization'])
def test_unmanaged_legacy_entrypoints_refuse_before_io(script, monkeypatch):
    module = importlib.import_module('dynapm.scripts.'+script)
    with pytest.raises(ValueError, match='unversioned_workflow_rejected'):
        module.main()


def test_materna_manifest_cohort_and_cli_are_readonly(tmp_path, capsys):
    from dynapm.data.loader import SCHEMA_COLUMNS
    from dynapm.scripts.provenance import main
    root = tmp_path/'data'
    for n in (1, 2, 3):
        p = root/f'Materna-Trace-{n}'; p.mkdir(parents=True)
        (p/'00-Trace-Info.txt').write_text('synthetic trace metadata')
        for vm, count in [('1', 3), ('2', 1)]:
            rows = [';'.join(SCHEMA_COLUMNS)]
            rows += [';'.join([f'01.01.2021 00:{i*5:02d}:00', *(['1']*12)]) for i in range(count)]
            (p/f'{vm}.csv').write_text('\n'.join(rows)+'\n')
    before = {str(p): file_sha256(p) for p in root.rglob('*') if p.is_file()}
    dataset = materna_manifest(root)
    cohort = materna_cohort(root, dataset, minimum_observations=3)
    assert dataset.file_count == 9 and sum(e.included for e in cohort.entities) == 3
    assert cohort_from_dict(json.loads(canonical_json(cohort))).sha256 == cohort.sha256
    dpath, cpath = tmp_path/'dataset.json', tmp_path/'cohort.json'
    assert main(['manifest-dataset', '--root', str(root), '--output', str(dpath)]) == 0
    assert main(['check-dataset', '--root', str(root), '--manifest', str(dpath)]) == 0
    assert main(['manifest-cohort', '--root', str(root), '--dataset', str(dpath),
                 '--minimum-observations', '3', '--output', str(cpath)]) == 0
    assert dataset_from_dict(read_json(dpath)).sha256 == dataset.sha256
    assert before == {str(p): file_sha256(p) for p in root.rglob('*') if p.is_file()}


def test_cli_fingerprint_and_cache_explanation(inputs, tmp_path, capsys):
    from dynapm.scripts.provenance import main
    run = completed(tmp_path, inputs)
    path = tmp_path/'experiment.json'; write_json(path, inputs[2])
    assert main(['fingerprint', '--experiment', str(path)]) == 0
    assert main(['validate-run', '--run', str(run.path), '--experiment', str(path), '--purpose', 'smoke']) == 0
    (run.path/'SUCCESS').unlink()
    assert main(['explain-cache', '--run', str(run.path), '--experiment', str(path), '--purpose', 'smoke']) == 2
    assert 'incomplete_run' in capsys.readouterr().out


def test_ancillary_backup_is_recorded_but_not_a_scientific_input(tmp_path):
    root = tmp_path/'raw'
    for n in (1, 2, 3):
        p = root/f'Materna-Trace-{n}'; p.mkdir(parents=True)
        (p/'1.csv').write_text('raw input')
        (p/'00-Trace-Info.txt').write_text('source metadata')
    a = materna_manifest(root)
    (root/'Materna-Trace-1/1.bak').write_text('not consumed')
    b = materna_manifest(root)
    assert a.sha256 == b.sha256 and a.file_count == b.file_count == 6
    assert len(b.ancillary_files) == 1
    assert b.ancillary_files[0].role == 'ancillary_not_loaded'
    assert dataset_from_dict(json.loads(canonical_json(b))).sha256 == b.sha256


def test_dataset_mismatch_cache_reason(inputs, tmp_path):
    run = completed(tmp_path, inputs)
    repo, raw, exp, env = inputs
    (raw/'Trace-A/1.csv').write_text('different')
    d = build_dataset_manifest(raw, dataset_id='fixture', source_name='synthetic',
        trace_names=('Trace-A',), schema_identity='fixture-schema-v1')
    other = replace(exp, dataset=d, cohort=replace(exp.cohort, dataset_manifest_sha256=d.sha256))
    assert 'dataset_mismatch' in check_cache(run.path, other, 'smoke').reasons


def test_unlisted_root_file_and_duplicate_json_keys_rejected(inputs, tmp_path):
    run = completed(tmp_path, inputs)
    (run.path/'unlisted.json').write_text('{}')
    assert 'run_inventory_mismatch' in check_cache(run.path, inputs[2], 'smoke').reasons
    p = tmp_path/'duplicate.json'; p.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match='duplicate JSON key'):
        read_json(p)


def test_explicit_timing_hardware_compatibility():
    env = EnvironmentProvenance.capture(execution_compatibility_keys=('logical_cpus',))
    assert env.scientific['execution_compatibility']['logical_cpus'] == env.execution['logical_cpus']
    with pytest.raises(ValueError, match='hostname/time/location'):
        EnvironmentProvenance.capture(execution_compatibility_keys=('hostname',))
    with pytest.raises(ValueError, match='cannot be disabled'):
        EnvironmentProvenance.capture(scientific_packages=('numpy',))


@pytest.mark.parametrize('name', ['task17b_provisioning', 'task18b_corpus_churn_rerun'])
def test_argparse_legacy_entrypoints_refuse_but_help_survives(name, monkeypatch):
    import sys
    module = importlib.import_module('dynapm.scripts.'+name)
    monkeypatch.setattr(sys, 'argv', [name])
    with pytest.raises(ValueError, match='unversioned_workflow_rejected'):
        module.main()
    monkeypatch.setattr(sys, 'argv', [name, '--help'])
    with pytest.raises(SystemExit) as outcome:
        module.main()
    assert outcome.value.code == 0


def test_observed_row_lag_semantics_across_a_gap_are_explicit():
    import pandas as pd
    from dynapm.core.features import build_features
    index = pd.date_range('2021-01-01', periods=100, freq='5min')
    index = index[:99].append(pd.DatetimeIndex([index[-1]+pd.Timedelta(hours=20)]))
    frame = pd.DataFrame({'CPU usage [%]': range(100)}, index=index)
    features = build_features(frame, 'CPU usage [%]')
    assert index[-1] not in features.index
    assert features.iloc[-1]['target_lag_1'] == 97
    assert index[-1]-index[-2] > pd.Timedelta(hours=20)
    assert DataConfig('fixture').lag_semantics == 'exact-nominal-five-minute-complete-history-v1'


def test_cli_prepare_experiment_and_rejected_dirty_creation(inputs, tmp_path):
    from dynapm.scripts.provenance import main
    repo, raw, exp, env = inputs
    paths = {}
    for key, value in [('config', exp.config), ('dataset', exp.dataset), ('cohort', exp.cohort)]:
        p = tmp_path/(key+'.json'); write_json(p, value); paths[key] = p
    output = tmp_path/'prepared.json'
    args = ['prepare-experiment', '--repo', str(repo), '--dataset-root', str(raw), '--output', str(output)]
    for key, path in paths.items():
        args += ['--'+key, str(path)]
    assert main(args) == 0
    assert experiment_from_dict(read_json(output)).fingerprint == exp.fingerprint
    (raw/'Trace-A/1.csv').write_text('changed')
    assert main(args) == 2


def test_old_threshold_lookup_is_not_a_provenance_bypass():
    from dynapm.scripts.task04_ground_truth import _threshold_map
    with pytest.raises(ValueError, match='unversioned_workflow_rejected'):
        _threshold_map()


def test_managed_production_replay_remains_a_smoke_not_a_claim(replay_repo, tmp_path):
    from dynapm.eval.runner_v2 import run_method_on_vm
    from dynapm.methods.factories import policy_factory
    from dynapm.data.manifests import MATERNA_SCHEMA
    # Existing 720-row synthetic fixture; Static fits no predictor.
    data = build_dataset_manifest(replay_repo/'data/raw', dataset_id='synthetic-replay',
        source_name='synthetic-test-only', trace_names=('TestTrace',), schema_identity=MATERNA_SCHEMA)
    cohort = CohortManifest(data.dataset_id, data.sha256, 'test-only', {'minimum_observations': 1},
        (CohortEntity('TestTrace', '1', True, None, 720),), 'metadata-only')
    config = ExperimentConfigProvenance(DataConfig(data.dataset_id, minimum_observations=1),
        ModelConfig(family='unused-observation-only'), (PolicyConfig('static_v2'),))
    repo = Path(__file__).resolve().parents[2]
    exp, env = prepare_experiment(repo, replay_repo/'data/raw', config, data, cohort,
                                   {'model': 42, 'bootstrap': 42})
    with RunSession(tmp_path/'managed', exp, env, repo=repo, dataset_root=replay_repo/'data/raw',
        purpose='smoke', required_outputs=[OutputSpec('outputs/static.json', 'synthetic-policy-replay')]) as run:
        result = run_method_on_vm('TestTrace', '1', policy_factory('static_v2'), repo_root=replay_repo)
        write_json(run.path/'outputs/static.json', result)
        run.complete()
    assert check_cache(run.path, exp, 'smoke').reusable
    assert not check_cache(run.path, exp, 'claim').reusable
    assert read_json(run.path/'outputs/static.json')['n_refresh_events'] == 0


@pytest.mark.parametrize('payload', [[], 'not a manifest', {'schema_version': PROVENANCE_SCHEMA}])
def test_malformed_manifest_returns_rejection_not_crash(inputs, tmp_path, payload):
    run = completed(tmp_path, inputs)
    write_json(run.path/'manifest.json', payload)
    assert not check_cache(run.path, inputs[2], 'smoke').reusable


def test_output_parquet_schema_and_caught_failure_metadata(inputs, tmp_path):
    import pandas as pd
    repo, raw, exp, env = inputs
    with RunSession(tmp_path/'success', exp, env, repo=repo, dataset_root=raw, purpose='smoke',
        required_outputs=[OutputSpec('outputs/table.parquet', 'synthetic-table')]) as run:
        pd.DataFrame({'x': [1, 2]}).to_parquet(run.path/'outputs/table.parquet', index=False)
        run.complete(failures=[{'entity': 'test-only', 'reason': 'synthetic child failure record'}])
    out = read_json(run.path/'output_manifest.json')['files'][0]
    assert out['row_count'] == 2 and out['table_schema'] == [['x', 'int64']]
    assert read_json(run.path/'manifest.json')['failures'][0]['entity'] == 'test-only'
    session = RunSession(tmp_path/'fail', exp, env, repo=repo, dataset_root=raw, purpose='smoke',
        required_outputs=[OutputSpec('outputs/result.json', 'required')])
    with pytest.raises(RuntimeError, match='synthetic crash'):
        with session:
            raise RuntimeError('synthetic crash')
    assert (session.path/'FAILED').is_file() and not (session.path/'SUCCESS').exists()


def test_missing_complete_cannot_silently_succeed(inputs, tmp_path):
    repo, raw, exp, env = inputs
    session = RunSession(tmp_path/'incomplete', exp, env, repo=repo, dataset_root=raw, purpose='smoke',
        required_outputs=[OutputSpec('outputs/result.json', 'required')])
    with pytest.raises(RuntimeError, match='complete.*was not called'):
        with session:
            write_json(session.path/'outputs/result.json', {'fixture': True})
    assert not (session.path/'SUCCESS').exists()


def test_git_diff_user_preferences_do_not_change_scientific_identity(inputs):
    repo, _, exp, _ = inputs
    (repo/'dynapm/model.py').write_text('x = 2\n')
    before = SourceProvenance.capture(repo)
    git(repo, 'config', 'diff.context', '17')
    git(repo, 'config', 'diff.algorithm', 'histogram')
    git(repo, 'config', 'color.ui', 'always')
    assert SourceProvenance.capture(repo).identity() == before.identity()


def test_staging_the_same_scientific_bytes_does_not_change_fingerprint(inputs):
    repo, raw, exp, env = inputs
    (repo/'dynapm/new.py').write_text('new = 1\n')
    before = SourceProvenance.capture(repo)
    assert before.untracked_scientific_files
    git(repo, 'add', 'dynapm/new.py')
    after = SourceProvenance.capture(repo)
    assert not after.untracked_scientific_files
    assert before.identity() == after.identity()
    assert replace(exp, source=before).fingerprint == replace(exp, source=after).fingerprint


def test_scientific_import_failure_is_not_complete_provenance(monkeypatch):
    from dynapm.core import provenance
    original = provenance.importlib.import_module
    def broken(name):
        if name == 'numpy':
            raise ImportError('synthetic broken binary')
        return original(name)
    monkeypatch.setattr(provenance.importlib, 'import_module', broken)
    with pytest.raises(RuntimeError, match='package import failed'):
        EnvironmentProvenance.capture()


def test_claim_cache_eligibility_has_no_override_escape_hatch(inputs, tmp_path):
    run = completed(tmp_path, inputs, 'claim', allow_dirty=True)
    assert run.manifest.classification == 'DEVELOPMENT_NONCANONICAL'
    decision = check_cache(run.path, inputs[2], 'claim')
    assert not decision.reusable and 'noncanonical_run' in decision.reasons
    with pytest.raises(TypeError):
        check_cache(run.path, inputs[2], 'claim', canonical_required=False)
