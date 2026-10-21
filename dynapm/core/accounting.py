"""One commit path and explicit accounting for profile maintenance operations."""
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

DYNAMIC_FIELDS = ("cpu_class", "memory_class", "predicted_cpu_p95_next_24h", "predicted_mem_p95_next_24h")
FIELD_CHANGE_METRICS = dict(zip(("n_cpu_class_value_changes", "n_memory_class_value_changes",
    "n_cpu_p95_value_changes", "n_mem_p95_value_changes"), DYNAMIC_FIELDS))
ACCOUNTING_SCHEMA = "refresh-accounting-v1"
ACCOUNTING_METRICS = (
    "n_initialization_events", "n_refresh_events", "n_field_writes", "n_field_value_changes",
    "n_periodic_refreshes", "n_drift_refreshes", "n_reactive_refreshes", "n_full_rewrite_refreshes",
    "n_budget_extra_refreshes",
    "nominal_periodic_ticks_due", "periodic_refresh_events_committed",
)


class Trigger(str, Enum):
    PERIODIC = "periodic"
    DRIFT = "drift"
    REACTIVE = "reactive"
    FULL_REWRITE = "full_rewrite"
    BUDGET_EXTRA = "budget_extra"


def value_changed(old, new):
    """Missing-to-missing is unchanged; other scalar assignments compare values."""
    if pd.isna(old):
        return not bool(pd.isna(new))
    if pd.isna(new):
        return True
    return bool(old != new)


@dataclass(frozen=True)
class InitializationEvent:
    actual_commit_time: pd.Timestamp
    fields_written: tuple[str, ...]
    fields_changed: tuple[str, ...]

    def to_dict(self):
        return {"actual_commit_time": self.actual_commit_time.isoformat(),
                "fields_written": list(self.fields_written), "fields_changed": list(self.fields_changed)}


@dataclass(frozen=True)
class RefreshEvent:
    actual_commit_time: pd.Timestamp
    trigger: Trigger
    nominal_scheduled_time: pd.Timestamp | None
    fields_written: tuple[str, ...]
    fields_changed: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "trigger", Trigger(self.trigger))
        object.__setattr__(self, "actual_commit_time", pd.Timestamp(self.actual_commit_time))
        if pd.isna(self.actual_commit_time):
            raise ValueError("commit timestamp must be valid")
        if self.nominal_scheduled_time is not None:
            object.__setattr__(self, "nominal_scheduled_time", pd.Timestamp(self.nominal_scheduled_time))
            if pd.isna(self.nominal_scheduled_time):
                raise ValueError("nominal timestamp must be valid")
        if self.trigger == Trigger.PERIODIC:
            if self.nominal_scheduled_time is None or self.nominal_scheduled_time > self.actual_commit_time:
                raise ValueError("periodic commit requires a due nominal timestamp")
        elif self.nominal_scheduled_time is not None:
            raise ValueError("only periodic refreshes have a nominal timestamp")
        if self.fields_written != DYNAMIC_FIELDS or len(set(self.fields_changed)) != len(self.fields_changed) or not set(self.fields_changed) <= set(self.fields_written):
            raise ValueError("a refresh writes the four dynamic fields; changed fields must be a subset")

    def as_record(self):
        return {"actual_commit_time": self.actual_commit_time, "trigger": self.trigger.value,
                "nominal_scheduled_time": self.nominal_scheduled_time,
                "fields_written": list(self.fields_written), "fields_changed": list(self.fields_changed)}

    def to_dict(self):
        record = self.as_record()
        record["actual_commit_time"] = self.actual_commit_time.isoformat()
        record["nominal_scheduled_time"] = self.nominal_scheduled_time.isoformat() if self.nominal_scheduled_time is not None else None
        return record


