"""Secondary Google collection sensitivity; no acquisition or policy execution."""
import argparse
from pathlib import Path
from dynapm.core.provenance import canonical_json,fingerprint
from dynapm.experiments.google_collection_robustness import frozen_spec,run_secondary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--cell',choices=('e','g'),required=True)
    p.add_argument('--primary-run',type=Path)
    p.add_argument('--execute',action='store_true')
    args=p.parse_args()
    spec=frozen_spec(args.repo)
    if args.execute:
        if args.primary_run is None:p.error('--execute requires --primary-run')
        print(canonical_json(dict(run_path=str(run_secondary(args.repo,args.primary_run,args.cell)))))
    else:
        print(canonical_json(dict(status='SECONDARY_SPEC_VERIFIED_NO_ANALYSIS',cell=args.cell,
            scope=spec['scopes'][args.cell],spec_sha256=fingerprint(spec))))

if __name__=='__main__':main()
