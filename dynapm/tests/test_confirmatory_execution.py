"""V3 confirmatory driver binding tests — no full-corpus scientific run."""
from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd
import pytest

from dynapm.experiments.confirmatory_design import (
    COMPARISON_FAMILIES,
    PERMANENT_PILOT_EXCLUSIONS,
    PRIMARY_METHODS,
    PROTOCOL_EXCLUSION_CODES,
    frozen_hashes,
)
from dynapm.experiments.confirmatory_estimation import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    holm_adjust,
    paired_bootstrap_cis,
    wilcoxon_report,
)
from dynapm.experiments.confirmatory_execution import (
    METHOD_FACTORIES,
    assert_pilots_excluded,
    classify_protocol_exclusion,
    confirmatory_config,
    factory_for,
    validate_confirmatory_config,
)
from dynapm.methods.baselines_v2 import (
    FullRewritePolicyV2,
    PeriodicPolicyV2,
    StaticPolicyV2,
)


def test_frozen_hashes_and_config_binding():
    hashes = frozen_hashes()
    assert hashes["design_fingerprint"] == "62c546a48ee25dff7e8ab46d3081e1688137f565024e5c102950100a03765296"
    assert hashes["gate_status"] == "PASS"
    config = confirmatory_config()
    validate_confirmatory_config(config)
    assert [p.method_id for p in config.policies] == list(PRIMARY_METHODS)
    assert config.statistics.bootstrap_repetitions == 10000
    assert config.statistics.bootstrap_seed == 20251022
    assert config.analysis["study_framing"] == "estimation_first"
    assert config.analysis["practical_significance"] == "NOT_DEFINED_AT_PROFILE_LEVEL"


def test_comparison_matrix_matches_freeze():
    config = confirmatory_config()
    frozen = config.analysis["comparison_families"]
    for family, pairs in COMPARISON_FAMILIES.items():
        got = [(row["treatment"], row["control"]) for row in frozen[family]]
        assert tuple(got) == pairs


def test_method_factories_are_observation_only():
    assert set(METHOD_FACTORIES) == set(PRIMARY_METHODS)
    assert factory_for("static") is StaticPolicyV2
    assert factory_for("full_rewrite") is FullRewritePolicyV2
    for hours in (3, 6, 12):
        fac = factory_for(f"pw_{hours}h")
        assert isinstance(fac, partial)
        assert fac.func is PeriodicPolicyV2
        assert fac.keywords["period_hours"] == float(hours)


def test_pilot_exclusion_guard():
    assert_pilots_excluded([{"trace": "Materna-Trace-1", "vm_id": "02"}])
    with pytest.raises(ValueError, match="pilot"):
        assert_pilots_excluded([{"trace": "Materna-Trace-1", "vm_id": "143"}])
    for trace, vm_id in PERMANENT_PILOT_EXCLUSIONS:
        with pytest.raises(ValueError, match="pilot"):
            assert_pilots_excluded([{"trace": trace, "vm_id": vm_id}])


def test_protocol_exclusion_codes_only():
    assert classify_protocol_exclusion(
        {
            "bootstrap_observations": 10,
            "globally_verifiable_opportunities": 100,
            "window24_eligible": 100,
            "valid_feature_rows": 100,
        }
    ) == "insufficient_bootstrap_history"
    assert classify_protocol_exclusion(
        {
            "bootstrap_observations": 600,
            "globally_verifiable_opportunities": 0,
            "window24_eligible": 100,
            "valid_feature_rows": 100,
        }
    ) == "insufficient_globally_verifiable_evaluation_origins"
    assert classify_protocol_exclusion(
        {
            "bootstrap_observations": 600,
            "globally_verifiable_opportunities": 100,
            "window24_eligible": 0,
            "valid_feature_rows": 100,
        }
    ) == "insufficient_exact_grid_feature_or_window_validity"
    # Review-flag style fractions alone must not exclude.
    assert (
        classify_protocol_exclusion(
            {
                "bootstrap_observations": 600,
                "globally_verifiable_opportunities": 100,
                "window24_eligible": 100,
                "valid_feature_rows": 100,
                "potential_eligibility_review": True,
                "training_valid_fraction": 0.9,
            }
        )
        is None
    )
    assert set(PROTOCOL_EXCLUSION_CODES) >= {
        "insufficient_bootstrap_history",
        "insufficient_exact_grid_feature_or_window_validity",
        "insufficient_globally_verifiable_evaluation_origins",
        "corrupt_or_nonfinite_source_data",
        "protocol_invalid_timeline_or_schema",
    }


def test_estimation_bootstrap_and_holm_frozen():
    assert BOOTSTRAP_B == 10000
    assert BOOTSTRAP_SEED == 20251022
    rng = np.random.default_rng(0)
    delta = rng.normal(size=50)
    a = paired_bootstrap_cis(delta)
    b = paired_bootstrap_cis(delta)
    assert a == b
    assert a["n"] == 50
    wil = wilcoxon_report(np.zeros(10))
    assert wil["pvalue"] == 1.0 and wil["all_ties"]
    adjusted = holm_adjust([0.01, 0.04, 0.03, None])
    assert adjusted[3] is None
    assert adjusted[0] <= adjusted[2] <= adjusted[1] or adjusted[0] <= 0.05


def test_validate_rejects_mutated_matrix():
    config = confirmatory_config()
    from dataclasses import replace
    from dynapm.core.provenance import PolicyConfig

    bad = replace(config, policies=tuple(list(config.policies) + [PolicyConfig("reactive")]))
    with pytest.raises(ValueError, match="exact five-method|must match frozen"):
        validate_confirmatory_config(bad)
