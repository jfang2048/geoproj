"""File upload validation and extension rules per data category."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

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


@dataclass
class ValidationResult:
    valid: bool
    message: str


def validate_upload(category: str, filename: str, file_size: int) -> ValidationResult:
    if category not in CATEGORY_RULES:
        return ValidationResult(False, f"Unknown upload category: {category}")

    rules = CATEGORY_RULES[category]
    suffix = Path(filename).suffix.lower()

    if file_size <= 0:
        return ValidationResult(False, f"Empty file rejected: {filename}")

    if suffix not in rules["extensions"]:
        return ValidationResult(
            False,
            f"Extension '{suffix}' not allowed for {category}. Accepted: {', '.join(sorted(rules['extensions']))}",
        )

    if "name_requires" in rules and rules["name_requires"] not in filename:
        return ValidationResult(
            False,
            f"Filename must contain '{rules['name_requires']}' for {category}.",
        )

    # Path traversal check
    safe = Path(filename).name
    if safe != filename:
        return ValidationResult(False, f"Path traversal rejected: {filename}")

    return ValidationResult(True, "OK")


def accepted_extensions_for(category: str) -> list[str]:
    rules = CATEGORY_RULES.get(category, {})
    return sorted(rules.get("extensions", set()))
