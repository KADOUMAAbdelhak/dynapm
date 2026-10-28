"""V7A local system harness; comparative/claim-generating execution is disabled."""
import argparse
from pathlib import Path
from dynapm.core.provenance import canonical_json,fingerprint
from dynapm.system_validation.design import frozen_design
from dynapm.system_validation.smoke import run_smoke


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--smoke',action='store_true',help='one real five-minute bucket, one method, synthetic bootstrap; no comparative evidence')
    a=p.parse_args();d=frozen_design(a.repo)
    if a.smoke:print(canonical_json(dict(run_path=str(run_smoke(a.repo)))))
    else:print(canonical_json(dict(status='SYSTEM_DESIGN_VALIDATED_NO_DEPLOYMENT',design_sha256=fingerprint(d),claim_trials_enabled=False)))

if __name__=='__main__':main()
