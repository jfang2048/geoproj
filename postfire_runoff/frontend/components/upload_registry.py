"""Upload manifest registry — tracks files placed via the Streamlit app."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from postfire_runoff.frontend.components.paths import WEBAPP, WEBAPP_UPLOAD_MANIFEST

MANIFEST_COLUMNS = [
    "timestamp",
    "category",
    "original_filename",
    "saved_path",
    "file_size_bytes",
    "checksum_sha256",
    "validation_warnings",
    "status",
    "note",
]


def _ensure_manifest() -> None:
    if not WEBAPP_UPLOAD_MANIFEST.exists():
        WEBAPP_UPLOAD_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with open(WEBAPP_UPLOAD_MANIFEST, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()


def record_upload(
    category: str,
    original_filename: str,
    saved_path: Path,
    file_size_bytes: int,
    status: str = "uploaded",
    note: str = "",
    checksum: str = "",
    warnings: str = "",
) -> None:
    _ensure_manifest()
    row = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": category,
        "original_filename": original_filename,
        "saved_path": str(saved_path),
        "file_size_bytes": str(file_size_bytes),
        "checksum_sha256": checksum,
        "validation_warnings": warnings,
        "status": status,
        "note": note,
    }
    with open(WEBAPP_UPLOAD_MANIFEST, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writerow(row)


def read_manifest() -> list[dict[str, str]]:
    _ensure_manifest()
    with open(WEBAPP_UPLOAD_MANIFEST, "r", newline="") as f:
        return list(csv.DictReader(f))
