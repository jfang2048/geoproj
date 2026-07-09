"""Display-layer writers for browser map previews."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping

from app.core.config import DISPLAY_CRS
from app.core.errors import DependencyMissingError, ProcessingError
from app.gis.validation import vector_read_path


def write_vector_display_geojson(input_path: Path, output_path: Path, *, properties: dict[str, Any] | None = None) -> Path:
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required to write map previews.") from exc
    try:
        gdf = gpd.read_file(vector_read_path(input_path))
        if gdf.crs is None:
            raise ProcessingError("Cannot write display layer for vector without CRS.")
        if properties:
            for key, value in properties.items():
                gdf[key] = value
        gdf = gdf.to_crs(DISPLAY_CRS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(output_path, driver="GeoJSON")
        return output_path
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Could not write vector display layer: {exc}") from exc


def write_bounds_geojson(bounds: list[float], crs: str, output_path: Path, *, properties: dict[str, Any]) -> Path:
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required to write map previews.") from exc
    geom = box(bounds[0], bounds[1], bounds[2], bounds[3])
    gdf = gpd.GeoDataFrame([properties], geometry=[geom], crs=crs).to_crs(DISPLAY_CRS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")
    return output_path


def write_geojson_featurecollection(features: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"type": "FeatureCollection", "features": features}
    output_path.write_text(json.dumps(payload), encoding="utf-8")
    return output_path


def feature_from_geometry(geometry: Any, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": mapping(geometry), "properties": properties}
