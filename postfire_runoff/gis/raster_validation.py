"""Raster metadata validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RasterInfo:
    path: str
    readable: bool = False
    crs: str = ""
    epsg: int | None = None
    width: int = 0
    height: int = 0
    bands: int = 0
    dtype: str = ""
    nodata: Any = None
    bounds: tuple = ()
    resolution: tuple = ()
    transform: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def inspect_raster(path: Path) -> RasterInfo:
    info = RasterInfo(path=str(path))
    try:
        import rasterio
        with rasterio.open(path) as ds:
            info.readable = True
            info.crs = str(ds.crs) if ds.crs else ""
            info.epsg = ds.crs.to_epsg() if ds.crs else None
            info.width = ds.width
            info.height = ds.height
            info.bands = ds.count
            info.dtype = str(ds.dtypes[0])
            info.nodata = ds.nodata
            info.bounds = tuple(ds.bounds)
            info.resolution = (float(ds.transform.a), float(abs(ds.transform.e)))
            info.transform = list(ds.transform)[:6]
            if info.width <= 0 or info.height <= 0:
                info.errors.append("Raster has zero dimensions")
            if ds.crs is None:
                info.errors.append("Raster has no CRS")
            if ds.nodata is None:
                info.warnings.append("Raster has no NoData value set")
    except Exception as e:
        info.errors.append(f"Raster not readable: {e}")
    return info
