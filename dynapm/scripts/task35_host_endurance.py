"""Host stability observation only; never starts Kubernetes or profile workloads."""
import argparse,signal
from pathlib import Path
from dynapm.system_validation.host_endurance import observe
from dynapm.system_validation.host_power import ENDURANCE_SECONDS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--observe',action='store_true')
    p.add_argument('--duration-seconds',type=int,default=ENDURANCE_SECONDS)
    a=p.parse_args()
    def terminate(signum,frame):raise KeyboardInterrupt('host_endurance_termination_requested:'+str(signum))
    signal.signal(signal.SIGTERM,terminate)
    if hasattr(signal,'SIGHUP'):signal.signal(signal.SIGHUP,terminate)
    if a.observe:observe(a.repo,a.duration_seconds)
    else:print('HOST OBSERVATION NOT STARTED; --observe requires a clean commit and 3–6 real hours')


if __name__=='__main__':main()
