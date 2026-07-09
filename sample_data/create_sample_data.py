"""Create a small upload-test dataset."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

OUT = Path(__file__).resolve().parent / "generated"
OUT.mkdir(parents=True, exist_ok=True)
CRS = "EPSG:32632"


def main() -> None:
    dem = np.arange(100, dtype="float32").reshape(10, 10) + 400
    with rasterio.open(
        OUT / "dem.tif",
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs=CRS,
        transform=from_origin(485000, 5080000, 30, 30),
        nodata=-9999,
    ) as dst:
        dst.write(dem, 1)

    boundary = box(485030, 5079730, 485270, 5079970)
    gpd.GeoDataFrame([{"name": "sample_fire"}], geometry=[boundary], crs=CRS).to_file(OUT / "fire_perimeter.geojson", driver="GeoJSON")
    gpd.GeoDataFrame([{"burn_class": "moderate"}], geometry=[boundary], crs=CRS).to_file(OUT / "burn_severity.geojson", driver="GeoJSON")
    gpd.GeoDataFrame([{"landcover_class": "forest"}], geometry=[boundary], crs=CRS).to_file(OUT / "land_cover.geojson", driver="GeoJSON")
    gpd.GeoDataFrame([{"hsg": "C"}], geometry=[boundary], crs=CRS).to_file(OUT / "hydrologic_soil_group.geojson", driver="GeoJSON")
    pd.DataFrame([
        {"event_id": "SAMPLE_001", "start_date": "2020-10-01", "end_date": "2020-10-01", "rainfall_mm": 25.0, "units": "mm"},
        {"event_id": "SAMPLE_002", "start_date": "2020-10-15", "end_date": "2020-10-15", "rainfall_mm": 60.0, "units": "mm"},
    ]).to_csv(OUT / "rainfall_events.csv", index=False)
    print(f"Wrote sample files to {OUT}")


if __name__ == "__main__":
    main()
