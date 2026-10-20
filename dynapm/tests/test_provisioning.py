"""Tests for dynapm.eval.provisioning."""
from __future__ import annotations

import math

import pytest

from dynapm.eval.provisioning import OVER_THRESHOLD, SAFETY_FACTOR, evaluate_provisioning


def test_under_case():
    r = evaluate_provisioning(10.0, 20.0, safety_factor=1.2, over_threshold=OVER_THRESHOLD)
    assert r["under_provisioned"] == 1
    assert r["over_provisioned"] == 0
    assert r["well_provisioned"] == 0


def test_well_case():
    r = evaluate_provisioning(10.0, 11.0, safety_factor=1.2, over_threshold=OVER_THRESHOLD)
    # rec = 12, actual 11: not under; 12 > 11*1.5? False -> well
    assert r["under_provisioned"] == 0
    assert r["over_provisioned"] == 0
    assert r["well_provisioned"] == 1


def test_over_case():
    r = evaluate_provisioning(10.0, 5.0, safety_factor=1.2, over_threshold=OVER_THRESHOLD)
    # rec=12 > 7.5
    assert r["under_provisioned"] == 0
    assert r["over_provisioned"] == 1


def test_boundary_under_exclusive():
    r = evaluate_provisioning(10.0, 12.0, safety_factor=1.2, over_threshold=OVER_THRESHOLD)
    # rec=12, actual=12 → not strictly under
    assert r["under_provisioned"] == 0


def test_boundary_over_exclusive():
    r = evaluate_provisioning(10.0, 8.0, safety_factor=1.5, over_threshold=1.5)
    # rec=15, actual*1.5=12 → strictly over
    assert r["over_provisioned"] == 1
    r_edge = evaluate_provisioning(10.0, 10.0, safety_factor=1.5, over_threshold=1.5)
    # rec=15, threshold line 15 → not strictly greater
    assert r_edge["over_provisioned"] == 0


def test_nan_inputs():
    r = evaluate_provisioning(float("nan"), 5.0)
    assert math.isnan(r["recommendation"])
    assert math.isnan(float(r["under_provisioned"]))
