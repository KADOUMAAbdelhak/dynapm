from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dynapm.core.provenance import file_sha256, read_json
from dynapm.core.run_store import write_json
from dynapm.experiments import google2019_durable_read as durable
from dynapm.experiments.google2019_g_local import canonicalize, freeze_cohort
from dynapm.experiments.google2019_local_canonical import require_corrected_generation
from dynapm.scripts import task42_google2019_cell_g as runner
from dynapm.tests.test_google2019_local_canonical import events, usage


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    old = tmp_path/runner.OCTOBER
    old.parent.mkdir(parents=True)
    write_json(old,{'October':'historical'})
    monkeypatch.setattr(runner,'OCTOBER_SHA',file_sha256(old))
    path = tmp_path/runner.LEDGER
    write_json(path,dict(month_utc=runner.MONTH,cap_bytes=runner.CAP,executed_entries=[],cumulative_executed_bytes=0))
    monkeypatch.setattr(runner,'ZERO_LEDGER_SHA',file_sha256(path))
    return path,old


def test_november_explicit_accounting_and_exactly_once(ledger,tmp_path):
    path,old = ledger
    old_hash = file_sha256(old)
    with pytest.raises(ValueError,match='explicit_november'):
        runner.read_ledger(tmp_path,'2026-10',path)
    with pytest.raises(ValueError,match='explicit_november'):
        runner.read_ledger(tmp_path,runner.MONTH,old)
    entry = dict(run_id='r',job_id='j',query_name='g:21_events_minimal.sql',executed_bytes=37,dry_run_bytes=500)
    runner.account(tmp_path,path,'r',entry)
    after = file_sha256(path)
    runner.account(tmp_path,path,'r',entry)
    assert file_sha256(path)==after
    assert runner.read_ledger(tmp_path,runner.MONTH,path,'r')['cumulative_executed_bytes']==37
    with pytest.raises(ValueError,match='recorded_job_metadata'):
        runner.account(tmp_path,path,'r',dict(entry,executed_bytes=38))
    with pytest.raises(ValueError,match='duplicate_logical_scan'):
        runner.account(tmp_path,path,'r',dict(entry,job_id='second'))
    with pytest.raises(ValueError,match='another_run'):
        runner.read_ledger(tmp_path,runner.MONTH,path,'other')
    assert file_sha256(old)==old_hash


def test_query_resume_uses_only_published_job(tmp_path):
    from google.api_core.exceptions import NotFound
    spec = runner.frozen_queries()['usage']
    run_id = 'ab'*32
    job = SimpleNamespace(job_id=f'dynapm_v4c2_g_usage_{run_id[:24]}',project='p',location='US',
        query=runner.render_plan_query(runner.TEMPLATES['usage'],'g'),use_query_cache=False,
        maximum_bytes_billed=spec['maximum_bytes_billed'])
    client = Mock()
    client.query.return_value = job
    client.get_job.return_value = job
    billing = Mock()
    dry = Mock(return_value=spec['expected_bytes'])
    for _ in range(2):
        assert runner.open_query(tmp_path,client,'p','usage',spec,run_id,0,billing,dry)[0] is job
    assert client.query.call_count==1 and dry.call_count==1 and client.get_job.call_count==1
    client.get_job.side_effect = NotFound('not yet visible')
    with pytest.raises(ValueError,match='uncertain_no_rescan'):
        runner.open_query(tmp_path,client,'p','usage',spec,run_id,0,billing,dry)
    assert client.query.call_count==1


def test_storage_read_reuses_session_and_committed_offsets(tmp_path,monkeypatch):
    from datetime import datetime, timezone
    from google.cloud import bigquery_storage_v1 as storage
    name = 'projects/p/datasets/_anon/tables/t'
    session = storage.types.ReadSession(table=name,name='session1',streams=[storage.types.ReadStream(name='stream1')])
    client = Mock()
    client.create_read_session.return_value = session
    monkeypatch.setattr(storage,'BigQueryReadClient',lambda *, credentials:client)
    monkeypatch.setattr(durable,'verify_storage_read_zero_spend',lambda *_:None)
    job = SimpleNamespace(job_id='job',destination=SimpleNamespace(project='p',dataset_id='_anon',table_id='t'))
    table = SimpleNamespace(created=datetime(2026,11,6,tzinfo=timezone.utc),etag='same',num_rows=4)
    calls = []

    def pages(stream, *, offset):
        calls.append((stream,offset))
        def generate():
            if offset==0:
                yield SimpleNamespace(to_arrow=lambda:pa.table({'v':[1,2]}))
                raise OSError('interrupted')
            yield SimpleNamespace(to_arrow=lambda:pa.table({'v':[2,3]}))
        return SimpleNamespace(rows=lambda active:SimpleNamespace(pages=generate()))

    client.read_rows.side_effect = pages
    with pytest.raises(OSError,match='interrupted'):
        durable.download_result(job,table,tmp_path,'p',credentials=None)
    result = durable.download_result(job,table,tmp_path,'p',credentials=None)
    paths = runner.raw_paths(tmp_path,result)
    assert pa.concat_tables([pq.read_table(p) for p in paths])['v'].to_pylist()==[1,2,2,3]
    assert calls==[('stream1',0),('stream1',2)]
    assert client.create_read_session.call_count==1
    assert durable.download_result(job,table,tmp_path,'p',credentials=None)==result
    table.etag = 'changed'
    with pytest.raises(ValueError,match='result_identity_changed'):
        durable.download_result(job,table,tmp_path,'p',credentials=None)
    paths[-1].chmod(0o644)
    pq.write_table(pa.table({'v':[3,4]}),paths[-1])
    with pytest.raises(ValueError,match='offset|chunk'):
        runner.raw_paths(tmp_path,result)


