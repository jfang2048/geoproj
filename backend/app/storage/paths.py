"""Filesystem-safe run storage utilities."""
from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from app.core.config import settings
from app.core.errors import NotFoundError, SafePathError, UploadValidationError

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
RUN_ID_RE = re.compile(r"^run_[0-9]{8}T[0-9]{6}Z_[a-f0-9]{8}$")
REQUIRED_RUN_DIRS = ("inputs", "normalized", "outputs", "logs", "reports")


def sanitize_filename(filename: str) -> str:
    """Return a safe basename or raise when traversal is present."""
    if not filename or "\x00" in filename:
        raise SafePathError("Missing or unsafe filename.")
    raw = filename.replace("\\", "/")
    if raw.startswith("/") or "../" in raw or raw == ".." or raw.endswith("/.."):
        raise SafePathError(f"Path traversal rejected: {filename}")
    name = Path(raw).name
    if name != raw:
        raise SafePathError(f"Path traversal rejected: {filename}")
    safe = SAFE_NAME_RE.sub("_", name).strip("._")
    if not safe:
        raise SafePathError("Filename became empty after sanitization.")
    return safe


def ensure_safe_archive(path: Path) -> None:
    """Reject zip archives with absolute paths or parent traversal."""
    if path.suffix.lower() != ".zip":
        return
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                parts = [p for p in name.split("/") if p]
                if name.startswith("/") or any(part == ".." for part in parts):
                    raise UploadValidationError(
                        "Unsafe archive contents rejected.",
                        details={"entry": info.filename},
                    )
    except zipfile.BadZipFile as exc:
        raise UploadValidationError("ZIP archive is not readable.") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_safe_run_id(run_id: str) -> None:
    if not RUN_ID_RE.match(run_id):
        raise SafePathError(f"Unsafe run ID: {run_id}")


def run_dir(run_id: str) -> Path:
    assert_safe_run_id(run_id)
    path = (settings.runs_dir / run_id).resolve()
    root = settings.runs_dir.resolve()
    if root not in path.parents and path != root:
        raise SafePathError("Run path escaped runs directory.")
    return path


def require_run_dir(run_id: str) -> Path:
    path = run_dir(run_id)
    if not path.exists():
        raise NotFoundError(f"Run not found: {run_id}")
    return path


def ensure_run_layout(run_id: str) -> Path:
    base = run_dir(run_id)
    for name in REQUIRED_RUN_DIRS:
        (base / name).mkdir(parents=True, exist_ok=True)
    (base / "outputs" / "display").mkdir(parents=True, exist_ok=True)
    (base / "outputs" / "qa").mkdir(parents=True, exist_ok=True)
    return base


def unique_destination(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(filename)
    candidate = directory / safe
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def resolve_under_run(run_id: str, relative_path: str) -> Path:
    base = require_run_dir(run_id).resolve()
    if not relative_path or "\x00" in relative_path:
        raise SafePathError("Invalid relative path.")
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise SafePathError("Requested path escaped run directory.")
    if not target.exists():
        raise NotFoundError(f"File not found: {relative_path}")
    if target.is_dir():
        raise SafePathError("Directory download is not allowed.")
    return target


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
