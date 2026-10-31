"""Non-claim clock-domain probe; no workload, bootstrap or policy outcomes."""
import argparse
from pathlib import Path
from dynapm.core.provenance import canonical_json
from dynapm.system_validation.clock_probe import probe,SECONDS,POLL_SECONDS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--run',action='store_true',help='explicit bounded real cluster/host clock probe')
    a=p.parse_args()
    if a.run:probe(a.repo)
    else:print(canonical_json(dict(status='NOT_STARTED',duration_seconds=SECONDS,poll_seconds=POLL_SECONDS,workloads=0,bootstrap_slots=0,comparisons=0)))


if __name__=='__main__':main()
