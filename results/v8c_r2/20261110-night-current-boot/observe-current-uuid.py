"""Supplemental UUID witness around the unchanged managed host-endurance command."""
import datetime,json,os,subprocess,time
from pathlib import Path
from dynapm.core.provenance import canonical_json,file_sha256
from dynapm.system_validation.v8_host_identity import read_boot

root=Path(__file__).resolve().parent
intent=json.loads((root/'intent.json').read_text())
args=[str(Path.cwd()/'.venv/bin/python'),'-m','dynapm.scripts.task35_host_endurance','--repo',str(Path.cwd()),'--observe','--duration-seconds','10800']
start_wall=time.time_ns();start=time.monotonic_ns();failure=None;previous=None
with (root/'host-observation.log').open('x') as log, (root/'boot-uuid-witness.jsonl').open('x') as witness:
    child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
    try:
        while True:
            w=time.time_ns();m=time.monotonic_ns();boot=read_boot()
            row=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_ns=w,monotonic_ns=m,boot=boot,child_pid=child.pid)
            witness.write(canonical_json(row)+'\n');witness.flush();os.fsync(witness.fileno())
            if boot['boot_uuid']!=intent['expected_boot_uuid']:raise ValueError('supplemental_boot_uuid_mismatch')
            if previous is not None and m-previous>30_000_000_000:raise ValueError('supplemental_uuid_witness_gap')
            if abs((w-start_wall)-(m-start))>2_000_000_000:raise ValueError('supplemental_wall_monotonic_discontinuity')
            previous=m
            if child.poll() is not None:break
            time.sleep(5)
    except BaseException as exc:
        failure=dict(type=type(exc).__name__,message=str(exc))
        if child.poll() is None:child.terminate()
    finally:
        code=child.wait(timeout=30)
record=dict(status='HOST_COMMAND_COMPLETE' if code==0 and failure is None else 'FAILED',returncode=code,failure=failure,elapsed_monotonic_seconds=(time.monotonic_ns()-start)/1e9,expected_boot_uuid=intent['expected_boot_uuid'],command=args,log_sha256=file_sha256(root/'host-observation.log'),witness_sha256=file_sha256(root/'boot-uuid-witness.jsonl'),recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
(root/'observation-terminal.json').write_text(canonical_json(record)+'\n')
print(canonical_json(record),flush=True)
