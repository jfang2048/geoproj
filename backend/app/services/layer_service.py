"""Map layer and download catalog services."""
from __future__ import annotations

from app.storage.manifest import load_manifest
from app.storage.paths import require_run_dir

LAYER_DEFS = [
    ("uploaded_fire_perimeter", "Uploaded fire perimeter preview", "outputs/display/uploaded_fire_perimeter.geojson", "Upload a fire perimeter to preview it."),
    ("uploaded_burn_severity", "Uploaded burn severity preview", "outputs/display/uploaded_burn_severity.geojson", "Upload burn severity data to preview it."),
    ("uploaded_land_cover", "Uploaded land cover preview", "outputs/display/uploaded_land_cover.geojson", "Upload land cover data to preview it."),
    ("catchment_boundary", "Catchment boundary", "outputs/display/catchment_boundary.geojson", "No output for this run yet. Run preprocessing and model calculation first."),
    ("fire_perimeter", "Fire perimeter", "outputs/display/fire_perimeter.geojson", "Run preprocessing to render the fire perimeter."),
    ("burn_severity", "Burn severity", "outputs/display/burn_severity.geojson", "Run preprocessing to render burn severity."),
    ("land_cover", "Land cover", "outputs/display/land_cover.geojson", "Run preprocessing to render land cover."),
    ("hydrologic_soil_group", "Hydrologic soil group", "outputs/display/hydrologic_soil_group.geojson", "Upload HSG data and run preprocessing to render it."),
    ("response_units", "Response units", "outputs/display/response_units.geojson", "No output for this run yet. Run preprocessing and model calculation first."),
    ("runoff_delta", "Runoff delta", "outputs/display/runoff_delta.geojson", "No output for this run yet. Run preprocessing and model calculation first."),
    ("water_body", "Water body", "outputs/display/water_body.geojson", "Optional water body layer was not uploaded."),
    ("hydrography", "Hydrography", "outputs/display/hydrography.geojson", "Optional hydrography layer was not uploaded."),
]


def layer_catalog(run_id: str) -> list[dict]:
    base = require_run_dir(run_id)
    catalog = []
    for layer_id, label, rel, missing_reason in LAYER_DEFS:
        path = base / rel
        exists = path.exists()
        catalog.append(
            {
                "layer_id": layer_id,
                "label": label,
                "exists": exists,
                "reason": None if exists else missing_reason,
                "url": f"/api/runs/{run_id}/layers/{layer_id}.geojson" if exists else None,
                "geometry_type": "geojson" if exists else None,
                "downloadable": exists,
            }
        )
    return catalog


def layer_path(run_id: str, layer_id: str):
    base = require_run_dir(run_id)
    from app.core.errors import NotFoundError

    for defined_id, _label, rel, _reason in LAYER_DEFS:
        if defined_id == layer_id:
            path = base / rel
            if not path.exists():
                raise NotFoundError(f"Layer is not available for this run: {layer_id}")
            return path
    raise NotFoundError(f"Unknown layer: {layer_id}")


def downloads(run_id: str) -> list[dict]:
    manifest = load_manifest(run_id)
    result = []
    for key, entry in sorted(manifest.get("outputs", {}).items()):
        path = entry.get("path")
        if not path:
            continue
        result.append(
            {
                "key": key,
                "description": entry.get("description", key),
                "kind": entry.get("kind", "file"),
                "path": path,
                "checksum_sha256": entry.get("checksum_sha256", ""),
                "url": f"/api/runs/{run_id}/download/{path}",
            }
        )
    return result
