"""Managed, non-claim host observation. No Kubernetes/application workloads."""
from pathlib import Path
import subprocess
import time

from dynapm.core.provenance import (SourceProvenance,DataConfig,ModelConfig,StatisticsConfig,
    ExperimentConfigProvenance,CohortManifest,CohortEntity,prepare_experiment,read_json,
    fingerprint,utc_now,experiment_from_dict)
from dynapm.core.run_store import RunSession,OutputSpec,write_json,check_cache
from dynapm.data.manifests import build_dataset_manifest
from dynapm.system_validation.host_power import (ManagedPowerGuard,SCHEMA,CHECK_SECONDS,POWER_SECONDS,
    ENDURANCE_SECONDS,MAX_HEARTBEAT_GAP_NS)
from dynapm.system_validation.estimation_design import frozen_spec

# No random action is performed; the provenance contract still requires an explicit seed map.
HOST_SEEDS={'host_observation':0}

OUTPUTS=(OutputSpec('outputs/power_guard.json','owned-power-assertion-lifecycle'),
    OutputSpec('outputs/host_continuity.jsonl','host-wall-monotonic-power-checkpoints'),
    OutputSpec('outputs/host_continuity_summary.json','host-continuity-summary'),
    OutputSpec('outputs/host_continuity_failure.json','host-continuity-rejection-evidence'),
    OutputSpec('outputs/endurance_summary.json','nonclaim-host-stability-observation'))


def require_endurance(repo,run_path):
    if run_path is None:raise ValueError('validated_host_endurance_run_required')
    root=Path(run_path).resolve();repo=Path(repo).resolve()
    if not root.is_relative_to(repo/'results/host_endurance/runs'):
        raise ValueError('managed_host_endurance_path_required')
    m=read_json(root/'manifest.json');exp=experiment_from_dict(m['experiment'])
    current=SourceProvenance.capture(repo)
    if current.dirty or fingerprint(current.identity())!=fingerprint(exp.source.identity()):
        raise ValueError('host_endurance_source_mismatch')
    decision=check_cache(root,exp,'smoke')
    if not decision.reusable:raise ValueError('host_endurance_invalid:'+','.join(decision.reasons))
    summary=read_json(root/'outputs/endurance_summary.json');guard=read_json(root/'outputs/power_guard.json')
    if (summary.get('schema_version')!='host-endurance-v1' or summary.get('elapsed_seconds',0)<ENDURANCE_SECONDS
        or summary.get('comparisons')!=0 or summary.get('profile_initializations')!=0
        or summary.get('requested_seconds',0)<ENDURANCE_SECONDS or not guard.get('release_confirmed')
        or guard.get('schema_version')!=SCHEMA or guard.get('failure') is not None
        or guard.get('status')!='RELEASED'):
        raise ValueError('host_endurance_incomplete')
    return root


def observation_config(dataset_id,descriptor):
    return ExperimentConfigProvenance(DataConfig(dataset_id,bootstrap_fraction=0.0,minimum_observations=0,
        sampling_cadence_seconds=CHECK_SECONDS,evaluation_cadence_seconds=CHECK_SECONDS,
        forecast_horizon_steps=0,minimum_ground_truth_paired_slots=0,feature_history_slots=0,
        minimum_trailing_24h_slots=0,minimum_trailing_6h_slots=0,
        lag_semantics='not-applicable-host-observation',evaluation_grid='host-continuity-observation-v1'),
        ModelConfig(family='unused-no-predictor'),(),StatisticsConfig(bootstrap_repetitions=0,
        test_specification={'enabled':False}),preprocessing=descriptor,
        analysis={'comparative':False,'scientific_outcomes':False})


def observe(repo,seconds=ENDURANCE_SECONDS):
    repo=Path(repo).resolve()
    if type(seconds) is not int or not ENDURANCE_SECONDS<=seconds<=21600:
        raise ValueError('host_endurance_duration_requires_3_to_6_hours')
    source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean_committed_source_required')
    spec=frozen_spec(repo)
    descriptor=dict(schema_version='host-endurance-v1',duration_seconds=seconds,
        seeds=dict(HOST_SEEDS),power_schema=SCHEMA,check_seconds=CHECK_SECONDS,power_seconds=POWER_SECONDS,
        maximum_heartbeat_gap_ns=MAX_HEARTBEAT_GAP_NS,system_design_sha256=fingerprint(spec),
        purpose='host continuity only; no workload, bootstrap, profiles or comparison')
    inputs=repo/'results/host_endurance/inputs'/fingerprint(descriptor)
    inputs.mkdir(parents=True,exist_ok=True)
    input_file=inputs/'host/observation.json'
    if input_file.exists() and read_json(input_file)!=descriptor:raise ValueError('immutable_input_mismatch')
    if not input_file.exists():write_json(input_file,descriptor)
    dataset=build_dataset_manifest(inputs,dataset_id='host-endurance-v1',source_name='local host observation contract',
        trace_names=('host',),schema_identity='host-endurance-input-v1',expected_cadence_seconds=CHECK_SECONDS)
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'one-host-no-application-v1',{'role':'host observation only'},
        (CohortEntity('host','execution-host',True,None,0),),utc_now())
    config=observation_config(dataset.dataset_id,descriptor)
    exp,env=prepare_experiment(repo,inputs,config,dataset,cohort,descriptor['seeds'],
        execution_compatibility_keys=tuple(spec['hardware']['compatibility_keys']))
    with RunSession(repo/'results/host_endurance',exp,env,repo=repo,dataset_root=inputs,
            purpose='smoke',required_outputs=OUTPUTS) as run:
        context=dict(run_id=run.manifest.run_id,experiment_fingerprint=exp.fingerprint,source_commit=source.commit)
        write_json(run.path/'outputs/endurance_summary.json',dict(status='INCOMPLETE'))
        with ManagedPowerGuard(run.path,context) as guard:
            start=time.monotonic();last_report=-60
            while True:
                guard.raise_if_failed();elapsed=time.monotonic()-start
                if elapsed-last_report>=60:
                    if SourceProvenance.capture(repo).identity()!=source.identity():
                        raise ValueError('source_changed_during_host_endurance')
                    print(dict(status='OBSERVING_HOST_ONLY',run_path=str(run.path),elapsed_seconds=elapsed,
                        requested_seconds=seconds,source_commit=source.commit),flush=True)
                    last_report=elapsed
                if elapsed>=seconds:break
                time.sleep(min(CHECK_SECONDS,seconds-elapsed))
            guard.checkpoint(force_power=True)
        summary=dict(schema_version='host-endurance-v1',status='COMPLETE_HOST_OBSERVATION',
            elapsed_seconds=time.monotonic()-start,requested_seconds=seconds,
            comparisons=0,profile_initializations=0,bootstrap_slots=0,workloads=0,
            scope='conditioned on AC, lid open and actual recorded idle settings; not proof against forced sleep')
        write_json(run.path/'outputs/endurance_summary.json',summary)
        run.complete()
        print(dict(status='COMPLETE',run_path=str(run.path),output_manifest_sha256=run.manifest.output_manifest_sha256),flush=True)
        return run.path
