"""Battery mechanics are explicit non-qualifying diagnostics, never AC admission."""
from types import SimpleNamespace
import json
import pytest
from dynapm.system_validation import battery_diagnostic_guard as b
from dynapm.system_validation.v8_host_identity import parse_boot


def fixture(tmp_path,monkeypatch):
    guard=b.BatteryDiagnosticGuard(tmp_path,{'scope':b.SCOPE})
    guard.out.mkdir()
    guard.process=SimpleNamespace(pid=123,poll=lambda:None)
    clock=[10**12,10**12]
    monkeypatch.setattr(b,'time',SimpleNamespace(time_ns=lambda:clock[0],monotonic_ns=lambda:clock[1]))
    boot=parse_boot('00000000-0000-0000-0000-000000000001','{ sec = 1, usec = 0 }')
    monkeypatch.setattr(b,'read_boot',lambda:dict(boot))
    monkeypatch.setattr(b,'battery_diagnostics',lambda:dict(CurrentCapacity=97,InstantAmperage=-1000,ExternalConnected=False))
    def command(args):
        if args[-1]=='custom':return 'lowpowermode 0'
        if args[-1]=='assertions':return 'pid 123(caffeinate): PreventUserIdleSystemSleep named: diagnostic'
        if args[-1]=='batt':return "Now drawing from 'Battery Power'"
        return '"AppleClamshellState" = No'
    monkeypatch.setattr(b,'command',command)
    return guard,clock,boot


def test_battery_record_is_never_a_claim_certificate(tmp_path,monkeypatch):
    guard,clock,_=fixture(tmp_path,monkeypatch)
    point=guard.checkpoint()
    assert point['scope']==b.SCOPE and point['claim_qualification_eligible'] is False
    assert point['power']['ac_power'] is False
    assert point['power']['prevent_system_sleep_qualified'] is False
    clock[0]+=5*10**9;clock[1]+=5*10**9
    guard.checkpoint()
    assert guard.max_gap==5*10**9 and guard.max_drift==0


@pytest.mark.parametrize('kind',['gap','drift','reboot','lid'])
def test_nonqualifying_scope_still_fails_on_continuity_loss(tmp_path,monkeypatch,kind):
    guard,clock,boot=fixture(tmp_path,monkeypatch)
    guard.checkpoint()
    clock[0]+=5*10**9;clock[1]+=5*10**9
    if kind=='gap':clock[0]+=30*10**9;clock[1]+=30*10**9
    if kind=='drift':clock[0]+=3*10**9
    if kind=='reboot':monkeypatch.setattr(b,'read_boot',lambda:dict(boot,boot_uuid='00000000-0000-0000-0000-000000000002'))
    if kind=='lid':
        original=b.command
        monkeypatch.setattr(b,'command',lambda a:'"AppleClamshellState" = Yes' if a[0]=='/usr/sbin/ioreg' else original(a))
    with pytest.raises(b.PowerGuardError):guard.checkpoint()
    failure=json.loads((guard.out/'host_continuity_failure.json').read_text())
    assert failure['claim_qualification_eligible'] is False


def test_strict_ac_power_gate_still_rejects_battery():
    from dynapm.system_validation.host_power import power_state
    with pytest.raises(b.PowerGuardError,match='mains_power_lost'):
        power_state(lambda args:"Now drawing from 'Battery Power'")
