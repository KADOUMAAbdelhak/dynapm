"""Development-only prediction of future mean/p95; no production integration."""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from dynapm.core.features import build_features
from dynapm.core.predictor import _causal_feature_row
from dynapm.core.temporal import (nominal_grid,forecast_targets,history_valid,trailing_targets,
    FEATURE_HISTORY_SLOTS,HORIZON_STEPS,MIN_OBSERVATIONS,SAMPLE_STEP,METRICS)
from dynapm.core.discretization import classify_value
from dynapm.data.bootstrap import LOCKED_BOOTSTRAP_FRACTION

VERSION='direct-profile-mean-p95-v2'


def profile_training_data(bootstrap,target):
    """Exact (origin,origin+24h] labels, paired finite >=200, fully elapsed in bootstrap.

    Feature row is indexed by first target time; it uses only history <=origin.
    A missing first target is allowed when enough later paired slots exist.
    """
    dense=bootstrap.loc[:,list(METRICS)].reindex(nominal_grid(bootstrap.index)).astype(float)
    if len(dense)<FEATURE_HISTORY_SLOTS+HORIZON_STEPS:raise ValueError('short profile bootstrap')
    features=build_features(dense,target)
    present=np.isfinite(dense.to_numpy()).all(axis=1)
    values=dense[target].where(present).to_numpy()
    windows=np.lib.stride_tricks.sliding_window_view(values,HORIZON_STEPS)
    pos=dense.index.get_indexer(features.index);keep=pos<len(windows)
    features,pos=features.loc[keep],pos[keep]
    labels=windows[pos];counts=np.isfinite(labels).sum(axis=1)
    valid=counts>=MIN_OBSERVATIONS;features,labels,counts=features.loc[valid],labels[valid],counts[valid]
    if features.empty:raise ValueError('no eligible profile labels')
    y=np.column_stack([np.nanmean(labels,axis=1),np.nanquantile(labels,.95,axis=1)])
    return features,y,counts


class DirectProfile:
    def __init__(self,target,method='rf_profile',n_estimators=200,max_depth=20):
        self.target=target;self.method=method
        if method=='rf_profile':
            self.model=RandomForestRegressor(n_estimators=n_estimators,max_depth=max_depth,
                max_features='sqrt',random_state=42,n_jobs=1)
        elif method=='ridge_profile':self.model=make_pipeline(StandardScaler(),Ridge(alpha=1.0))
        else:raise ValueError('unknown predefined direct-profile model')

    def fit(self,bootstrap):
        x,y,counts=profile_training_data(bootstrap,self.target)
        self.model.fit(x.to_numpy(),y);self.training_rows=len(x)
        self.label_slots_min=int(counts.min());self.label_slots_max=int(counts.max())
        self.last_training_target=x.index[-1]+(HORIZON_STEPS-1)*SAMPLE_STEP
        if self.last_training_target>bootstrap.index[-1]:raise ValueError('label leakage')

    def predict_profile(self,observations,origin,thresholds):
        past=observations.loc[observations.index<=origin]
        if past.empty or past.index[-1]!=origin or not history_valid(past,origin):raise ValueError('invalid profile origin')
        history=past.reindex(trailing_targets(origin,FEATURE_HISTORY_SLOTS)).to_numpy(dtype=float)
        x=_causal_feature_row(np.r_[history,0.],forecast_targets(origin)[0])
        mean,p95=np.asarray(self.model.predict(x.reshape(1,-1))[0],dtype=float)
        if not np.isfinite([mean,p95]).all():raise ValueError('nonfinite profile')
        return {'mean':float(mean),'p95':float(p95),'class':classify_value(float(mean),thresholds)}

    def state_bytes(self):
        """Learned numeric-array state lower bound; not peak RSS or serialized package size."""
        if self.method=='rf_profile':
            return sum(t.tree_.__getstate__()['nodes'].nbytes+t.tree_.value.nbytes for t in self.model.estimators_)
        scaler,ridge=self.model.steps[0][1],self.model.steps[1][1]
        return sum(a.nbytes for a in [scaler.mean_,scaler.var_,scaler.scale_,ridge.coef_,ridge.intercept_])


def timestamp_availability(index,trace,vm):
    """Timestamp presence only; no resource values or confirmatory outcomes."""
    index=pd.DatetimeIndex(index).sort_values();grid=nominal_grid(index)
    present=pd.Series(grid.isin(index),index=grid,dtype=bool)
    history=present.rolling(FEATURE_HISTORY_SLOTS,min_periods=FEATURE_HISTORY_SLOTS).sum().eq(FEATURE_HISTORY_SLOTS)
    counts=present.rolling(HORIZON_STEPS,min_periods=1).sum()
    cut=index[int(len(index)*LOCKED_BOOTSTRAP_FRACTION)]
    origins=index[index>=cut];eligible=history.reindex(origins)
    samples=counts.reindex(origins)[eligible]
    return {'trace':trace,'vm_id':str(vm),'observed_stream_origins':len(origins),
        'predictor_eligible_origins':int(eligible.sum()),
        'seasonal_complete_288':int(samples.eq(HORIZON_STEPS).sum()),
        'seasonal_density_200':int(samples.ge(MIN_OBSERVATIONS).sum()),
        'seasonal_incomplete_but_200':int((samples.ge(MIN_OBSERVATIONS)&samples.lt(HORIZON_STEPS)).sum()),
        'seasonal_below_200':int(samples.lt(MIN_OBSERVATIONS).sum())}


def availability_metadata(direct_profile, point_slots=None):
    """Distinguish scalar inference history from actual point forecast availability."""
    if direct_profile:
        return {'profile_available':True,'point_forecast_slots_available':None,
                'profile_feature_history_slots':FEATURE_HISTORY_SLOTS}
    if point_slots is None or not MIN_OBSERVATIONS<=point_slots<=HORIZON_STEPS:
        raise ValueError('eligible point forecast count required')
    return {'profile_available':True,'point_forecast_slots_available':int(point_slots),
            'profile_feature_history_slots':None}
