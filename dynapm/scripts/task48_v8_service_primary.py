"""Versioned Service primary executor. Diagnostic scope uses the exact primary lifecycle."""
import argparse
import signal
from pathlib import Path

from dynapm.core.provenance import read_json, file_sha256
from dynapm.system_validation.service_primary import campaign, stable_spec_hash


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',type=Path,required=True)
    p.add_argument('--spec-sha256',required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--scope',choices=('DIAGNOSTIC_NON_CLAIM','AMENDED_V8_PRIMARY','DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'),required=True)
    p.add_argument('--authorize-diagnostic',action='store_true')
    p.add_argument('--authorize-battery-nonqualifying',action='store_true')
    p.add_argument('--authorize-claim',action='store_true')
    p.add_argument('--qualification',type=Path)
    p.add_argument('--qualification-sha256')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--max-slots',type=int)
    p.add_argument('--stop-after-slot',type=int)
    a=p.parse_args()
    if file_sha256(a.spec)!=a.spec_sha256:raise ValueError('executor_spec_hash_mismatch')
    if a.scope=='DIAGNOSTIC_NON_CLAIM' and not a.authorize_diagnostic:raise ValueError('explicit_diagnostic_authorization_required')
    if a.scope=='DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING' and not a.authorize_battery_nonqualifying:
        raise ValueError('explicit_nonqualifying_battery_authorization_required')
    qualification=None
    if a.scope=='AMENDED_V8_PRIMARY':
        if not a.authorize_claim or not a.qualification or not a.qualification_sha256:
            raise ValueError('explicit_claim_authorization_and_qualification_required')
        if file_sha256(a.qualification)!=a.qualification_sha256:raise ValueError('primary_qualification_hash_mismatch')
        qualification=read_json(a.qualification)
        if qualification.get('campaign_spec_sha256')!=stable_spec_hash(read_json(a.spec)):raise ValueError('qualified_spec_mismatch')
        root=a.qualification.parent
        for path,digest in qualification.get('files',{}).items():
            candidate=(root/path).resolve()
            if Path(path).is_absolute() or '..' in Path(path).parts or not candidate.is_relative_to(root.resolve()) or file_sha256(candidate)!=digest:
                raise ValueError('qualification_evidence_tampered')
        if not qualification.get('files'):raise ValueError('qualification_inventory_missing')
    def interrupted(*_):raise KeyboardInterrupt('launcher_signal')
    signal.signal(signal.SIGTERM,interrupted)
    state=campaign(Path.cwd(),a.root.resolve(),read_json(a.spec),a.scope,resume=a.resume,
        max_slots=a.max_slots,stop_after_slot=a.stop_after_slot,qualification=qualification)
    print('slots:',[(s['cell']['sequence'],s['status']) for s in state['slots']],flush=True)


if __name__=='__main__':main()
