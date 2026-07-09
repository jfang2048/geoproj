"""Spatial normalization helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shapely.validation import make_valid

from app.core.config import WORKING_CRS
from app.core.errors import DependencyMissingError, ProcessingError
from app.gis.validation import first_matching_column, vector_read_path
from app.models.categories import CATEGORY_RULES, DataKind, InputCategory


def resampling_for_category(category: InputCategory) -> str:
    """Documented resampling rule used during raster normalization."""
    return "nearest" if CATEGORY_RULES[category].categorical else "bilinear"


def normalize_vector(input_path: Path, output_path: Path, category: InputCategory) -> tuple[Path, list[str]]:
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required to normalize vectors.") from exc

    warnings: list[str] = []
    try:
        gdf = gpd.read_file(vector_read_path(input_path))
    except Exception as exc:
        raise ProcessingError(f"Could not read vector input {input_path.name}: {exc}") from exc
    if gdf.crs is None:
        raise ProcessingError(f"Vector input {input_path.name} has no CRS.")
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(make_valid)
        warnings.append(f"Repaired {int(invalid.sum())} invalid geometries in {input_path.name}.")
    gdf = gdf.to_crs(WORKING_CRS)
    rule = CATEGORY_RULES[category]
    if rule.aliases and rule.required_attributes:
        match = first_matching_column(gdf.columns, rule.aliases)
        if match is None:
            raise ProcessingError(f"Required attribute missing for {rule.label}.")
        canonical = rule.required_attributes[0]
        if match != canonical:
            gdf[canonical] = gdf[match]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GPKG")
    return output_path, warnings


def normalize_raster(
    input_path: Path,
    output_path: Path,
    category: InputCategory,
    *,
    reference_path: Path | None = None,
) -> tuple[Path, list[str]]:
    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.warp import calculate_default_transform, reproject
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("rasterio is required to normalize rasters.") from exc

    warnings: list[str] = []
    method_name = resampling_for_category(category)
    method = Resampling.nearest if method_name == "nearest" else Resampling.bilinear
    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise ProcessingError(f"Raster input {input_path.name} has no CRS.")
        profile = src.profile.copy()
        if reference_path is not None:
            with rasterio.open(reference_path) as ref:
                dst_crs = ref.crs
                dst_transform = ref.transform
                width = ref.width
                height = ref.height
                if CATEGORY_RULES[category].categorical and method_name != "nearest":
                    raise ProcessingError("Categorical rasters must use nearest-neighbor resampling.")
        else:
            dst_crs = WORKING_CRS
            dst_transform, width, height = calculate_default_transform(
                src.crs,
                dst_crs,
                src.width,
                src.height,
                *src.bounds,
            )
        profile.update(
            crs=dst_crs,
            transform=dst_transform,
            width=width,
            height=height,
            driver="GTiff",
            compress="deflate",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=method,
                )
        if str(src.crs) != str(dst_crs):
            warnings.append(f"Reprojected {input_path.name} to {dst_crs} using {method_name} resampling.")
        return output_path, warnings


def assert_raster_alignment(paths: list[Path]) -> None:
    if len(paths) < 2:
        return
    try:
        import rasterio
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("rasterio is required to check raster alignment.") from exc
    reference: dict[str, Any] | None = None
    for path in paths:
        with rasterio.open(path) as ds:
            current = {"crs": ds.crs, "transform": ds.transform, "shape": (ds.height, ds.width)}
        if reference is None:
            reference = current
            continue
        if current != reference:
            raise ProcessingError(f"Raster alignment failed for {path.name}.")
