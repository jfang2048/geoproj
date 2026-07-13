"""Frontend path definitions."""
from __future__ import annotations

from pathlib import Path

from postfire_runoff.backend.io.paths import project_root

ROOT = project_root()
DATA_PROCESSED = ROOT / "data/processed"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
FRONTEND = ROOT / "postfire_runoff/frontend"
RUN_LOGS = FRONTEND / "run_logs"
UPLOAD_MANIFEST = FRONTEND / "upload_manifest.csv"
PARAMS_PATH = FRONTEND / "current_parameters.yaml"
PROJECT_CONFIG = ROOT / "config/project.yaml"

REQUIRED_CORE = {
    "Catchment boundary": DATA_PROCESSED / "boundary/catchment_utm32.gpkg",
    "Official fire perimeter": DATA_PROCESSED / "fire_perimeter/fire_perimeter_utm32.gpkg",
    "Burn severity raster": DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif",
    "Runoff response units": DATA_PROCESSED / "model_inputs/runoff_units.gpkg",
    "Rainfall events": DATA_PROCESSED / "weather/post_fire_rainfall_events.csv",
    "Runoff units table": TABLES / "runoff_units.csv",
    "Runoff delta table": TABLES / "runoff_delta_by_event.csv",
    "Runoff event summary": TABLES / "runoff_event_summary.csv",
}

REQUIRED_WEPPCLOUD = {
    "Normalized WEPPcloud export": TABLES / "weppcloud_summary.csv",
}


def resolve_safe(target_dir: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    resolved = (target_dir / safe_name).resolve()
    if not str(resolved).startswith(str(target_dir.resolve())):
        raise ValueError(f"Path traversal rejected: {filename}")
    return resolved