def test_phase_recovers_atomic_outputs_without_replay(tmp_path):
    calls=[]
    def produce(stage):
        calls.append(stage)
        (stage/'value').write_text('result')
        if len(calls)==1:
            raise OSError('interruption')
        return {'result':1}
    with pytest.raises(OSError):
        runner.phase(tmp_path,'phase',{'bound':True},produce)
    for _ in range(2):
        assert runner.phase(tmp_path,'phase',{'bound':True},produce)=={'result':1}
    assert len(calls)==2
    with pytest.raises(ValueError,match='sealed_phase'):
        runner.phase(tmp_path,'phase',{'bound':False},produce)


def test_g_canonical_and_deterministic_held_out_selection(tmp_path):
    e = tmp_path/'events.parquet'
    u = tmp_path/'usage.parquet'
    events().to_parquet(e,index=False)
    usage().to_parquet(u,index=False)
    out = tmp_path/'canonical'
    out.mkdir()
    raw = dict(events={'rows':len(events())},usage={'rows':len(usage())})
    m = canonicalize(out,'g',raw,dict(events=[e],usage=[u]),'fixture')
    assert require_corrected_generation(out)==m
    assert m['diagnostics']['request_history']['ambiguous_groups']==1
    assert m['validation']['ambiguous_requests_selected']==0
    assert m['output_row_count']+m['diagnostics']['rejected_rows']==len(usage())
    canonical = pq.read_table(out/'canonical_usage').to_pandas()
    assert canonical.cell.tolist()==['g','g']
    assert all('clusterdata_2019_g.' in t for t in canonical.usage_source_table)
    table = pd.DataFrame(dict(cell=['g']*1002,collection_id=range(1002),instance_index=0,
                              nominal_protocol_eligible=True))
    eligibility = tmp_path/'eligibility.parquet'
    rule = dict(mode='lowest_sha256_per_cell',maximum_entities_per_cell=1000)
    protocol = dict(protocol_fingerprint='frozen',clock_contract_sha256='clock')
    identities=[]
    for n in (1,2):
        table.sample(frac=1,random_state=n).to_parquet(eligibility,index=False)
        folder = tmp_path/f'cohort-{n}'
        folder.mkdir()
        assert freeze_cohort(folder,'g',m['canonical_dataset_sha256'],eligibility,protocol,rule)['cohort_size']==1000
        identities.append(read_json(folder/'g_cohort.json')['entities'])
    assert identities[0]==identities[1]


def test_complete_local_g_phases_and_resume(tmp_path,monkeypatch):
    import numpy as np
    interval = 300_000_000
    n = 4200
    starts = np.arange(n,dtype='int64')*interval
    e = tmp_path/'events.parquet'
    u = tmp_path/'usage.parquet'
    events().iloc[[0]].to_parquet(e,index=False)
    pd.DataFrame(dict(collection_id=1,instance_index=0,collection_type=1,start_time=starts,
                      end_time=starts+interval,average_cpu=3.,average_memory=2.)).to_parquet(u,index=False)
    root = tmp_path/'g'
    root.mkdir()
    (tmp_path/'configs').mkdir()
    write_json(tmp_path/runner.E_BINDING,{'cohort_path':'e','cell':'e'})
    monkeypatch.setattr(runner,'load_stage_inputs',Mock())
    raw = dict(events={'rows':1},usage={'rows':n})
    protocol = dict(protocol_fingerprint='protocol',clock_contract_sha256='clock')
    design = dict(cohort_selection_rule={'mode':'lowest_sha256_per_cell','maximum_entities_per_cell':1000})
    files = dict(events=[e],usage=[u])
    binding,manifest = runner.finish(tmp_path,root,'source',raw,files,protocol,design)
    assert read_json(manifest)['stage_b_executed'] is False
    assert read_json(root/'availability/manifest.json')['summary']['eligible_entities']==1
    assert read_json(tmp_path/binding['cohort_path'])['entities'][0]['cell']=='g'
    monkeypatch.setattr(runner,'canonicalize',Mock(side_effect=AssertionError('replayed completed phase')))
    assert runner.finish(tmp_path,root,'source',raw,files,protocol,design)==(binding,manifest)


