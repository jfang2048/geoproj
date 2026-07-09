"""Input file validators for raster, vector, and rainfall CSV uploads."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.errors import DependencyMissingError, UploadValidationError
from app.models.categories import CATEGORY_RULES, DataKind, InputCategory
from app.storage.paths import ensure_safe_archive

RAINFALL_COLUMNS = ("event_id", "start_date", "end_date", "rainfall_mm", "units")
RASTER_DTYPES = {
    "uint8",
    "uint16",
    "uint32",
    "int16",
    "int32",
    "float32",
    "float64",
}


@dataclass
class ValidationReport:
    valid: bool
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def require_valid(self) -> None:
        if not self.valid:
            raise UploadValidationError(
                "File validation failed.",
                details={"errors": self.errors, "warnings": self.warnings, "metadata": self.metadata},
            )


def validate_file(category: InputCategory, path: Path) -> ValidationReport:
    rule = CATEGORY_RULES[category]
    suffix = path.suffix.lower()
    if suffix not in rule.extensions:
        return ValidationReport(
            valid=False,
            kind="unknown",
            errors=[f"Extension '{suffix}' is not accepted for {rule.label}."],
        )
    if path.stat().st_size <= 0:
        return ValidationReport(valid=False, kind="unknown", errors=["Empty files are rejected."])
    if suffix == ".zip":
        ensure_safe_archive(path)
    kind = infer_kind(path)
    if kind not in rule.kinds:
        return ValidationReport(
            valid=False,
            kind=kind.value,
            errors=[f"{path.name} is a {kind.value} file, not valid for {rule.label}."],
        )
    if kind == DataKind.raster:
        return validate_raster(path, category)
    if kind == DataKind.vector:
        return validate_vector(path, category)
    if kind == DataKind.table:
        return validate_rainfall_csv(path)
    return ValidationReport(valid=False, kind="unknown", errors=["Unknown file type."])


def infer_kind(path: Path) -> DataKind:
    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        return DataKind.raster
    if suffix in {".gpkg", ".geojson", ".zip"}:
        return DataKind.vector
    if suffix == ".csv":
        return DataKind.table
    return DataKind.table


def validate_raster(path: Path, category: InputCategory) -> ValidationReport:
    try:
        import rasterio
    except Exception as exc:  # pragma: no cover - depends on runtime install
        raise DependencyMissingError("rasterio is required to validate raster uploads.") from exc

    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {"path": str(path), "warnings": warnings}
    try:
        with rasterio.open(path) as ds:
            bounds = ds.bounds
            transform = ds.transform
            res = ds.res
            crs = ds.crs
            dtype = ds.dtypes[0] if ds.dtypes else None
            nodata = ds.nodata
            metadata.update(
                {
                    "kind": "raster",
                    "driver": ds.driver,
                    "crs": crs.to_string() if crs else None,
                    "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                    "transform": list(transform)[:6],
                    "resolution": [float(abs(res[0])), float(abs(res[1]))],
                    "width": int(ds.width),
                    "height": int(ds.height),
                    "count": int(ds.count),
                    "dtype": dtype,
                    "nodata": nodata,
                    "categorical": CATEGORY_RULES[category].categorical,
                }
            )
            if crs is None:
                errors.append("CRS is missing.")
            if ds.width <= 0 or ds.height <= 0:
                errors.append("Raster width and height must be greater than zero.")
            if not transform or transform.is_identity:
                errors.append("Raster transform is missing or identity.")
            if any(not math.isfinite(v) for v in metadata["bounds"]):
                errors.append("Raster bounds are not finite.")
            if res[0] <= 0 or res[1] <= 0:
                errors.append("Raster resolution must be positive.")
            if max(abs(res[0]), abs(res[1])) > 10000:
                warnings.append("Raster resolution is coarse for local runoff screening.")
            if nodata is None:
                warnings.append("NoData value is not set; it will be recorded as missing.")
            if dtype not in RASTER_DTYPES:
                errors.append(f"Raster pixel type '{dtype}' is not accepted.")
            if CATEGORY_RULES[category].categorical:
                metadata["required_resampling"] = "nearest"
    except UploadValidationError:
        raise
    except Exception as exc:
        return ValidationReport(valid=False, kind="raster", errors=[f"Raster could not be read: {exc}"])

    return ValidationReport(valid=not errors, kind="raster", metadata=metadata, errors=errors, warnings=warnings)


def validate_vector(path: Path, category: InputCategory) -> ValidationReport:
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover - depends on runtime install
        raise DependencyMissingError("geopandas is required to validate vector uploads.") from exc

    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {"path": str(path), "warnings": warnings}
    try:
        read_path = vector_read_path(path)
        gdf = gpd.read_file(read_path)
    except Exception as exc:
        return ValidationReport(valid=False, kind="vector", errors=[f"Vector file could not be read: {exc}"])

    metadata.update(
        {
            "kind": "vector",
            "driver_path": vector_read_path(path),
            "crs": gdf.crs.to_string() if gdf.crs is not None else None,
            "feature_count": int(len(gdf)),
            "columns": [str(c) for c in gdf.columns],
        }
    )
    if gdf.crs is None:
        errors.append("CRS is missing.")
    if "geometry" not in gdf.columns:
        errors.append("Geometry column is missing.")
        return ValidationReport(valid=False, kind="vector", metadata=metadata, errors=errors, warnings=warnings)
    if gdf.empty:
        errors.append("Vector layer has no features.")
    empty_count = int(gdf.geometry.is_empty.fillna(True).sum()) if len(gdf) else 0
    if empty_count:
        errors.append(f"Vector layer contains {empty_count} empty geometries.")
    invalid_count = int((~gdf.geometry.is_valid).sum()) if len(gdf) else 0
    metadata["invalid_geometry_count"] = invalid_count
    if invalid_count:
        warnings.append(f"Vector layer contains {invalid_count} invalid geometries; preprocessing will attempt repair.")
    try:
        bounds = gdf.total_bounds
        metadata["bounds"] = [float(v) for v in bounds]
        if any(not math.isfinite(float(v)) for v in bounds):
            errors.append("Vector bounds are not finite.")
    except Exception as exc:
        errors.append(f"Vector bounds could not be calculated: {exc}")

    rule = CATEGORY_RULES[category]
    if rule.required_attributes:
        matched = first_matching_column(gdf.columns, rule.aliases)
        if matched is None:
            errors.append(
                f"Required attribute missing for {rule.label}. Expected one of: {', '.join(rule.aliases)}."
            )
        else:
            metadata["category_attribute"] = matched

    return ValidationReport(valid=not errors, kind="vector", metadata=metadata, errors=errors, warnings=warnings)


def validate_rainfall_csv(path: Path) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return ValidationReport(valid=False, kind="table", errors=[f"CSV could not be read: {exc}"])

    missing = [col for col in RAINFALL_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"Missing required rainfall columns: {', '.join(missing)}.")
    metadata: dict[str, Any] = {
        "kind": "table",
        "columns": [str(c) for c in df.columns],
        "row_count": int(len(df)),
        "required_columns": list(RAINFALL_COLUMNS),
        "warnings": warnings,
    }
    if errors:
        return ValidationReport(valid=False, kind="table", metadata=metadata, errors=errors, warnings=warnings)

    if df.empty:
        errors.append("Rainfall CSV has no rows.")
    if df["event_id"].isna().any():
        errors.append("Rainfall event_id contains missing values.")
    duplicate_ids = sorted(df.loc[df["event_id"].duplicated(), "event_id"].astype(str).unique().tolist())
    if duplicate_ids:
        errors.append(f"Duplicate rainfall event IDs: {', '.join(duplicate_ids)}.")
    for date_col in ("start_date", "end_date"):
        parsed = pd.to_datetime(df[date_col], errors="coerce")
        if parsed.isna().any():
            errors.append(f"Column {date_col} contains dates that cannot be parsed.")
    rainfall = pd.to_numeric(df["rainfall_mm"], errors="coerce")
    if rainfall.isna().any():
        errors.append("rainfall_mm contains missing or non-numeric values.")
    if (rainfall < 0).any():
        errors.append("rainfall_mm contains negative values.")
    units = df["units"].astype(str).str.lower().str.strip()
    invalid_units = sorted(set(units[~units.isin({"mm", "millimeter", "millimeters"})]))
    if invalid_units:
        errors.append(f"Rainfall units must be mm. Invalid values: {', '.join(invalid_units)}.")
    metadata["rainfall_total_mm"] = float(rainfall.sum()) if not rainfall.isna().any() else None
    return ValidationReport(valid=not errors, kind="table", metadata=metadata, errors=errors, warnings=warnings)


def read_valid_rainfall_csv(path: Path) -> pd.DataFrame:
    report = validate_rainfall_csv(path)
    report.require_valid()
    df = pd.read_csv(path)
    df = df[list(RAINFALL_COLUMNS)].copy()
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date.astype(str)
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.date.astype(str)
    df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="raise").astype(float)
    df["units"] = "mm"
    return df


def vector_read_path(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        return f"zip://{path}"
    return str(path)


def first_matching_column(columns: Any, aliases: tuple[str, ...]) -> str | None:
    lower_map = {str(col).lower(): str(col) for col in columns}
    for alias in aliases:
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None
