"""Shared-bootstrap artifact tooling only; never starts a workload or trial."""
import argparse
from pathlib import Path
from dynapm.core.provenance import read_json,canonical_json
from dynapm.system_validation.estimation_design import frozen_spec
from dynapm.system_validation.shared_bootstrap import create_artifact,load_artifact,contract_specification


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    sub=p.add_subparsers(dest='action',required=True)
    f=sub.add_parser('freeze');f.add_argument('--acquisition-run',type=Path,required=True)
    f.add_argument('--artifact-store',type=Path,required=True)
    v=sub.add_parser('validate');v.add_argument('--artifact',type=Path,required=True)
    v.add_argument('--expected-sha256',required=True)
    a=p.parse_args();design=frozen_spec(a.repo)
    if read_json(a.repo/'configs/system_shared_bootstrap_v1.json')!=contract_specification(a.repo,design):
        raise ValueError('shared_bootstrap_contract_mismatch')
    if a.action=='freeze':
        root=create_artifact(a.acquisition_run,a.artifact_store,design)
        print(canonical_json(dict(path=str(root),artifact_sha256=root.name)))
    else:
        m,b=load_artifact(a.artifact,a.expected_sha256,design)
        print(canonical_json(dict(status='VALID',artifact_sha256=m['artifact_sha256'],paired_slots=b.accepted_slots)))


if __name__=='__main__':main()
