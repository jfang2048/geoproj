"""Run manifest — records inputs, outputs, parameters, warnings, and errors."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def create_run_manifest(
    run_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id or uuid.uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "started",
        "inputs": {},
        "input_checksums": {},
        "spatial_metadata": {},
        "parameters": parameters or {},
        "processing_crs": "EPSG:32632",
        "outputs": {},
        "output_checksums": {},
        "warnings": [],
        "errors": [],
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str))


def add_input(manifest: dict[str, Any], category: str, path: Path, checksum: str = "") -> None:
    manifest["inputs"][category] = str(path)
    if checksum:
        manifest["input_checksums"][category] = checksum


def add_output(manifest: dict[str, Any], name: str, path: Path, checksum: str = "") -> None:
    manifest["outputs"][name] = str(path)
    if checksum:
        manifest["output_checksums"][name] = checksum


def add_warning(manifest: dict[str, Any], message: str) -> None:
    manifest["warnings"].append(message)


def add_error(manifest: dict[str, Any], message: str) -> None:
    manifest["errors"].append(message)
    manifest["status"] = "failed"


def set_succeeded(manifest: dict[str, Any]) -> None:
    if manifest["status"] != "failed":
        manifest["status"] = "succeeded"
