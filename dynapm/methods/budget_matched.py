"""Analysis-only paired budget control. Not a deployable online policy."""
import pandas as pd

from dynapm.core.accounting import Trigger
from dynapm.core.temporal import PeriodicGrid
from dynapm.methods.baselines_v2 import PeriodicPredictorPolicyV2

BUDGET_SCHEDULE_VERSION = "budget-match-uniform-eligible-v2"


def periodic_commit_times(timeline, anchor, period_hours=6, eligibility_mask=None):
    grid = PeriodicGrid(anchor, period_hours)
    return pd.DatetimeIndex([t for t in timeline if grid.pop_due(t, True if eligibility_mask is None else bool(eligibility_mask.loc[t])) is not None])


def budget_extra_times(timeline, periodic_commits, k):
    """Midpoint equal-spacing indices, integer arithmetic, no drift-time input.

    Candidates are observed processed times minus base periodic commits. For
    0<=K<=N, floor((2*i+1)*N/(2*K)) yields K unique ordered indices.
    Only the paired event COUNT K enters; no detector/label/outcome information.
    """
    timeline = pd.DatetimeIndex(timeline)
    if not timeline.is_unique or not timeline.is_monotonic_increasing:
        raise ValueError("processed timeline must be unique and ordered")
    candidates = timeline[~timeline.isin(periodic_commits)]
    if not isinstance(k, int) or not 0 <= k <= len(candidates):
        raise ValueError("extra budget must fit unique non-periodic opportunities")
    if k == 0:
        return pd.DatetimeIndex([])
    return candidates[[(2*i+1)*len(candidates)//(2*k) for i in range(k)]]


class BudgetMatchedPredictorPolicy(PeriodicPredictorPolicyV2):
    allowed_triggers = (Trigger.PERIODIC, Trigger.BUDGET_EXTRA)

    def __init__(self, *args, extra_times, **kwargs):
        super().__init__(*args, **kwargs)
        times = pd.DatetimeIndex(extra_times)
        if not times.is_unique:
            raise ValueError("duplicate extra timestamps")
        self.extra_times = frozenset(times)

    def step(self, t, cpu_obs_window, mem_obs_window):
        before = len(self.accounting.refresh_events)
        super().step(t, cpu_obs_window, mem_obs_window)
        if pd.Timestamp(t) in self.extra_times:
            if len(self.accounting.refresh_events) != before:
                raise ValueError("budget extra collides with base periodic commit")
            cpu, mem = self._causal_windows(t)
            self._commit_forecast(t, cpu, mem, trigger=Trigger.BUDGET_EXTRA)
