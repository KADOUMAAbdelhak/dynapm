from copy import deepcopy

import pytest

from dynapm.scripts.task40_v8_campaign import start_payload, synthetic_endpoints, terminal_payload
from dynapm.system_validation.v8_analysis import analyze, interval, request_endpoints
from dynapm.core.provenance import fingerprint
from dynapm.system_validation.v8_campaign import (
    ARTIFACT_1, BLOCKS, CONFIG_HASHES, DESIGN_SHA, QUALIFICATION_1, SCOPE, Campaign,
    calendar, expected_sequence,
)



@pytest.fixture
def setup(tmp_path):
    design = {'sequence': expected_sequence()}
    artifacts = {BLOCKS[0]: dict(artifact_sha256=ARTIFACT_1, qualification_sha256=QUALIFICATION_1)}
    for block in BLOCKS[1:]:
        artifacts[block] = dict(artifact_sha256=fingerprint({'synthetic_slot': block}),
                                qualification_sha256=None, synthetic=True)
    header = dict(scope=SCOPE, design_sha256=DESIGN_SHA, configuration=dict(CONFIG_HASHES),
                  artifacts=artifacts, source_commit='a'*40, boot_identity='boot', host_identity='host')
    return design, header, Campaign(tmp_path/'campaign', header, create=True)


def test_frozen_calendar(setup):
    design, _, _ = setup
    rows = calendar(design)
    assert len(rows) == 28
    assert [r['sequence'] for r in rows] == list(range(1, 29))
    assert rows[0]['start_offset_seconds'] == 178200
    assert rows[-1]['end_offset_seconds'] == 5092200
    assert all(a['end_offset_seconds'] == b['start_offset_seconds'] for a, b in zip(rows, rows[1:]))
    assert sum(r['stage'] == 'MANDATORY_SECONDARY' for r in rows) == 4


def test_resume_refuses_duplicate_and_frozen_cell_drift(setup):
    design, header, campaign = setup
    cell = design['sequence'][0]
    start = start_payload(header, cell, 'first')
    altered = deepcopy(start)
    altered['binding']['cell']['workload_seed'] = 1
    with pytest.raises(ValueError, match='binding'):
        campaign.record('START', altered)
    campaign.record('START', start)
    resumed = Campaign(campaign.root, header, checkpoint=campaign.checkpoint())
    assert resumed.state()['active'] == start
    with pytest.raises(ValueError, match='active_attempt'):
        resumed.record('START', start)
    resumed.record('TERMINAL', terminal_payload(start, endpoints=synthetic_endpoints(cell)))
    assert Campaign(campaign.root, header).state()['next_sequence'] == 2
    with pytest.raises(ValueError, match='next_frozen'):
        resumed.record('START', start)


@pytest.mark.parametrize('field,value', [('boot_identity', 'new-boot'), ('host_identity', 'new-host'),
                                         ('source_commit', 'b'*40), ('configuration', {})])
def test_resume_rejects_identity_mismatch(setup, field, value):
    _, header, campaign = setup
    header[field] = value
    with pytest.raises(ValueError, match='resume_'):
        Campaign(campaign.root, header)


def test_missing_durable_tail_rejected_with_saved_checkpoint(setup):
    design, header, campaign = setup
    campaign.record('START', start_payload(header, design['sequence'][0], 'first'))
    checkpoint = campaign.checkpoint()
    (campaign.root/'000001.event.json').unlink()
    with pytest.raises(ValueError, match='checkpoint_missing'):
        Campaign(campaign.root, header, checkpoint=checkpoint)


def test_global_replacement_cap_and_explicit_approval(setup):
    design, header, campaign = setup
    for i in range(3):
        cell = design['sequence'][i]
        original = start_payload(header, cell, f'orig-{i}')
        campaign.record('START', original)
        failed = terminal_payload(original, status='HARNESS_FAILED', elapsed=3600,
                                  failure='host_continuity_failure', exogenous=True)
        campaign.record('TERMINAL', failed)
        replacement = start_payload(header, cell, f'repl-{i}', replacement_for=original['attempt_id'])
        with pytest.raises(ValueError, match='explicit_replacement'):
            campaign.record('START', replacement)
        approval = dict(sequence=i+1, failed_attempt_id=original['attempt_id'], approval_id=f'review-{i}', reviewer='fixture')
        if i == 2:
            with pytest.raises(ValueError, match='not_eligible'):
                campaign.record('APPROVE_REPLACEMENT', approval)
        else:
            campaign.record('APPROVE_REPLACEMENT', approval)
            campaign.record('START', replacement)
            campaign.record('TERMINAL', terminal_payload(replacement, endpoints=synthetic_endpoints(cell)))
    assert campaign.state()['replacements_used'] == 2
    assert len(campaign.state()['failures']) == 3
    assert campaign.state()['next_sequence'] == 3


@pytest.mark.parametrize('hour', [1, 24, 47])
def test_partial_run_censored_not_completed_endpoint_or_replacement(setup, hour):
    design, header, campaign = setup
    cell = design['sequence'][0]
    start = start_payload(header, cell, 'first')
    campaign.record('START', start)
    with pytest.raises(ValueError, match='full_horizon'):
        campaign.record('TERMINAL', terminal_payload(start, elapsed=hour*3600, endpoints=synthetic_endpoints(cell)))
    campaign.record('TERMINAL', terminal_payload(start, status='OPERATIONAL_CENSORED',
                    elapsed=hour*3600, failure='resize_watchdog'))
    assert campaign.state()['next_sequence'] == 2
    assert analyze(campaign)['rows'][0]['endpoints'] is None
    assert all(r['pointwise_95'] is None for r in analyze(campaign)['contrasts'])


def test_interval_values_and_degeneracy():
    out = interval([1, 2, 3])
    assert out['pointwise_95'] == pytest.approx([2-2.48413771175, 2+2.48413771175])
    assert out['bonferroni_95'] == pytest.approx([2-19.9874978292, 2+19.9874978292])
    assert interval([0, 0, 0])['pointwise_95'] is None
    assert interval([1, None, 3])['status'] == 'NOT_ESTIMABLE'


def test_offered_cohort_retains_timeout_after_boundary_and_rejects_loss():
    rows = [dict(request_id=0, scheduled_at=0, completed_at=.25, success=True,
                 dropped=False, latency_seconds=.25),
            dict(request_id=1, scheduled_at=172799, completed_at=172804, success=False,
                 dropped=False, latency_seconds=None)]
    result = request_endpoints(rows, [0, 172799], 0, 172800)
    assert result['offered_requests'] == 2 and result['slo_violation_rate'] == .5
    with pytest.raises(ValueError):
        request_endpoints(rows[:1], [0, 172799], 0, 172800)
