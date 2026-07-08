from pathlib import Path

import geopandas as gpd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
EPSG = 32632


def test_processed_vectors_use_working_crs_when_present():
    for rel in [
        "data/processed/boundary/processing_aoi_utm32.gpkg",
        "data/processed/boundary/catchment_utm32.gpkg",
        "data/processed/model_inputs/runoff_units.gpkg",
    ]:
        path = ROOT / rel
        if path.exists():
            gdf = gpd.read_file(path)
            assert gdf.crs is not None, rel
            assert gdf.crs.to_epsg() == EPSG, rel
            assert not gdf.empty, rel


def test_processed_rasters_use_working_crs_when_present():
    for rel in [
        "data/processed/dem/dem_utm32.tif",
        "data/processed/dem/flow_accumulation.tif",
        "data/processed/burn/burn_severity_proxy_uint8.tif",
        "data/processed/soil/hydrologic_soil_group.tif",
    ]:
        path = ROOT / rel
        if path.exists():
            with rasterio.open(path) as ds:
                assert ds.crs is not None, rel
                assert ds.crs.to_epsg() == EPSG, rel
                assert ds.width > 0 and ds.height > 0, rel


def test_working_crs_is_wgs84_utm32n_and_matches_config():
    import yaml
    from pyproj import CRS
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from pipeline_utils import WORKING_CRS

    cfg = yaml.safe_load((ROOT / "config/project.yaml").read_text())
    assert WORKING_CRS == cfg["project"]["crs_working"] == "EPSG:32632"
    crs = CRS.from_user_input(WORKING_CRS)
    assert crs.to_epsg() == 32632
    assert "UTM zone 32N" in crs.name


def test_raster_reprojection_utility_handles_non_working_source_crs(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from pipeline_utils import read_raster_window_to_working

    src = tmp_path / "tiny_wgs84_dem.tif"
    data = np.arange(100, dtype="float32").reshape(10, 10)
    with rasterio.open(
        src,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(8.80, 45.92, 0.005, 0.005),
        nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)

    arr, transform, src_crs, dst_crs = read_raster_window_to_working(
        src,
        bounds_working=(484000, 5079500, 488500, 5085200),
        resolution=250,
        nodata=-9999.0,
    )
    assert src_crs.to_epsg() == 4326
    assert dst_crs.to_epsg() == 32632
    assert arr.size > 0
    assert round(transform.a, 6) == 250
    assert round(abs(transform.e), 6) == 250
