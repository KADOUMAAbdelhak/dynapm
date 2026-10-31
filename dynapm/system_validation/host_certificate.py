"""Host-safety compatibility only; never scientific result-cache compatibility."""
import ast
import hashlib
from pathlib import Path
import re
import subprocess

SCHEMA='host-runtime-compatibility-v2'
RUNTIME=('dynapm/system_validation/host_power.py',
    'dynapm/scripts/task35_host_endurance.py','dynapm/core/provenance.py',
    'dynapm/core/run_store.py','dynapm/data/manifests.py')
OBSERVER='dynapm/system_validation/host_endurance.py'


def runtime_identity(repo,commit=None):
    repo=Path(repo)
    if commit is not None and not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('pinned_host_source_commit_required')
    def source(path):
        if commit is None:return (repo/path).read_bytes()
        try:return subprocess.check_output(['git','show',commit+':'+path],cwd=repo,stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:raise ValueError('host_source_object_unavailable:'+path) from exc
    result={p:hashlib.sha256(source(p)).hexdigest() for p in RUNTIME}
    # Pin the unchanged host-clock invariant, not unrelated cluster reception.
    clock='dynapm/system_validation/clock_observations.py'
    clock_tree=ast.parse(source(clock).decode())
    cls=next(n for n in clock_tree.body if isinstance(n,ast.ClassDef) and n.name=='ObservationClock')
    check=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='check_host')
    limit=next(n for n in clock_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_CLOCK_DELTA_NS' for t in n.targets))
    result[clock+'#host-invariant']=hashlib.sha256((ast.dump(check,include_attributes=False)+ast.dump(limit,include_attributes=False)).encode()).hexdigest()
    tree=ast.parse(source(OBSERVER).decode())
    # This helper is only called by future calibration, never by observe(). All
    # observation acquisition code, imports and constants are otherwise pinned.
    tree.body=[n for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) or n.name!='require_endurance']
    result[OBSERVER+'#acquisition']=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()
    return result


def require_same_host_runtime(repo,old_commit):
    old=runtime_identity(repo,old_commit);current=runtime_identity(repo)
    if old!=current:raise ValueError('host_endurance_runtime_mismatch')
    return dict(schema_version=SCHEMA,observation_source_commit=old_commit,runtime=current)
