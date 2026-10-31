"""Explicit operator authorization fixtures, never physical host qualification."""
from types import SimpleNamespace
import json
import pytest
from dynapm.system_validation import calibration_runner as runner


def record(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.SourceProvenance,'capture',lambda repo:SimpleNamespace(commit='a'*40))
    monkeypatch.setattr(runner.subprocess,'check_output',lambda *a,**k:'UNIT_BOOT\n')
    p=tmp_path/'results/shared_bootstrap/authorization.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps(dict(schema_version='authorized-bootstrap-host-deviation-v1',maximum_acquisitions=1,
        allow_external_power_deficit=True,current_boot_endurance_waived=True,claim_eligible=False,
        source_commit='a'*40,boot_uuid='UNIT_BOOT')))
    return p


def test_explicit_authorization_is_bound_and_single_use(tmp_path,monkeypatch):
    p=record(tmp_path,monkeypatch)
    result=runner.consume_host_deviation(tmp_path,p,bootstrap_only=True,plumbing_only=False)
    assert result['claim_eligible'] is False and result['endurance_qualified'] is False
    assert len(result['record_sha256'])==64 and p.with_suffix('.consumed').exists()
    with pytest.raises(FileExistsError):runner.consume_host_deviation(tmp_path,p,bootstrap_only=True,plumbing_only=False)


@pytest.mark.parametrize('bootstrap,plumbing',[(False,False),(False,True),(True,True)])
def test_authorization_cannot_enable_calibration_or_smoke(tmp_path,monkeypatch,bootstrap,plumbing):
    p=record(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='bootstrap_only_required'):
        runner.consume_host_deviation(tmp_path,p,bootstrap_only=bootstrap,plumbing_only=plumbing)
    assert not p.with_suffix('.consumed').exists()


@pytest.mark.parametrize('field,value,reason',[('source_commit','b'*40,'invalid_host_deviation'),('boot_uuid','OTHER_BOOT','boot_mismatch'),('claim_eligible',True,'invalid_host_deviation'),('maximum_acquisitions',2,'invalid_host_deviation')])
def test_authorization_rejects_wrong_identity_or_scope(tmp_path,monkeypatch,field,value,reason):
    p=record(tmp_path,monkeypatch);v=json.loads(p.read_text());v[field]=value;p.write_text(json.dumps(v))
    with pytest.raises(ValueError,match=reason):runner.consume_host_deviation(tmp_path,p,bootstrap_only=True,plumbing_only=False)
    assert not p.with_suffix('.consumed').exists()
