"""Generate a small explicitly synthetic dataset for pipeline verification.

The generated files are not Monte Martica measurements. They are simple,
overlapping geometries designed to exercise the real input-to-output workflow.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

OUT = Path(__file__).resolve().parent / "generated"
CRS = "EPSG:32632"


def _write(gdf: gpd.GeoDataFrame, name: str) -> None:
    path = OUT / name
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GeoJSON")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1 km² synthetic catchment near the Monte Martica UTM zone. Coordinates are
    # arbitrary verification geometry in EPSG:32632.
    x0, y0 = 485000.0, 5080000.0
    catchment_geom = box(x0, y0, x0 + 1000.0, y0 + 1000.0)
    _write(gpd.GeoDataFrame([{"name": "synthetic_catchment"}], geometry=[catchment_geom], crs=CRS), "catchment.geojson")

    fire_geom = box(x0 + 250.0, y0 + 250.0, x0 + 900.0, y0 + 850.0)
    _write(gpd.GeoDataFrame([{"name": "synthetic_context_fire"}], geometry=[fire_geom], crs=CRS), "fire_perimeter.geojson")

    burn_records = [
        {"burn_class": 0, "geometry": box(x0, y0, x0 + 1000.0, y0 + 250.0)},
        {"burn_class": 0, "geometry": box(x0, y0 + 850.0, x0 + 1000.0, y0 + 1000.0)},
        {"burn_class": 1, "geometry": box(x0, y0 + 250.0, x0 + 250.0, y0 + 850.0)},
        {"burn_class": 2, "geometry": box(x0 + 250.0, y0 + 250.0, x0 + 650.0, y0 + 850.0)},
        {"burn_class": 3, "geometry": box(x0 + 650.0, y0 + 250.0, x0 + 1000.0, y0 + 850.0)},
    ]
    _write(gpd.GeoDataFrame(burn_records, crs=CRS), "burn_severity.geojson")

    land_records = [
        {"landcover_class": "forest", "geometry": box(x0, y0, x0 + 500.0, y0 + 1000.0)},
        {"landcover_class": "grassland", "geometry": box(x0 + 500.0, y0, x0 + 1000.0, y0 + 1000.0)},
    ]
    _write(gpd.GeoDataFrame(land_records, crs=CRS), "land_cover.geojson")

    hsg_records = [
        {"hsg": "B", "geometry": box(x0, y0, x0 + 1000.0, y0 + 500.0)},
        {"hsg": "C", "geometry": box(x0, y0 + 500.0, x0 + 1000.0, y0 + 1000.0)},
    ]
    _write(gpd.GeoDataFrame(hsg_records, crs=CRS), "hydrologic_soil_group.geojson")

    pd.DataFrame([
        {"event_id": "SYNTH_001", "start_date": "2020-10-01", "end_date": "2020-10-01", "rainfall_mm": 6.0},
        {"event_id": "SYNTH_002", "start_date": "2020-10-15", "end_date": "2020-10-15", "rainfall_mm": 55.0},
    ]).to_csv(OUT / "rainfall_events.csv", index=False)

    (OUT / "README.txt").write_text(
        "Synthetic verification dataset only. Not Monte Martica observations.\n"
        "All vector layers use EPSG:32632 and are simple overlapping polygons.\n"
    )
    print(f"Wrote synthetic sample files to {OUT}")


if __name__ == "__main__":
    main()
