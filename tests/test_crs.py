from __future__ import annotations

from pyproj import CRS


def test_analysis_crs_is_projected_utm32():
    from app.core.config import WORKING_CRS

    crs = CRS.from_user_input(WORKING_CRS)
    assert crs.to_epsg() == 32632
    assert crs.is_projected


def test_display_crs_is_wgs84():
    from app.core.config import DISPLAY_CRS

    crs = CRS.from_user_input(DISPLAY_CRS)
    assert crs.to_epsg() == 4326
    assert crs.is_geographic
