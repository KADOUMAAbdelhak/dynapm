"""Exact target boundaries and sparse-window eligibility."""
import pandas as pd
import pytest

from dynapm.core.predictor import VMPredictor, forecast_at_origin
from dynapm.core.temporal import forecast_targets, forward_observations, HORIZON, SAMPLE_STEP
from dynapm.core.ground_truth import derive_ground_truth_at_t, derive_ground_truth_at_t_v2
from dynapm.core.evaluation_clock import compute_data_aware_evaluation_timestamps
from dynapm.data.bootstrap import compute_split

CPU, MEM = "CPU usage [%]", "Memory usage [%]"
TH = {"p20": 10, "p40": 30, "p60": 60, "p80": 90, "p95": 95}


def test_real_forecast_and_truth_have_identical_target_timestamps(synthetic_frame):
    boot, _, _ = compute_split(synthetic_frame)
    model = VMPredictor(CPU, n_estimators=3, max_depth=3)
    model.fit(boot)
    t = synthetic_frame.index[350]
    forecast = forecast_at_origin(model, synthetic_frame[CPU], t)
    observed = forward_observations(synthetic_frame, t)
    assert forecast.index.equals(observed.index)
    assert forecast.index.equals(forecast_targets(t))
    assert len(forecast) == 288
    assert forecast.index[0] == t + SAMPLE_STEP
    assert forecast.index[-1] == t + HORIZON
    assert t not in observed.index
    gt = derive_ground_truth_at_t_v2(synthetic_frame, t, cpu_thresholds=TH, mem_thresholds=TH)
    assert gt["p95_cpu_next_24h"] == observed[CPU].quantile(.95)


def test_gap_at_start_of_history_cannot_double_forecast_cadence(synthetic_frame):
    boot, _, _ = compute_split(synthetic_frame)
    model = VMPredictor(CPU, n_estimators=3, max_depth=3)
    model.fit(boot)
    history = synthetic_frame[CPU].iloc[:351].drop(synthetic_frame.index[1])
    forecast = model.predict_causal_horizon(history)
    assert forecast.index.equals(forecast_targets(history.index[-1]))
    with pytest.raises(ValueError, match="five minutes"):
        model.predict_causal_horizon(history, step=pd.Timedelta(minutes=10))


def test_origin_excluded_endpoint_included(synthetic_frame):
    t = synthetic_frame.index[350]
    df = synthetic_frame.copy()
    df[[CPU, MEM]] = 20.0
    df.loc[t, CPU] = 1e12
    df.loc[t + HORIZON, CPU] = 1000.0
    targets = forward_observations(df, t)
    assert len(targets) == 288
    assert targets.index[0] == t + SAMPLE_STEP and targets.index[-1] == t + HORIZON
    for derive in [derive_ground_truth_at_t, derive_ground_truth_at_t_v2]:
        gt = derive(df, t, cpu_thresholds=TH, mem_thresholds=TH)
        assert gt["cpu_class"] == "low"  # Mean ~23.4; the huge origin is excluded.


@pytest.mark.parametrize("n_observed", [199, 200, 288])
def test_sparse_density_counts_only_exact_forward_targets(synthetic_frame, n_observed):
    t = synthetic_frame.index[100]
    targets = forecast_targets(t)
    sparse = synthetic_frame.drop(targets[:288 - n_observed])
    window = forward_observations(sparse, t)
    assert len(window) == n_observed
    assert window.index.isin(targets).all()
    clock, _ = compute_data_aware_evaluation_timestamps(sparse, sparse.index[sparse.index >= t])
    if n_observed >= 200:
        assert t in clock
        gt = derive_ground_truth_at_t_v2(sparse, t, cpu_thresholds=TH, mem_thresholds=TH)
        assert gt["p95_cpu_next_24h"] == window[CPU].quantile(.95)
    else:
        assert t not in clock  # Origin is present, but cannot be counted as target 200.
        with pytest.raises(ValueError, match="insufficient"):
            derive_ground_truth_at_t_v2(sparse, t, cpu_thresholds=TH, mem_thresholds=TH)


def test_dense_but_truncated_horizon_is_ineligible(synthetic_frame):
    t = synthetic_frame.index[100]
    truncated = synthetic_frame.loc[:t + HORIZON - SAMPLE_STEP]
    assert len(forward_observations(truncated, t)) == 287
    with pytest.raises(ValueError, match="not elapsed"):
        derive_ground_truth_at_t(truncated, t, cpu_thresholds=TH, mem_thresholds=TH)
    clock, _ = compute_data_aware_evaluation_timestamps(truncated, truncated.index[100:])
    assert t not in clock


def test_missing_evaluation_origin_is_dropped_without_moving_next_tick(synthetic_frame):
    idx = pd.date_range("2021-01-01", periods=3 * 288 + 1, freq="5min")
    missing = idx[144]
    idx = idx[idx != missing]
    df = pd.DataFrame({CPU: 20.0, MEM: 30.0}, index=idx)
    clock, _ = compute_data_aware_evaluation_timestamps(df, idx)
    assert missing not in clock
    assert missing + pd.Timedelta(hours=12) in clock
    assert missing + SAMPLE_STEP not in clock


def test_clock_requires_actual_origin_even_if_candidate_index_contains_it(synthetic_frame):
    t = synthetic_frame.index[100]
    no_origin = synthetic_frame.drop(t)
    clock, _ = compute_data_aware_evaluation_timestamps(no_origin, synthetic_frame.index[100:])
    assert t not in clock


def test_density_requires_paired_cpu_memory_values(synthetic_frame):
    t = synthetic_frame.index[100]
    df = synthetic_frame.copy()
    df.loc[forecast_targets(t)[:89], MEM] = float("nan")
    assert len(forward_observations(df, t)) == 199
    clock, _ = compute_data_aware_evaluation_timestamps(df, df.index[100:])
    assert t not in clock
    with pytest.raises(ValueError, match="insufficient"):
        derive_ground_truth_at_t(df, t, cpu_thresholds=TH, mem_thresholds=TH)


def test_refresh_rejects_a_predictor_with_old_left_closed_targets(synthetic_frame):
    t = synthetic_frame.index[350]
    class WrongBoundaryPredictor:
        def predict_causal_horizon(self, history, n_steps=288):
            return pd.Series(0.0, index=pd.date_range(history.index[-1], periods=n_steps, freq="5min"))
    with pytest.raises(ValueError, match="exactly the 288 targets"):
        forecast_at_origin(WrongBoundaryPredictor(), synthetic_frame[CPU], t)
