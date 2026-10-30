"""Neutral PW6 event timing; no workload launcher or compression selector."""
from dataclasses import dataclass,field
import math
import numpy as np

SCHEMA='neutral-system-timing-probes-v1'


def elapsed(start,end):
    if type(start) is not int or type(end) is not int or end<start:raise ValueError('ordered_local_monotonic_ns_required')
    return (end-start)/1e9


@dataclass
class ResizeProbe:
    decision_id:str
    submitted_monotonic_ns:int
    submitted_wall_ns:int
    target_cpu_millicores:int
    target_memory_mib:int
    cpu_changed:bool
    memory_changed:bool
    first_observed:dict=field(default_factory=dict)
    observations:list=field(default_factory=list)

    def acknowledged(self,mono_ns,wall_ns):
        if 'api_ack' in self.first_observed:raise ValueError('duplicate_patch_ack')
        elapsed(self.submitted_monotonic_ns,mono_ns)
        self.first_observed['api_ack']=(mono_ns,wall_ns)

    def observe(self,mono_ns,wall_ns,*,pod_cpu_millicores,pod_memory_mib,cgroup_cpu_cores,cgroup_memory_bytes,
                persistent_workset_bytes=None):
        elapsed(self.submitted_monotonic_ns,mono_ns)
        if self.observations and mono_ns<=self.observations[-1]['monotonic_ns']:raise ValueError('nonincreasing_probe_observation')
        values=[pod_cpu_millicores,pod_memory_mib,cgroup_cpu_cores,cgroup_memory_bytes]
        if any(not math.isfinite(v) for v in values):raise ValueError('finite_probe_observation_required')
        matched=dict(pod_cpu=self.cpu_changed and pod_cpu_millicores==self.target_cpu_millicores,
            pod_memory=self.memory_changed and pod_memory_mib==self.target_memory_mib,
            cgroup_cpu=self.cpu_changed and abs(cgroup_cpu_cores*1000-self.target_cpu_millicores)<1e-6,
            cgroup_memory=self.memory_changed and cgroup_memory_bytes==self.target_memory_mib*2**20)
        for key,ok in matched.items():
            if ok and key not in self.first_observed:self.first_observed[key]=(mono_ns,wall_ns)
        self.observations.append(dict(monotonic_ns=mono_ns,wall_ns=wall_ns,matches=matched,
            persistent_workset_bytes=persistent_workset_bytes))

    def record(self,*,pending_end_monotonic_ns=None,skipped_decisions=0,timeout=False):
        metrics={k:elapsed(self.submitted_monotonic_ns,v[0]) for k,v in self.first_observed.items()}
        return dict(schema_version=SCHEMA,method='pw_6h',decision_id=self.decision_id,
            submitted_wall_ns=self.submitted_wall_ns,submitted_monotonic_ns=self.submitted_monotonic_ns,
            target_cpu_millicores=self.target_cpu_millicores,target_memory_mib=self.target_memory_mib,
            changed={'cpu':self.cpu_changed,'memory':self.memory_changed},first_observed=self.first_observed,
            seconds=metrics,pending_seconds=None if pending_end_monotonic_ns is None else elapsed(self.submitted_monotonic_ns,pending_end_monotonic_ns),
            skipped_decisions=skipped_decisions,timeout=timeout,observations=self.observations,
            enforcement_interpretation='first-observed upper bounds at polling resolution; API acknowledgement is separate',
            application_steady_state='NOT_ESTABLISHED; raw response/drain analysis required')


def request_drain_seconds(requests,enforced_wall_seconds):
    """Mechanical settling component, not proof of latency-distribution stability."""
    old=[r for r in requests if r.get('sent_at') is not None and r['sent_at']<enforced_wall_seconds and r['completed_at']>=enforced_wall_seconds]
    return dict(pre_enforcement_requests=len(old),drain_seconds=max((r['completed_at']-enforced_wall_seconds for r in old),default=0),
        incomplete_or_failed=sum(not r['success'] for r in old),scope='old in-flight request drain only')


def distribution(values,*,missing=0,censored=0):
    if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('finite_nonnegative_timings_required')
    return dict(n=len(values),missing=missing,censored=censored,
        **{name:float(np.quantile(values,q)) if values else None for name,q in [('min',0),('median',.5),('p95',.95),('p99',.99),('max',1)]})


def collect_local_durations(*,telemetry_start_ns,body_received_ns,decode_finished_ns,recommendation_start_ns,recommendation_end_ns):
    return dict(telemetry_transport_seconds=elapsed(telemetry_start_ns,body_received_ns),
        telemetry_decode_seconds=elapsed(body_received_ns,decode_finished_ns),
        recommendation_compute_seconds=elapsed(recommendation_start_ns,recommendation_end_ns))


def contract_specification(repo):
    from pathlib import Path
    from dynapm.core.provenance import file_sha256
    paths=('dynapm/system_validation/timing_probes.py','dynapm/system_validation/calibration_workers.py')
    return dict(schema_version=SCHEMA,method='pw_6h',launch_enabled=False,comparisons=False,
        compression_duration_selected=False,clock='local monotonic durations; wall provenance retained',
        components=['telemetry','recommendation','API acknowledgement','Pod CPU/memory status',
            'cgroup CPU enforcement','cgroup memory enforcement','pending duration','old-request drain'],
        uncertainty='first-observed enforcement is bounded by polling, not exact kernel event time',
        application_steady_state='NOT_ESTABLISHED; drain is only a mechanical component',
        statistics=['n','missing','censored','min','median','p95','p99','max'],
        implementation_sha256={p:file_sha256(Path(repo)/p) for p in paths})
