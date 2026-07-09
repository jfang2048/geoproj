"""CRS policy enforcement."""
from __future__ import annotations

from typing import Any

METRIC_CRS = "EPSG:32632"
WEB_CRS = "EPSG:4326"

FORBIDDEN_DEGREE_OPERATIONS = ["area", "distance", "slope", "buffer", "hydrologic_routing"]


def require_crs(gdf: Any, expected_epsg: int, label: str) -> None:
    if gdf.crs is None:
        raise ValueError(f"{label}: missing CRS")
    epsg = gdf.crs.to_epsg()
    if epsg is None:
        raise ValueError(f"{label}: cannot extract EPSG code from {gdf.crs}")
    if epsg != expected_epsg:
        raise ValueError(f"{label}: expected EPSG:{expected_epsg}, found EPSG:{epsg}")


def assert_not_degree_crs(crs: Any, operation: str) -> None:
    if crs is None:
        return
    try:
        if crs.is_geographic:
            raise ValueError(
                f"Cannot compute {operation} in geographic CRS ({crs}). Reproject to {METRIC_CRS}."
            )
    except AttributeError:
        pass


def to_metric(gdf: Any) -> Any:
    epsg = gdf.crs.to_epsg() if gdf.crs else None
    if epsg == 32632:
        return gdf
    return gdf.to_crs(METRIC_CRS)


def to_web(gdf: Any) -> Any:
    epsg = gdf.crs.to_epsg() if gdf.crs else None
    if epsg == 4326:
        return gdf
    return gdf.to_crs(WEB_CRS)
