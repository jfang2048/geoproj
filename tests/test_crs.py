"""Test CRS policy enforcement."""
from pyproj import CRS


def test_local_crs_is_utm32():
    crs = CRS.from_user_input("EPSG:32632")
    assert crs.to_epsg() == 32632
    assert crs.is_projected


def test_web_crs_is_wgs84():
    crs = CRS.from_user_input("EPSG:4326")
    assert crs.to_epsg() == 4326
    assert crs.is_geographic
