"""Stop the campaign cleanly after slot N seals, before slot N+1 begins (user-requested pause)."""
import json, os, signal, subprocess, sys, time
from datetime import datetime, timezone
V = 'results/v8c_r2/amended-v8-claim-campaign-v2'; N = int(sys.argv[1])
cp = V+'/claim-campaign/checkpoint.json'
def slots():
    try: return json.load(open(cp))['slots']
    except (OSError, ValueError): return None
while True:
    s = slots()
    if s and s[N-1]['status'] in ('SEALED_VALID', 'SEALED_INVALID', 'INTERRUPTED'): break
    time.sleep(0.25)
st, nxt = s[N-1]['status'], s[N]['status']
pids = [int(p) for p in subprocess.run(['pgrep', '-f', 'task48_v8_service_primary'], capture_output=True, text=True).stdout.split()]
action = 'none'
if st == 'SEALED_VALID' and nxt == 'PENDING' and pids:
    for p in pids: os.kill(p, signal.SIGTERM)
    action = 'SIGTERM_after_seal_before_next_begin'
time.sleep(5)
s2 = slots()
rec = dict(paused_after_slot=N, slot_status=st, next_status_at_signal=nxt, next_status_after=s2[N]['status'],
           pids=pids, action=action, recorded_at=datetime.now(timezone.utc).isoformat(),
           reason='User asked to pause the experiments and resume later')
out = V+'/pause-after-slot-%d.json' % N
while os.path.exists(out): out = out[:-5]+'-retry.json'
open(out, 'w').write(json.dumps(rec, sort_keys=True))
print(json.dumps(rec))
