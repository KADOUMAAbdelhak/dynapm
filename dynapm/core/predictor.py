"""Per-VM random-forest predictor and residual stream generation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from dynapm.core.features import LAGS, MAX_CONTEXT, ROLL_WINDOWS, build_features


def _causal_feature_row(values: np.ndarray, ts: pd.Timestamp) -> np.ndarray:
    """
    Build one causal feature row for the last index of ``values``.

    ``values[-1]`` is the contemporaneous slot (ignored by causal rolls/diffs);
    lags/rolls/diffs use only earlier entries.
    """
    s = values.astype(float)
    n = len(s)
    feats: list[float] = []
    for lag in LAGS:
        feats.append(float(s[n - 1 - lag]))
    # Past-only series ending at previous value
    past = s[:-1]
    for w in ROLL_WINDOWS:
        window = past[-w:]
        r_mean = float(window.mean())
        r_std = float(window.std(ddof=0))
        r_min = float(window.min())
        r_max = float(window.max())
        feats.extend([r_mean, r_std, r_min, r_max, r_max - r_min])
    feats.append(float(past[-1] - past[-2]))  # diff 1 on past
    feats.append(float(past[-1] - past[-13]))  # diff 12 on past
    hour = float(ts.hour)
    dow = float(ts.dayofweek)
    feats.extend(
        [
            np.sin(2.0 * np.pi * hour / 24.0),
            np.cos(2.0 * np.pi * hour / 24.0),
            np.sin(2.0 * np.pi * dow / 7.0),
            np.cos(2.0 * np.pi * dow / 7.0),
        ]
    )
    return np.asarray(feats, dtype=float)


class VMPredictor:
    def __init__(
        self,
        target: str,
        n_estimators: int = 200,
        max_depth: int = 20,
        random_state: int = 42,
    ):
        self.target = target
        self.model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            n_jobs=1,
            max_features="sqrt",
        )
        self.feature_names_ = None

    def fit(self, df_bootstrap: pd.DataFrame) -> None:
        features = build_features(df_bootstrap, self.target)
        if len(features) == 0:
            raise ValueError("no training rows after feature construction")
        X = features.values
        y = df_bootstrap.loc[features.index, self.target].values
        self.model.fit(X, y)
        self.feature_names_ = list(features.columns)

    def predict_streaming(self, df_streaming: pd.DataFrame) -> pd.DataFrame:
        if self.feature_names_ is None:
            raise ValueError("model must be fit before predict_streaming")
        features = build_features(df_streaming, self.target)
        if len(features) == 0:
            return pd.DataFrame(columns=["y_true", "y_pred", "residual"], index=features.index)
        y_pred = self.model.predict(features.values)
        y_true = df_streaming.loc[features.index, self.target].values
        residual = y_true - y_pred
        return pd.DataFrame(
            {
                "y_true": y_true,
                "y_pred": y_pred,
                "residual": residual,
            },
            index=features.index,
        )

    def predict_causal_horizon(
        self,
        history: pd.Series,
        n_steps: int = 288,
        step: pd.Timedelta | None = None,
    ) -> pd.Series:
        """
        Causal multi-step forecast ``{û_{t+k|t}}_{k=1..n_steps}``.

        ``history`` must contain observations available at the refresh origin
        (index up to and including ``t``). Each recursive step appends only the
        model's prediction; no future observations are used.
        """
        if self.feature_names_ is None:
            raise ValueError("model must be fit before predict_causal_horizon")
        if len(history) < 2:
            return pd.Series(dtype=float, name="y_pred")

        hist = history.astype(float).dropna().sort_index()
        if step is None:
            step = pd.Timedelta(hist.index[1] - hist.index[0])
            if step <= pd.Timedelta(0):
                step = pd.Timedelta(minutes=5)

        keep = MAX_CONTEXT + max(LAGS) + 8
        buf = hist.iloc[-keep:].to_numpy(dtype=float).copy()
        last_ts = pd.Timestamp(hist.index[-1])
        preds: list[float] = []
        index: list[pd.Timestamp] = []
        predict = self.model.predict
        for _ in range(int(n_steps)):
            next_t = last_ts + step
            # Append dummy contemporaneous value (ignored by causal features).
            buf = np.concatenate([buf, [buf[-1]]])
            if len(buf) > keep + 2:
                buf = buf[-(keep + 2) :]
            x = _causal_feature_row(buf, next_t).reshape(1, -1)
            yhat = float(predict(x)[0])
            buf[-1] = yhat
            preds.append(yhat)
            index.append(next_t)
            last_ts = next_t

        return pd.Series(preds, index=pd.DatetimeIndex(index), name="y_pred")
