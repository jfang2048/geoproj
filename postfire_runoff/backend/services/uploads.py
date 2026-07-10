"""Upload validation and storage without Streamlit dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd

from postfire_runoff.backend.io.checksums import sha256_hex
from postfire_runoff.backend.io.paths import project_root
from postfire_runoff.backend.io.safe_files import sanitize_filename

CATEGORY_RULES: dict[str, dict] = {
    "Catchment boundary": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw"},
    "Fire perimeter": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw"},
    "Burn severity": {"extensions": {".gpkg", ".geojson", ".json", ".tif"}, "target": "data/raw"},
    "Land cover": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw"},
    "Soil / HSG": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw"},
    "Rainfall / weather": {"extensions": {".csv"}, "target": "data/raw"},
    "Lake water quality": {"extensions": {".csv", ".tif"}, "target": "data/raw/lake_varese_water_quality"},
    "WEPPcloud output": {"extensions": {".csv"}, "target": "outputs/models/weppcloud/download"},
}

# Legacy UI labels kept as aliases so old screenshots/manual navigation stay recognizable.
CATEGORY_ALIASES = {
    "DEM / DTM": "Catchment boundary",
    "Sentinel-2 L2A SAFE": "Lake water quality",
    "Soil / HSG / SoilGrids": "Soil / HSG",
}

MAX_SIZE_MB = 500


@dataclass
class UploadResult:
    valid: bool
    message: str
    checksum: str = ""
    saved_path: str = ""
    warnings: list[str] = field(default_factory=list)


def canonical_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def accepted_extensions_for(category: str) -> list[str]:
    rules = CATEGORY_RULES.get(canonical_category(category), {})
    return sorted(rules.get("extensions", set()))


def validate_upload(category: str, filename: str, file_size: int, data: bytes | None = None) -> UploadResult:
    category = canonical_category(category)
    if category not in CATEGORY_RULES:
        return UploadResult(False, f"Unknown category: {category}")

    rules = CATEGORY_RULES[category]
    try:
        safe_name = sanitize_filename(filename)
    except ValueError as exc:
        return UploadResult(False, str(exc))

    size = int(file_size)
    if size <= 0:
        return UploadResult(False, "Empty file rejected")
    if size > MAX_SIZE_MB * 1024 * 1024:
        return UploadResult(False, f"File exceeds {MAX_SIZE_MB} MB limit")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in rules["extensions"]:
        return UploadResult(False, f"Extension '{suffix}' not accepted. Allowed: {', '.join(sorted(rules['extensions']))}")

    checksum = sha256_hex(data) if data is not None else ""
    warnings: list[str] = []
    if data is not None:
        warnings.extend(_content_warnings(category, safe_name, data))
        if any(w.startswith("ERROR:") for w in warnings):
            return UploadResult(False, "; ".join(warnings), checksum=checksum, warnings=warnings)
    return UploadResult(True, "OK", checksum=checksum, warnings=warnings)


def handle_upload(category: str, filename: str, file_bytes: bytes, root: str | Path | None = None) -> UploadResult:
    validation = validate_upload(category, filename, len(file_bytes), file_bytes)
    if not validation.valid:
        return validation
    category = canonical_category(category)
    rules = CATEGORY_RULES[category]
    target = project_root(root) / rules["target"]
    target.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    dest = target / safe_name
    if dest.exists():
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = target / f"{dest.stem}_{ts}{dest.suffix}"
    dest.write_bytes(file_bytes)
    validation.saved_path = str(dest)
    validation.message = "Uploaded"
    return validation


def _content_warnings(category: str, filename: str, data: bytes) -> list[str]:
    suffix = Path(filename).suffix.lower()
    warnings: list[str] = []
    if suffix == ".csv":
        try:
            df = pd.read_csv(BytesIO(data))
        except Exception as exc:
            return [f"ERROR: CSV not readable: {exc}"]
        if category == "Rainfall / weather":
            lower = {c.lower(): c for c in df.columns}
            if not ({"rainfall_mm", "total_precip_mm", "precip_mm", "precipitation_mm"} & set(lower)):
                warnings.append("ERROR: rainfall CSV needs rainfall_mm or a supported precipitation alias")
            if "event_id" not in lower:
                warnings.append("ERROR: rainfall CSV needs event_id")
        if category == "WEPPcloud output":
            required = {"scenario", "period", "source_filename"}
            lower_cols = {c.lower() for c in df.columns}
            missing = sorted(required - lower_cols)
            if missing:
                warnings.append(f"ERROR: WEPPcloud CSV missing required columns: {', '.join(missing)}")
    elif suffix in {".gpkg", ".geojson", ".json"}:
        try:
            import geopandas as gpd
            gdf = gpd.read_file(BytesIO(data))
        except Exception as exc:
            return [f"ERROR: vector file not readable: {exc}"]
        if gdf.crs is None:
            warnings.append("ERROR: vector file has no CRS")
        if gdf.empty:
            warnings.append("ERROR: vector file has no features")
        if gdf.geometry.is_empty.any():
            warnings.append("ERROR: vector file contains empty geometries")
    elif suffix in {".tif", ".tiff"}:
        try:
            import rasterio
            with rasterio.MemoryFile(data) as mf:
                with mf.open() as ds:
                    if ds.crs is None:
                        warnings.append("ERROR: raster file has no CRS")
                    if ds.width <= 0 or ds.height <= 0:
                        warnings.append("ERROR: raster file has zero dimensions")
        except Exception as exc:
            return [f"ERROR: raster file not readable: {exc}"]
    return warnings
