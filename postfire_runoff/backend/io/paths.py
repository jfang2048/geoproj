"""Repository and runtime path resolution."""
from __future__ import annotations

import os
from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def project_root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("GEOPROJECT_ROOT", "")
    if env:
        return Path(env).expanduser().resolve()
    return default_project_root()


def resolve_under_root(root: str | Path, value: str | Path) -> Path:
    value_path = Path(value).expanduser()
    if value_path.is_absolute():
        return value_path.resolve()
    return (Path(root).resolve() / value_path).resolve()


def ensure_runtime_dirs(root: str | Path) -> dict[str, Path]:
    root = Path(root).resolve()
    dirs = {
        "data_raw": root / "data/raw",
        "data_processed": root / "data/processed",
        "outputs": root / "outputs",
        "output_tables": root / "outputs/tables",
        "weppcloud": root / "outputs/models/weppcloud",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
