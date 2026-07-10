"""Thin Streamlit-facing adapters over backend services and output contracts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from postfire_runoff.backend.io.paths import project_root
from postfire_runoff.backend.services.uploads import (
    CATEGORY_RULES,
    UploadResult,
    accepted_extensions_for,
    handle_upload,
    validate_upload,
)


def save_upload(category: str, filename: str, file_bytes: bytes) -> UploadResult:
    return handle_upload(category, filename, file_bytes, root=project_root())


def project_reference_points(root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    cfg = root / "config/project.yaml"
    if not cfg.exists():
        return {}
    try:
        data = yaml.safe_load(cfg.read_text()) or {}
    except Exception:
        return {}
    return data.get("reference_points", {}) or {}


def outlet_lonlat(root: Path | None = None) -> tuple[float, float] | None:
    points = project_reference_points(root)
    outlet = points.get("provisional_outlet_wgs84") or points.get("outlet_wgs84")
    if isinstance(outlet, dict) and outlet.get("lon") is not None and outlet.get("lat") is not None:
        try:
            return float(outlet["lon"]), float(outlet["lat"])
        except (TypeError, ValueError):
            return None
    return None
