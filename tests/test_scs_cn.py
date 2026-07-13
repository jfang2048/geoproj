"""Numerical checks for the SCS-CN implementation."""
import numpy as np
import pytest

from postfire_runoff.backend.hydrology.scs_cn import aggregate_response_unit_runoff, burned_cn, scs_runoff_mm


def manual_scs(p, cn, lam=0.20):
    s = 25400 / cn - 254
    ia = lam * s
    return 0.0 if p <= ia else (p - ia) ** 2 / (p + (1 - lam) * s)


def test_scs_runoff_formula_for_dry_and_wet_events():
    cn = 60.0
    s = 25400 / cn - 254
    dry_rain = 0.20 * s - 0.001
    assert float(scs_runoff_mm(dry_rain, cn, 0.20)) == 0.0
    assert float(scs_runoff_mm(100.0, 70.0, 0.20)) == pytest.approx(manual_scs(100.0, 70.0, 0.20))


@pytest.mark.parametrize("cn", [0.0, 99.0, float("nan")])
def test_cn_range_validation(cn):
    with pytest.raises(ValueError):
        scs_runoff_mm(50.0, cn)


def test_area_weighted_runoff_aggregation():
    areas = np.array([1000.0, 3000.0])
    baseline = np.array([55.0, 74.0])
    burned = np.array([63.0, 82.0])
    agg = aggregate_response_unit_runoff(60.0, baseline, burned, areas, 0.20)
    expected = float(np.sum(scs_runoff_mm(60.0, baseline, 0.20) * areas) / areas.sum())
    assert agg.baseline_runoff_mm == pytest.approx(expected)
    assert agg.baseline_volume_m3 == pytest.approx(agg.baseline_runoff_mm / 1000.0 * areas.sum())
    assert agg.delta_runoff_mm == pytest.approx(agg.burned_runoff_mm - agg.baseline_runoff_mm)
    assert agg.delta_volume_m3 == pytest.approx(agg.burned_volume_m3 - agg.baseline_volume_m3)


def test_burned_cn_clamps_to_project_max_and_rejects_unknown_class():
    assert burned_cn(95.0, 3, {0: 0, 1: 4, 2: 8, 3: 12}) == 98.0
    with pytest.raises(ValueError):
        burned_cn(70.0, 9)
