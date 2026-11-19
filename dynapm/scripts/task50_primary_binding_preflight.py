"""Strict primary preflight under the observer-binding amendment ONLY.

Never calls campaign() or treatment(): no cooldown, cluster, generator, 75-minute
lifecycle, claim treatment or integration can start from this entry point.
"""
import argparse
import json
from pathlib import Path
import traceback

from dynapm.core.provenance import canonical_json, file_sha256, read_json, utc_now
from dynapm.system_validation.service_primary import host_qualification, preflight, source_binding

# The pending 18-slot strict-AC qualification checkpoint must stay byte-identical.
PROTECTED_CHECKPOINT = 'results/v8c_r2/20261109-next-strict-ac/qualification-campaign/checkpoint.json'
PROTECTED_CHECKPOINT_SHA256 = '16c07107b4063037c922ea766398c72e526a4d68f4e931f184a5c0264ad07ce6'


def protected_state(repo):
    path = repo/PROTECTED_CHECKPOINT
    state = read_json(path)
    return dict(sha256=file_sha256(path), unchanged=file_sha256(path) == PROTECTED_CHECKPOINT_SHA256,
                slots=len(state['slots']), all_pending=all(s['status'] == 'PENDING' for s in state['slots']))


def run(repo, spec_path, spec_sha256, root, remaining):
    if file_sha256(spec_path) != spec_sha256:
        raise ValueError('executor_spec_hash_mismatch')
    spec = read_json(spec_path)
    before = protected_state(repo)
    if not (before['unchanged'] and before['slots'] == 18 and before['all_pending']):
        raise ValueError('protected_pending_checkpoint_changed')
    gates = {}
    record = dict(schema='v8-primary-binding-strict-preflight-v1', spec_sha256=spec_sha256,
                  remaining_slots=remaining, gates=gates, primary_lifecycle_started=False,
                  claim_started=False, integration_started=False, protected_checkpoint_before=before)
    try:
        gates['source_binding'] = source_binding(repo, spec)
        gates['host_qualification'] = host_qualification(repo, spec)
        session, _, _, _ = preflight(repo, root, spec, remaining)
        gates['strict_preflight'] = session
        record.update(status='PASS')
    except Exception as exc:
        record.update(status='BLOCKED', exception_type=type(exc).__name__, reason=str(exc),
                      failed_after_gates=list(gates), traceback=traceback.format_exc())
    after = protected_state(repo)
    record.update(protected_checkpoint_after=after, recorded_at=utc_now())
    if after != before:
        record.update(status='BLOCKED', reason='protected_pending_checkpoint_changed')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--spec-sha256', required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--remaining', type=int, default=18)
    p.add_argument('--result', type=Path, required=True)
    a = p.parse_args()
    repo = Path.cwd().resolve()
    record = run(repo, a.spec.resolve(), a.spec_sha256, a.root.resolve(), a.remaining)
    a.result.write_text(canonical_json(record)+'\n')
    print(json.dumps({k: record[k] for k in ('status', 'reason') if k in record}), flush=True)


if __name__ == '__main__':
    main()
