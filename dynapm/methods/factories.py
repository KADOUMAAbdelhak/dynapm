"""Shared policy factories and explicit dependency requirements."""
from functools import partial

from dynapm.methods.baselines_v2 import (
    _BasePolicyV2, StaticPolicyV2, PeriodicPolicyV2, ReactiveThresholdPolicyV2,
    FullRewritePolicyV2, PeriodicPredictorPolicyV2,
)
from dynapm.methods.dynapm_v3 import DynAPMPolicyV3


def policy_class(factory):
    """Accept policy classes or partials; never guess requirements from names."""
    cls = factory
    while isinstance(cls, partial):
        cls = cls.func
    if not isinstance(cls, type) or not issubclass(cls, _BasePolicyV2):
        raise TypeError("use a policy class or functools.partial(policy_class, ...) as factory")
    return cls


def policy_factory(method: str):
    factories = {
        "static_v2": StaticPolicyV2,
        "periodic_6h_v2": partial(PeriodicPolicyV2, period_hours=6.0),
        "reactive_v2": ReactiveThresholdPolicyV2,
        "full_rewrite_v2": FullRewritePolicyV2,
        "periodic_predictor_6h_v2": partial(PeriodicPredictorPolicyV2, period_hours=6.0),
        "dynapm_v3_v2": partial(DynAPMPolicyV3, period_hours=6.0, drift_delta=0.002),
    }
    try:
        return factories[method]
    except KeyError:
        raise ValueError(f"unknown policy method: {method}") from None
