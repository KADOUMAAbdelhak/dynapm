"""Fail-closed wall-clock observations with durable, isolated rejection evidence.

Monotonic clocks diagnose local elapsed time only. Container and host monotonic
epochs are never compared. Scientific availability remains the host receipt wall
time; source-ahead is forbidden even by one nanosecond.
"""
import base64
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from dynapm.core.provenance import canonical_json, fingerprint, file_sha256, read_json
from dynapm.core.run_store import write_json

SCHEMA = 'system-clock-observation-v1'
MAX_CLOCK_DELTA_NS = 2_000_000_000


def receive_observation(url, *, wall_ns=None, monotonic_ns=None, opener=None):
    """Timestamp immediately after reading the complete HTTP body, before JSON parsing."""
    wall_ns = wall_ns or time.time_ns
    monotonic_ns = monotonic_ns or time.monotonic_ns
    opener = opener or urllib.request.urlopen
    start_wall, start_mono = wall_ns(), monotonic_ns()
    with opener(url, timeout=5) as response:
        raw = response.read()
        receipt_wall, receipt_mono = wall_ns(), monotonic_ns()
    return dict(raw_payload_base64=base64.b64encode(raw).decode('ascii'),
        raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
        request_wall_ns=start_wall, request_monotonic_ns=start_mono,
        received_at_ns=receipt_wall, receipt_monotonic_ns=receipt_mono)


class ClockRejected(ValueError):
    pass


def _append(path, record):
    with path.open('a') as file:
        file.write(canonical_json(record)+'\n')
        file.flush()
        os.fsync(file.fileno())


