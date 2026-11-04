import pytest
from dynapm.system_validation.outcome_taxonomy import classify,observation_window,OutcomeLedger
from dynapm.system_validation.reservation_protocol import Target
@pytest.mark.parametrize('kind',['request_timeout','http_error','application_error','slo_violation','throughput_degradation','queue_buildup'])
def test_application_harm_is_retained_outcome(kind):assert not classify(kind)['invalidates_run']
@pytest.mark.parametrize('kind',['generator_failure','lost_control_telemetry','controller_crash','enforcement_unverifiable','missing_provenance','host_continuity_failure','corrupt_measurement_stream'])
def test_measurement_failures_invalidate(kind):assert classify(kind)['invalidates_run']
def test_diagnostic_failure_requires_independent_evidence():assert 'condition' in classify('application_diagnostic_timeout')
def test_fresh_failed_attempts_complete_observation_without_claiming_health():
 l=OutcomeLedger(lambda:(7_000_000_000,7_000_000_000));l.intend('low',Target(100,64));l.no_op({'complete':True,'gates':{'all':True}})
 l.active['enforced_ns']=0
 records=[dict(request_id=i,sent_monotonic_ns=i*250_000_000,completed_monotonic_ns=i*250_000_000+100_000_000,success=i!=3,work_verified=i!=3) for i in range(24)]
 w=observation_window(records,[],0,7_000_000_000)
 assert w['observation_complete'] and w['application_failures']==1 and not w['healthy'] and not w['server_drain_proven']
 assert l.finish_window(w) and l.active is None and not l.terminal
 assert l.events[-1]['event']=='POST_ENFORCEMENT_MEASUREMENT_COMPLETE'
 assert l.events[-1]['application_failures']==1
def test_missing_registry_does_not_complete():assert not observation_window([],None,0,7_000_000_000)['observation_complete']
def test_unknown_event_cannot_be_silently_accepted():
 with pytest.raises(ValueError):classify('unknown')
