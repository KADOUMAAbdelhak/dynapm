"""Immutable measured prehistory and isolated treatment initialization.

Only raw bootstrap and acquisition provenance are reused, never measurement-phase
results or initialized profiles. Original wall clocks are retained; logical
reindexing is explicit, and is not a claim of live contiguous Pod telemetry.
"""
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
import json
import shutil
import time

import pandas as pd

from dynapm.core.provenance import read_json,file_sha256,fingerprint,experiment_from_dict,canonical_json
from dynapm.core.run_store import write_json,check_cache
from dynapm.system_validation.trial_preparation import measured_bootstrap,MeasuredBootstrap,MeasuredProfileAdapter
from dynapm.experiments.confirmatory_design import PRIMARY_METHODS
from dynapm.system_validation.host_power import SCHEMA as POWER_SCHEMA,MAX_HEARTBEAT_GAP_NS
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS

SCHEMA='shared-measured-bootstrap-v1'
BLOCK_SCHEMA='shared-bootstrap-blocks-v1'
STEP_NS=300*10**9
DAY_NS=288*STEP_NS
FILES=('raw_samples.jsonl','parent_manifest.json','parent_output_manifest.json','parent_SUCCESS.json','parent_plan.json','parent_bootstrap_summary.json','parent_diagnostics.json','parent_power_guard.json','parent_continuity_summary.json')


def content_contract(design):
    return dict(schema_version=SCHEMA,cadence_seconds=300,slots=288,minimum_paired=200,last_complete=96,
        references=design['references'],telemetry=design['telemetry'],
        protocol=design['core_protocol'],accounting=design['accounting_schema'])


def _no_links(root):
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('bootstrap_symlinks_forbidden')


def _parent_metadata(manifest,summary,plan,diagnostics):
    if manifest['status']!='SUCCESS' or manifest['purpose']!='pilot' or manifest.get('allow_dirty'):
        raise ValueError('completed_clean_measured_acquisition_required')
    if manifest['experiment']['source']['dirty']:
        raise ValueError('dirty_acquisition_forbidden')
    metadata=manifest['experiment']['config']['preprocessing']
    hardware=manifest['experiment']['scientific_environment'].get('execution_compatibility',{})
    if not hardware or any(v is None for v in hardware.values()) or not metadata.get('execution_environment',{}).get('image_ids'):
        raise ValueError('acquisition_hardware_and_images_required')
    mode=metadata.get('mode')
    if mode not in ('MEASURED_BOOTSTRAP_ONLY_V1','NEUTRAL_CALIBRATION_REAL_BOOTSTRAP'):
        raise ValueError('measured_acquisition_mode_required')
    if diagnostics.get('synthetic_bootstrap_used') is not False or diagnostics.get('real_bootstrap_complete') is not True:
        raise ValueError('real_bootstrap_provenance_required')
    if summary.get('real_duration_seconds')!=86400 or plan['design']['bootstrap']['workload']!='stable':
        raise ValueError('stable_real_24h_bootstrap_required')
    if not plan.get('bootstrap_source_pod_uid') or summary.get('source_pod_uid')!=plan['bootstrap_source_pod_uid']:
        raise ValueError('bootstrap_source_pod_identity_required')
    start=plan['bootstrap_start_seconds'];end=plan['measurement_start_seconds']
    if int(start)!=start or int(end)!=end:raise ValueError('integer_acquisition_seconds_required')
    started=pd.Timestamp(manifest['started_at']);finished=pd.Timestamp(manifest['ended_at'])
    if started.tzinfo is None or finished.tzinfo is None or started.value>int(start)*10**9 or finished.value<int(end)*10**9 or finished.value-started.value<DAY_NS:
        raise ValueError('parent_did_not_cover_real_acquisition_interval')
    return int(start)*10**9,int(end)*10**9


def _raw_contract(entries,design):
    samples=[s for e in sorted(entries,key=lambda e:e['end_ns']) for s in e['samples']]
    if any(s.get('cpu_limit_cores')!=design['references']['cpu_millicores']/1000 or
            s.get('memory_limit_bytes')!=design['references']['memory_mib']*2**20 for s in samples):
        raise ValueError('fixed_reference_resources_required_during_bootstrap')
    if any(not 0<=s['received_at_ns']-s['sample_time_ns']<=MAX_CLOCK_DELTA_NS for s in samples):
        raise ValueError('bootstrap_sample_clock_invariant')
    times=[s['sample_time_ns'] for s in samples]
    if len(times)!=len(set(times)) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('bootstrap_raw_observation_order')


