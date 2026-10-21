"""Metadata-only exact-grid eligibility audit: no predictors or policy execution."""
from pathlib import Path
import numpy as np
import pandas as pd
from dynapm.core.temporal import (METRICS, SAMPLE_STEP, HORIZON, FEATURE_HISTORY_SLOTS,
    TEMPORAL_PROTOCOL, EVALUATION_GRID, validity_table)
from dynapm.data.bootstrap import compute_split


def audit_frame(frame, trace, vm_id, bootstrap_fraction=.30):
    boot, stream, _ = compute_split(frame, bootstrap_fraction)
    mask = validity_table(frame)
    anchor = stream.index[0]
    boot_targets = boot.index[boot.index >= frame.index[0]+FEATURE_HISTORY_SLOTS*SAMPLE_STEP]
    valid = mask.one_step.reindex(boot_targets).sum()
    stream_valid = mask.one_step.reindex(stream.index)
    hourly = pd.date_range(anchor, stream.index[-1]-HORIZON, freq='1h')
    verified = mask.forward_slots.reindex(hourly, fill_value=0).ge(200)
    observed = mask.observed.reindex(stream.index)
    eligible_times = stream.index[(mask.periodic.reindex(stream.index)&observed).to_numpy()]
    invalid = ~mask.predictor_origin.loc[anchor:]
    runs = invalid.ne(invalid.shift()).cumsum()
    recovery_lengths = invalid.groupby(runs).sum()
    row = dict(trace=trace, vm_id=str(vm_id), bootstrap_observations=len(boot),
        candidate_training_targets=len(boot_targets), valid_feature_rows=int(valid),
        invalid_gap_affected_rows=int(len(boot_targets)-valid),
        training_valid_fraction=float(valid/len(boot_targets)) if len(boot_targets) else 0.,
        streaming_observations=len(stream), streaming_valid_one_step=int(stream_valid.sum()),
        streaming_predictor_eligible_fraction=float(stream_valid.mean()),
        long_recovery_periods=int((recovery_lengths>=FEATURE_HISTORY_SLOTS).sum()),
        window24_eligible=int(mask.window24.reindex(stream.index).sum()),
        window6_eligible=int(mask.window6.reindex(stream.index).sum()),
        nominal_hourly_opportunities=len(hourly), globally_verifiable_opportunities=int(verified.sum()),
        evaluation_retained_fraction=float(verified.mean()) if len(hourly) else 0.,
        gap_validity_affected=bool(len(boot_targets)-valid or (~stream_valid).any()))
    for h in (3,6,12):
        ticks = pd.date_range(anchor+pd.Timedelta(hours=h),stream.index[-1],freq=f'{h}h')
        positions = eligible_times.searchsorted(ticks)
        available = positions < len(eligible_times)
        # Multiple pending nominal ticks map to one resume commit, latest tick wins.
        pairs = pd.DataFrame({'nominal':ticks[available], 'actual':eligible_times[positions[available]]})
        commits = pairs.groupby('actual',as_index=False).nominal.max()
        delays = (commits.actual-commits.nominal).dt.total_seconds()
        immediate = mask.periodic.reindex(ticks,fill_value=False)&mask.observed.reindex(ticks,fill_value=False)
        row.update({f'p{h}_nominal_ticks':len(ticks), f'p{h}_immediate_ticks':int(immediate.sum()),
            f'p{h}_commits':len(commits), f'p{h}_delayed_commits':int((delays>0).sum()),
            f'p{h}_max_delay_seconds':float(delays.max()) if len(delays) else 0.,
            f'p{h}_max_tick_wait_seconds':float((pairs.actual-pairs.nominal).dt.total_seconds().max()) if len(pairs) else 0.,
            f'p{h}_unresolved_ticks':int((~available).sum())})
    # Diagnostic flags only; final cohort/exclusion criteria belong to V2.5.
    row['potential_eligibility_review'] = bool(row['valid_feature_rows']==0 or
        row['globally_verifiable_opportunities']==0 or row['streaming_predictor_eligible_fraction']<.95 or
        row['training_valid_fraction']<.95 or row['evaluation_retained_fraction']<.95)
    return row


def audit_dataset(raw_root, dataset, config):
    rows=[]
    for entry in dataset.files:
        if entry.role!='raw_entity': continue
        frame=pd.read_csv(Path(raw_root)/entry.path,sep=';',usecols=['Timestamp',*METRICS],dtype=str)
        if len(frame)<config.data.minimum_observations: continue
        frame.index=pd.to_datetime(frame.pop('Timestamp'),format='%d.%m.%Y %H:%M:%S')
        frame=frame.sort_index()
        for metric in METRICS:
            frame[metric]=pd.to_numeric(frame[metric].str.replace(',','.',regex=False),errors='raise')
        rows.append(audit_frame(frame,entry.trace,entry.entity_id,config.data.bootstrap_fraction))
    table=pd.DataFrame(rows)
    summary={'protocol':TEMPORAL_PROTOCOL,'evaluation_grid':EVALUATION_GRID,'n_vms':len(table),
        'gap_validity_affected_vms':int(table.gap_validity_affected.sum()),
        'potential_eligibility_review_vms':int(table.potential_eligibility_review.sum()),
        'review_rule':'diagnostic only: zero training/evaluation, or <95% training/streaming/evaluation validity; not an exclusion rule',
        'zero_training_vms':int(table.valid_feature_rows.eq(0).sum()),
        'zero_evaluation_vms':int(table.globally_verifiable_opportunities.eq(0).sum()),
        'nominal_evaluations':int(table.nominal_hourly_opportunities.sum()),
        'verifiable_evaluations':int(table.globally_verifiable_opportunities.sum()),
        'decision':'ACCEPTABLE FOR V3',
        'decision_scope':'Gap handling is explicit, not evidence that all entities qualify; V2.5 freezes eligibility before confirmation.'}
    return table,summary
