"""GIS input normalization helpers."""
from __future__ import annotations

from pathlib import Path
import geopandas as gpd
from postfire_runoff.backend.gis.crs import METRIC_CRS


class SpatialInputError(ValueError):
    """Raised for missing CRS, unreadable, invalid, or non-overlapping GIS inputs."""


def read_vector(path: Path, label: str) -> gpd.GeoDataFrame:
    if not path.exists():
        raise SpatialInputError(f"{label}: file not found: {path}")
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:  # pragma: no cover - message depends on GDAL
        raise SpatialInputError(f"{label}: unreadable vector file: {exc}") from exc
    if gdf.empty:
        raise SpatialInputError(f"{label}: vector contains no features")
    if gdf.crs is None:
        raise SpatialInputError(f"{label}: missing CRS")
    if gdf.geometry.is_empty.any():
        raise SpatialInputError(f"{label}: contains empty geometries")
    invalid = ~gdf.geometry.is_valid
    if bool(invalid.any()):
        raise SpatialInputError(f"{label}: contains invalid geometries")
    return gdf


def to_working_crs(gdf: gpd.GeoDataFrame, working_crs: str = METRIC_CRS) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise SpatialInputError("Cannot reproject a layer without CRS")
    if gdf.crs.to_string() == working_crs or gdf.crs.to_epsg() == int(working_crs.split(':')[-1]):
        return gdf.copy()
    return gdf.to_crs(working_crs)


def require_overlap(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame, a_label: str, b_label: str) -> None:
    if a.crs != b.crs:
        b = b.to_crs(a.crs)
    if not bool(a.geometry.union_all().intersects(b.geometry.union_all())):
        raise SpatialInputError(f"{a_label} does not spatially overlap {b_label}")


def save_vector(gdf: gpd.GeoDataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GPKG")
    return path


def normalize_polygons(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out = out[out.geometry.notna() & ~out.geometry.is_empty].copy()
    if out.empty:
        raise SpatialInputError(f"{label}: no non-empty geometries")
    poly_mask = out.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    if not bool(poly_mask.all()):
        raise SpatialInputError(f"{label}: expected Polygon/MultiPolygon geometries")
    return out
