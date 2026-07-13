"""Burn-severity input normalization."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import shape

from postfire_runoff.backend.gis.normalize import SpatialInputError, normalize_polygons, read_vector, to_working_crs
from postfire_runoff.backend.gis.crs import METRIC_CRS

BURN_CLASS_LABELS = {
    0: "unburned",
    1: "low",
    2: "moderate",
    3: "high",
    255: "NoData",
}

BURN_CLASS_ALIASES = {
    "0": 0,
    "unburned": 0,
    "unchanged": 0,
    "none": 0,
    "1": 1,
    "low": 1,
    "low_severity": 1,
    "2": 2,
    "moderate": 2,
    "moderate_severity": 2,
    "medium": 2,
    "3": 3,
    "high": 3,
    "high_severity": 3,
}


def normalize_burn_class(value: object) -> int:
    if value is None:
        raise ValueError("Burn class is missing")
    if isinstance(value, (int, np.integer)):
        code = int(value)
    else:
        text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if text not in BURN_CLASS_ALIASES:
            raise ValueError(f"Unsupported burn severity class: {value!r}")
        code = BURN_CLASS_ALIASES[text]
    if code not in {0, 1, 2, 3}:
        raise ValueError(f"Burn severity class must be 0, 1, 2, or 3; got {value!r}")
    return code


def load_burn_polygons(path: Path, column: str = "burn_class", working_crs: str = METRIC_CRS) -> gpd.GeoDataFrame:
    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        return _burn_polygons_from_raster(path, working_crs)
    gdf = normalize_polygons(to_working_crs(read_vector(path, "burn severity"), working_crs), "burn severity")
    if column not in gdf.columns:
        candidates = [c for c in ("burn_class", "severity", "class", "dnbr_class") if c in gdf.columns]
        if not candidates:
            raise SpatialInputError(f"burn severity: missing burn class column '{column}'")
        column = candidates[0]
    out = gdf[[column, "geometry"]].copy()
    out["burn_class"] = out[column].apply(normalize_burn_class).astype("int16")
    return out[["burn_class", "geometry"]]


def _burn_polygons_from_raster(path: Path, working_crs: str) -> gpd.GeoDataFrame:
    if not path.exists():
        raise SpatialInputError(f"burn severity raster not found: {path}")
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise SpatialInputError("burn severity raster: missing CRS")
            arr = ds.read(1)
            mask = arr != (ds.nodata if ds.nodata is not None else 255)
            records = []
            for geom, value in raster_shapes(arr.astype("int16"), mask=mask, transform=ds.transform):
                code = normalize_burn_class(int(value))
                records.append({"burn_class": code, "geometry": shape(geom)})
            gdf = gpd.GeoDataFrame(records, crs=ds.crs)
    except SpatialInputError:
        raise
    except Exception as exc:  # pragma: no cover
        raise SpatialInputError(f"burn severity raster unreadable: {exc}") from exc
    if gdf.empty:
        raise SpatialInputError("burn severity raster contains no valid burn pixels")
    return to_working_crs(gdf, working_crs)


def write_burn_raster(
    burn_gdf: gpd.GeoDataFrame,
    catchment_gdf: gpd.GeoDataFrame,
    output_path: Path,
    resolution_m: float = 30.0,
    nodata: int = 255,
) -> Path:
    """Rasterize burn-class polygons over the catchment extent."""
    if resolution_m <= 0:
        raise ValueError("Raster resolution must be positive")
    bounds = catchment_gdf.total_bounds
    minx, miny, maxx, maxy = map(float, bounds)
    width = max(1, int(np.ceil((maxx - minx) / resolution_m)))
    height = max(1, int(np.ceil((maxy - miny) / resolution_m)))
    transform = from_origin(minx, maxy, resolution_m, resolution_m)
    shapes = [(geom, int(code)) for geom, code in zip(burn_gdf.geometry, burn_gdf["burn_class"])]
    arr = rasterize(shapes, out_shape=(height, width), fill=nodata, transform=transform, dtype="uint8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=catchment_gdf.crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)
    return output_path