def test_live_preflight_respects_existing_v8_lock(tmp_path,monkeypatch):
    import fcntl
    root = tmp_path/runner.V8_CAMPAIGN
    root.mkdir(parents=True)
    lock = root/'.lock'
    lock.touch()
    monkeypatch.setattr(runner,'completed_attempts',Mock())
    monkeypatch.setattr(runner.subprocess,'check_output',Mock(return_value=b''))
    with lock.open('rb') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            with runner.idle_v8(tmp_path):
                pytest.fail('active V8 campaign was admitted')
    before = file_sha256(lock)
    with runner.idle_v8(tmp_path):
        pass
    assert file_sha256(lock)==before


def test_source_only_continuation_keeps_original_job_binding(tmp_path):
    from dynapm.core.provenance import fingerprint
    old = dict(source_commit='original',month=runner.MONTH,queries=runner.frozen_queries(),project='p')
    initial = dict(old,run_id=fingerprint(old),preflight={'safe':True})
    write_json(tmp_path/'run.json',initial)
    new = dict(old,source_commit='direct-child')
    assert runner.bind_existing_run(tmp_path,initial,old,None,None)==initial['run_id']
    with pytest.raises(ValueError,match='incompatible'):
        runner.bind_existing_run(tmp_path,initial,new,None,None)
    with pytest.raises(ValueError,match='incompatible'):
        runner.bind_existing_run(tmp_path,initial,dict(new,project='other'),'original','original')
    assert runner.bind_existing_run(tmp_path,initial,new,'original','original')==initial['run_id']
    assert runner.bind_existing_run(tmp_path,initial,new,'original','original')==initial['run_id']
    assert read_json(tmp_path/'run.json')==initial


def test_partitioned_request_history_reconciles_event_only_and_usage_only_entities(tmp_path):
    e = tmp_path/'events.parquet'
    u = tmp_path/'usage.parquet'
    pd.concat([events(),events().assign(collection_id=9000)]).to_parquet(e,index=False)
    pd.concat([usage(),usage().assign(collection_id=8000)]).to_parquet(u,index=False)
    out = tmp_path/'generation'
    out.mkdir()
    m = canonicalize(out,'g',dict(events={'rows':12},usage={'rows':8}),dict(events=[e],usage=[u]),'fixture')
    assert m['diagnostics']['request_history']['raw_event_rows']==12
    assert m['diagnostics']['request_history']['ambiguous_groups']==2
    assert m['validation']['ambiguous_groups_excluded']==2
    assert m['diagnostics']['exclusion_reasons']['missing_unambiguous_positive_request']==4


def test_recovery_is_single_dispatch_with_original_usage_id(tmp_path):
    from google.api_core.exceptions import NotFound
    from dynapm.core.provenance import utc_now
    run_id = 'fa'*32
    spec = runner.frozen_queries()['usage']
    job_id = f'dynapm_v4c2_g_usage_{run_id[:24]}'
    job = SimpleNamespace(job_id=job_id,project='p',location='US',
        query=runner.render_plan_query(runner.TEMPLATES['usage'],'g'),use_query_cache=False,
        maximum_bytes_billed=spec['maximum_bytes_billed'])
    client = Mock()
    client.query.return_value = job
    client.get_job.side_effect = NotFound('no usage job')
    billing = Mock()
    dry = Mock(return_value=spec['expected_bytes'])
    log = tmp_path/'usage-pre-submit-failure.log'
    log.write_text('in open_query\n    billing(project)\nAcquisitionBlocked: billing_info_unavailable\n')
    intent = tmp_path/'usage-query.json'
    binding = dict(kind='usage',job_id=job_id,project='p',location='US',spec=spec,month=runner.MONTH)
    write_json(intent,dict(binding=binding,dry_run_bytes=spec['expected_bytes'],created_at=utc_now()))
    proof = tmp_path/'usage-pre-submit-recovery.json'
    write_json(proof,dict(run_id=run_id,job_id=job_id,intent_sha256=file_sha256(intent),
        failure='BILLING_CHECK_FAILED_BEFORE_SUBMIT',server_lookup='NOT_FOUND',execution_log_sha256=file_sha256(log)))
    assert runner.open_query(tmp_path,client,'p','usage',spec,run_id,0,billing,dry,recovery=proof)[0] is job
    assert client.query.call_args.kwargs['job_id']==job_id
    with pytest.raises(ValueError,match='uncertain_no_rescan'):
        runner.open_query(tmp_path,client,'p','usage',spec,run_id,0,billing,dry,recovery=proof)
    client.get_job.side_effect = None
    client.get_job.return_value = job
    assert runner.open_query(tmp_path,client,'p','usage',spec,run_id,0,billing,dry)[0] is job
    assert client.query.call_count==dry.call_count==1


def test_failed_final_billing_check_leaves_no_fresh_intent(tmp_path):
    spec = runner.frozen_queries()['usage']
    client = Mock()
    billing = Mock(side_effect=[None,ValueError('billing unavailable')])
    with pytest.raises(ValueError,match='billing unavailable'):
        runner.open_query(tmp_path,client,'p','usage',spec,'c'*64,0,billing,Mock(return_value=spec['expected_bytes']))
    assert not (tmp_path/'usage-query.json').exists()
    client.query.assert_not_called()
