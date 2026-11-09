"""Primary resource verification v2: application readiness remains an outcome.

The physical patch/watchdog logic is the frozen implementation. Only the
verification projection separates Pod readiness from independent resource gates.
"""
import json
import subprocess
import time
from dynapm.core.provenance import canonical_json
from dynapm.system_validation.bounded_v8 import NS
from dynapm.system_validation.bounded_v8_runtime import OperationalStop, append
from dynapm.system_validation.reservation_protocol import reservation_patch, resources_match
from dynapm.system_validation.outcome_taxonomy import control_enforcement as frozen_control_enforcement


def control_enforcement(*args, **kwargs):
    original = frozen_control_enforcement(*args, **kwargs)
    if 'pod_ready' not in original['gates']:
        raise ValueError('frozen_resource_gate_schema_changed')
    resource_gates = {k:v for k,v in original['gates'].items() if k != 'pod_ready'}
    return dict(original, schema_version='primary-resource-verification-v2',
                complete=all(resource_gates.values()), gates=resource_gates,
                application_observations=dict(pod_ready=original['gates']['pod_ready']),
                legacy_readiness_gated_complete=original['complete'],
                source='independent specification/status/reservation/cgroup; application readiness retained as outcome')


def confirm(kube, observer, uid, target, generation, ack_ns, evidence):
    pod = kube.pod()
    received = time.monotonic_ns()
    node = observer.enforcement()
    result = control_enforcement(pod,node,target,pod_uid=uid,generation=generation,ack_ns=ack_ns,
                                 pod_received_ns=received,now_ns=time.monotonic_ns())
    if any(node['values'][k]!='0' for k in ('memory.min','memory.low','memory.swap.current')):
        raise ValueError('memory_qos_or_swap_changed')
    append(evidence,dict(pod=pod,node=node,target=vars(target),check=result,receipt_monotonic_ns=received))
    return result['complete']


def actuate(kube, observer, uid, target, evidence, emit, guard):
    begin = time.monotonic_ns()
    pod = kube.pod()
    if pod['metadata']['uid'] != uid:
        raise ValueError('pod_uid_changed')
    current = next(c['resources'] for c in pod['spec']['containers'] if c['name']=='workload')
    generation = pod['metadata']['generation']
    status = 'NO_OP'
    append(evidence,dict(event='INTENDED',target=vars(target),monotonic_ns=begin))
    if not resources_match(current,target):
        payload = reservation_patch(target,pod)
        append(evidence,dict(event='PATCH_SUBMITTED',payload=payload,monotonic_ns=time.monotonic_ns()))
        try:
            ack = json.loads(kube.call(['patch','pod','application','--subresource=resize','--type=strategic',
                                        '-p',canonical_json(payload),'-o','json'],controller=True,timeout=60))
        except subprocess.TimeoutExpired as exc:
            raise OperationalStop('patch_acceptance_unknown_right_censored') from exc
        except RuntimeError as exc:
            # Only an explicit server rejection is a known operational failure.
            if 'Error from server' in str(exc) and not any(x in str(exc) for x in ('(Unauthorized)','(Forbidden)','(NotFound)')):
                raise OperationalStop('api_rejected_resize') from exc
            raise
        ack_ns = time.monotonic_ns()
        if ack['metadata']['uid']!=uid or not resources_match(next(c['resources'] for c in ack['spec']['containers'] if c['name']=='workload'),target):
            raise ValueError('resize_ack_target_mismatch')
        generation = ack['metadata']['generation']
        append(evidence,dict(event='ACCEPTED',monotonic_ns=ack_ns,pod=ack))
        status = 'ENFORCED'
    else:
        ack_ns = begin
    while time.monotonic_ns()-begin<60*NS:
        guard.raise_if_failed()
        if confirm(kube,observer,uid,target,generation,ack_ns,evidence):
            enforced = time.monotonic_ns()
            if enforced-begin>=60*NS:
                break
            row = dict(status=status,**vars(target),ack_monotonic_ns=ack_ns,enforced_monotonic_ns=enforced,
                       actuation_latency_seconds=(enforced-begin)/NS if status=='ENFORCED' else None)
            emit(row)
            return row
        time.sleep(.2)
    raise OperationalStop('resize_watchdog_right_censored')
