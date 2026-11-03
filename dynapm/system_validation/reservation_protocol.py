"""Prospective reservation-oriented v2 contract. Offline only; no cluster launcher.

The v1 requests==limits consumer and physical-time telemetry remain untouched.
This module supplies payloads, verification predicates and a serialized ledger;
it does not claim runtime integration or compressed equivalence validation.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import time

from dynapm.core.provenance import fingerprint,file_sha256,read_json,canonical_json
from dynapm.core.run_store import write_json
from dynapm.system_validation.consumer import recommend,cpu_millicores,memory_bytes
from dynapm.system_validation.design import resource_manifests
from dynapm.system_validation.estimation_design import frozen_spec

SCHEMA='scheduler-reservation-actuation-v2'
SPEC='configs/system_resource_actuation_v2.json'
RESOURCES='harness/system/reservation-v2-resources.json'
FIXED_MEMORY_LIMIT_MIB=1024
WATCHDOG_NS=60*10**9
POST_RESPONSES=20
POST_WINDOW_NS=5*10**9


@dataclass(frozen=True)
class Target:
    cpu_millicores:int
    memory_request_mib:int

    def __post_init__(self):
        if (type(self.cpu_millicores) is not int or type(self.memory_request_mib) is not int or
                not 50<=self.cpu_millicores<=1000 or self.cpu_millicores%10 or
                not 64<=self.memory_request_mib<=512 or self.memory_request_mib%4):
            raise ValueError('target_outside_frozen_v2_reservation_grid')

    def resources(self):
        return dict(requests=dict(cpu=f'{self.cpu_millicores}m',memory=f'{self.memory_request_mib}Mi'),
                    limits=dict(cpu=f'{self.cpu_millicores}m',memory=f'{FIXED_MEMORY_LIMIT_MIB}Mi'))


def reservation_recommendation(profile,design):
    old=recommend(profile,design)  # Unchanged p95/headroom/quantization; values are requests.
    return Target(old['cpu_millicores'],old['memory_mib'])


def reservation_patch(target,pod):
    return dict(metadata=dict(uid=pod['metadata']['uid'],resourceVersion=pod['metadata']['resourceVersion']),
        spec=dict(containers=[dict(name='workload',resources=target.resources())]))


def reservation_resources(design):
    result=deepcopy(resource_manifests(design))
    for item in result['items']:
        if item['kind']=='Pod':
            item['metadata']['labels']={'app':'dynapm-workload' if item['metadata']['name']=='application' else 'dynapm-prometheus'}
            if item['metadata']['name']=='application':
                item['spec']['containers'][0]['resources']=Target(1000,512).resources()
    return result


def resources_match(value,target):
    try:
        return (all(cpu_millicores(value[k]['cpu'])==target.cpu_millicores for k in ('requests','limits')) and
            memory_bytes(value['requests']['memory'])==target.memory_request_mib*2**20 and
            memory_bytes(value['limits']['memory'])==FIXED_MEMORY_LIMIT_MIB*2**20)
    except (KeyError,TypeError,ValueError):return False


def enforcement_check(pod,sample,target,*,pod_uid,app_instance_id,accepted_generation,accepted_monotonic_ns,pod_receipt_monotonic_ns,read_monotonic_ns):
    """Reservation is API/node accounting; constant memory.max is the physical cap."""
    if pod['metadata']['uid']!=pod_uid or sample['instance_id']!=app_instance_id:
        raise ValueError('runtime_identity_changed')
    source_clock=sample.get('source_clock',{})
    if (source_clock.get('domain')!=sample.get('cluster_clock_domain') or
            not sample['sample_time_ns']<=source_clock.get('wall_ns',-1)<=sample['cluster_received_at_ns'] or
            source_clock.get('monotonic_ns',float('inf'))>sample.get('cluster_receipt_monotonic_ns',-1) or
            sample.get('clock_schema')!='system-clock-observation-v2' or
            not 0<=sample['cluster_received_at_ns']-sample['sample_time_ns']<=2*10**9 or
            sample['host_admitted_at_ns']<sample['received_at_ns'] or
            sample['host_admitted_monotonic_ns']<sample['host_receipt_monotonic_ns']):
        raise ValueError('causal_admission_violation')
    container=next(c for c in pod['status']['containerStatuses'] if c['name']=='workload')
    if container['restartCount']!=0 or container.get('lastState') or sample['oom_kills']:
        raise ValueError('restart_or_oom')
    allocated=container.get('allocatedResources',{})
    try:reservation=(cpu_millicores(allocated['cpu'])==target.cpu_millicores and memory_bytes(allocated['memory'])==target.memory_request_mib*2**20)
    except (KeyError,ValueError,TypeError):reservation=False
    conditions=[c for c in pod['status'].get('conditions',[]) if c['type'] in ('PodResizePending','PodResizeInProgress') and c['status']=='True']
    spec=next(c['resources'] for c in pod['spec']['containers'] if c['name']=='workload')
    gates=dict(specification=resources_match(spec,target),status=resources_match(container.get('resources'),target),
        reservation_accounted=reservation,qos_burstable=pod['status'].get('qosClass')=='Burstable',
        observed_generation=pod['status'].get('observedGeneration',-1)>=max(accepted_generation,pod['metadata']['generation']),
        fresh_observation=accepted_monotonic_ns<=sample['host_receipt_monotonic_ns']<=sample['host_admitted_monotonic_ns']<=read_monotonic_ns and accepted_monotonic_ns<=pod_receipt_monotonic_ns<=read_monotonic_ns,
        cpu_enforced=abs(sample['cpu_limit_cores']*1000-target.cpu_millicores)<1e-6,
        fixed_memory_cap_enforced=sample['memory_limit_bytes']==FIXED_MEMORY_LIMIT_MIB*2**20,
        resize_conditions_resolved=not conditions,
        pod_ready=any(c['type']=='Ready' and c['status']=='True' for c in pod['status'].get('conditions',[])))
    return dict(complete=all(gates.values()),gates=gates,resize_conditions=conditions,
        memory_request_meaning='scheduler/kubelet reservation; NOT reclaimed or capped resident pages')


def application_window(records,inflight_ids,enforced_ns,now_ns):
    """A mechanical/healthy response window, explicitly not statistical stationarity."""
    if inflight_ids is None:
        return dict(ready=False,reason='live_inflight_registry_required',statistically_settled=None)
    by_id={r['request_id']:r for r in records}
    if len(by_id)!=len(records):raise ValueError('duplicate_request_identity')
    if any(type(r.get('sent_monotonic_ns')) is int and type(r.get('completed_monotonic_ns')) is int and r['completed_monotonic_ns']<r['sent_monotonic_ns'] for r in records):raise ValueError('request_clock_order')
    drained=all(i in by_id and by_id[i].get('completed_monotonic_ns') is not None for i in inflight_ids)
    post=sorted([r for r in records if type(r.get('sent_monotonic_ns')) is int and type(r.get('completed_monotonic_ns')) is int and r['sent_monotonic_ns']>=enforced_ns and
        r['completed_monotonic_ns']<=now_ns],key=lambda r:r['completed_monotonic_ns'])
    window=len(post)>=POST_RESPONSES and now_ns-enforced_ns>=POST_WINDOW_NS and post[-1]['completed_monotonic_ns']-enforced_ns>=POST_WINDOW_NS
    failures=sum(not r['success'] or not r.get('work_verified',False) for r in post)+sum(not by_id[i]['success'] for i in inflight_ids if i in by_id)
    return dict(ready=drained and window and failures==0,pre_change_requests_drained=drained,
        post_response_count=len(post),physical_window_complete=window,application_failures=failures,
        statistically_settled=None,scope='mechanical progress and unchanged-work health only')


class ActuationLedger:
    """Serialized single-owner state machine; transport remains a separate adapter.

    Accepted server patches are never cancelled/overwritten. Only one latest
    unsubmitted intent is retained. A watchdog stops the run with censored state.
    """
    def __init__(self,clock=None):
        self.clock=clock or (lambda:(time.monotonic_ns(),time.time_ns()))
        self.events=[];self.seen=set();self.active=None;self.queued=None;self.terminal=False

    def _emit(self,event,decision,**extra):
        mono,wall=self.clock()
        if type(mono) is not int or type(wall) is not int or (self.events and mono<self.events[-1]['monotonic_ns']):
            self.terminal=True;raise ValueError('local_event_clock_order')
        row=dict(event=event,decision_id=decision,monotonic_ns=mono,wall_ns=wall,**deepcopy(extra))
        self.events.append(row);return row

    def intend(self,decision,target):
        if self.terminal:raise ValueError('terminal_run_no_new_intent')
        if not isinstance(target,Target):raise ValueError('typed_target_required')
        if decision in self.seen:raise ValueError('decision_id_reuse')
        self.seen.add(decision);row=self._emit('INTENDED',decision,target=vars(target))
        if self.active is not None:
            self._emit('SKIPPED_OPPORTUNITY',decision,pending_decision=self.active['id'],phase=self.active['phase'])
            if self.queued is not None:self._emit('SUPERSEDED_BEFORE_SUBMISSION',self.queued['id'],by=decision)
            self.queued=dict(id=decision,target=target)
            return None
        self.active=dict(id=decision,target=target,phase='SUBMITTING',issued_ns=row['monotonic_ns'])
        return target

    def patch(self,pod):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase']!='SUBMITTING':raise ValueError('no_unique_submittable_patch')
        self.active['phase']='ACK_WAIT';row=self._emit('PATCH_SUBMITTED',self.active['id']);self.active['submitted_ns']=row['monotonic_ns']
        return reservation_patch(self.active['target'],pod)

    def acknowledged(self,generation):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase']!='ACK_WAIT':raise ValueError('unexpected_ack')
        self.active.update(phase='IN_FLIGHT',generation=generation)
        self._emit('ACCEPTED',self.active['id'],accepted_generation=generation)

    def deferred(self,evidence):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase'] not in ('IN_FLIGHT','DEFERRED'):raise ValueError('unexpected_deferral')
        self.active['phase']='DEFERRED';self._emit('DEFERRED',self.active['id'],evidence=deepcopy(evidence))

    def observe(self,evidence):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase'] not in ('IN_FLIGHT','DEFERRED'):raise ValueError('no_accepted_actuation')
        self._emit('ACTUATION_OBSERVED',self.active['id'],evidence=deepcopy(evidence))
        if not evidence['complete']:return False
        if not evidence.get('gates') or not all(evidence['gates'].values()):raise ValueError('complete_requires_all_enforcement_gates')
        row=self._emit('PHYSICALLY_ENFORCED',self.active['id'],target=vars(self.active['target']),memory_pages_reclaimed='NOT_CLAIMED')
        self.active.update(phase='SETTLING',enforced_ns=row['monotonic_ns'])
        self._emit('ENFORCEMENT_COMPLETE',self.active['id'],decision_to_enforcement_seconds=(row['monotonic_ns']-self.active['issued_ns'])/1e9,patch_to_enforcement_seconds=(row['monotonic_ns']-self.active['submitted_ns'])/1e9)
        return True

    def no_op(self,evidence):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase']!='SUBMITTING' or not evidence['complete'] or not evidence.get('gates') or not all(evidence['gates'].values()):raise ValueError('no_op_requires_reconciled_target')
        row=self._emit('ACCEPTED_NO_CHANGE',self.active['id'],latency_seconds=None)
        self.active.update(phase='SETTLING',enforced_ns=row['monotonic_ns'])
        self._emit('ENFORCEMENT_COMPLETE',self.active['id'],no_change=True,latency_seconds=None)

    def finish_window(self,observation):
        if self.terminal:raise ValueError('terminal_callbacks_diagnostic_only')
        if not self.active or self.active['phase']!='SETTLING':raise ValueError('enforcement_required_before_window')
        self._emit('APPLICATION_WINDOW_OBSERVED',self.active['id'],evidence=deepcopy(observation))
        if not observation['ready']:return False
        self._emit('APPLICATION_MECHANICAL_WINDOW_COMPLETE',self.active['id'],statistically_settled=None)
        self.active=None;return True

    def next_queued(self):
        if self.terminal or self.active is not None:raise ValueError('cannot_overlap_accepted_actuation_or_window')
        if self.queued is None:return None
        queued=self.queued;self.queued=None;row=self._emit('QUEUED_INTENT_RELEASED',queued['id'])
        self.active=dict(**queued,phase='SUBMITTING',issued_ns=row['monotonic_ns'])
        return queued['target']

    def fail(self,kind,detail):
        if self.terminal:raise ValueError('already_terminal')
        decision=self.active['id'] if self.active else None
        self._emit(kind,decision,detail=detail,latency_seconds=None)
        if self.queued:self._emit('CANCELLED_UNSUBMITTED_ON_TERMINAL_FAILURE',self.queued['id'])
        self.queued=None;self.terminal=True  # Keep active/accepted state for postmortem.

    def watchdog(self):
        if not self.active or self.terminal:return False
        now,_=self.clock();origin=self.active.get('enforced_ns',self.active['issued_ns'])
        if now-origin<WATCHDOG_NS:return False
        phase=self.active['phase']
        kind={'SETTLING':'APPLICATION_WINDOW_RIGHT_CENSORED','SUBMITTING':'CONTROLLER_DISPATCH_FAILURE','ACK_WAIT':'ACK_UNKNOWN_RIGHT_CENSORED'}.get(phase,'ACTUATION_UNRESOLVED_RIGHT_CENSORED')
        self.fail(kind,dict(phase=phase,watchdog_ns=WATCHDOG_NS));return True


def protocol_specification(repo):
    repo=Path(repo);base=frozen_spec(repo)
    if base['consumer']['memory_mib_maximum']*2!=FIXED_MEMORY_LIMIT_MIB:
        raise ValueError('fixed_limit_basis_changed_requires_new_protocol')
    implementation=('dynapm/system_validation/reservation_protocol.py','dynapm/system_validation/consumer.py',
        'dynapm/system_validation/clock_observations.py','dynapm/system_validation/workloads.py')
    return dict(schema_version=SCHEMA,status='FROZEN_PROSPECTIVE_RUNTIME_VERIFICATION_OUTSTANDING',
        base_contract_sha256=file_sha256(repo/'configs/system_trials_v8_estimation_v2.json'),
        original_requests_equal_limits_contract_unchanged=True,comparative_execution_enabled=False,
        selected_memory_semantics='B',fixed_memory_limit_mib=FIXED_MEMORY_LIMIT_MIB,
        fixed_limit_basis='2 * pre-existing 512MiB maximum reservation; strictly greater than all requests to retain Burstable QoS; not selected from treatment outcomes',
        workload_peak_workset_mib=max(v.get('high_memory_mib',v.get('memory_mib',0)) for v in base['scenarios'].values()),
        memory_request_grid=dict(minimum_mib=64,maximum_mib=512,quantum_mib=4),
        cpu_requests_equal_limits=True,qos='Burstable from creation; no QoS transition',
        memory_endpoint='time integral of observed kubelet allocated reservation; desired request and fixed limit separate; not reclaimed RAM or hardware cost',
        memory_qos='require runtime capture; MemoryQoS disabled baseline; no memory.min/low protection assumed',
        pending=dict(single_accepted_patch=True,unsent_queue='one latest; supersede unsent only',accepted_patch_cancellation=False,
            timeout='terminal operational failure with right-censoring, never finite success; no automatic retry',
            acknowledgement_timeout='acceptance unknown; keep unresolved target, fail closed, no next patch',
            api_rejection='explicit API/contract rejection; no physical enforcement claimed; fail closed',
            watchdog_seconds=60,window_watchdog_seconds=60,
            operational_harms='retain deferred/rejected/timeout failures and trial termination; no selective rerun or successful full-window endpoint fabrication'),
        settling=dict(enforcement='ACK + spec + allocated reservation + status + cgroup CPU quota + fixed memory.max + observed generation + no resize condition + Ready + stable identities',
            mechanical_window=dict(pre_change_inflight_registry_required=True,min_completed_responses=POST_RESPONSES,min_physical_seconds=5,
                basis='one configured 5s HTTP-I/O timeout interval, not a total-request deadline; explicit registry establishes drain; 20 unchanged-work completed responses establish health/progress, not stationarity'),
            application_statistically_settled='UNRESOLVED_NOT_CLAIMED'),
        telemetry=dict(path='U',host_bucket_seconds=300,min_samples=50,min_host_receipt_span_seconds=270,
            membership='[start,end)',source_age_seconds=2,source_future_tolerance_ns=0,
            cpu_rate='source monotonic elapsed',host_admission='physical program order and local monotonic order',
            compression_enabled=False,candidate_slot_duration_seconds=None),
        acceleration_decision='UNCOMPRESSED_SYSTEM_VALIDATION_REQUIRED',
        acceleration_basis='fixed RPS/work plus shorter physical slots changes workload exposure, averaging support, phase duration and initialization/refresh information; cadence ratios alone do not preserve the original physical-time estimand; no validated equivalence or settling contract',
        shortest_physical_design=dict(shared_bootstrap_slots=288,reuse_qualified_block1=True,measurement_seconds=172800,
            real_measurement_slots=576,cooldown_seconds=900,warmup_seconds=1800,
            repetitions='not chosen; existing precision/randomization/hardware gates remain',
            note='retain predeclared 48h exposure per treatment; do not opportunistically shorten from favorable timing'),
        engineering_verification=dict(method='pw_6h',execution='OFFLINE_ONLY_USER_DIRECTED',live_verified=False,
            planned_targets=[vars(Target(c,m)) for c,m in [(80,64),(500,256),(500,256),(100,256),(500,256),(500,64),(500,512),(1000,128),(250,128),(250,64),(250,64)]],
            stale_pending_test='queue 250m/128MiB then 500m/256MiB while first accepted target awaits reconciliation; older unsent intent superseded; no overlapping patch'),
        resources_template_sha256=fingerprint(reservation_resources(base)),
        implementation_sha256={p:file_sha256(repo/p) for p in implementation})


def write_protocol(repo):
    repo=Path(repo);spec=protocol_specification(repo)
    write_json(repo/SPEC,spec);write_json(repo/RESOURCES,reservation_resources(frozen_spec(repo)))
    return fingerprint(spec)


def read_protocol(repo):
    repo=Path(repo);spec=read_json(repo/SPEC)
    if spec!=protocol_specification(repo) or canonical_json(read_json(repo/RESOURCES))!=canonical_json(reservation_resources(frozen_spec(repo))):
        raise ValueError('reservation_protocol_or_source_drift')
    return spec