class ObservationClock:
    def __init__(self, root, context):
        self.root = Path(root)
        self.context = dict(context)
        self.sequence = 0
        self.previous = None
        self.host_origin = None
        self.rejections = self.root/'outputs/clock_rejections.jsonl'
        self.observations = self.root/'outputs/clock_observations.jsonl'
        self.manifest = self.root/'outputs/clock_evidence_manifest.json'
        self.rejections.touch(exist_ok=False)
        self.observations.touch(exist_ok=False)
        self._seal()

    def _seal(self):
        body = dict(schema_version=SCHEMA, context=self.context,
            rejections_sha256=file_sha256(self.rejections),
            observations_sha256=file_sha256(self.observations))
        write_json(self.manifest, {**body, 'manifest_sha256': fingerprint(body)})

    def reject(self, invariant, evidence, sample=None):
        source = sample.get('sample_time_ns') if isinstance(sample, dict) else None
        receipt = evidence.get('received_at_ns')
        delta = receipt-source if type(source) is int and type(receipt) is int else None
        body = dict(schema_version=SCHEMA, context=self.context, invariant=invariant,
            sample_index=self.sequence, raw_source_time_ns=source, raw_receipt_time_ns=receipt,
            receipt_minus_source_ns=delta,
            receipt_minus_source_us=None if delta is None else delta/1000,
            receipt_minus_source_ms=None if delta is None else delta/1_000_000,
            previous_accepted=self.previous, telemetry_identity=sample.get('instance_id') if isinstance(sample, dict) else None,
            raw_sample=sample, observation=evidence, recorded_wall_ns=time.time_ns(),
            recorded_monotonic_ns=time.monotonic_ns())
        record = {**body, 'record_sha256': fingerprint(body)}
        _append(self.rejections, record)
        self._seal()
        raise ClockRejected(invariant+'; clock_evidence_manifest_sha256='+file_sha256(self.manifest))

    def check_host(self, wall_ns, mono_ns):
        if self.host_origin is None:
            self.host_origin = (wall_ns, mono_ns)
        drift = (wall_ns-self.host_origin[0])-(mono_ns-self.host_origin[1])
        if abs(drift)>MAX_CLOCK_DELTA_NS:
            self.reject('host_sleep_or_clock_discontinuity', dict(
                received_at_ns=wall_ns, receipt_monotonic_ns=mono_ns,
                origin_wall_ns=self.host_origin[0], origin_monotonic_ns=self.host_origin[1],
                wall_minus_monotonic_elapsed_ns=drift))

    def accept(self, evidence, scientific_file):
        """Validate before scientific persistence; rejected bodies are always saved first."""
        self.sequence += 1
        try:
            raw = base64.b64decode(evidence['raw_payload_base64'], validate=True)
            def invalid_constant(value):
                raise ValueError('nonfinite_json_constant')
            sample = json.loads(raw, parse_constant=invalid_constant)
        except (ValueError, TypeError):
            self.reject('invalid_telemetry_json', evidence)
        if not isinstance(sample, dict):
            self.reject('telemetry_object_required', evidence, sample)
        if hashlib.sha256(raw).hexdigest()!=evidence['raw_payload_sha256']:
            self.reject('raw_payload_hash_mismatch', evidence, sample)
        source, receipt = sample.get('sample_time_ns'), evidence['received_at_ns']
        if type(source) is not int or source<=0 or type(receipt) is not int:
            self.reject('integer_nanosecond_timestamp_required', evidence, sample)
        if source>receipt:
            self.reject('source_ahead_of_receipt', evidence, sample)
        if receipt-source>MAX_CLOCK_DELTA_NS:
            self.reject('source_receipt_delta_exceeds_2s', evidence, sample)
        elapsed = evidence['receipt_monotonic_ns']-evidence['request_monotonic_ns']
        wall_elapsed = receipt-evidence['request_wall_ns']
        if elapsed<0 or abs(wall_elapsed-elapsed)>MAX_CLOCK_DELTA_NS:
            self.reject('transport_wall_clock_discontinuity', evidence, sample)
        if not isinstance(sample.get('instance_id'), str) or not sample['instance_id']:
            self.reject('telemetry_identity_required', evidence, sample)
        source_clock = sample.get('source_clock')
        if source_clock is not None and (not isinstance(source_clock, dict) or any(
                type(source_clock.get(k)) is not int for k in ('wall_ns','monotonic_ns'))):
            self.reject('invalid_source_clock_diagnostics', evidence, sample)
        if self.previous:
            if sample['instance_id']!=self.previous['instance_id']:
                self.reject('telemetry_instance_changed', evidence, sample)
            if source==self.previous['sample_time_ns']:
                self.reject('duplicate_source_timestamp', evidence, sample)
            if source<self.previous['sample_time_ns']:
                self.reject('out_of_order_source_timestamp', evidence, sample)
            if receipt<self.previous['received_at_ns']:
                self.reject('receipt_clock_moved_backward', evidence, sample)
            old = self.previous.get('source_clock')
            new = sample.get('source_clock')
            if old and new:
                drift = (new['wall_ns']-old['wall_ns'])-(new['monotonic_ns']-old['monotonic_ns'])
                if abs(drift)>MAX_CLOCK_DELTA_NS:
                    self.reject('source_wall_monotonic_discontinuity', evidence, sample)
        sample['received_at_ns'] = receipt
        diagnostic = dict(schema_version=SCHEMA, context=self.context, sample_index=self.sequence,
            sample_time_ns=source, received_at_ns=receipt, receipt_minus_source_ns=receipt-source,
            transport_elapsed_ns=elapsed, transport_wall_elapsed_ns=wall_elapsed,
            request_wall_ns=evidence['request_wall_ns'], request_monotonic_ns=evidence['request_monotonic_ns'],
            receipt_monotonic_ns=evidence['receipt_monotonic_ns'], raw_payload_sha256=evidence['raw_payload_sha256'],
            source_clock=sample.get('source_clock'))
        _append(self.observations, diagnostic)
        scientific_file.write(canonical_json(sample)+'\n')
        scientific_file.flush()
        self.previous = {k:sample[k] for k in ('sample_time_ns','received_at_ns','instance_id')}
        self.previous['source_clock'] = sample.get('source_clock')
        return sample

    def finalize(self):
        self._seal()


def validate_clock_evidence(root, context):
    root = Path(root)/'outputs'
    manifest = read_json(root/'clock_evidence_manifest.json')
    body = {k:v for k,v in manifest.items() if k!='manifest_sha256'}
    if (manifest.get('schema_version')!=SCHEMA or manifest.get('context')!=context
            or manifest['manifest_sha256']!=fingerprint(body)):
        raise ValueError('clock_evidence_provenance_mismatch')
    for name in ('rejections','observations'):
        if file_sha256(root/('clock_'+name+'.jsonl'))!=manifest[name+'_sha256']:
            raise ValueError('clock_evidence_hash_mismatch')
    for line in (root/'clock_rejections.jsonl').read_text().splitlines():
        record = json.loads(line)
        body = {k:v for k,v in record.items() if k!='record_sha256'}
        if record['context']!=context or fingerprint(body)!=record['record_sha256']:
            raise ValueError('clock_rejection_hash_or_provenance_mismatch')
        e = record['observation']
        if 'raw_payload_base64' in e and hashlib.sha256(base64.b64decode(e['raw_payload_base64'])).hexdigest()!=e['raw_payload_sha256']:
            raise ValueError('clock_rejection_raw_hash_mismatch')
    return True
