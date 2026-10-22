"""Development-only fixed-origin design. Does not change production prediction."""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from dynapm.core.features import build_features
from dynapm.core.predictor import _causal_feature_row
from dynapm.core.temporal import nominal_grid, forecast_targets, history_valid, trailing_targets, FEATURE_HISTORY_SLOTS, HORIZON_STEPS

HORIZON = HORIZON_STEPS
DESIGN_VERSION = 'joint-direct-rf-development-v1'


def direct_training_data(bootstrap, target):
    """Every feature precedes its first label; all 288 labels stay in bootstrap.

    A vector-valued target shares tree partitions across horizons; there are no
    per-horizon models, no prediction feedback, and no interpolated labels.
    """
    series = bootstrap[target].reindex(nominal_grid(bootstrap.index)).astype(float)
    if len(series) < FEATURE_HISTORY_SLOTS + HORIZON:
        raise ValueError('insufficient bootstrap for direct horizon')
    windows = np.lib.stride_tricks.sliding_window_view(series.to_numpy(), HORIZON)
    features = build_features(bootstrap, target)
    pos = series.index.get_indexer(features.index)
    keep = pos < len(windows)
    features, pos = features.loc[keep], pos[keep]
    labels = windows[pos]
    valid = np.isfinite(labels).all(axis=1)
    features, labels = features.loc[valid], labels[valid]
    if features.empty: raise ValueError('no complete direct bootstrap labels')
    return features, labels


class DirectHorizonRF:
    def __init__(self, target, n_estimators=200, max_depth=20, random_state=42):
        self.target = target
        self.model = RandomForestRegressor(n_estimators=n_estimators,max_depth=max_depth,
            max_features='sqrt',random_state=random_state,n_jobs=1)

    def fit(self, bootstrap):
        features, labels = direct_training_data(bootstrap, self.target)
        self.model.fit(features.to_numpy(),labels)
        self.training_rows = len(features)
        self.last_training_origin = features.index[-1]-pd.Timedelta(minutes=5)
        self.last_training_target = features.index[-1]+pd.Timedelta(minutes=5*(HORIZON-1))
        if self.last_training_target > bootstrap.index[-1]: raise ValueError('bootstrap label leakage')

    def predict_causal_horizon(self, history, n_steps=288):
        if n_steps != HORIZON or history.empty or not history_valid(history,history.index[-1]):
            raise ValueError('direct forecast requires 288 targets and complete origin history')
        origin = history.index[-1]
        past = history.reindex(trailing_targets(origin,FEATURE_HISTORY_SLOTS)).to_numpy(dtype=float)
        targets = forecast_targets(origin)
        # Same causal feature definition as the production RF's first target.
        x = _causal_feature_row(np.r_[past,0.],targets[0])
        result = np.asarray(self.model.predict(x.reshape(1,-1))[0],dtype=float)
        if result.shape!=(HORIZON,) or not np.isfinite(result).all(): raise ValueError('invalid direct horizon')
        return pd.Series(result,index=targets,name='y_pred')


def tree_state_bytes(predictor):
    """Tree node/value array bytes, a lower bound rather than peak RSS."""
    return sum(tree.tree_.__getstate__()['nodes'].nbytes+tree.tree_.value.nbytes
               for tree in predictor.model.estimators_)
