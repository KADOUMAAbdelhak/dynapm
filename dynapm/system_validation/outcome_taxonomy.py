"""V7C.13 taxonomy v1: outcomes do not invalidate observable enforcement."""
from dynapm.system_validation.reservation_protocol import ActuationLedger, application_window, resources_match
from dynapm.system_validation.consumer import cpu_millicores, memory_bytes
SCHEMA = 'reservation-outcome-observability-v1'
APPLICATION = frozenset(('request_timeout','http_error','application_error','slo_violation','throughput_degradation','queue_buildup'))
HARNESS = frozenset(('generator_failure','lost_control_telemetry','controller_crash','enforcement_unverifiable','missing_provenance','host_continuity_failure','corrupt_measurement_stream'))
DIAGNOSTIC = frozenset(('application_diagnostic_timeout','application_diagnostic_error'))

def classify(kind):
    if kind in APPLICATION:return dict(category='APPLICATION_OUTCOME',invalidates_run=False)
    if kind in HARNESS:return dict(category='HARNESS_MEASUREMENT_FAILURE',invalidates_run=True)
    if kind in DIAGNOSTIC:return dict(category='CONTROL_PLANE_DIAGNOSTIC_FAILURE',invalidates_run=False,condition='independent control-plane/cgroup evidence remains valid')
    raise ValueError('unclassified_event')


def observation_window(records,inflight_ids,enforced_ns,now_ns):
    old=application_window(records,inflight_ids,enforced_ns,now_ns)
    if inflight_ids is None:return dict(old,observation_complete=False)
    # Failures are retained, not deleted or converted to successes.
    complete=old['pre_change_requests_drained'] and old['physical_window_complete']
    return dict(old,ready=complete,observation_complete=complete,healthy=old['application_failures']==0,
        server_drain_proven=old['pre_change_requests_drained'] and old['application_failures']==0,
        scope='completed host request attempts and elapsed observation; errors retained; no statistical settling')


class OutcomeLedger(ActuationLedger):
    def finish_window(self,observation):
        if self.terminal or not self.active or self.active['phase']!='SETTLING':raise ValueError('accepted_enforcement_required')
        self._emit('POST_ENFORCEMENT_OBSERVED',self.active['id'],evidence=observation)
        if not observation.get('observation_complete'):return False
        self._emit('POST_ENFORCEMENT_MEASUREMENT_COMPLETE',self.active['id'],application_failures=observation['application_failures'],healthy=observation['healthy'],statistically_settled=None)
        self.active=None;return True


def control_enforcement(pod,node,target,*,pod_uid,generation,ack_ns,pod_received_ns,now_ns):
    if pod['metadata']['uid']!=pod_uid:raise ValueError('pod_identity_changed')
    cs=next(c for c in pod['status']['containerStatuses'] if c['name']=='workload')
    if cs['restartCount']!=0:raise ValueError('container_restart_requires_explicit_stream_reconciliation')
    spec=next(c['resources'] for c in pod['spec']['containers'] if c['name']=='workload')
    allocated=cs.get('allocatedResources',{})
    try:reservation=cpu_millicores(allocated['cpu'])==target.cpu_millicores and memory_bytes(allocated['memory'])==target.memory_request_mib*2**20
    except (KeyError,ValueError,TypeError):reservation=False
    quota,period=map(int,node['values']['cpu.max'].split())
    conditions=[c for c in pod['status'].get('conditions',[]) if c['type'] in ('PodResizePending','PodResizeInProgress') and c['status']=='True']
    binding=node.get('binding',{})
    owner=binding.get('container_id')==cs.get('containerID','').split('://')[-1] and bool(binding.get('container_id')) and binding.get('node')==pod['spec'].get('nodeName')
    gates=dict(container_identity=owner,specification=resources_match(spec,target),status=resources_match(cs.get('resources'),target),reservation_accounted=reservation,
        qos_burstable=pod['status'].get('qosClass')=='Burstable',observed_generation=pod['status'].get('observedGeneration',-1)>=max(generation,pod['metadata']['generation']),
        fresh_observation=ack_ns<=pod_received_ns<=now_ns and ack_ns<=node['start_monotonic_ns']<=node['end_monotonic_ns']<=now_ns,
        cpu_enforced=abs(quota/period*1000-target.cpu_millicores)<1e-6,fixed_memory_cap_enforced=int(node['values']['memory.max'])==1024*2**20,
        resize_conditions_resolved=not conditions,pod_ready=any(c['type']=='Ready' and c['status']=='True' for c in pod['status'].get('conditions',[])))
    return dict(complete=all(gates.values()),gates=gates,resize_conditions=conditions,source='independent node cgroup and Kubernetes; application diagnostics not required')
