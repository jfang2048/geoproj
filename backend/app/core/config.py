"""Application configuration for the Web GIS runoff screening API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_VERSION = "0.1.0"
WORKING_CRS = "EPSG:32632"
DISPLAY_CRS = "EPSG:4326"

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    """Runtime settings read from environment variables."""

    app_name: str = "Post-fire runoff screening API"
    app_version: str = APP_VERSION
    repo_root: Path = REPO_ROOT
    runs_dir: Path = Path(os.getenv("RUNOFF_RUNS_DIR", str(REPO_ROOT / "runs")))
    max_upload_bytes: int = int(os.getenv("RUNOFF_MAX_UPLOAD_BYTES", str(512 * 1024 * 1024)))
    working_crs: str = os.getenv("RUNOFF_WORKING_CRS", WORKING_CRS)
    display_crs: str = DISPLAY_CRS
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "RUNOFF_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )


settings = Settings()
