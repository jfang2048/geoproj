"""File upload validation with deep content inspection for GIS data."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import pandas as pd

CATEGORY_RULES: dict[str, dict] = {
    "DEM / DTM": {
        "extensions": {".zip", ".tif", ".img"},
        "target": "data/raw/zip",
    },
    "Fire perimeter": {
        "extensions": {".zip", ".gpkg", ".shp"},
        "target": "data/raw/zip",
    },
    "Sentinel-2 L2A SAFE": {
        "extensions": {".zip"},
        "target": "data/raw/zip",
        "name_requires": ".SAFE.zip",
    },
    "Land cover": {
        "extensions": {".zip", ".gpkg"},
        "target": "data/raw/zip",
    },
    "Soil / HSG / SoilGrids": {
        "extensions": {".zip", ".tif", ".csv"},
        "target": "data/raw/zip",
    },
    "Rainfall / weather": {
        "extensions": {".zip", ".csv"},
        "target": "data/raw/zip",
    },
    "Lake water quality": {
        "extensions": {".zip", ".csv", ".xlsx"},
        "target": "data/raw/zip/lake_varese_water_quality",
    },
    "WEPPcloud output": {
        "extensions": {".csv", ".zip", ".pdf", ".gpkg"},
        "target": "outputs/models/weppcloud/download",
    },
}

MAX_FILE_SIZE_MB = 500


@dataclass
class ValidationResult:
    valid: bool
    message: str
    checksum: str = ""
    warnings: list[str] = field(default_factory=list)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sanitize_filename(name: str) -> str:
    safe = Path(name).name
    if safe != name:
        raise ValueError("Path traversal rejected")
    # Replace dangerous characters
    for ch in ("\\", ":", "*", "?", '"', "<", ">", "|", "&", ";", "$", "`"):
        safe = safe.replace(ch, "_")
    return safe.strip() or "unnamed_file"


def validate_upload(category: str, filename: str, file_size: int, data: bytes | None = None) -> ValidationResult:
    if category not in CATEGORY_RULES:
        return ValidationResult(False, f"Unknown category: {category}")

    rules = CATEGORY_RULES[category]
    suffix = Path(filename).suffix.lower()

    try:
        _sanitize_filename(filename)
    except ValueError as e:
        return ValidationResult(False, str(e))

    if file_size <= 0:
        return ValidationResult(False, "Empty file rejected")

    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return ValidationResult(False, f"File exceeds {MAX_FILE_SIZE_MB} MB limit")

    if suffix not in rules["extensions"]:
        return ValidationResult(
            False,
            f"Extension '{suffix}' not accepted for {category}. Accepted: {', '.join(sorted(rules['extensions']))}",
        )

    if "name_requires" in rules and rules["name_requires"] not in filename:
        return ValidationResult(
            False,
            f"Filename must contain '{rules['name_requires']}' for {category}.",
        )

    cs = _sha256(data) if data else ""

    return ValidationResult(True, "OK", checksum=cs)


def validate_raster_content(data: bytes) -> list[str]:
    """Deep-check a raster file. Returns list of warning strings."""
    warnings = []
    try:
        import rasterio
        with rasterio.MemoryFile(data) as mf:
            with mf.open() as ds:
                if ds.crs is None:
                    warnings.append("Raster has no CRS")
                if ds.width <= 0 or ds.height <= 0:
                    warnings.append("Raster has zero dimensions")
                if ds.nodata is None:
                    warnings.append("Raster has no NoData value set")
    except Exception:
        warnings.append("Raster not readable by rasterio")
    return warnings


def validate_vector_content(data: bytes) -> list[str]:
    """Deep-check a vector file. Returns list of warning strings."""
    warnings = []
    try:
        import geopandas as gpd
        gdf = gpd.read_file(BytesIO(data))
        if gdf.crs is None:
            warnings.append("Vector has no CRS")
        if gdf.empty:
            warnings.append("Vector is empty (no features)")
        if gdf.geometry.is_empty.any():
            warnings.append("Vector contains empty geometries")
        if not gdf.geometry.is_valid.all():
            warnings.append("Vector contains invalid geometries")
    except Exception:
        warnings.append("Vector not readable by geopandas")
    return warnings


def validate_rainfall_csv(data: bytes) -> list[str]:
    """Check a rainfall CSV for required columns and valid values."""
    warnings = []
    try:
        df = pd.read_csv(BytesIO(data))
        cols_lower = {c.lower() for c in df.columns}

        has_date = any(k in cols_lower for k in ("date", "datetime", "timestamp", "start_date", "event_start"))
        has_precip = any(k in cols_lower for k in ("rain", "precip", "rainfall", "precipitation", "total_precip_mm"))

        if not has_date:
            warnings.append("No date or datetime column found")
        if not has_precip:
            warnings.append("No rainfall or precipitation column found")

        # Check for negative rainfall
        for c in df.columns:
            if c.lower() in ("rain", "precip", "rainfall", "precipitation", "total_precip_mm"):
                vals = pd.to_numeric(df[c], errors="coerce")
                if (vals < 0).any():
                    warnings.append(f"Column '{c}' contains negative values")
                if vals.isna().any():
                    warnings.append(f"Column '{c}' contains missing or non-numeric values")
                break

        # Check for duplicate event IDs
        for id_col in ("event_id", "id", "station_id"):
            if id_col in df.columns:
                if df[id_col].duplicated().any():
                    warnings.append(f"Column '{id_col}' has duplicate values")
                break
    except Exception:
        warnings.append("CSV not readable as rainfall data")
    return warnings


def accepted_extensions_for(category: str) -> list[str]:
    rules = CATEGORY_RULES.get(category, {})
    return sorted(rules.get("extensions", set()))
