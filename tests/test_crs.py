"""Test CRS policy enforcement."""
import pytest
from pyproj import CRS
from postfire_runoff.backend.gis.crs import (
    METRIC_CRS, WEB_CRS, FORBIDDEN_DEGREE_OPERATIONS,
    assert_not_degree_crs, require_crs,
)


def test_metric_crs_is_utm32():
    crs = CRS.from_user_input(METRIC_CRS)
    assert crs.to_epsg() == 32632
    assert crs.is_projected


def test_web_crs_is_wgs84():
    crs = CRS.from_user_input(WEB_CRS)
    assert crs.to_epsg() == 4326
    assert crs.is_geographic


def test_degree_crs_rejected_for_area():
    crs = CRS.from_user_input("EPSG:4326")
    with pytest.raises(ValueError):
        assert_not_degree_crs(crs, "area")


def test_projected_crs_passes():
    crs = CRS.from_user_input("EPSG:32632")
    assert_not_degree_crs(crs, "area")


def test_forbidden_operations():
    assert "area" in FORBIDDEN_DEGREE_OPERATIONS
    assert "distance" in FORBIDDEN_DEGREE_OPERATIONS
    assert "hydrologic_routing" in FORBIDDEN_DEGREE_OPERATIONS


def test_require_crs_missing():
    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs=None)
    with pytest.raises(ValueError):
        require_crs(gdf, 32632, "layer")


def test_require_crs_wrong():
    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    with pytest.raises(ValueError):
        require_crs(gdf, 32632, "layer")


def test_require_crs_correct():
    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(500000, 5000000)], crs="EPSG:32632")
    require_crs(gdf, 32632, "layer")
