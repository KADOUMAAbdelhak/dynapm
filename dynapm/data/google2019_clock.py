"""Google completed-slot clock projection; canonical storage is never rewritten."""
from __future__ import annotations
import numpy as np
import pandas as pd
from dynapm.core.discretization import compute_thresholds

CLOCK_VERSION = 'google-completed-slot-availability-v1'
STEP_US = 300_000_000
HORIZON_SLOTS = 288
MIN_PAIRED_SLOTS = 200
RESOURCES = ('cpu_utilization', 'memory_utilization')


def clock_contract():
    return dict(version=CLOCK_VERSION,cadence_us=STEP_US,horizon_slots=HORIZON_SLOTS,
        measurement_interval='[source_start_time_us, source_end_time_us)',
        canonical_storage_label='b = floor(source_start_time_us / cadence_us) * cadence_us; unchanged',
        analysis_label='q = b + cadence_us; nominal closing-slot label, an explicit derived view',
        required_containment='b <= source_start_time_us < source_end_time_us <= q; one row per entity/b',
        available_at='a = source_end_time_us',
        admitted_at='q; conservative completed-bin admission even for early-ending partial intervals',
        visible_at_read='a <= r AND q <= r; all state consumers use this gate',
        reads='r is a physical trace-relative clock on the 300s grid; hourly anchor is first streaming q',
        bootstrap='first floor(0.30*N) nominal closing slots; observed q < cut; thresholds freeze from completed bootstrap at first streaming q',
        trailing='closing slots (r-24h,r], q=r-287*cadence,...,r; physical bins [r-24h,r)',
        truth='closing slots (r,r+24h], q=r+cadence,...,r+288*cadence; physical bins [r,r+24h)',
        verification='not before r+24h; full target horizon within trace; every used a <= verification read',
        coverage='>=200/288 paired finite observed slots, with no imputation, clipping, rescaling or duration weighting',
        partial_intervals='one observed partial interval counts as one nominal slot; never claim 288 complete-duration measurements',
        periodic='anchor=first streaming q; existing anchored pending/coalescing grid; require observed completed q and >=200 paired trailing slots plus inherited 96 complete slots for PW',
        residual_state='if used in future: history/state uses admitted q only; one-step target at q cannot enter features before q',
        invalid_interval='block this clock contract for a cell with noncontained/overlapping/duplicate retained intervals; do not silently exclude or split',
        scientific_questions_changed=False,policy_outcomes_authorized=False)


def _read_us(value):
    return int(value) if isinstance(value,(int,np.integer)) else int(pd.Timestamp(value).value//1000)


def closing_labels(canonical):
    """Validate a single entity before creating any analysis-time view."""
    if len(canonical[['collection_id','instance_index']].drop_duplicates())!=1:
        raise ValueError('single_entity_required')
    b=canonical.timestamp_us.to_numpy(dtype=np.int64)
    s=canonical.source_start_time_us.to_numpy(dtype=np.int64)
    e=canonical.source_end_time_us.to_numpy(dtype=np.int64)
    q=b+STEP_US
    if len(b)==0 or np.any(b%STEP_US) or np.any(np.diff(b)<=0):
        raise ValueError('invalid_or_duplicate_nominal_slots')
    if np.any((s<b)|(s>=q)|(e<=s)|(e>q)):
        raise ValueError('measurement_interval_not_contained')
    if np.any(s[1:]<e[:-1]):raise ValueError('overlapping_measurement_intervals')
    return q


def observation_frame(canonical):
    """Single entity, indexed by q, with physical ratio units explicitly retained."""
    q=closing_labels(canonical)
    out=canonical.copy();out['analysis_slot_close_us']=q
    out.index=pd.to_datetime(q,unit='us');out.index.name='completed_slot'
    out.attrs.update(clock_version=CLOCK_VERSION,resource_units='request_normalized_ratio',
        timestamp_note='trace-relative microseconds; pandas epoch is an indexing bridge, not a claimed calendar date')
    return out


def visible_observations(frame,read_time):
    if frame.attrs.get('clock_version')!=CLOCK_VERSION:
        raise ValueError('completed_slot_clock_frame_required')
    r=_read_us(read_time)
    visible=frame.analysis_slot_close_us.le(r)&frame.source_end_time_us.le(r)
    return frame.loc[visible].copy()


def bootstrap_partition(frame):
    if frame.attrs.get('clock_version')!=CLOCK_VERSION:
        raise ValueError('completed_slot_clock_frame_required')
    q=frame.analysis_slot_close_us.to_numpy(dtype=np.int64)
    n=int((q[-1]-q[0])//STEP_US)+1;cut=int(q[0])+(n*3//10)*STEP_US
    boot=frame.loc[q<cut].copy();stream=frame.loc[q>=cut].copy()
    if boot.empty or stream.empty:raise ValueError('insufficient_bootstrap_or_streaming_history')
    anchor=int(stream.analysis_slot_close_us.iloc[0])
    if (boot.source_end_time_us>anchor).any():raise ValueError('incomplete_bootstrap_aggregate')
    return boot,stream,dict(bootstrap_cut_us=cut,stream_anchor_us=anchor,nominal_slots=n)


def bootstrap_thresholds_at_read(frame,read_time):
    boot,_,info=bootstrap_partition(frame);r=_read_us(read_time)
    if r<info['stream_anchor_us']:raise ValueError('bootstrap_not_frozen_yet')
    visible=visible_observations(boot,r)
    paired=np.isfinite(visible[list(RESOURCES)].to_numpy(float)).all(axis=1)
    visible=visible.loc[paired]
    if len(visible)<96:raise ValueError('insufficient_bootstrap_history')
    return {resource:compute_thresholds(visible,resource) for resource in RESOURCES}


def _grid_read(value):
    r=_read_us(value)
    if r%STEP_US:raise ValueError('read_not_on_nominal_grid')
    return r


def target_labels(origin):
    r=_grid_read(origin)
    return r+np.arange(1,HORIZON_SLOTS+1,dtype=np.int64)*STEP_US


def trailing_observations(frame,read_time):
    r=_grid_read(read_time);visible=visible_observations(frame,r)
    keep=visible.analysis_slot_close_us.gt(r-HORIZON_SLOTS*STEP_US)
    out=visible.loc[keep]
    return out.loc[np.isfinite(out[list(RESOURCES)].to_numpy(float)).all(axis=1)]


def forward_truth_observations(frame,origin,verification_time):
    r=_grid_read(origin);v=_read_us(verification_time);end=r+HORIZON_SLOTS*STEP_US
    if v<end:raise ValueError('forward_horizon_not_elapsed')
    if int(frame.analysis_slot_close_us.max())<end:raise ValueError('forward_horizon_outside_trace')
    visible=visible_observations(frame,v)
    out=visible.loc[visible.analysis_slot_close_us.isin(target_labels(r))]
    out=out.loc[np.isfinite(out[list(RESOURCES)].to_numpy(float)).all(axis=1)]
    if len(out)<MIN_PAIRED_SLOTS:raise ValueError('insufficient_forward_paired_slots')
    return out


def refresh_eligible(frame,read_time,*,periodic=True):
    r=_grid_read(read_time);visible=visible_observations(frame,r)
    if r not in visible.analysis_slot_close_us.to_numpy():return False
    window=trailing_observations(frame,r)
    if len(window)<MIN_PAIRED_SLOTS:return False
    if not periodic:return True
    # Inherited PW gate, not an RF fit or prediction. Both resources must exist
    # in all exact closing slots [r-95*step,r].
    history=window[window.analysis_slot_close_us.ge(r-95*STEP_US)]
    return len(history)==96
