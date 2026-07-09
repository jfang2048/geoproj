"""Central path definitions for the webapp.

Resolve all project paths relative to the repository root so the webapp
can be launched from any working directory.
"""
from __future__ import annotations

from pathlib import Path

# Repository root = four levels up from components/paths.py
ROOT = Path(__file__).resolve().parents[4]

DATA_RAW = ROOT / "data/raw"
SCRIPTS = ROOT / "postfire_runoff/cli"
DATA_RAW_ZIP = ROOT / "data/raw/zip"
DATA_PROCESSED = ROOT / "data/processed"
OUTPUTS = ROOT / "outputs"
TABLES = ROOT / "outputs/tables"
LATEX = ROOT / "latex"
QA_SPATIAL = ROOT / "qa/spatial"
WEBAPP = ROOT / "postfire_runoff/webapp"
WEBAPP_RUN_LOGS = WEBAPP / "run_logs"
WEBAPP_UPLOAD_MANIFEST = WEBAPP / "upload_manifest.csv"
WEBAPP_PARAMS = WEBAPP / "current_parameters.yaml"
WEPPCLOUD_DOWNLOAD = ROOT / "outputs/models/weppcloud/download"

# Minimum required files for data check
REQUIRED_CORE = {
    "Catchment boundary": DATA_PROCESSED / "boundary/catchment_utm32.gpkg",
    "Burn severity proxy": DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif",
    "Runoff response units": DATA_PROCESSED / "model_inputs/runoff_units.gpkg",
    "Rainfall events": DATA_PROCESSED / "weather/post_fire_rainfall_events.csv",
    "Runoff delta table": TABLES / "runoff_delta_by_event.csv",
    "Runoff event summary": TABLES / "runoff_event_summary.csv",
}

REQUIRED_WEPPCLOUD = {
    "WEPPcloud comparison doc": ROOT / "outputs/models/weppcloud/WEPPcloud_vs_SCS_CN_COMPARISON.md",
    "WEPPcloud sediment figure": LATEX / "fig09_weppcloud_sediment.png",
}

REQUIRED_LAKE_WQ = {
    "Lake WQ runner": ROOT / "postfire_runoff/cli/run_lake_wq.py",
    "Selected events": TABLES / "lake_response_selected_events.csv",
    "Lake WQ anomalies": TABLES / "lake_wq_event_anomalies.csv",
    "Lake WQ analytical context": TABLES / "lake_wq_analytical_context_by_period.csv",
}

REQUIRED_FIGURES = {
    f"fig{n:02d}{suffix}": LATEX / f"fig{n:02d}{suffix}"
    for n, suffix in [
        (1, "a_north_Italy.png"),
        (1, "c_local_domain.png"),
        (2, "_dem_hydrology_qa.png"),
        (3, "_response_units_map.png"),
        (4, "_event_rainfall_response.png"),
        (4, "_response_unit_cn_adjustment.png"),
        (5, "_burn_footprint_area.png"),
        (6, "_burn_runoff_response.png"),
        (7, "_event_delta_cdf.png"),
        (8, "_sensitivity_hierarchy.png"),
        (9, "_weppcloud_sediment.png"),
        (10, "_runoff_vs_lake_turbidity_proxy.png"),
        (11, "_runoff_vs_lake_chla_proxy.png"),
        (12, "_lake_water_quality_event_panel.png"),
        (13, "_runoff_to_lake_wq_closure.png"),
    ]
}

WORKFLOW_PNG = LATEX / "workflow_new.png"


def resolve_safe(target_dir: Path, filename: str) -> Path:
    """Resolve a safe path inside target_dir using only the file basename."""
    safe_name = Path(filename).name
    resolved = (target_dir / safe_name).resolve()
    if not str(resolved).startswith(str(target_dir.resolve())):
        raise ValueError(f"Path traversal rejected: {filename}")
    return resolved
