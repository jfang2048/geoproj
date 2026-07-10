"""Canonical repository and runtime path resolution.

The repository root is resolved from an explicit argument, the
``GEOPROJECT_ROOT`` environment variable, or the installed package location. It
never depends on the process working directory and never guesses a parent project
outside a standalone clone.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_project_root() -> Path:
    # postfire_runoff/backend/io/paths.py -> repo root
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


DATA_RAW = "data/raw"
DATA_PROCESSED = "data/processed"
OUTPUTS = "outputs"
SAMPLE_DATA = "sample_data"
