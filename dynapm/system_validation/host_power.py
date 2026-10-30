"""Owned macOS assertions and independent fail-closed host continuity diagnostics.

Assertions prevent ordinary idle sleep, not lid-close/forced sleep. AC and an open
lid are required. No global power setting or scientific clock tolerance changes.
"""
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from dynapm.core.provenance import canonical_json,file_sha256,utc_now,fingerprint
from dynapm.core.run_store import write_json
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS

SCHEMA='managed-macos-power-v1'
CHECK_SECONDS=5
POWER_SECONDS=30
MAX_HEARTBEAT_GAP_NS=30_000_000_000
ENDURANCE_SECONDS=10800
TYPES=('PreventUserIdleSystemSleep','PreventSystemSleep')


class PowerGuardError(ValueError):
    pass


def command(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=2)
    if p.returncode:raise PowerGuardError('host_diagnostic_unavailable:'+args[0]+':'+p.stderr.strip())
    return p.stdout


def power_state(read=command):
    battery=read(['/usr/bin/pmset','-g','batt'])
    lid=read(['/usr/sbin/ioreg','-r','-k','AppleClamshellState','-d','4'])
    boot=read(['/usr/sbin/sysctl','-n','kern.boottime'])
    if not re.search(r"Now drawing from ['\"]AC Power['\"]",battery):
        raise PowerGuardError('mains_power_lost:'+battery.strip())
    closed=re.search(r'"AppleClamshellState"\s*=\s*(Yes|No)',lid)
    if not closed:raise PowerGuardError('lid_state_unavailable')
    if closed.group(1)!='No':raise PowerGuardError('lid_closed')
    epoch=re.search(r'\bsec\s*=\s*(\d+)',boot)
    if not epoch:raise PowerGuardError('boot_identity_unavailable')
    return dict(ac_power=True,lid_open=True,boot_epoch_seconds=int(epoch.group(1)),battery=battery.strip())


def assertion_lines(text,pid):
    return re.findall(r'^\s*pid\s+'+str(pid)+r'\(caffeinate\):[^\n]*',text,re.M)


def own_assertions(text,pid):
    lines=assertion_lines(text,pid)
    if not all(any(t in line for line in lines) for t in TYPES):
        raise PowerGuardError('owned_power_assertion_missing')
    return [line.strip() for line in lines]


