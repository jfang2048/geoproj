"""Optional lake water-quality proxy stage.

The stage is intentionally conservative: without configured local pre/post
Sentinel-2 L2A reflectance inputs it records a machine-readable unavailable
status and does not emit numeric proxy anomalies.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from postfire_runoff.backend.config import load_config
from postfire_runoff.backend.io.paths import ensure_runtime_dirs


OPTIONAL_MISSING_INPUT_EXIT = 2


@dataclass(frozen=True)
class LakeWQResult:
    status: str
    status_table: Path
    exit_code: int
    message: str


def run_lake_wq(config_path: str | Path = "config/project.yaml", project_root: str | Path | None = None) -> LakeWQResult:
    cfg = load_config(config_path, project_root)
    ensure_runtime_dirs(cfg.root)
    tables = cfg.root / "outputs/tables"
    tables.mkdir(parents=True, exist_ok=True)
    status_path = tables / "lake_wq_status.csv"
    availability_path = tables / "lake_wq_event_image_availability.csv"

    event_summary = cfg.root / "outputs/tables/runoff_event_summary.csv"
    if not event_summary.exists():
        message = "Runoff event summary is required before lake WQ window selection."
        _write_missing(status_path, availability_path, message, [])
        return LakeWQResult("missing_input", status_path, OPTIONAL_MISSING_INPUT_EXIT, message)

    events = pd.read_csv(event_summary)
    event_ids = events.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
    pre = cfg.input_path("lake_pre_event_imagery", required=False)
    post = cfg.input_path("lake_post_event_imagery", required=False)
    lake_boundary = cfg.input_path("lake_boundary", required=False)
    missing = []
    for label, path in (("lake_pre_event_imagery", pre), ("lake_post_event_imagery", post), ("lake_boundary", lake_boundary)):
        if path is None or not path.exists():
            missing.append(label)
    if missing:
        message = "Optional lake stage unavailable; configure real local pre/post Sentinel-2 imagery and lake boundary: " + ", ".join(missing)
        _write_missing(status_path, availability_path, message, event_ids)
        return LakeWQResult("missing_input", status_path, OPTIONAL_MISSING_INPUT_EXIT, message)

    # A complete optical-index implementation requires actual reflectance stacks
    # and QA bands. Rather than fake a result, record the current unsupported
    # status if files are present but no reviewed reader is configured.
    message = "Configured lake inputs require a reviewed Sentinel-2 reflectance reader before numeric NDTI/NDCI summaries can be produced."
    _write_missing(status_path, availability_path, message, event_ids)
    return LakeWQResult("missing_input", status_path, OPTIONAL_MISSING_INPUT_EXIT, message)


def _write_missing(status_path: Path, availability_path: Path, message: str, event_ids: list[str]) -> None:
    pd.DataFrame([{
        "stage": "lake_wq",
        "status": "missing_input",
        "message": message,
        "numeric_proxy_rows": 0,
    }]).to_csv(status_path, index=False)
    rows = [{
        "event_id": event_id,
        "pre_products_found": 0,
        "post_products_found": 0,
        "usable_pair": "NO",
        "status": "MISSING_INPUT",
    } for event_id in event_ids]
    pd.DataFrame(rows, columns=["event_id", "pre_products_found", "post_products_found", "usable_pair", "status"]).to_csv(availability_path, index=False)
