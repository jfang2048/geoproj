"""Numerical checks for the canonical SCS-CN implementation."""
import math

import numpy as np
import pytest

from postfire_runoff.backend.hydrology.scs_cn import aggregate_response_unit_runoff, burned_cn, scs_runoff_mm


def manual_scs(p, cn, lam=0.20):
    s = 25400 / cn - 254
    ia = lam * s
    return 0.0 if p <= ia else (p - ia) ** 2 / (p + (1 - lam) * s)


def test_known_positive_runoff_case():
    assert float(scs_runoff_mm(100.0, 70.0, 0.20)) == pytest.approx(manual_scs(100.0, 70.0, 0.20))


def test_threshold_behavior_returns_zero_at_and_below_abstraction():
    cn = 60.0
    s = 25400 / cn - 254
    ia = 0.20 * s
    assert float(scs_runoff_mm(ia, cn, 0.20)) == 0.0
    assert float(scs_runoff_mm(ia - 0.001, cn, 0.20)) == 0.0


@pytest.mark.parametrize("rainfall", [-1.0, float("nan")])
def test_invalid_rainfall_rejected(rainfall):
    with pytest.raises(ValueError):
        scs_runoff_mm(rainfall, 70)


@pytest.mark.parametrize("cn", [0.0, 99.0, float("nan")])
def test_invalid_cn_rejected(cn):
    with pytest.raises(ValueError):
        scs_runoff_mm(50.0, cn)


@pytest.mark.parametrize("lam", [0.0, 1.0, -0.1, float("nan")])
def test_invalid_lambda_rejected(lam):
    with pytest.raises(ValueError):
        scs_runoff_mm(50.0, 70.0, lam)


def test_burned_cn_clamps_to_documented_max_and_rejects_unknown_class():
    assert burned_cn(95.0, 3, {0: 0, 1: 4, 2: 8, 3: 12}) == 98.0
    with pytest.raises(ValueError):
        burned_cn(70.0, 9)


def test_area_weighted_depth_and_volume_conversion():
    areas = np.array([1000.0, 3000.0])
    baseline = np.array([55.0, 74.0])
    burned = np.array([63.0, 82.0])
    agg = aggregate_response_unit_runoff(60.0, baseline, burned, areas, 0.20)
    q_base = scs_runoff_mm(60.0, baseline, 0.20)
    expected_depth = float(np.sum(q_base * areas) / areas.sum())
    assert agg.baseline_runoff_mm == pytest.approx(expected_depth)
    assert agg.baseline_volume_m3 == pytest.approx(agg.baseline_runoff_mm / 1000.0 * areas.sum())
    assert agg.delta_runoff_mm == pytest.approx(agg.burned_runoff_mm - agg.baseline_runoff_mm)
    assert agg.delta_volume_m3 == pytest.approx(agg.burned_volume_m3 - agg.baseline_volume_m3)
