"""Historical V7B v1 preparation (superseded by task34); no Kubernetes execution or comparative outcomes."""
import argparse
from pathlib import Path
from dynapm.core.provenance import canonical_json
from dynapm.system_validation.trial_preparation import preparation_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    args=parser.parse_args()
    print(canonical_json(preparation_report(args.repo)))

if __name__=='__main__':main()
