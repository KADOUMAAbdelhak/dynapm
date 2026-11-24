#!/bin/zsh
# Usage: run_block.sh <block-number> [slots, default 3]. Gate first; block 1 fresh, later blocks --resume.
cd /Users/fgtek002/dynapm-v8c-frozen
V=results/v8c_r2/amended-v8-claim-campaign-v2
N=$1
G=$V/block-$N-gate.json
PYTHONPATH=. .venv/bin/python - "$N" > $G <<'PY'
import json,shutil,subprocess,sys
from dynapm.core.provenance import utc_now
from dynapm.system_validation.v8_host_identity import read_boot
n=int(sys.argv[1]);free=shutil.disk_usage('.').free;boot=read_boot()
batt=subprocess.check_output(['/usr/bin/pmset','-g','batt'],text=True)
pm=subprocess.check_output(['/usr/bin/pmset','-g','custom'],text=True)
guard=json.load(open('results/host_endurance/runs/9df3b3f0b8dfde31caa25c6533a1df342cf6f7d3f13cb6f56bc003c0755535ed/2026-11-22T151815.248945Z-9df3b3f0b8df-30075d02/outputs/power_guard.json'))
kind=subprocess.run(['kind','get','clusters'],capture_output=True,text=True)
docker_up=subprocess.run(['docker','info'],capture_output=True).returncode==0
clusters=[l for l in (kind.stdout).splitlines() if l.strip()]
checks=dict(free_ge_31GB=free>=31e9,same_boot=boot['boot_uuid']=='26051F76-7B84-4CBD-A25D-1418E39980A2',
 ac_power="AC Power" in batt,pmset_unchanged=pm==guard['power_settings'],no_kind_cluster=not clusters and kind.returncode==0,docker_up=docker_up,
 clean_source=subprocess.check_output(['git','status','--porcelain'],text=True).strip()=='')
print(json.dumps(dict(block=n,checks=checks,free_bytes=free,boot=boot,clusters=clusters,passed=all(checks.values()),recorded_at=utc_now()),sort_keys=True))
PY
if ! python3 -c "import json,sys;sys.exit(0 if json.load(open('$G'))['passed'] else 1)"; then echo "GATE FAILED block $N"; cat $G; exit 3; fi
# Amendment v3: once intent-amendment-v3.json exists, resumed blocks use spec v3 + Step B v3 qualification.
I=$V/intent.json; [[ -f $V/intent-amendment-v3.json ]] && I=$V/intent-amendment-v3.json
echo "intent $I $(shasum -a 256 $I | cut -d' ' -f1)" > $V/block-$N-intent.txt
CMD=($(python3 -c "import json;d=json.load(open('$I'));print(' '.join(d['first_block'] if $N==1 else d['later_blocks']))"))
SLOTS=${2:-3}
case "$SLOTS" in 1|2|3) ;; *) echo "slots must be 1-3"; exit 2;; esac
for ((i=1; i<=${#CMD}; i++)); do [[ "${CMD[$i]}" == "--max-slots" ]] && CMD[$((i+1))]=$SLOTS; done
echo "block $N slots $SLOTS" > $V/block-$N-slots.txt
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"${CMD[@]}" > $V/block-$N-execution.log 2>&1
RC=$?
printf '{"block":%d,"started_at":"%s","finished_at":"%s","returncode":%d,"log_sha256":"%s"}\n' $N "$START" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $RC "$(shasum -a 256 $V/block-$N-execution.log | cut -d' ' -f1)" > $V/block-$N-terminal.json
exit $RC
