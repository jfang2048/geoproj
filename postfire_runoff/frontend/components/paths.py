"""Canonical frontend path definitions."""
from __future__ import annotations

from pathlib import Path

from postfire_runoff.backend.io.paths import project_root

ROOT = project_root()
DATA_RAW = ROOT / "data/raw"
DATA_PROCESSED = ROOT / "data/processed"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
MODELS = OUTPUTS / "models"
WEPPCLOUD_DOWNLOAD = MODELS / "weppcloud/download"
FRONTEND = ROOT / "postfire_runoff/frontend"
WEBAPP = FRONTEND  # compatibility name used by the existing app layout
WEBAPP_RUN_LOGS = FRONTEND / "run_logs"
WEBAPP_UPLOAD_MANIFEST = FRONTEND / "upload_manifest.csv"
WEBAPP_PARAMS = FRONTEND / "current_parameters.yaml"
DATA_RAW_ZIP = DATA_RAW

REQUIRED_CORE = {
    "Catchment boundary": DATA_PROCESSED / "boundary/catchment_utm32.gpkg",
    "Official fire perimeter": DATA_PROCESSED / "fire_perimeter/fire_perimeter_utm32.gpkg",
    "Burn severity proxy": DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif",
    "Runoff response units": DATA_PROCESSED / "model_inputs/runoff_units.gpkg",
    "Rainfall events": DATA_PROCESSED / "weather/post_fire_rainfall_events.csv",
    "Runoff units table": TABLES / "runoff_units.csv",
    "Runoff delta table": TABLES / "runoff_delta_by_event.csv",
    "Runoff event summary": TABLES / "runoff_event_summary.csv",
}

REQUIRED_WEPPCLOUD = {
    "Normalized WEPPcloud export": TABLES / "weppcloud_summary.csv",
}

REQUIRED_LAKE_WQ = {
    "Lake WQ status": TABLES / "lake_wq_status.csv",
    "Lake image availability": TABLES / "lake_wq_event_image_availability.csv",
}

REQUIRED_FIGURES = {
    "Overview screenshot": ROOT / "screenshots/01_overview.png",
    "Data screenshot": ROOT / "screenshots/02_data.png",
    "Explorer map screenshot": ROOT / "screenshots/03_explorer_map.png",
    "Explorer parameters screenshot": ROOT / "screenshots/04_explorer_params.png",
    "Results screenshot": ROOT / "screenshots/05_results.png",
    "Lake WQ screenshot": ROOT / "screenshots/06_lake_wq.png",
}

WORKFLOW_PNG = ROOT / "screenshots/01_overview.png"


def resolve_safe(target_dir: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    resolved = (target_dir / safe_name).resolve()
    if not str(resolved).startswith(str(target_dir.resolve())):
        raise ValueError(f"Path traversal rejected: {filename}")
    return resolved
