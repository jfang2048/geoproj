"""Upload acceptance service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.errors import SafePathError, UploadValidationError
from app.gis.display import write_bounds_geojson, write_vector_display_geojson
from app.gis.validation import validate_file
from app.models.categories import DataKind, InputCategory, category_from_string
from app.storage.manifest import record_input, record_output
from app.storage.paths import ensure_run_layout, sanitize_filename, sha256_file, unique_destination


def accept_upload(run_id: str, category_value: str, filename: str, source: BinaryIO) -> dict:
    category = category_from_string(category_value)
    safe_name = sanitize_filename(filename)
    base = ensure_run_layout(run_id)
    incoming_dir = base / "inputs" / ".incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    tmp = unique_destination(incoming_dir, safe_name)
    try:
        size = _write_limited(source, tmp, settings.max_upload_bytes)
        if size <= 0:
            raise UploadValidationError("Empty files are rejected.")
        report = validate_file(category, tmp)
        report.require_valid()
        dest = unique_destination(base / "inputs" / category.value, safe_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), dest)
        checksum = sha256_file(dest)
        metadata = dict(report.metadata)
        metadata["size_bytes"] = size
        metadata["warnings"] = list(report.warnings or metadata.get("warnings", []))
        input_entry = record_input(run_id, category.value, dest, checksum, metadata)
        preview_path = _write_upload_preview(run_id, category, dest, metadata)
        if preview_path is not None:
            record_output(
                run_id,
                f"preview_{category.value}",
                preview_path,
                kind="display_layer",
                description=f"Uploaded {category.value} preview for browser map.",
            )
        return {
            "run_id": run_id,
            "category": category.value,
            "filename": dest.name,
            "checksum_sha256": checksum,
            "metadata": metadata,
            "input": input_entry,
            "message": "File accepted and stored in the run directory.",
        }
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _write_limited(source: BinaryIO, target: Path, limit: int) -> int:
    total = 0
    with target.open("wb") as handle:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise UploadValidationError(
                    "Upload size limit exceeded.",
                    details={"limit_bytes": limit, "received_bytes": total},
                )
            handle.write(chunk)
    return total


def _write_upload_preview(run_id: str, category: InputCategory, path: Path, metadata: dict) -> Path | None:
    base = ensure_run_layout(run_id)
    output = base / "outputs" / "display" / f"uploaded_{category.value}.geojson"
    kind = metadata.get("kind")
    properties = {"layer": category.value, "source": "uploaded_file", "filename": path.name}
    if kind == DataKind.vector.value or kind == "vector":
        return write_vector_display_geojson(path, output, properties=properties)
    if kind == DataKind.raster.value or kind == "raster":
        bounds = metadata.get("bounds")
        crs = metadata.get("crs")
        if bounds and crs:
            return write_bounds_geojson(bounds, crs, output, properties={**properties, "display_type": "raster_footprint"})
    return None
