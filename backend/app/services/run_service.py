"""Run lifecycle service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.storage.manifest import create_manifest, load_manifest
from app.storage.paths import ensure_run_layout, require_run_dir


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"


def create_run(name: str | None = None) -> dict:
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = new_run_id()
    ensure_run_layout(run_id)
    return create_manifest(run_id, name=name)


def get_run(run_id: str) -> dict:
    require_run_dir(run_id)
    return load_manifest(run_id)


def list_runs() -> list[dict]:
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict] = []
    for path in sorted(settings.runs_dir.glob("run_*"), reverse=True):
        if not path.is_dir():
            continue
        try:
            manifest = load_manifest(path.name)
            runs.append(
                {
                    "run_id": manifest["run_id"],
                    "name": manifest.get("name", manifest["run_id"]),
                    "timestamp": manifest.get("timestamp", ""),
                    "status": manifest.get("status", "unknown"),
                    "manifest_path": str(Path(path.name) / "run_manifest.json"),
                }
            )
        except Exception:
            continue
    return runs