class ManagedPowerGuard:
    def __init__(self,root,context,*,read=command,spawn=None,platform=None,background=True,startup_timeout=5):
        self.root=Path(root);self.out=self.root/'outputs';self.context=dict(context)
        self.read=read;self.spawn=spawn or subprocess.Popen;self.platform=platform or sys.platform
        self.background=background;self.startup_timeout=startup_timeout
        self.process=None;self.thread=None;self.stop_event=threading.Event();self.lock=threading.Lock()
        self.failure=None;self.previous=None;self.baseline=None;self.cached=None;self.last_power=None
        self.checkpoints=0;self.max_drift=0;self.max_gap=0;self.state={};self.started=False
        self.log=self.out/'host_continuity.jsonl'
        self.failure_path=self.out/'host_continuity_failure.json'

    def _append(self,row):
        with self.log.open('a') as f:
            f.write(canonical_json(row)+'\n');f.flush();os.fsync(f.fileno())

    def _fail(self,invariant,evidence):
        if self.failure is None:
            failure=dict(schema_version=SCHEMA,context=self.context,invariant=invariant,
                evidence=evidence,recorded_at=utc_now(),wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns())
            write_json(self.failure_path,failure)
            self._append(dict(kind='FAILURE',**failure))
            self.failure=failure
        raise PowerGuardError(invariant+'; host_continuity_failure_sha256='+file_sha256(self.failure_path))

    def _snapshot(self):
        if self.process is None or self.process.poll() is not None:
            raise PowerGuardError('power_assertion_process_exited')
        state=power_state(self.read)
        settings=self.read(['/usr/bin/pmset','-g','custom'])
        if settings!=self.state['power_settings']:raise PowerGuardError('host_power_policy_changed')
        state['power_settings_sha256']=fingerprint(settings)
        state['own_assertion_lines']=own_assertions(self.read(['/usr/bin/pmset','-g','assertions']),self.process.pid)
        if self.cached and state['boot_epoch_seconds']!=self.cached['boot_epoch_seconds']:
            raise PowerGuardError('host_boot_identity_changed')
        return state

    def checkpoint(self,*,wall_ns=None,mono_ns=None,force_power=False):
        with self.lock:
            self.raise_if_failed()
            wall=time.time_ns() if wall_ns is None else wall_ns
            mono=time.monotonic_ns() if mono_ns is None else mono_ns
            if self.baseline is None:self.baseline=(wall,mono)
            drift=(wall-self.baseline[0])-(mono-self.baseline[1])
            gap=0 if self.previous is None else mono-self.previous[1]
            evidence=dict(wall_ns=wall,monotonic_ns=mono,origin_wall_ns=self.baseline[0],
                origin_monotonic_ns=self.baseline[1],previous_checkpoint=self.previous,
                wall_minus_monotonic_elapsed_ns=drift,checkpoint_gap_ns=gap,assertion_pid=self.process.pid)
            if abs(drift)>MAX_CLOCK_DELTA_NS:self._fail('host_sleep_or_clock_discontinuity',evidence)
            if gap<0 or gap>MAX_HEARTBEAT_GAP_NS:self._fail('host_continuity_heartbeat_gap',evidence)
            self.max_drift=max(self.max_drift,abs(drift));self.max_gap=max(self.max_gap,gap)
            if force_power or self.last_power is None or mono-self.last_power>=POWER_SECONDS*10**9:
                try:self.cached=self._snapshot()
                except (OSError,subprocess.SubprocessError,PowerGuardError) as exc:
                    self._fail(str(exc),evidence)
                self.last_power=mono
            evidence.update(power=self.cached,uptime_seconds=wall/1e9-self.cached['boot_epoch_seconds'])
            self._append(dict(schema_version=SCHEMA,context=self.context,kind='CHECKPOINT',**evidence))
            self.previous=(wall,mono);self.checkpoints+=1
            self._summary('RUNNING')

    def _summary(self,status):
        write_json(self.out/'host_continuity_summary.json',dict(schema_version=SCHEMA,context=self.context,status=status,
            checkpoints=self.checkpoints,last_checkpoint=self.previous,maximum_absolute_drift_ns=self.max_drift,
            maximum_checkpoint_gap_ns=self.max_gap,failure=self.failure,
            log_sha256=None if status=='RUNNING' else file_sha256(self.log)))

    def raise_if_failed(self):
        if self.started and self.thread is not None and not self.thread.is_alive() and not self.stop_event.is_set() and self.failure is None:
            self._fail('host_continuity_monitor_exited',dict(assertion_pid=self.process.pid))
        if self.failure is not None:
            raise PowerGuardError(self.failure['invariant']+'; host_continuity_failure_sha256='+file_sha256(self.failure_path))

    def _loop(self):
        while not self.stop_event.wait(CHECK_SECONDS):
            try:self.checkpoint()
            except BaseException as exc:
                if self.failure is None:
                    try:self._fail('host_continuity_monitor_error',dict(error_type=type(exc).__name__,message=str(exc)))
                    except BaseException:pass
                return

    def __enter__(self):
        if self.platform!='darwin':raise PowerGuardError('macos_power_guard_requires_platform_adapter')
        self.out.mkdir(parents=True,exist_ok=True);self.log.touch(exist_ok=False)
        write_json(self.failure_path,dict(schema_version=SCHEMA,context=self.context,status='NO_FAILURE'))
        self.state=dict(schema_version=SCHEMA,context=self.context,owner_pid=os.getpid(),assertion_pid=None,
            assertion_types=list(TYPES),flags=['-i','-s','-w'],started_at=utc_now(),ended_at=None,
            status='PREFLIGHT',release_confirmed=False)
        try:
            # No workload may start until power/lid and this exact child's assertions validate.
            power_state(self.read)
            self.state['power_settings']=self.read(['/usr/bin/pmset','-g','custom'])
            args=['/usr/bin/caffeinate','-i','-s','-w',str(os.getpid())]
            self.process=self.spawn(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                start_new_session=True)
            self.state.update(assertion_pid=self.process.pid,command=args)
            deadline=time.monotonic()+self.startup_timeout
            while True:
                try:self.cached=self._snapshot();break
                except PowerGuardError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            self.state['status']='ACTIVE';self.state['verified_assertions']=self.cached['own_assertion_lines']
            write_json(self.out/'power_guard.json',self.state)
            self.checkpoint(force_power=True);self.started=True
            if self.background:
                self.thread=threading.Thread(target=self._loop,name='host-continuity',daemon=True);self.thread.start()
            return self
        except BaseException as exc:
            try:
                if self.failure is None:self._fail('power_guard_preflight_failed',dict(error=str(exc)))
            except BaseException:pass
            self._release('PREFLIGHT_FAILED')
            if self.failure_path.exists():
                raise PowerGuardError(str(exc)+'; host_continuity_failure_sha256='+file_sha256(self.failure_path)) from exc
            raise

    def _release(self,status):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=15)
            if self.thread.is_alive() and self.failure is None:
                try:self._fail('host_continuity_monitor_shutdown_timeout',dict(assertion_pid=self.process.pid))
                except PowerGuardError:pass
        released=self.process is None
        if self.process is not None:
            if self.process.poll() is None:self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            deadline=time.monotonic()+5
            while True:
                try:
                    text=self.read(['/usr/bin/pmset','-g','assertions'])
                    if not assertion_lines(text,self.process.pid):released=True;break
                except (OSError,subprocess.SubprocessError,PowerGuardError):break
                if time.monotonic()>=deadline:break
                time.sleep(.1)
        self.state.update(ended_at=utc_now(),status=status,release_confirmed=released,
            failure=self.failure,continuity_log_sha256=file_sha256(self.log))
        write_json(self.out/'power_guard.json',self.state)
        self._summary('FAILED' if self.failure else status)
        return released

    def __exit__(self,typ,error,tb):
        released=self._release('FAILED' if error or self.failure else 'RELEASED')
        if error is None:
            self.raise_if_failed()
            if not released:raise PowerGuardError('power_assertion_release_unverified')
        return False
