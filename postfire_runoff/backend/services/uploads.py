"""Upload validation, storage, and project configuration assignment."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import yaml

from postfire_runoff.backend.io.checksums import sha256_hex
from postfire_runoff.backend.io.paths import project_root
from postfire_runoff.backend.io.safe_files import sanitize_filename
from postfire_runoff.backend.services.weppcloud import validate_weppcloud_columns

CATEGORY_RULES: dict[str, dict[str, object]] = {
    "Catchment boundary": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw/catchment_boundary", "config_key": "catchment_boundary"},
    "Fire perimeter": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw/fire_perimeter", "config_key": "fire_perimeter"},
    "Burn severity": {"extensions": {".gpkg", ".geojson", ".json", ".tif", ".tiff"}, "target": "data/raw/burn_severity", "config_key": "burn_severity"},
    "Land cover": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw/land_cover", "config_key": "land_cover"},
    "Soil / HSG": {"extensions": {".gpkg", ".geojson", ".json"}, "target": "data/raw/hsg", "config_key": "hsg"},
    "Rainfall / weather": {"extensions": {".csv"}, "target": "data/raw/rainfall_events", "config_key": "rainfall_events"},
    "WEPPcloud output": {"extensions": {".csv"}, "target": "data/raw/weppcloud", "config_key": "weppcloud_export"},
}

MAX_SIZE_MB = 500
RAINFALL_COLUMNS = {"event_id", "start_date", "end_date"}
RAINFALL_DEPTH_ALIASES = {"rainfall_mm", "total_precip_mm", "precip_mm", "precipitation_mm"}


@dataclass
class UploadResult:
    valid: bool
    message: str
    checksum: str = ""
    saved_path: str = ""
    assigned_config_key: str = ""
    assigned_config_path: str = ""
    warnings: list[str] = field(default_factory=list)


def category_config_key(category: str) -> str:
    if category not in CATEGORY_RULES:
        raise ValueError(f"Unknown category: {category}")
    return str(CATEGORY_RULES[category]["config_key"])


def accepted_extensions_for(category: str) -> list[str]:
    rules = CATEGORY_RULES.get(category, {})
    return sorted(rules.get("extensions", set()))


def validate_upload(category: str, filename: str, file_size: int, data: bytes | None = None) -> UploadResult:
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
        allowed = ", ".join(sorted(rules["extensions"]))
        return UploadResult(False, f"Extension '{suffix}' not accepted. Allowed: {allowed}")

    checksum = sha256_hex(data) if data is not None else ""
    warnings: list[str] = []
    if data is not None:
        warnings.extend(_content_warnings(category, safe_name, data))
        if any(w.startswith("ERROR:") for w in warnings):
            return UploadResult(False, "; ".join(warnings), checksum=checksum, warnings=warnings)
    return UploadResult(True, "OK", checksum=checksum, warnings=warnings)


def handle_upload(
    category: str,
    filename: str,
    file_bytes: bytes,
    root: str | Path | None = None,
    config_path: str | Path = "config/project.yaml",
    assign_to_config: bool = True,
) -> UploadResult:
    validation = validate_upload(category, filename, len(file_bytes), file_bytes)
    if not validation.valid:
        return validation

    root_path = project_root(root)
    rules = CATEGORY_RULES[category]
    target = root_path / str(rules["target"])
    target.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    dest = target / safe_name
    if dest.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = target / f"{dest.stem}_{ts}{dest.suffix}"
    dest.write_bytes(file_bytes)

    validation.saved_path = str(dest)
    validation.message = "Uploaded"
    if assign_to_config:
        config_file = root_path / config_path if not Path(config_path).is_absolute() else Path(config_path)
        key = str(rules["config_key"])
        rel = dest.resolve().relative_to(root_path.resolve()).as_posix()
        assign_input_path(config_file, key, rel)
        validation.assigned_config_key = f"inputs.{key}"
        validation.assigned_config_path = rel
    return validation


def read_input_assignments(config_file: str | Path, root: str | Path | None = None) -> dict[str, str]:
    root_path = project_root(root)
    path = root_path / config_file if not Path(config_file).is_absolute() else Path(config_file)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    inputs = data.get("inputs", {}) or {}
    return {str(k): "" if v is None else str(v) for k, v in inputs.items()}


def assign_input_path(config_file: str | Path, key: str, relative_path: str) -> None:
    path = Path(config_file)
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    inputs = data.setdefault("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("Configuration 'inputs' section must be a mapping")
    inputs[key] = relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _content_warnings(category: str, filename: str, data: bytes) -> list[str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return _csv_warnings(category, data)
    if suffix in {".gpkg", ".geojson", ".json"}:
        return _vector_warnings(data, suffix)
    if suffix in {".tif", ".tiff"}:
        return _raster_warnings(data)
    return []


def _csv_warnings(category: str, data: bytes) -> list[str]:
    try:
        df = pd.read_csv(BytesIO(data))
    except Exception as exc:
        return [f"ERROR: CSV not readable: {exc}"]
    lower = {c.lower() for c in df.columns}
    warnings: list[str] = []
    if category == "Rainfall / weather":
        missing = sorted(RAINFALL_COLUMNS - lower)
        if missing:
            warnings.append(f"ERROR: rainfall CSV missing required columns: {', '.join(missing)}")
        if not (RAINFALL_DEPTH_ALIASES & lower):
            warnings.append("ERROR: rainfall CSV needs rainfall_mm or a supported precipitation alias")
    elif category == "WEPPcloud output":
        missing = validate_weppcloud_columns(list(df.columns))
        if missing:
            warnings.append(f"ERROR: WEPPcloud CSV missing required columns: {', '.join(missing)}")
    return warnings


def _vector_warnings(data: bytes, suffix: str) -> list[str]:
    try:
        import geopandas as gpd
        with NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            gdf = gpd.read_file(tmp.name)
    except Exception as exc:
        return [f"ERROR: vector file not readable: {exc}"]
    warnings: list[str] = []
    if gdf.crs is None:
        warnings.append("ERROR: vector file has no CRS")
    if gdf.empty:
        warnings.append("ERROR: vector file has no features")
    if gdf.geometry.is_empty.any():
        warnings.append("ERROR: vector file contains empty geometries")
    if not gdf.geometry.is_valid.all():
        warnings.append("ERROR: vector file contains invalid geometries")
    return warnings


def _raster_warnings(data: bytes) -> list[str]:
    try:
        import rasterio
        with rasterio.MemoryFile(data) as mf:
            with mf.open() as ds:
                warnings: list[str] = []
                if ds.crs is None:
                    warnings.append("ERROR: raster file has no CRS")
                if ds.width <= 0 or ds.height <= 0:
                    warnings.append("ERROR: raster file has zero dimensions")
                return warnings
    except Exception as exc:
        return [f"ERROR: raster file not readable: {exc}"]