def create_artifact(acquisition_run,artifact_store,design,*,allow_unit_fixture=False):
    """Accepts a bootstrap-only SUCCESS; no policy-measurement phase is required."""
    parent=Path(acquisition_run);_no_links(parent)
    m=read_json(parent/'manifest.json');exp=experiment_from_dict(m['experiment'])
    decision=check_cache(parent,exp,'pilot')
    if not decision.reusable:raise ValueError('bootstrap_parent_integrity:'+','.join(decision.reasons))
    unit_fixture=m['experiment']['config'].get('analysis',{}).get('unit_test_fixture') is True
    if unit_fixture and not allow_unit_fixture:raise ValueError('unit_fixture_not_scientific_acquisition')
    summary=read_json(parent/'outputs/bootstrap_summary.json');plan=read_json(parent/'outputs/plan.json')
    diagnostics=read_json(parent/'outputs/diagnostics.json')
    start,end=_parent_metadata(m,summary,plan,diagnostics)
    if content_contract(plan['design'])!=content_contract(design):raise ValueError('bootstrap_content_contract_mismatch')
    raw=parent/'outputs/bootstrap_samples.jsonl'
    entries=[json.loads(line) for line in raw.read_text().splitlines() if line]
    available=pd.Timestamp(m['ended_at']).value
    boot=measured_bootstrap(entries,start,end,available,design)
    if boot.evidence_sha256!=summary['evidence_sha256'] or boot.accepted_slots!=summary['accepted_slots']:
        raise ValueError('bootstrap_summary_reconstruction_mismatch')
    instance_ids={s['instance_id'] for e in entries for s in e['samples']}
    _raw_contract(entries,design)
    originals=dict(zip(FILES,(raw,parent/'manifest.json',parent/'output_manifest.json',parent/'SUCCESS',
        parent/'outputs/plan.json',parent/'outputs/bootstrap_summary.json',parent/'outputs/diagnostics.json',
        parent/'outputs/power_guard.json',parent/'outputs/host_continuity_summary.json')))
    body=dict(schema_version=SCHEMA,data_kind='UNIT_TEST_ONLY' if unit_fixture else 'MEASURED_24H',content_contract=content_contract(design),
        acquisition_start_ns=start,acquisition_end_ns=end,available_at_ns=available,
        source_instance_id=next(iter(instance_ids)),source_pod_uid=plan['bootstrap_source_pod_uid'],acquisition_run_id=m['run_id'],
        source_commit=exp.source.commit,acquisition_fingerprint=m['experiment_fingerprint'],
        hardware_fingerprint=fingerprint(exp.scientific_environment.get('execution_compatibility',{})),
        source_image_ids=m['experiment']['config']['preprocessing'].get('execution_environment',{}).get('image_ids',{}),
        accepted_slots=boot.accepted_slots,missing_slots=boot.missing_slots,
        evidence_sha256=boot.evidence_sha256,prehistory='stable',
        files={name:dict(size_bytes=p.stat().st_size,sha256=file_sha256(p)) for name,p in originals.items()})
    identity=fingerprint(body);root=Path(artifact_store)/identity
    if root.exists():load_artifact(root,identity,design);return root
    root.mkdir(parents=True,exist_ok=False)
    for name,p in originals.items():
        shutil.copyfile(p,root/name)
    write_json(root/'manifest.json',{**body,'artifact_sha256':identity})
    write_json(root/'COMPLETE',dict(artifact_sha256=identity,manifest_sha256=file_sha256(root/'manifest.json')))
    load_artifact(root,identity,design)
    return root


