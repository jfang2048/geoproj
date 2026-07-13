"""Land-cover and HSG curve-number checks."""
import pytest

from postfire_runoff.backend.hydrology.curve_numbers import lookup_curve_number, normalize_hsg, normalize_landcover


def test_landcover_alias_normalization_uses_underscore_form():
    assert normalize_landcover("open water") == "water"
    assert normalize_landcover("open_water") == "water"
    assert normalize_landcover("built-up") == "urban"
    assert normalize_landcover("bare soil") == "bare_soil"
    assert normalize_landcover("woodland") == "forest"
    assert normalize_landcover("cropland") == "agriculture"


def test_unknown_landcover_label_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown land-cover label"):
        normalize_landcover("orchard")


def test_lookup_and_hsg_normalization():
    assert normalize_hsg("c soil") == "C"
    assert lookup_curve_number("forest", "B") == 55.0
    assert lookup_curve_number("grassland", "C") == 74.0
    with pytest.raises(ValueError):
        lookup_curve_number("forest", "Z")
