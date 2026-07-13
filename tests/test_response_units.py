"""Response-unit construction and burn coverage checks."""
import geopandas as gpd
import pytest
from shapely.geometry import box

from postfire_runoff.backend.gis.response_units import build_response_units

CRS = "EPSG:32632"


def _gdf(records):
    geoms = [record.pop("geometry") for record in records]
    return gpd.GeoDataFrame(records, geometry=geoms, crs=CRS)


def test_partial_burn_polygons_create_unburned_class_and_cover_catchment():
    catchment = _gdf([{"geometry": box(0, 0, 100, 100)}])
    landcover = _gdf([{"landcover_class": "forest", "geometry": box(0, 0, 100, 100)}])
    hsg = _gdf([{"hsg": "B", "geometry": box(0, 0, 100, 100)}])
    burn = _gdf([{"burn_class": 2, "geometry": box(20, 20, 80, 80)}])

    units, diagnostics = build_response_units(catchment, landcover, hsg, burn)

    assert set(units["burn_class"]) == {0, 2}
    assert diagnostics.uncovered_area_m2 == pytest.approx(0.0)
    assert diagnostics.overlap_error_m2 == pytest.approx(0.0)
    assert units["area_m2"].sum() == pytest.approx(10000.0)
    assert units.geometry.union_all().area == pytest.approx(10000.0)


def test_overlapping_response_units_are_rejected():
    catchment = _gdf([{"geometry": box(0, 0, 100, 100)}])
    landcover = _gdf([
        {"landcover_class": "forest", "geometry": box(0, 0, 75, 100)},
        {"landcover_class": "grassland", "geometry": box(25, 0, 100, 100)},
    ])
    hsg = _gdf([{"hsg": "B", "geometry": box(0, 0, 100, 100)}])
    burn = _gdf([{"burn_class": 1, "geometry": box(20, 20, 80, 80)}])

    with pytest.raises(Exception, match="double-count"):
        build_response_units(catchment, landcover, hsg, burn)