def load_artifact(path,expected_sha256,design):
    root=Path(path);_no_links(root)
    if {p.name for p in root.iterdir()}!=set(FILES)|{'manifest.json','COMPLETE'}:
        raise ValueError('bootstrap_artifact_inventory_mismatch')
    m=read_json(root/'manifest.json');marker=read_json(root/'COMPLETE')
    body={k:v for k,v in m.items() if k!='artifact_sha256'}
    if m.get('schema_version')!=SCHEMA or fingerprint(body)!=expected_sha256 or m['artifact_sha256']!=expected_sha256:
        raise ValueError('bootstrap_artifact_identity_mismatch')
    if (root/'COMPLETE').read_text()!=canonical_json(marker):raise ValueError('noncanonical_bootstrap_marker')
    if marker!=dict(artifact_sha256=expected_sha256,manifest_sha256=file_sha256(root/'manifest.json')):
        raise ValueError('bootstrap_completion_marker_mismatch')
    if m['content_contract']!=content_contract(design):raise ValueError('bootstrap_content_contract_mismatch')
    if set(m['files'])!=set(FILES):raise ValueError('bootstrap_file_manifest_inventory')
    for name,info in m['files'].items():
        p=root/name
        if p.stat().st_size!=info['size_bytes'] or file_sha256(p)!=info['sha256']:
            raise ValueError('bootstrap_artifact_hash_mismatch:'+name)
    parent=read_json(root/'parent_manifest.json');success=read_json(root/'parent_SUCCESS.json')
    outputs=read_json(root/'parent_output_manifest.json')
    if parent['status']!='SUCCESS' or parent['purpose']!='pilot' or parent['experiment']['source']['dirty']:
        raise ValueError('invalid_bootstrap_parent')
    if success['manifest_sha256']!=file_sha256(root/'parent_manifest.json') or success['output_manifest_sha256']!=fingerprint(outputs):
        raise ValueError('bootstrap_parent_chain_mismatch')
    for target,original in [('raw_samples.jsonl','bootstrap_samples.jsonl'),('parent_plan.json','plan.json'),
            ('parent_bootstrap_summary.json','bootstrap_summary.json'),('parent_diagnostics.json','diagnostics.json'),('parent_power_guard.json','power_guard.json'),
            ('parent_continuity_summary.json','host_continuity_summary.json')]:
        item=next((x for x in outputs['files'] if x['path']=='outputs/'+original),None)
        if not item or item['sha256']!=file_sha256(root/target):raise ValueError('bootstrap_raw_lineage_mismatch')
    expected_kind='UNIT_TEST_ONLY' if parent['experiment']['config'].get('analysis',{}).get('unit_test_fixture') is True else 'MEASURED_24H'
    if m.get('data_kind')!=expected_kind:raise ValueError('bootstrap_data_kind_mismatch')
    start,end=_parent_metadata(parent,read_json(root/'parent_bootstrap_summary.json'),
        read_json(root/'parent_plan.json'),read_json(root/'parent_diagnostics.json'))
    if start!=m['acquisition_start_ns'] or end!=m['acquisition_end_ns']:raise ValueError('bootstrap_parent_window_mismatch')
    guard=read_json(root/'parent_power_guard.json');continuity=read_json(root/'parent_continuity_summary.json')
    if guard.get('schema_version')!=POWER_SCHEMA or continuity.get('schema_version')!=POWER_SCHEMA:
        raise ValueError('unsupported_bootstrap_host_schema')
    if not guard.get('release_confirmed') or guard.get('failure') is not None or continuity.get('failure') is not None or continuity.get('maximum_absolute_drift_ns',float('inf'))>MAX_CLOCK_DELTA_NS or continuity.get('maximum_checkpoint_gap_ns',float('inf'))>MAX_HEARTBEAT_GAP_NS:
        raise ValueError('bootstrap_host_continuity_invalid')
    if guard.get('status')!='RELEASED' or guard.get('context',{}).get('run_id')!=parent['run_id']:
        raise ValueError('bootstrap_guard_provenance_mismatch')
    parent_plan=read_json(root/'parent_plan.json')
    if (m['available_at_ns']!=pd.Timestamp(parent['ended_at']).value or m['source_commit']!=parent['experiment']['source']['commit']
        or m['acquisition_run_id']!=parent['run_id'] or m['acquisition_fingerprint']!=parent['experiment_fingerprint']
        or m['source_pod_uid']!=parent_plan['bootstrap_source_pod_uid']):
        raise ValueError('bootstrap_provenance_fields_mismatch')
    entries=[json.loads(s) for s in (root/'raw_samples.jsonl').read_text().splitlines() if s]
    if {s['instance_id'] for e in entries for s in e['samples']}!={m['source_instance_id']}:
        raise ValueError('bootstrap_source_instance_mismatch')
    _raw_contract(entries,design)
    b=measured_bootstrap(entries,m['acquisition_start_ns'],m['acquisition_end_ns'],m['available_at_ns'],design)
    if b.evidence_sha256!=m['evidence_sha256'] or b.accepted_slots!=m['accepted_slots']:
        raise ValueError('bootstrap_artifact_reconstruction_mismatch')
    return m,b


