"""Prospective UUID-based host observation. No live application or claim workload."""
from pathlib import Path
import hashlib
import re
import subprocess
import time

from dynapm.core.provenance import (SourceProvenance, CohortManifest, CohortEntity,
    prepare_experiment, read_json, fingerprint, utc_now)
from dynapm.core.run_store import RunSession, write_json
from dynapm.data.manifests import build_dataset_manifest
from dynapm.system_validation.host_power import (SCHEMA, CHECK_SECONDS, POWER_SECONDS,
    ENDURANCE_SECONDS, MAX_HEARTBEAT_GAP_NS)
from dynapm.system_validation.v8_host_identity import (UUIDPowerGuard, UUID_ENDURANCE_SCHEMA,
    qualification_inputs, read_boot, same_boot)
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.host_endurance import HOST_SEEDS, OUTPUTS, observation_config
from dynapm.system_validation.host_certificate import runtime_identity as legacy_runtime_identity

UUID_RUNTIME = ('dynapm/system_validation/uuid_host_observer.py',
    'dynapm/scripts/task49_host_uuid_observation.py',
    'dynapm/system_validation/v8_host_identity.py')


def runtime_identity(repo, commit=None):
    repo=Path(repo)
    if commit is not None and not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('pinned_host_source_commit_required')
    result=legacy_runtime_identity(repo,commit)
    for name in UUID_RUNTIME:
        try:
            source=(repo/name).read_bytes() if commit is None else subprocess.check_output(
                ['git','show',commit+':'+name],cwd=repo,stderr=subprocess.DEVNULL)
        except (OSError,subprocess.CalledProcessError) as exc:
            raise ValueError('uuid_host_source_unavailable:'+name) from exc
        result[name]=hashlib.sha256(source).hexdigest()
    return result


def require_same_uuid_runtime(repo, commit):
    current=runtime_identity(repo)
    if current!=runtime_identity(repo,commit):
        raise ValueError('uuid_host_endurance_runtime_mismatch')
    return dict(schema='uuid-host-runtime-compatibility-v1',
        observation_source_commit=commit,runtime=current)


def require_endurance(repo,run_path):
    if run_path is None:raise ValueError('validated_host_endurance_run_required')
    root=Path(run_path).resolve();repo=Path(repo).resolve()
    if not root.is_relative_to(repo/'results/host_endurance/runs'):
        raise ValueError('managed_host_endurance_path_required')
    if SourceProvenance.capture(repo).dirty:raise ValueError('host_endurance_source_mismatch')
    inputs,guard=qualification_inputs(repo,root)
    from dynapm.system_validation.host_power import power_state,command
    now=power_state()
    if inputs['original_uuid_recorded']:
        same_boot(inputs['boot_uuid'],read_boot(),anchor_ns=inputs['boot_timeval_anchor_ns'])
    elif now['boot_epoch_seconds']!=inputs['legacy_epoch']:
        raise ValueError('host_endurance_boot_mismatch')
    if command(['/usr/bin/pmset','-g','custom'])!=guard['power_settings']:
        raise ValueError('host_endurance_power_policy_mismatch')
    return root


def observe(repo,seconds=ENDURANCE_SECONDS):
    repo=Path(repo).resolve()
    if type(seconds) is not int or not ENDURANCE_SECONDS<=seconds<=21600:
        raise ValueError('host_endurance_duration_requires_3_to_6_hours')
    source=SourceProvenance.capture(repo)
    if source.dirty:raise ValueError('clean_committed_source_required')
    spec=frozen_spec(repo)
    descriptor=dict(schema_version=UUID_ENDURANCE_SCHEMA,duration_seconds=seconds,
        boot_identity='exact-uuid-bounded-calendar-v1',maximum_calendar_discrepancy_ns=MAX_CLOCK_DELTA_NS,
        observer_runtime_sha256=runtime_identity(repo),
        seeds=dict(HOST_SEEDS),power_schema=SCHEMA,check_seconds=CHECK_SECONDS,power_seconds=POWER_SECONDS,
        maximum_heartbeat_gap_ns=MAX_HEARTBEAT_GAP_NS,system_design_sha256=fingerprint(spec),
        purpose='host continuity only; no workload, bootstrap, profiles or comparison')
    inputs=repo/'results/host_endurance/inputs'/fingerprint(descriptor)
    inputs.mkdir(parents=True,exist_ok=True)
    input_file=inputs/'host/observation.json'
    if input_file.exists() and read_json(input_file)!=descriptor:raise ValueError('immutable_input_mismatch')
    if not input_file.exists():write_json(input_file,descriptor)
    dataset=build_dataset_manifest(inputs,dataset_id=UUID_ENDURANCE_SCHEMA,source_name='local host observation contract',
        trace_names=('host',),schema_identity='host-endurance-input-v2-uuid',expected_cadence_seconds=CHECK_SECONDS)
    cohort=CohortManifest(dataset.dataset_id,dataset.sha256,'one-host-no-application-v1',{'role':'host observation only'},
        (CohortEntity('host','execution-host',True,None,0),),utc_now())
    config=observation_config(dataset.dataset_id,descriptor)
    exp,env=prepare_experiment(repo,inputs,config,dataset,cohort,descriptor['seeds'],
        execution_compatibility_keys=tuple(spec['hardware']['compatibility_keys']))
    with RunSession(repo/'results/host_endurance',exp,env,repo=repo,dataset_root=inputs,
            purpose='smoke',required_outputs=OUTPUTS) as run:
        context=dict(run_id=run.manifest.run_id,experiment_fingerprint=exp.fingerprint,source_commit=source.commit)
        write_json(run.path/'outputs/endurance_summary.json',dict(status='INCOMPLETE'))
        with UUIDPowerGuard(run.path,context) as guard:
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
        summary=dict(schema_version=UUID_ENDURANCE_SCHEMA,status='COMPLETE_HOST_OBSERVATION',
            boot_uuid=guard.state['boot_uuid_anchor'],boot_timeval_anchor_ns=guard.state['boot_timeval_anchor_ns'],
            elapsed_seconds=time.monotonic()-start,requested_seconds=seconds,
            comparisons=0,profile_initializations=0,bootstrap_slots=0,workloads=0,
            scope='conditioned on AC, lid open and actual recorded idle settings; not proof against forced sleep')
        write_json(run.path/'outputs/endurance_summary.json',summary)
        run.complete()
        print(dict(status='COMPLETE',run_path=str(run.path),output_manifest_sha256=run.manifest.output_manifest_sha256),flush=True)
        return run.path
