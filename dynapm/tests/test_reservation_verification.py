"""Late diagnostic completion must not reuse a stale healthy response window."""
import pytest
from dynapm.system_validation.reservation_protocol import ActuationLedger, Target, application_window
from dynapm.system_validation.reservation_verification import finish_observed_window


class Clock:
    now = 0
    def __call__(self):
        return self.now, self.now


def settling():
    clock = Clock()
    ledger = ActuationLedger(clock)
    ledger.intend('test', Target(100, 64))
    ledger.no_op({'complete': True, 'gates': {'reconciled': True}})
    return ledger, clock


def requests():
    return [dict(request_id=i, sent_monotonic_ns=i*250_000_000,
                 completed_monotonic_ns=i*250_000_000+200_000_000,
                 success=True, work_verified=True) for i in range(21)]


def test_failure_during_later_diagnostic_invalidates_previously_ready_window():
    ledger, clock = settling()
    records = requests()
    assert application_window(records, [], 0, 6_000_000_000)['ready']
    # Analogous to V7C.12: a blocking diagnostic follows the initial healthy check.
    records.append(dict(request_id=21, sent_monotonic_ns=7_000_000_000,
                        completed_monotonic_ns=12_000_000_000,
                        success=False, work_verified=False))
    clock.now = 15_000_000_000
    assert not finish_observed_window(ledger, records, [])
    assert ledger.terminal and ledger.active is not None
    assert ledger.events[-1]['event'] == 'APPLICATION_REQUEST_FAILURE'
    assert ledger.events[-1]['latency_seconds'] is None
    assert not any(e['event'] == 'APPLICATION_MECHANICAL_WINDOW_COMPLETE' for e in ledger.events)
    with pytest.raises(ValueError, match='terminal_run'):
        ledger.intend('retry', Target(1000, 512))


def test_fresh_complete_window_releases_only_after_final_observation():
    ledger, clock = settling()
    clock.now = 6_000_000_000
    assert finish_observed_window(ledger, requests(), [])
    assert ledger.active is None and not ledger.terminal


def test_incomplete_or_uncaptured_window_does_not_release_active_operation():
    ledger, clock = settling()
    clock.now = 6_000_000_000
    assert not finish_observed_window(ledger, requests(), None)
    assert ledger.active is not None and not ledger.terminal
    assert not finish_observed_window(ledger, requests()[:10], [])
    assert ledger.active is not None
