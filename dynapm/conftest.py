"""Pytest configuration for DynAPM."""
from dynapm.scripts import _matplotlib_setup  # noqa: F401

import numpy as np
import pandas as pd
import pytest

from dynapm.core.features import build_features
from dynapm.data.loader import SCHEMA_COLUMNS


@pytest.fixture
def synthetic_frame():
    """Small deterministic trace; no external dataset or expensive forest needed."""
    idx = pd.date_range("2021-01-01", periods=720, freq="5min")
    df = pd.DataFrame(0.0, index=idx, columns=SCHEMA_COLUMNS[1:])
    df["CPU usage [%]"] = 40 + 8 * np.sin(np.arange(len(idx)) / 17)
    df["Memory usage [%]"] = 65 + 4 * np.cos(np.arange(len(idx)) / 23)
    df["CPU cores"] = 2
    df["Memory capacity provisioned [KB]"] = 4 * 1024**2
    return df


class LagPredictor:
    """Cheap causal test double; production replay still fits and routes it."""
    instances = []

    def __init__(self, target):
        self.target = target
        self.fit_index = None
        self.histories = []
        self.__class__.instances.append(self)

    def fit(self, df):
        assert self.fit_index is None, "predictor fit more than once"
        self.fit_index = df.index.copy()

    def predict_streaming(self, df):
        f = build_features(df, self.target)
        y = df.loc[f.index, self.target]
        p = f["target_lag_1"]
        return pd.DataFrame({"y_true": y, "y_pred": p, "residual": y - p})

    def predict_causal_horizon(self, history, n_steps=288):
        self.histories.append(history.copy())
        return pd.Series(float(history.iloc[-1]), index=pd.date_range(
            history.index[-1] + pd.Timedelta(minutes=5), periods=n_steps, freq="5min"), name="y_pred")


@pytest.fixture
def lag_predictor_factory():
    LagPredictor.instances = []
    return LagPredictor


@pytest.fixture
def replay_repo(tmp_path, synthetic_frame):
    """Write one tiny raw VM into a temporary, isolated replay repository."""
    raw = tmp_path / "data/raw/TestTrace/1.csv"
    raw.parent.mkdir(parents=True)
    frame = synthetic_frame.copy()
    frame.insert(0, "Timestamp", frame.index.strftime("%d.%m.%Y %H:%M:%S"))
    frame.to_csv(raw, sep=";", index=False)
    return tmp_path
