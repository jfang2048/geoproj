"""Upload manifest for files placed through the Streamlit Data page."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from postfire_runoff.frontend.components.paths import UPLOAD_MANIFEST

MANIFEST_COLUMNS = [
    "timestamp",
    "category",
    "config_key",
    "original_filename",
    "saved_path",
    "file_size_bytes",
    "checksum_sha256",
    "validation_warnings",
    "status",
    "note",
]


def _ensure_manifest() -> None:
    if not UPLOAD_MANIFEST.exists():
        UPLOAD_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with open(UPLOAD_MANIFEST, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS).writeheader()


def record_upload(
    category: str,
    config_key: str,
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
        "config_key": config_key,
        "original_filename": original_filename,
        "saved_path": str(saved_path),
        "file_size_bytes": str(file_size_bytes),
        "checksum_sha256": checksum,
        "validation_warnings": warnings,
        "status": status,
        "note": note,
    }
    with open(UPLOAD_MANIFEST, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS).writerow(row)


def read_manifest() -> list[dict[str, str]]:
    _ensure_manifest()
    with open(UPLOAD_MANIFEST, "r", newline="") as f:
        return list(csv.DictReader(f))