class ProfileCommitter:
    """All six policies initialize and write dynamic state through this helper."""
    def __init__(self, profile, allowed_triggers):
        self.profile = profile
        self.allowed_triggers = frozenset(Trigger(t) for t in allowed_triggers)
        self.initialization_events: list[InitializationEvent] = []
        self.refresh_events: list[RefreshEvent] = []

    def _changed_fields(self, values):
        if set(values) != set(DYNAMIC_FIELDS):
            raise ValueError("commit requires exactly the four dynamic fields")
        return tuple(f for f in DYNAMIC_FIELDS if value_changed(getattr(self.profile.dynamic, f), values[f]))

    def _assign(self, t, values):
        for field in DYNAMIC_FIELDS:
            setattr(self.profile.dynamic, field, values[field])
            self.profile.last_updated[field] = t

    def initialize(self, t, values):
        if self.initialization_events:
            raise ValueError("profile initialization may occur only once")
        t = pd.Timestamp(t)
        if pd.isna(t):
            raise ValueError("initialization timestamp must be valid")
        event = InitializationEvent(t, DYNAMIC_FIELDS, self._changed_fields(values))
        self._assign(t, values)
        self.initialization_events.append(event)

    def commit(self, t, values, *, trigger, nominal_scheduled_time=None):
        t = pd.Timestamp(t)
        trigger = Trigger(trigger)
        if not self.initialization_events:
            raise ValueError("initialize before runtime refresh")
        if pd.isna(t) or t < self.initialization_events[0].actual_commit_time:
            raise ValueError("runtime commit must follow initialization")
        if trigger not in self.allowed_triggers:
            raise ValueError("trigger is not supported by this policy")
        if self.refresh_events and t <= self.refresh_events[-1].actual_commit_time:
            raise ValueError("at most one refresh per strictly increasing processed timestamp")
        event = RefreshEvent(t, trigger, nominal_scheduled_time, DYNAMIC_FIELDS, self._changed_fields(values))
        self._assign(t, values)  # Every runtime refresh performs four assignments, even unchanged ones.
        self.refresh_events.append(event)

    def counters(self, nominal_ticks_due=0):
        counts = {t: sum(e.trigger == t for e in self.refresh_events) for t in Trigger}
        return {
            "n_initialization_events": len(self.initialization_events),
            "n_refresh_events": len(self.refresh_events),
            "n_field_writes": sum(len(e.fields_written) for e in self.refresh_events),
            "n_field_value_changes": sum(len(e.fields_changed) for e in self.refresh_events),
            "n_periodic_refreshes": counts[Trigger.PERIODIC], "n_drift_refreshes": counts[Trigger.DRIFT],
            "n_reactive_refreshes": counts[Trigger.REACTIVE], "n_full_rewrite_refreshes": counts[Trigger.FULL_REWRITE],
            "n_budget_extra_refreshes": counts[Trigger.BUDGET_EXTRA],
            "nominal_periodic_ticks_due": nominal_ticks_due,
            "periodic_refresh_events_committed": counts[Trigger.PERIODIC],
        }


def require_accounting_metrics(frame):
    """Reject legacy/malformed counters; never infer or normalize counts from logs."""
    if "accounting_schema" not in frame or not frame.accounting_schema.eq(ACCOUNTING_SCHEMA).all():
        raise ValueError("matching refresh accounting schema is required")
    if not set(ACCOUNTING_METRICS) <= set(frame):
        raise ValueError("canonical accounting counters are required")
    ok = frame[frame.run_status == "ok"] if "run_status" in frame else frame
    counts = ok[list(ACCOUNTING_METRICS)].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(counts.to_numpy()).all() or ((counts < 0) | (counts % 1 != 0)).any().any():
        raise ValueError("accounting counters must be finite nonnegative integers")
    trigger_sum = counts[["n_periodic_refreshes", "n_drift_refreshes", "n_reactive_refreshes", "n_full_rewrite_refreshes", "n_budget_extra_refreshes"]].sum(axis=1)
    if not (counts.n_refresh_events.eq(trigger_sum).all()
            and counts.n_initialization_events.eq(1).all()
            and counts.n_field_writes.eq(4 * counts.n_refresh_events).all()
            and counts.n_field_value_changes.le(counts.n_field_writes).all()
            and counts.periodic_refresh_events_committed.eq(counts.n_periodic_refreshes).all()
            and counts.nominal_periodic_ticks_due.ge(counts.n_periodic_refreshes).all()):
        raise ValueError("inconsistent canonical accounting counters")
    if "method" in ok:
        for method, permitted in {
            "static_v2": [], "periodic_6h_v2": ["n_periodic_refreshes"],
            "periodic_predictor_6h_v2": ["n_periodic_refreshes"],
            "dynapm_v3_v2": ["n_periodic_refreshes", "n_drift_refreshes"],
            "reactive_v2": ["n_reactive_refreshes"], "full_rewrite_v2": ["n_full_rewrite_refreshes"],
        }.items():
            rows = counts.loc[ok.method == method]
            if not rows.n_refresh_events.eq(rows[permitted].sum(axis=1) if permitted else 0).all():
                raise ValueError("policy trigger decomposition is inconsistent")
