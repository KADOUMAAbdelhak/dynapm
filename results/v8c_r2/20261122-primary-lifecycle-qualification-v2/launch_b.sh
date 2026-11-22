#!/bin/zsh
cd /Users/fgtek002/dynapm-v8c-frozen
L=results/v8c_r2/20261122-primary-lifecycle-qualification-v2
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CMD=($(python3 -c "import json;print(' '.join(json.load(open('$L/intent.json'))['command']))"))
"${CMD[@]}" > $L/lifecycle-execution.log 2>&1
RC=$?
printf '{"started_at":"%s","finished_at":"%s","returncode":%d,"log_sha256":"%s"}\n' "$START" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $RC "$(shasum -a 256 $L/lifecycle-execution.log | cut -d' ' -f1)" > $L/launcher-terminal.json
exit $RC
