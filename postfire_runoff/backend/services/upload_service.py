"""Upload validation and storage — no Streamlit dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from postfire_runoff.backend.io.checksums import sha256_hex
from postfire_runoff.backend.io.safe_files import sanitize_filename
from postfire_runoff.backend.io.paths import project_root

CATEGORIES = {
    "DEM / DTM": {"extensions": {".zip", ".tif", ".img"}, "target": "data/raw/zip"},
    "Fire perimeter": {"extensions": {".zip", ".gpkg", ".shp"}, "target": "data/raw/zip"},
    "Sentinel-2 L2A SAFE": {"extensions": {".zip"}, "target": "data/raw/zip", "name_requires": ".SAFE.zip"},
    "Land cover": {"extensions": {".zip", ".gpkg"}, "target": "data/raw/zip"},
    "Soil / HSG / SoilGrids": {"extensions": {".zip", ".tif", ".csv"}, "target": "data/raw/zip"},
    "Rainfall / weather": {"extensions": {".zip", ".csv"}, "target": "data/raw/zip"},
    "Lake water quality": {"extensions": {".zip", ".csv", ".xlsx"}, "target": "data/raw/zip/lake_varese_water_quality"},
    "WEPPcloud output": {"extensions": {".csv", ".zip", ".pdf", ".gpkg"}, "target": "outputs/models/weppcloud/download"},
}

MAX_SIZE_MB = 500


@dataclass
class UploadResult:
    valid: bool
    message: str
    checksum: str = ""
    saved_path: str = ""
    warnings: list[str] = field(default_factory=list)


def handle_upload(category: str, filename: str, file_bytes: bytes) -> UploadResult:
    if category not in CATEGORIES:
        return UploadResult(False, f"Unknown category: {category}")

    rules = CATEGORIES[category]
    suffix = Path(filename).suffix.lower()

    try:
        safe_name = sanitize_filename(filename)
    except ValueError as e:
        return UploadResult(False, str(e))

    size = len(file_bytes)
    if size <= 0:
        return UploadResult(False, "Empty file rejected")
    if size > MAX_SIZE_MB * 1024 * 1024:
        return UploadResult(False, f"File exceeds {MAX_SIZE_MB} MB limit")

    if suffix not in rules["extensions"]:
        return UploadResult(False, f"Extension '{suffix}' not accepted. Allowed: {', '.join(sorted(rules['extensions']))}")

    if "name_requires" in rules and rules["name_requires"] not in filename:
        return UploadResult(False, f"Filename must contain '{rules['name_requires']}'")

    cs = sha256_hex(file_bytes)
    target = project_root() / rules["target"]
    target.mkdir(parents=True, exist_ok=True)
    dest = target / safe_name
    if dest.exists():
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem, ext = dest.stem, dest.suffix
        dest = target / f"{stem}_{ts}{ext}"

    dest.write_bytes(file_bytes)
    return UploadResult(True, "Uploaded", checksum=cs, saved_path=str(dest))
