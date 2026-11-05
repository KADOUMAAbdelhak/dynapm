"""V7E offline plan audit and synthetic orchestration dry run."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import subprocess

from dynapm.core.provenance import canonical_json, file_sha256, fingerprint, read_json
from dynapm.system_validation.neutral_characterization import qualification
from dynapm.system_validation.v8_analysis import analyze, request_endpoints
from dynapm.system_validation.v8_campaign import (
    BLOCKS, DURATION, Campaign, acquisition_slots, calendar, cell_binding, load_design,
    synthetic_header, publish_record,
)

GIB = 2**30


def offered_counts():
    # Integer rate integrals on the frozen piecewise-constant scenarios.
    return dict(stable=4*DURATION, periodic=6*(2+12)*12600 + 2*12600 + 12*9000,
                burst=4*DURATION + (20-4)*10*1200,
                abrupt_regime_shift=(4+12)*86400)


def storage_plan(repo, design, qualified_artifact, qualification_record):
    """Projection from prior neutral observations and explicit writer budgets."""
    repo = Path(repo)
    parent = next((repo / 'results/system_calibration/runs').glob(
        '*/' + qualification_record['parent_run_id']))
    observed = {}
    for name in ('requests', 'clock_observations', 'telemetry', 'host_continuity'):
        path = parent / 'outputs' / f'{name}.jsonl'
        with path.open('rb') as handle:
            count = sum(1 for _ in handle)
        observed[name] = dict(bytes=path.stat().st_size, records=count,
                              bytes_per_record=path.stat().st_size / count)
    node = repo / 'results/resource_semantics/v7c13/2026-11-04T221617-280859+0000-5404f4bd/outputs/cgroup_observations.jsonl'
    with node.open('rb') as handle:
        observed['node_bytes_per_record'] = node.stat().st_size / sum(1 for _ in handle)
    observed['bootstrap_parent_bytes'] = sum(p.stat().st_size for p in parent.rglob('*') if p.is_file())
    observed['bootstrap_artifact_bytes'] = sum(p.stat().st_size for p in qualified_artifact.rglob('*') if p.is_file())
    # Warmup adds 7200 offers. Plan for uncompressed raw records and overhead.
    projection = {}
    for scenario, count in offered_counts().items():
        projection[scenario] = dict(measurement_offers=count, request_record_budget_bytes=512,
            total_bytes=(count + 7200)*512 + 34920*6144 + 175500*2304 + 35100*3072 + 128*2**20)
    counts = Counter(c['scenario'] for c in design['sequence'])
    forecast = sum(counts[k]*projection[k]['total_bytes'] for k in counts)
    bootstrap_estimate = 2 * (observed['bootstrap_parent_bytes'] + observed['bootstrap_artifact_bytes'])
    free = shutil.disk_usage(repo).free
    return dict(observed=observed, per_scenario=projection, treatment_projection_bytes=forecast,
                bootstrap_projection_bytes=bootstrap_estimate, projected_total_bytes=forecast+bootstrap_estimate,
                treatment_budget_bytes=3*GIB, bootstrap_budget_bytes=GIB,
                successful_treatment_reservation_bytes=28*3*GIB, acquisition_reservation_bytes=2*GIB,
                replacement_reservation_bytes=2*3*GIB, free_floor_bytes=20*GIB,
                minimum_initial_free_bytes=112*GIB, measured_free_bytes=free,
                campaign_disk_ready=free >= 112*GIB, reservation_is_policy_budget_not_empirical_max=True)


def start_payload(header, cell, attempt, *, replacement_for=None):
    return dict(sequence=cell['sequence'], attempt_id=attempt, replacement_for=replacement_for,
                source_commit=header['source_commit'], campaign_sha256=fingerprint(header),
                binding=cell_binding(cell, header['artifacts'][cell['bootstrap_block']], header['configuration']),
                runtime_identities={k: f'{attempt}:{k}' for k in
                                    ('cluster', 'pod', 'application', 'profile', 'controller', 'telemetry')})


def terminal_payload(start, *, status='COMPLETE', elapsed=DURATION, failure=None,
                     exogenous=False, endpoints=None):
    return dict(sequence=start['sequence'], attempt_id=start['attempt_id'], status=status,
                measurement_elapsed_seconds=elapsed, failure_kind=failure, exogenous=exogenous,
                endpoints=endpoints, binding_sha256=fingerprint(start),
                evidence_sha256=fingerprint(dict(synthetic_attempt=start['attempt_id'], status=status,
                                                 elapsed=elapsed, failure=failure, endpoints=endpoints)))


def synthetic_endpoints(cell):
    offset = (cell['sequence'] % 9) / 1000
    requests = [dict(request_id=0, scheduled_at=1, completed_at=1.1+offset, success=True,
                     dropped=False, latency_seconds=.1+offset),
                dict(request_id=1, scheduled_at=DURATION-1, completed_at=DURATION+4,
                     success=False, dropped=False, latency_seconds=None)]
    return dict(request_endpoints(requests, [1, DURATION-1], 0, DURATION),
                mean_cpu_requested_cores=.25+offset, mean_memory_requested_bytes=128*2**20,
                mean_cpu_allocated_cores=.25, mean_memory_allocated_bytes=128*2**20,
                cpu_utilization_efficiency=.5+offset, memory_utilization_efficiency=.25,
                maintenance_cpu_seconds=1+offset, cpu_churn_cores=0., memory_churn_bytes=0)


def dry_run(repo, output, source_commit):
    design = load_design(repo)
    artifact, qualified = qualification(repo)
    storage = storage_plan(repo, design, artifact, qualified)
    header = synthetic_header(repo, source_commit=source_commit,
                              boot_identity='synthetic-boot', host_identity='synthetic-host')
    campaign = Campaign(output, header, create=True)
    for cell in design['sequence']:
        attempt = f"dry-{cell['sequence']:02d}"
        started = start_payload(header, cell, attempt)
        campaign.record('START', started)
        campaign = Campaign(output, header, checkpoint=campaign.checkpoint())
        if campaign.state()['active'] != started:
            raise RuntimeError('synthetic_restart_failed')
        if cell['sequence'] in (1, 9):
            failure = terminal_payload(started, status='HARNESS_FAILED', elapsed=3600,
                                       failure='host_continuity_failure', exogenous=True)
            campaign.record('TERMINAL', failure)
            campaign = Campaign(output, header, checkpoint=campaign.checkpoint())
            campaign.record('APPROVE_REPLACEMENT', dict(sequence=cell['sequence'],
                            failed_attempt_id=attempt, approval_id=f'dry-review-{attempt}',
                            reviewer='synthetic-test'))
            started = start_payload(header, cell, attempt+'-replacement', replacement_for=attempt)
            campaign.record('START', started)
        campaign.record('TERMINAL', terminal_payload(started, endpoints=synthetic_endpoints(cell)))
    state = Campaign(output, header).state()
    if state['next_sequence'] != 29 or len(state['completed']) != 28 or state['replacements_used'] != 2:
        raise RuntimeError('synthetic_campaign_incomplete')
    publish_record(output / 'analysis.json', analyze(campaign))
    publish_record(output / 'calendar.json', calendar(design))
    publish_record(output / 'acquisition_slots.json', acquisition_slots())
    publish_record(output / 'storage.json', storage)
    publish_record(output / 'offline_summary.json', dict(scope=header['scope'], live_execution=False,
        cells=28, retained_harness_failures=2, explicit_replacements=2,
        calendar_sha256=file_sha256(output/'calendar.json'),
        analysis_sha256=file_sha256(output/'analysis.json'),
        storage_sha256=file_sha256(output/'storage.json')))
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--dry-run-output', type=Path, required=True)
    args = parser.parse_args()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=args.repo).strip():
        parser.error('clean committed source required')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.repo, text=True).strip()
    dry_run(args.repo, args.dry_run_output, source)
    print(canonical_json(read_json(args.dry_run_output / 'offline_summary.json')))


if __name__ == '__main__':
    main()
