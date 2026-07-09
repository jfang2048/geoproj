"""Run manifest read/write helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.storage.paths import ensure_run_layout, require_run_dir, sha256_file

MANIFEST_NAME = "run_manifest.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_manifest(run_id: str, *, name: str | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "name": name or run_id,
        "timestamp": now_utc(),
        "app_version": settings.app_version,
        "status": "created",
        "input_filenames": {},
        "input_checksums": {},
        "spatial_metadata": {},
        "raster_resolution": {},
        "bounds": {},
        "nodata_values": {},
        "selected_parameters": {},
        "generated_outputs": [],
        "output_checksums": {},
        "warnings": [],
        "fatal_errors": [],
        "inputs": {},
        "outputs": {},
        "jobs": {},
    }


def manifest_path(run_id: str) -> Path:
    return require_run_dir(run_id) / MANIFEST_NAME


def create_manifest(run_id: str, *, name: str | None = None) -> dict[str, Any]:
    ensure_run_layout(run_id)
    manifest = default_manifest(run_id, name=name)
    write_manifest(run_id, manifest)
    return manifest


def load_manifest(run_id: str) -> dict[str, Any]:
    path = manifest_path(run_id)
    if not path.exists():
        manifest = default_manifest(run_id)
        write_manifest(run_id, manifest)
        return manifest
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(run_id: str, manifest: dict[str, Any]) -> None:
    ensure_run_layout(run_id)
    path = require_run_dir(run_id) / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_warning(run_id: str, message: str) -> None:
    manifest = load_manifest(run_id)
    warnings = manifest.setdefault("warnings", [])
    if message not in warnings:
        warnings.append(message)
    write_manifest(run_id, manifest)


def add_fatal_error(run_id: str, message: str) -> None:
    manifest = load_manifest(run_id)
    errors = manifest.setdefault("fatal_errors", [])
    errors.append({"timestamp": now_utc(), "message": message})
    manifest["status"] = "failed"
    write_manifest(run_id, manifest)


def relative_to_run(run_id: str, path: Path) -> str:
    base = require_run_dir(run_id).resolve()
    return str(path.resolve().relative_to(base))


def record_input(run_id: str, category: str, path: Path, checksum: str, metadata: dict[str, Any]) -> dict[str, Any]:
    manifest = load_manifest(run_id)
    rel = relative_to_run(run_id, path)
    entry = {
        "category": category,
        "filename": path.name,
        "path": rel,
        "checksum_sha256": checksum,
        "metadata": metadata,
        "accepted_at": now_utc(),
    }
    manifest.setdefault("inputs", {})[category] = entry
    manifest.setdefault("input_filenames", {})[category] = path.name
    manifest.setdefault("input_checksums", {})[category] = checksum
    if "crs" in metadata:
        manifest.setdefault("spatial_metadata", {})[category] = metadata
    if "bounds" in metadata:
        manifest.setdefault("bounds", {})[category] = metadata.get("bounds")
    if "resolution" in metadata:
        manifest.setdefault("raster_resolution", {})[category] = metadata.get("resolution")
    if "nodata" in metadata:
        manifest.setdefault("nodata_values", {})[category] = metadata.get("nodata")
    for warning in metadata.get("warnings", []) or []:
        if warning not in manifest.setdefault("warnings", []):
            manifest["warnings"].append(warning)
    manifest["status"] = "inputs_uploaded"
    write_manifest(run_id, manifest)
    return entry


def record_output(run_id: str, key: str, path: Path, *, kind: str, description: str) -> dict[str, Any]:
    checksum = sha256_file(path)
    rel = relative_to_run(run_id, path)
    manifest = load_manifest(run_id)
    entry = {
        "key": key,
        "path": rel,
        "kind": kind,
        "description": description,
        "checksum_sha256": checksum,
        "created_at": now_utc(),
    }
    manifest.setdefault("outputs", {})[key] = entry
    generated = manifest.setdefault("generated_outputs", [])
    if rel not in generated:
        generated.append(rel)
    manifest.setdefault("output_checksums", {})[rel] = checksum
    write_manifest(run_id, manifest)
    return entry


def record_parameters(run_id: str, parameters: dict[str, Any]) -> None:
    manifest = load_manifest(run_id)
    manifest.setdefault("selected_parameters", {}).update(parameters)
    write_manifest(run_id, manifest)