def freeze_blocks(artifacts,design,*,common_stable_prehistory,seed=20251022,purpose='pilot'):
    """Outcome-blind block IDs; no treatment outcomes or precision N are inputs."""
    if common_stable_prehistory is not True:raise ValueError('explicit_common_stable_prehistory_required')
    if purpose not in ('smoke','pilot','claim'):raise ValueError('explicit_block_purpose_required')
    rows=[];ids=set();instances=set();parents=set();intervals=[]
    for i,(path,sha) in enumerate(artifacts):
        m,_=load_artifact(path,sha,design)
        if m['data_kind']=='UNIT_TEST_ONLY' and purpose!='smoke':raise ValueError('unit_artifact_forbidden_for_scientific_blocks')
        if sha in ids or m['source_instance_id'] in instances or m['acquisition_run_id'] in parents:
            raise ValueError('independent_bootstrap_blocks_required')
        if any(m['acquisition_start_ns']<b and a<m['acquisition_end_ns'] for a,b in intervals):
            raise ValueError('serial_independent_acquisition_windows_required')
        ids.add(sha);instances.add(m['source_instance_id']);parents.add(m['acquisition_run_id'])
        intervals.append((m['acquisition_start_ns'],m['acquisition_end_ns']))
        base=sorted(PRIMARY_METHODS,key=lambda name:fingerprint({'seed':seed,'method':name}))
        shift=i%len(base)
        rows.append(dict(block_id=i,artifact_sha256=sha,acquisition_run_id=m['acquisition_run_id'],method_order=base[shift:]+base[:shift]))
    if not rows:raise ValueError('nonempty_bootstrap_blocks_required')
    body=dict(schema_version=BLOCK_SCHEMA,purpose=purpose,common_stable_prehistory=True,seed=seed,blocks=rows,
        methods=list(PRIMARY_METHODS),estimand='fresh systems initialized with common stable measured prehistory')
    return {**body,'design_sha256':fingerprint(body)}


@dataclass(frozen=True)
class StartupEvidence:
    treatment_id:str
    pod_uid:str
    app_instance_id:str
    profile_instance_id:str
    controller_instance_id:str
    telemetry_instance_id:str
    initial_runtime_refreshes:int
    initial_observations:int
    initial_resource_changes:int
    pending_resize:bool


class SharedProfile(MeasuredProfileAdapter):
    def _snapshot(self):
        result=super()._snapshot()
        result.update(scope='UNIT_TEST_SHARED_PREHISTORY' if self.shared_bootstrap['data_kind']=='UNIT_TEST_ONLY' else 'SHARED_MEASURED_PREHISTORY',shared_bootstrap=self.shared_bootstrap)
        return result


