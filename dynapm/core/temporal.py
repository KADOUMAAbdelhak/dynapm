"""Canonical five-minute forecast targets and observation-driven wall-clock ticks."""
import numpy as np
import pandas as pd

SAMPLE_STEP = pd.Timedelta(minutes=5)
HORIZON_STEPS = 288
HORIZON = HORIZON_STEPS * SAMPLE_STEP
MIN_OBSERVATIONS = 200
TEMPORAL_PROTOCOL = "causal-timeline-v3"


def forecast_targets(origin, n_steps=HORIZON_STEPS) -> pd.DatetimeIndex:
    """Exactly t+5m, ..., t+n_steps*5m; the origin itself is excluded."""
    if int(n_steps) != n_steps or n_steps <= 0:
        raise ValueError("n_steps must be a positive integer")
    return pd.date_range(pd.Timestamp(origin) + SAMPLE_STEP, periods=int(n_steps), freq=SAMPLE_STEP)


def forward_observations(df, origin, window_hours=24):
    """Available paired observations on the nominal (origin, origin+window] grid.

    Missing slots are omitted, never imputed. With CPU/memory columns present,
    both must be non-null to count as an observed target. Generic clock fixtures
    can supply timestamp-only frames instead.
    """
    if not isinstance(df.index, pd.DatetimeIndex) or not df.index.is_unique:
        raise ValueError("forward windows require unique datetime timestamps")
    duration = pd.Timedelta(hours=window_hours)
    if duration <= pd.Timedelta(0) or duration % SAMPLE_STEP:
        raise ValueError("window must be a positive multiple of five minutes")
    targets = forecast_targets(origin, duration // SAMPLE_STEP)
    window = df.loc[df.index.intersection(targets)].sort_index()
    metrics = ["CPU usage [%]", "Memory usage [%]"]
    if all(c in window for c in metrics):
        window = window.loc[np.isfinite(window[metrics].to_numpy(dtype=float)).all(axis=1)]
    return window


class PeriodicGrid:
    """Deliver the latest due tick once, without re-anchoring after a gap.

    Bootstrap-derived state precedes the grid; scheduled refreshes are k>=1.
    pop_due is called only when a new observation is actually processed.
    """
    def __init__(self, anchor, period_hours):
        self.anchor = pd.Timestamp(anchor)
        self.period = pd.Timedelta(hours=period_hours)
        if pd.isna(self.anchor) or pd.isna(self.period) or self.period <= pd.Timedelta(0):
            raise ValueError("anchor and positive finite period are required")
        self.next_tick = self.anchor + self.period
        self._previous_observation = None
        self.nominal_ticks_due = 0
        self.pending_tick = None

    def pop_due(self, observation_time, eligible=True):
        t = pd.Timestamp(observation_time)
        if t < self.anchor or (self._previous_observation is not None and t <= self._previous_observation):
            raise ValueError("observation times must increase strictly from the anchor")
        self._previous_observation = t
        if t >= self.next_tick:
            latest = self.anchor + ((t - self.anchor) // self.period) * self.period
            self.nominal_ticks_due += int((latest - self.next_tick) // self.period) + 1
            self.next_tick = latest + self.period
            self.pending_tick = latest
        if eligible and self.pending_tick is not None:
            tick, self.pending_tick = self.pending_tick, None
            return tick
        return None


FEATURE_HISTORY_SLOTS = 96
REACTIVE_SLOTS = 72
MIN_REACTIVE_OBSERVATIONS = 50
EVALUATION_GRID = "phase-balanced-hourly-v1"
METRICS = ("CPU usage [%]", "Memory usage [%]")


def nominal_grid(index):
    """Dense nominal timestamps, with missing values left missing on reindex."""
    index = pd.DatetimeIndex(index)
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("nominal grid requires unique increasing timestamps")
    if len(index) and ((index-index[0]) % SAMPLE_STEP != pd.Timedelta(0)).any():
        raise ValueError("observations must lie on one five-minute nominal grid")
    return pd.date_range(index[0], index[-1], freq=SAMPLE_STEP) if len(index) else index


def trailing_targets(origin, slots=HORIZON_STEPS):
    return pd.date_range(pd.Timestamp(origin)-(slots-1)*SAMPLE_STEP, periods=slots, freq=SAMPLE_STEP)


def exact_lookup(series, timestamps):
    return series.reindex(pd.DatetimeIndex(timestamps))


def history_valid(series, origin):
    """96 complete actual slots ending at origin support its next prediction."""
    return bool(np.isfinite(exact_lookup(series, trailing_targets(origin, FEATURE_HISTORY_SLOTS)).to_numpy(dtype=float)).all())


def trailing_observations(series, origin, hours=24):
    """Actual finite samples on (origin-hours, origin], never an observed-row tail."""
    slots = pd.Timedelta(hours=hours)//SAMPLE_STEP
    values = exact_lookup(series, trailing_targets(origin, slots))
    return values[np.isfinite(values.to_numpy(dtype=float))]


def eligibility(cpu, mem, origin):
    """Shared content gate, requiring both resources at each counted slot."""
    frame = pd.concat([cpu.rename('cpu'), mem.rename('mem')], axis=1)
    paired = frame.reindex(trailing_targets(origin))
    window_ok = int(np.isfinite(paired.to_numpy(dtype=float)).all(axis=1).sum()) >= MIN_OBSERVATIONS
    origin_ok = history_valid(cpu, origin) and history_valid(mem, origin)
    return window_ok and origin_ok


def validity_table(frame):
    """Vectorized presence-only semantics shared by replay and corpus metadata audit.

    No model, value interpolation, policy, outcome, or detector is evaluated.
    """
    dense = frame.loc[:, list(METRICS)].reindex(nominal_grid(frame.index))
    present = pd.Series(np.isfinite(dense.to_numpy(dtype=float)).all(axis=1), index=dense.index)
    origin = present.rolling(FEATURE_HISTORY_SLOTS, min_periods=FEATURE_HISTORY_SLOTS).sum().eq(FEATURE_HISTORY_SLOTS)
    out = pd.DataFrame({'observed': present, 'predictor_origin': origin,
        'one_step': origin.shift(1, fill_value=False) & present,
        'window24': present.rolling(288, min_periods=1).sum().ge(200),
        'window6': present.rolling(72, min_periods=1).sum().ge(50)}, index=dense.index)
    out['periodic'] = out.predictor_origin & out.window24
    out['forward_slots'] = present.iloc[::-1].rolling(288, min_periods=1).sum().iloc[::-1].shift(-1).fillna(0).astype(int)
    return out
