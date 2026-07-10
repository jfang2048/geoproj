"""Curve-number lookup and burn adjustment checks."""
import pytest

from postfire_runoff.backend.hydrology.curve_numbers import apply_burn_adjustment, lookup_curve_number, normalize_hsg, normalize_landcover


def test_landcover_and_hsg_lookup_uses_two_dimensional_table():
    assert normalize_landcover("woods") == "forest"
    assert normalize_hsg("c soil") == "C"
    assert lookup_curve_number("forest", "B") == 55.0
    assert lookup_curve_number("grassland", "C") == 74.0


def test_invalid_hsg_rejected():
    with pytest.raises(ValueError):
        lookup_curve_number("forest", "Z")


def test_burn_adjustment_applies_only_configured_class_increment():
    adjustments = {0: 0, 1: 4, 2: 8, 3: 12}
    assert apply_burn_adjustment(70, 0, adjustments) == 70
    assert apply_burn_adjustment(70, 2, adjustments) == 78
