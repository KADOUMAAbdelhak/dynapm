"""Managed 18-VM DEVELOPMENT pilot. No full-corpus execution path exists here."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import time

import pandas as pd

from dynapm.core.provenance import (SourceProvenance, canonical_json, fingerprint, prepare_experiment,
    read_json, config_from_dict)
from dynapm.core.run_store import RunSession, OutputSpec, check_cache, write_json
from dynapm.data.manifests import materna_manifest, check_dataset
from dynapm.experiments.pilot_design import (default_config, characterize_inputs, select_pilot,
    pilot_cohort_manifest, guard_cohort, summarize_gaps)
from dynapm.experiments.pilot_execution import run_vm, validate_config
from dynapm.experiments.gap_eligibility import audit_dataset

OUTPUTS = {
    'materna_gap_eligibility_v3.parquet': 'all-retained-metadata-only-gap-eligibility',
    'materna_gap_eligibility_v3.json': 'gap-safe-protocol-feasibility-summary',
    'pilot_cohort.json': 'permanent-development-pilot-selection',
    'pilot_cohort.parquet': 'development-pilot-selection-table',
    'selection_pool.parquet': 'bootstrap-only-selection-pool',
    'per_vm_results.parquet': 'exploratory-pilot-method-vm-results',
    'refresh_events.parquet': 'canonical-maintenance-events',
    'evaluation_records.parquet': 'shared-snapshot-verification-evidence',
    'matched_budget_schedule.parquet': 'nonadaptive-budget-extra-timestamps',
    'materna_gap_audit.parquet': 'timestamp-only-all-retained-gap-audit',
    'materna_gap_audit.json': 'gap-summary-and-preconfirmation-decision',
    'pilot_diagnostics.json': 'exact-invariants-and-runtime-diagnostics',
    'pilot_summary.json': 'descriptive-only-development-summary',
}


def integrity_probes(path, exp):
    """Validate canonical bytes; tamper only with an isolated disposable COPY."""
    exact = check_cache(path, exp, 'pilot')
    altered_policy = replace(exp.config.policies[0], periodic_interval_hours=4)
    altered = replace(exp, config=replace(exp.config,
        policies=(altered_policy, *exp.config.policies[1:])))
    mutation = check_cache(path, altered, 'pilot')
    claim = check_cache(path, exp, 'claim')
    with tempfile.TemporaryDirectory(prefix='dynapm-pilot-tamper-') as tmp:
        copy = Path(tmp)/'run'
        # Copy metadata and a hardlink-free byte copy of every artifact.
        shutil.copytree(path, copy)
        output = copy/'outputs/pilot_summary.json'
        output.write_bytes(output.read_bytes()+b' ')
        tamper = check_cache(copy, exp, 'pilot')
    assert exact.reusable and not mutation.reusable and not tamper.reusable and not claim.reusable
    assert 'config_mismatch' in mutation.reasons and 'output_hash_mismatch' in tamper.reasons
    assert check_cache(path, exp, 'pilot').reusable
    return {'exact_pilot': exact.reusable, 'changed_config': mutation.reasons,
            'tampered_copy': tamper.reasons, 'claim_request': claim.reasons}


def execute(repo, config, *, workers=2):
    """Selection/gap preparation is read-only; all 198 evaluations are managed."""
    repo = Path(repo).resolve()
    source = SourceProvenance.capture(repo)
    if source.dirty:
        raise ValueError('pilot requires clean committed source; no --allow-dirty override')
    if not 1 <= workers <= 4:
        raise ValueError('bounded pilot permits 1..4 VM workers')
    validate_config(config)
    preparation_start = time.perf_counter()
    raw = repo/'data/raw'
    dataset = materna_manifest(raw)
    pool, gaps = characterize_inputs(raw, dataset, config)
    selected, tier_metadata = select_pilot(pool)
    guard_cohort(selected)
    expected = {'Materna-Trace-1': {'374','213','96','64','143','76'},
                'Materna-Trace-2': {'396','207','388','398','516','11'},
                'Materna-Trace-3': {'212','151','83','133','224','127'}}
    if {t:set(g.vm_id.astype(str)) for t,g in selected.groupby('trace')} != expected:
        raise ValueError('remediation must retain exactly the original development cohort')
    cohort = pilot_cohort_manifest(dataset, selected, tier_metadata, config.data.minimum_observations)
    gap_summary = summarize_gaps(gaps)
    eligibility_table, eligibility_summary = audit_dataset(raw, dataset, config)
    if len(pool)!=1576 or len(eligibility_table)!=1576:
        raise ValueError("retained metadata cohort must remain exactly 1576")
    check_dataset(raw, dataset)
    exp, env = prepare_experiment(repo, raw, config, dataset, cohort,
        {'model': config.model.random_state, 'descriptive_statistics': config.statistics.bootstrap_seed})
    required = [OutputSpec('outputs/'+name, role) for name, role in OUTPUTS.items()]
    required += [OutputSpec(f'logs/{r.trace}__{r.vm_id}.json', 'per-vm-attempt-progress')
                 for r in selected.itertuples()]
    with RunSession(repo/'results', exp, env, repo=repo, dataset_root=raw,
        purpose='pilot', required_outputs=required) as run:
        out = run.path/'outputs'
        write_json(out/'pilot_cohort.json', {'manifest': cohort, 'selection': selected.to_dict('records'),
            'permanent_role': 'DEVELOPMENT PILOT COHORT',
            'confirmation_exclusion_rule': 'primary retained Materna cohort excludes these 18 entities'})
        selected.to_parquet(out/'pilot_cohort.parquet', index=False)
        pool.to_parquet(out/'selection_pool.parquet', index=False)
        gaps.to_parquet(out/'materna_gap_audit.parquet', index=False)
        write_json(out/'materna_gap_audit.json', gap_summary)
        eligibility_table.to_parquet(out/'materna_gap_eligibility_v3.parquet',index=False)
        write_json(out/'materna_gap_eligibility_v3.json',eligibility_summary)
        print(canonical_json({'run_path': str(run.path), 'fingerprint': exp.fingerprint,
            'run_id': run.manifest.run_id, 'source_commit': source.commit, 'cohort_sha256': cohort.sha256,
            'selected': selected[['trace','vm_id','volatility_tier']].to_dict('records'),
            'gap_semantics': eligibility_summary['decision']}), flush=True)
        compute_start = time.perf_counter()
        answers = []
        # Processes parallelize VMs only; each process reuses its two frozen models.
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for row in selected.to_dict('records'):
                log = run.path/'logs'/f"{row['trace']}__{row['vm_id']}.json"
                write_json(log, {'trace': row['trace'], 'vm_id': row['vm_id'], 'status': 'SUBMITTED', 'methods': 11})
                futures[executor.submit(run_vm, row, config, repo)] = (row, log)
            for future in as_completed(futures):
                row, log = futures[future]
                try:
                    answer = future.result()
                except Exception as error:
                    write_json(log, {'trace': row['trace'], 'vm_id': row['vm_id'], 'status': 'FAILED',
                        'error_type': type(error).__name__, 'message': str(error)})
                    for pending in futures: pending.cancel()
                    raise
                answers.append(answer)
                write_json(log, {'status': 'COMPLETED', **answer['diagnostics']})
                print(canonical_json({'completed_vms': len(answers), **answer['diagnostics']}), flush=True)
        rows = [r for a in answers for r in a['rows']]
        assert len(rows) == 198 and len({(r['trace'],r['vm_id'],r['method_id']) for r in rows}) == 198
        frame = pd.DataFrame(rows).sort_values(['trace','vm_id','method_id'])
        frame.to_parquet(out/'per_vm_results.parquet', index=False)
        events = pd.DataFrame([r for a in answers for r in a['events']])
        events.sort_values(['trace','vm_id','method_id','actual_commit_time']).to_parquet(out/'refresh_events.parquet', index=False)
        evaluations = pd.DataFrame([r for a in answers for r in a['evaluations']])
        evaluations.sort_values(['trace','vm_id','method_id','eval_timestamp']).to_parquet(out/'evaluation_records.parquet', index=False)
        extras = pd.DataFrame([r for a in answers for r in a['extras']], columns=[
            'trace','vm_id','timestamp','schedule_version','k','ordinal','candidate_count'])
        extras.to_parquet(out/'matched_budget_schedule.parquet', index=False)
        columns = ['cpu_class_accuracy','memory_class_accuracy','cpu_p95_mae','mem_p95_mae',
                   'n_refresh_events','n_periodic_refreshes','n_drift_refreshes','n_budget_extra_refreshes']
        stats = frame.groupby('method_id')[columns].agg(['mean','median','min','max'])
        summary = {str(method): {f'{col}__{stat}': float(value) for (col,stat),value in row.items()}
                   for method,row in stats.iterrows()}
        wall = time.perf_counter()-compute_start
        diagnostics = {'purpose': 'pilot', 'source_commit': source.commit,
            'experiment_fingerprint': exp.fingerprint, 'run_id': run.manifest.run_id,
            'cohort_sha256': cohort.sha256, 'attempted': 198, 'completed': 198,
            'preparation_seconds': compute_start-preparation_start, 'pilot_wall_seconds': wall,
            'workers': workers, 'per_vm': sorted([a['diagnostics'] for a in answers], key=lambda d:(d['trace'],d['vm_id'])),
            'execution_invariants': 'PASS', 'gap_semantics': eligibility_summary['decision'],
            'v2_gate': 'PASS' if eligibility_summary['decision']=='ACCEPTABLE FOR V3' else 'BLOCKED',
            'claim_eligible': False, 'no_historical_inputs': True,
            'forecast_reuse': 'same-vm-frozen-target-model-origin-and-history-sha256-in-memory-only'}
        diagnostics['profile_age_by_method'] = {m: {'min':float(g.profile_age_hours.min()), 'median':float(g.profile_age_hours.median()), 'max':float(g.profile_age_hours.max()), 'zero_fraction':float(g.profile_age_hours.eq(0).mean())} for m,g in evaluations.groupby('method_id')}
        write_json(out/'pilot_diagnostics.json', diagnostics)
        write_json(out/'pilot_summary.json', {'label': 'PILOT / EXPLORATORY / DESCRIPTIVE ONLY',
            'confirmatory_tests': 'NOT PERFORMED', 'parameter_tuning': 'NOT PERFORMED', 'by_method': summary})
        run.complete()
    probes = integrity_probes(run.path, exp)
    report = {'run_path': str(run.path), **diagnostics, 'cache_integrity': probes,
        'output_manifest_sha256': read_json(run.path/'manifest.json')['output_manifest_sha256']}
    # Verification report is outside the completed run; never rewrite completed outputs.
    write_json(repo/'results/pilot-verification'/f'{run.manifest.run_id}.json', report)
    print(canonical_json(report), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--write-config', type=Path, help='write frozen pilot config; does not run')
    args = parser.parse_args(argv)
    if args.write_config:
        write_json(args.write_config, default_config())
        return 0
    config = default_config() if args.config is None else config_from_dict(read_json(args.config))
    report = execute(args.repo, config, workers=args.workers)
    return 0 if report['v2_gate']=='PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
