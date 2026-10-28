"""Frozen sequential Google replication. Defaults to input verification, not outcomes."""
from pathlib import Path
import argparse
from dynapm.core.provenance import canonical_json,fingerprint
from dynapm.experiments.google_replication import load_stage_inputs,execute


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cell',choices=('e','g'),required=True)
    p.add_argument('--cohort-manifest',type=Path,required=True)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--workers',type=int,choices=(1,2,3,4),default=1)
    p.add_argument('--execute',action='store_true',help='explicitly execute outcomes; requires clean committed source')
    p.add_argument('--reuse-run',type=Path)
    args=p.parse_args()
    if args.reuse_run and not args.execute:p.error('--reuse-run requires --execute and full compatibility validation')
    if args.execute:
        result=execute(args.repo,args.cell,args.cohort_manifest,workers=args.workers,reuse_run=args.reuse_run)
        print(canonical_json(dict(run_path=str(result),cell=args.cell)))
    else:
        b=load_stage_inputs(args.repo,args.cell,args.cohort_manifest)
        print(canonical_json(dict(status='INPUTS_VERIFIED_NO_OUTCOMES',cell=args.cell,entities=len(b['entities']),
            method_entity_runs=len(b['entities'])*5,design_fingerprint=fingerprint(b['design']),execution_performed=False)))

if __name__=='__main__':main()
