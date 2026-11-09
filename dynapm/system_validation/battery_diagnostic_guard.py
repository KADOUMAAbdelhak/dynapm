"""Explicitly non-qualifying battery observations. Never a claim/AC certificate.

The strict host_power and UUIDPowerGuard implementations are unchanged. This
separate scope records battery operation while retaining owned idle-sleep
assertion, open lid, exact boot identity and the existing 2 s / 30 s continuity
failure bounds. PreventSystemSleep is not claimed on battery.
"""
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from dynapm.core.provenance import canonical_json,file_sha256,utc_now,fingerprint
from dynapm.system_validation.host_power import (command,battery_diagnostics,
    assertion_lines,PowerGuardError,MAX_HEARTBEAT_GAP_NS)
from dynapm.system_validation.clock_observations import MAX_CLOCK_DELTA_NS
from dynapm.system_validation.service_checkpoint import atomic_record
from dynapm.system_validation.v8_host_identity import read_boot,same_boot

SCOPE='DIAGNOSTIC_NON_CLAIM_NON_QUALIFYING'
SCHEMA='nonqualifying-battery-diagnostic-power-v1'


class BatteryDiagnosticGuard:
    def __init__(self,root,context):
        self.root=Path(root);self.out=self.root/'outputs';self.context=dict(context)
        self.process=None;self.thread=None;self.stop=threading.Event();self.lock=threading.Lock()
        self.failure=None;self.previous=None;self.boot=None;self.policy=None
        self.state={};self.points=0;self.max_drift=0;self.max_gap=0

    def _failure(self,invariant):
        if self.failure is None:
            self.failure=dict(invariant=invariant,recorded_at=utc_now(),context=self.context,scope=SCOPE,claim_qualification_eligible=False)
            atomic_record(self.out/'host_continuity_failure.json',self.failure)
        raise PowerGuardError(invariant)

    def raise_if_failed(self):
        if self.failure:raise PowerGuardError(self.failure['invariant'])

    def checkpoint(self,*,force_power=False):
        del force_power
        with self.lock:
            try:
                self.raise_if_failed()
                wall,mono=time.time_ns(),time.monotonic_ns()
                if self.previous:
                    drift=abs((wall-self.previous[0])-(mono-self.previous[1]));gap=mono-self.previous[1]
                    self.max_drift=max(self.max_drift,drift);self.max_gap=max(self.max_gap,gap)
                    if drift>MAX_CLOCK_DELTA_NS:self._failure('host_wall_monotonic_discrepancy')
                    if gap>MAX_HEARTBEAT_GAP_NS:self._failure('host_checkpoint_gap')
                identity=read_boot()
                if self.boot:same_boot(self.boot['boot_uuid'],identity,anchor_ns=self.boot['boot_timeval_ns'])
                else:self.boot=identity
                settings=command(['/usr/bin/pmset','-g','custom'])
                if self.policy is not None and settings!=self.policy:self._failure('host_power_policy_changed')
                self.policy=settings
                lid=command(['/usr/sbin/ioreg','-r','-k','AppleClamshellState','-d','4'])
                if not re.search(r'"AppleClamshellState"\s*=\s*No',lid):self._failure('lid_closed_or_unobservable')
                battery=battery_diagnostics();power=command(['/usr/bin/pmset','-g','batt'])
                if self.process is None or self.process.poll() is not None:self._failure('owned_idle_assertion_lost')
                lines=assertion_lines(command(['/usr/bin/pmset','-g','assertions']),self.process.pid)
                if not any('PreventUserIdleSystemSleep' in line for line in lines):self._failure('owned_idle_assertion_missing')
                row=dict(kind='CHECKPOINT',schema_version=SCHEMA,scope=SCOPE,claim_qualification_eligible=False,
                    wall_ns=wall,monotonic_ns=mono,power=dict(**identity,battery=power.strip(),battery_diagnostics=battery,
                    ac_power=battery.get('ExternalConnected'),lid_open=True,own_assertion_lines=lines,
                    prevent_system_sleep_qualified=False,power_settings_sha256=fingerprint(settings)))
                with (self.out/'host_continuity.jsonl').open('a') as sink:
                    sink.write(canonical_json(row)+'\n');sink.flush();os.fsync(sink.fileno())
                self.previous=(wall,mono);self.points+=1
                self.state.update(points=self.points,max_drift_ns=self.max_drift,max_gap_ns=self.max_gap,
                                  current_battery=battery,last_power_source=power.strip())
                return row
            except BaseException as exc:
                self._failure(str(exc))

    def _observe(self):
        while not self.stop.wait(5):
            try:self.checkpoint()
            except BaseException as exc:
                try:self._failure(str(exc))
                except BaseException:pass
                return

    def __enter__(self):
        self.out.mkdir(parents=True,exist_ok=True)
        args=['/usr/bin/caffeinate','-i','-w',str(os.getpid())]
        self.process=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.state=dict(schema_version=SCHEMA,scope=SCOPE,status='ACTIVE',claim_qualification_eligible=False,
            ac_qualification_passed=False,owner_pid=os.getpid(),assertion_pid=self.process.pid,
            assertion_types=['PreventUserIdleSystemSleep'],strict_claim_assertions_satisfied=False,
            command=args,started_at=utc_now(),context=self.context)
        try:
            deadline=time.monotonic()+5
            while True:
                lines=assertion_lines(command(['/usr/bin/pmset','-g','assertions']),self.process.pid)
                if any('PreventUserIdleSystemSleep' in line for line in lines):break
                if time.monotonic()>deadline:raise PowerGuardError('idle_assertion_startup_timeout')
                time.sleep(.1)
            self.checkpoint()
            atomic_record(self.out/'power_guard.json',self.state)
            self.thread=threading.Thread(target=self._observe,daemon=True);self.thread.start()
            return self
        except BaseException:
            self.__exit__(Exception,None,None)
            raise

    def __exit__(self,exc_type,exc_value,traceback):
        self.stop.set()
        if self.thread:self.thread.join(timeout=25)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        released=self.process is None or self.process.poll() is not None
        self.state.update(status='FAILED' if self.failure else 'RELEASED',failure=self.failure,ended_at=utc_now(),
                          release_confirmed=released,points=self.points,max_drift_ns=self.max_drift,max_gap_ns=self.max_gap)
        log=self.out/'host_continuity.jsonl'
        if log.exists():self.state['continuity_log_sha256']=file_sha256(log)
        atomic_record(self.out/'power_guard.json',self.state)
        if self.failure and exc_type is None:
            raise PowerGuardError(self.failure['invariant'])
