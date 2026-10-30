"""Synthetic binding/contract checks; no Kubernetes command is executed."""
from pathlib import Path
import sys

from dynapm.core.provenance import read_json
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.shared_bootstrap import contract_specification
from dynapm.system_validation.timing_probes import contract_specification as timing_contract

ROOT=Path(__file__).parents[2]


def test_frozen_shared_and_timing_contracts_match_implementation():
    d=frozen_spec(ROOT)
    shared=read_json(ROOT/'configs/system_shared_bootstrap_v1.json')
    assert shared==contract_specification(ROOT,d)
    assert not shared['requires_completed_72h_anchor'] and shared['bootstrap_only_acquisition_supported']
    timing=read_json(ROOT/'configs/system_neutral_timing_probes_v1.json')
    assert timing==timing_contract(ROOT) and not timing['launch_enabled']
    assert not timing['compression_duration_selected']


def test_bootstrap_only_cli_binds_one_collection_without_campaign(monkeypatch,capsys):
    from dynapm.scripts import task34_system_calibration as cli
    calls=[]
    monkeypatch.setattr(sys,'argv',['unit','--collect-bootstrap-only','--host-endurance-run','UNIT_CERTIFICATE'])
    monkeypatch.setattr(cli.signal,'signal',lambda *a:None)
    monkeypatch.setattr(cli,'frozen_spec',lambda repo:{})
    monkeypatch.setattr(cli,'calibration_plan',lambda repo:[{'method':'pw_6h','scenario':'stable'}])
    def collect(repo,trial,**kwargs):calls.append((trial,kwargs));return Path('UNIT_NOT_A_REAL_RUN')
    monkeypatch.setattr(cli,'run_trial',collect)
    monkeypatch.setattr(cli,'campaign',lambda *a,**k:(_ for _ in ()).throw(AssertionError('no campaign')))
    cli.main()
    assert len(calls)==1 and calls[0][0]=={'method':'pw_6h','scenario':'stable'}
    assert calls[0][1]=={'bootstrap_only':True,'host_endurance_run':Path('UNIT_CERTIFICATE')}
    assert 'UNIT_NOT_A_REAL_RUN' in capsys.readouterr().out
