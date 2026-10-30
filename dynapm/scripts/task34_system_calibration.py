"""V7B estimation-first neutral calibration; never executes comparative methods."""
import argparse,signal
from pathlib import Path
from dynapm.core.provenance import canonical_json,fingerprint
from dynapm.system_validation.estimation_design import frozen_spec,calibration_plan
from dynapm.system_validation.calibration_runner import run_trial,campaign


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--plumbing-check',action='store_true',help='one real bucket; NO policy initialization or calibration conclusion')
    mode.add_argument('--collect-bootstrap-only',action='store_true',help='one real 24h bootstrap acquisition; no policy initialization or measurement outcomes')
    mode.add_argument('--run-calibration',action='store_true',help='six maximum independent PW6 stable/periodic trials; >=18 days sequential')
    parser.add_argument('--maximum-trials',type=int,default=6)
    parser.add_argument('--host-endurance-run',type=Path,help='validated compatible-host-runtime managed >=3h host observation required for long trials')
    args=parser.parse_args();d=frozen_spec(args.repo)
    def terminate(signum,frame):raise KeyboardInterrupt('calibration_termination_requested')
    signal.signal(signal.SIGTERM,terminate)
    if args.plumbing_check:result=dict(run_path=str(run_trial(args.repo,calibration_plan(args.repo)[0],plumbing_only=True)))
    elif args.collect_bootstrap_only:result=dict(run_path=str(run_trial(args.repo,calibration_plan(args.repo)[0],bootstrap_only=True,host_endurance_run=args.host_endurance_run)))
    elif args.run_calibration:result=dict(campaign_record=str(campaign(args.repo,maximum_trials=args.maximum_trials,host_endurance_run=args.host_endurance_run)))
    else:result=dict(status='ESTIMATION_FIRST_CALIBRATION_REQUIRED',design_sha256=fingerprint(d),
        plan=calibration_plan(args.repo),practical_benefit='NOT_DEFINED',comparative_execution_enabled=False)
    print(canonical_json(result))

if __name__=='__main__':main()
