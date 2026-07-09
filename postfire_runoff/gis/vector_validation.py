"""Vector metadata validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VectorInfo:
    path: str
    readable: bool = False
    crs: str = ""
    epsg: int | None = None
    feature_count: int = 0
    geometry_types: list[str] = field(default_factory=list)
    bounds: tuple = ()
    has_empty_geometries: bool = False
    has_invalid_geometries: bool = False
    columns: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def inspect_vector(path: Path) -> VectorInfo:
    info = VectorInfo(path=str(path))
    try:
        import geopandas as gpd
        gdf = gpd.read_file(path)
        info.readable = True
        info.crs = str(gdf.crs) if gdf.crs else ""
        info.epsg = gdf.crs.to_epsg() if gdf.crs else None
        info.feature_count = len(gdf)
        info.geometry_types = list(gdf.geometry.geom_type.unique())
        info.bounds = tuple(gdf.total_bounds)
        info.columns = list(gdf.columns)
        if gdf.crs is None:
            info.errors.append("Vector has no CRS")
        if info.feature_count == 0:
            info.errors.append("Vector has no features")
        if gdf.geometry.is_empty.any():
            info.has_empty_geometries = True
            info.warnings.append("Vector contains empty geometries")
        if not gdf.geometry.is_valid.all():
            info.has_invalid_geometries = True
            info.warnings.append("Vector contains invalid geometries")
    except Exception as e:
        info.errors.append(f"Vector not readable: {e}")
    return info
