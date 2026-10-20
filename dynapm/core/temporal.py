"""Canonical five-minute forecast targets and observation-driven wall-clock ticks."""
import pandas as pd

SAMPLE_STEP = pd.Timedelta(minutes=5)
HORIZON_STEPS = 288
HORIZON = HORIZON_STEPS * SAMPLE_STEP
MIN_OBSERVATIONS = 200
TEMPORAL_PROTOCOL = "causal-timeline-v2"


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
        window = window.dropna(subset=metrics)
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

    def pop_due(self, observation_time):
        t = pd.Timestamp(observation_time)
        if t < self.anchor or (self._previous_observation is not None and t <= self._previous_observation):
            raise ValueError("observation times must increase strictly from the anchor")
        self._previous_observation = t
        if t < self.next_tick:
            return None
        latest = self.anchor + ((t - self.anchor) // self.period) * self.period
        self.next_tick = latest + self.period
        return latest
