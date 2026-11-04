"""Fresh application-window completion for bounded reservation verification.

Call after the last blocking diagnostic, with a fresh locked request snapshot.
The frozen v2 predicates remain unchanged. This adapter stops on application
failure; an earlier successful window is never reused after further observation.
"""
from dynapm.system_validation.reservation_protocol import application_window


def finish_observed_window(ledger, records, inflight_ids):
    if ledger.active is None or ledger.active['phase'] != 'SETTLING':
        raise ValueError('enforcement_required_before_final_observation')
    now_ns, _ = ledger.clock()
    observation = application_window(
        records, inflight_ids, ledger.active['enforced_ns'], now_ns)
    if observation.get('application_failures', 0):
        ledger.fail('APPLICATION_REQUEST_FAILURE', observation)
        return False
    return ledger.finish_window(observation)
