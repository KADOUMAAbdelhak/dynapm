"""Predefined development-only content comparison; never constructs policies."""
import numpy as np
import pandas as pd
from dynapm.core.discretization import classify_value
from dynapm.core.temporal import (HORIZON, MIN_OBSERVATIONS, METRICS,
    history_valid, trailing_observations, forward_observations, SAMPLE_STEP, HORIZON_STEPS)
from dynapm.experiments.profile_prediction import profile_training_data

VERSION = 'operational-profile-disposition-v2'
VALIDATION_FOLDS = 4


def operational_origins(events):
    """All distinct predictor-policy commits, labelled for PP6/drift contrasts."""
    pp = events.loc[events.method_id.eq('pp_6h')]
    v3p = events.loc[events.method_id.eq('v3') & events.trigger.eq('periodic')]
    if not pp.trigger.eq('periodic').all():
        raise ValueError('unexpected PP6 trigger')
    keys = ['trace', 'vm_id', 'actual_commit_time']
    if set(map(tuple, pp[keys].to_numpy())) != set(map(tuple, v3p[keys].to_numpy())):
        raise ValueError('paired periodic origin mismatch')
    drift = events.loc[events.method_id.eq('v3') & events.trigger.eq('drift')]
    primary = pd.concat([pp.assign(origin_group='periodic_6h'), drift.assign(origin_group='v3_drift')])
    if primary.duplicated(keys).any():
        raise ValueError('duplicate/colliding operational origin')
    predictor = events.loc[events.method_id.isin(['pp_3h','pp_6h','pp_12h','v3','budget_matched'])]
    sources = predictor.groupby(keys).method_id.agg(lambda s: '|'.join(sorted(set(s)))).reset_index(name='source_methods')
    out = sources.merge(primary[keys+['origin_group']], on=keys, how='left', validate='one_to_one')
    out['origin_group'] = out.origin_group.fillna('other_predictor_refresh')
    return out.rename(columns={'actual_commit_time': 'origin'}).sort_values(keys[:2] + ['origin']).reset_index(drop=True)



def seasonal_profile(series, origin, thresholds):
    """Exactly PW content, including partial >=200-slot seasonal histories."""
    values = trailing_observations(series, origin, hours=24)
    if len(values) < MIN_OBSERVATIONS:
        return None
    mean, p95 = float(values.mean()), float(values.quantile(.95))
    return {'mean': mean, 'p95': p95, 'class': classify_value(mean, thresholds)}


def bootstrap_origins(bootstrap):
    """Four evenly indexed eligible 6h clock origins, >=72h initial training.

    A full validation horizon must end inside bootstrap. Presence eligibility
    uses only bootstrap data. No streaming values or method errors are inputs.
    """
    # Presence-only training eligibility: a prefix must actually contain at
    # least one mature label before it can train. Values/errors never rank folds.
    # First feature index is first future target, hence +287 slots label end.
    mature_after = max(profile_training_data(bootstrap, m)[0].index[0] +
                       (HORIZON_STEPS-1)*SAMPLE_STEP for m in METRICS)
    candidates = []
    for t in pd.date_range(bootstrap.index[0] + pd.Timedelta(hours=72),
                           bootstrap.index[-1] - HORIZON, freq='6h'):
        if t not in bootstrap.index or t < mature_after:
            continue
        if not all(history_valid(bootstrap[m], t) and
                   len(trailing_observations(bootstrap[m], t, hours=24)) >= MIN_OBSERVATIONS
                   for m in METRICS):
            continue
        if len(forward_observations(bootstrap, t)) >= MIN_OBSERVATIONS:
            candidates.append(t)
    if len(candidates) < VALIDATION_FOLDS:
        raise ValueError('insufficient bootstrap rolling validation origins')
    indices = np.linspace(0, len(candidates) - 1, VALIDATION_FOLDS, dtype=int)
    return pd.DatetimeIndex([candidates[i] for i in indices])


def choose_content(rf_class, seasonal_class, rf_mae, seasonal_mae):
    """Strictly improve BOTH metrics; ties and every other case choose seasonal."""
    if not np.isfinite([rf_class, seasonal_class, rf_mae, seasonal_mae]).all():
        raise ValueError('nonfinite selector evidence')
    return 'rf_profile' if rf_class > seasonal_class and rf_mae < seasonal_mae else 'seasonal'
