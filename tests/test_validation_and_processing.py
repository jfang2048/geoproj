from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box


def test_vector_geometry_validation_reports_invalid(tmp_path):
    from app.gis.validation import validate_vector
    from app.models.categories import InputCategory

    invalid = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    path = tmp_path / "burn.geojson"
    gpd.GeoDataFrame([{"burn_class": "low"}], geometry=[invalid], crs="EPSG:4326").to_file(path, driver="GeoJSON")

    report = validate_vector(path, InputCategory.burn_severity)
    assert report.valid
    assert report.metadata["invalid_geometry_count"] == 1
    assert report.warnings


def test_crs_transformation_to_analysis_crs(tmp_path):
    from app.gis.normalize import normalize_vector
    from app.models.categories import InputCategory

    src = tmp_path / "land.geojson"
    dst = tmp_path / "land.gpkg"
    gpd.GeoDataFrame([{"landcover_class": "forest"}], geometry=[box(8.8, 45.8, 8.81, 45.81)], crs="EPSG:4326").to_file(src, driver="GeoJSON")
    normalize_vector(src, dst, InputCategory.land_cover)
    out = gpd.read_file(dst)
    assert out.crs.to_epsg() == 32632


def test_rainfall_csv_validation_rejects_bad_rows(tmp_path):
    from app.gis.validation import validate_rainfall_csv

    path = tmp_path / "rain.csv"
    pd.DataFrame(
        [
            {"event_id": "E1", "start_date": "2020-01-01", "end_date": "2020-01-01", "rainfall_mm": 10, "units": "mm"},
            {"event_id": "E1", "start_date": "bad", "end_date": "2020-01-02", "rainfall_mm": -1, "units": "inch"},
        ]
    ).to_csv(path, index=False)
    report = validate_rainfall_csv(path)
    assert not report.valid
    assert any("Duplicate" in e for e in report.errors)
    assert any("negative" in e for e in report.errors)
    assert any("units" in e for e in report.errors)


def test_missing_required_input_failure(isolated_runs):
    from app.core.errors import MissingRequiredInputError
    from app.services.processing_service import preprocess_run
    from app.services.run_service import create_run

    run = create_run("missing-inputs")
    with pytest.raises(MissingRequiredInputError):
        preprocess_run(run["run_id"])


def test_raster_metadata_validation_and_crs_detection(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    import numpy as np
    from rasterio.transform import from_origin

    from app.gis.validation import validate_raster
    from app.models.categories import InputCategory

    path = tmp_path / "dem.tif"
    data = np.arange(100, dtype="float32").reshape(10, 10)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(8.8, 45.9, 0.001, 0.001),
        nodata=-9999,
    ) as dst:
        dst.write(data, 1)
    report = validate_raster(path, InputCategory.dem)
    assert report.valid
    assert report.metadata["crs"] == "EPSG:4326"
    assert report.metadata["width"] == 10
    assert report.metadata["nodata"] == -9999


def test_categorical_raster_resampling_rule_is_nearest():
    from app.gis.normalize import resampling_for_category
    from app.models.categories import InputCategory

    assert resampling_for_category(InputCategory.land_cover) == "nearest"
    assert resampling_for_category(InputCategory.burn_severity) == "nearest"
    assert resampling_for_category(InputCategory.hydrologic_soil_group) == "nearest"
    assert resampling_for_category(InputCategory.dem) == "bilinear"