class TreatmentRegistry:
    """Run-planner bookkeeping only. Each returned policy/history is newly allocated.

The real runner must capture StartupEvidence from new Pod/service identities;
this library validates its identity/reset contract, not Kubernetes deployment.
"""
    def __init__(self,block_design):
        body={k:v for k,v in block_design.items() if k!='design_sha256'}
        if block_design.get('schema_version')!=BLOCK_SCHEMA or fingerprint(body)!=block_design['design_sha256']:
            raise ValueError('invalid_shared_block_design')
        rows=block_design['blocks']
        if (len({x['block_id'] for x in rows})!=len(rows) or len({x['artifact_sha256'] for x in rows})!=len(rows)
            or any(sorted(x['method_order'])!=sorted(PRIMARY_METHODS) for x in rows)):
            raise ValueError('invalid_independent_block_matrix')
        self.purpose=block_design['purpose']
        self.blocks={x['block_id']:deepcopy(x) for x in rows};self.used=set();self.identities=set()

    def initialize(self,block_id,method,path,design,origin_ns,startup,*,read_wall_ns,planned_streaming_slots=576):
        begin=time.perf_counter();cpu=time.thread_time()
        block=self.blocks[block_id]
        if method not in block['method_order'] or (block_id,method) in self.used:raise ValueError('duplicate_or_invalid_treatment')
        if any(type(getattr(startup,k)) is not int or getattr(startup,k)!=0 for k in
            ('initial_runtime_refreshes','initial_observations','initial_resource_changes')) or startup.pending_resize is not False:
            raise ValueError('fresh_treatment_state_required')
        names=('treatment_id','pod_uid','app_instance_id','profile_instance_id','controller_instance_id','telemetry_instance_id')
        values=[getattr(startup,k) for k in names]
        if any(not isinstance(v,str) or not v for v in values) or len(set(values))!=len(values):raise ValueError('fresh_unique_startup_identities_required')
        if self.identities.intersection(values):raise ValueError('treatment_identity_reuse')
        m,b=load_artifact(path,block['artifact_sha256'],design)
        if m['data_kind']=='UNIT_TEST_ONLY' and self.purpose!='smoke':raise ValueError('unit_artifact_forbidden_for_scientific_treatment')
        if startup.app_instance_id==m['source_instance_id'] or startup.pod_uid==m['source_pod_uid']:raise ValueError('acquisition_instance_reused')
        if type(origin_ns) is not int or type(read_wall_ns) is not int or origin_ns%STEP_NS or read_wall_ns<origin_ns or m['available_at_ns']>origin_ns:
            raise ValueError('bootstrap_unavailable_at_treatment_origin')
        frame=b.frame.copy(deep=True)
        frame.index=pd.date_range(end=pd.Timestamp(origin_ns,tz='UTC'),periods=288,freq='5min')
        view=MeasuredBootstrap(frame,origin_ns-DAY_NS,origin_ns,b.accepted_slots,b.missing_slots,b.evidence_sha256)
        adapter=SharedProfile(method,view,design,planned_streaming_slots=planned_streaming_slots)
        adapter.shared_bootstrap=dict(artifact_sha256=block['artifact_sha256'],block_id=block_id,data_kind=m['data_kind'],
            treatment_id=startup.treatment_id,acquisition_start_ns=b.start_ns,acquisition_end_ns=b.end_ns,
            logical_origin_ns=origin_ns,raw_clocks_rewritten=False,
            initialization_wall_seconds=time.perf_counter()-begin,initialization_thread_cpu_seconds=time.thread_time()-cpu,
            measurement_includes_initialization_and_initial_actuation=True,startup=dict(vars(startup)))
        self.used.add((block_id,method));self.identities.update(values)
        return adapter


def contract_specification(repo,design):
    paths=('dynapm/system_validation/shared_bootstrap.py','dynapm/system_validation/trial_preparation.py',
        'dynapm/experiments/confirmatory_execution.py','dynapm/scripts/task36_shared_bootstrap.py')
    return dict(schema_version='shared-bootstrap-implementation-contract-v1',artifact_schema=SCHEMA,
        block_schema=BLOCK_SCHEMA,content=content_contract(design),methods=list(PRIMARY_METHODS),
        common_stable_prehistory=True,requires_completed_72h_anchor=False,bootstrap_only_acquisition_supported=True,
        initial_content={'static':'whole bootstrap','pw_12h':'last12h','pw_6h':'last6h','pw_3h':'last3h','full_rewrite':'last24h'},
        treatment='fresh Pod/app/controller/profile/telemetry identities; initialization and actuation remain treatment costs',
        raw_clocks='preserved; logical initialization view mapping recorded explicitly',
        reuse_forbidden=['measurement outputs','mutable initialized profile/controller','acquisition identities across blocks'],
        integrity='expected artifact SHA, parent SUCCESS, hashes, measured raw history, schema and host provenance',
        implementation_sha256={p:file_sha256(Path(repo)/p) for p in paths})
