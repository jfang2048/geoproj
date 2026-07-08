"""Shared utilities for the Lake Varese / Monte Martica automation pipeline.

The helpers in this module enforce the project runbook rules:
- pathlib everywhere
- idempotent generated outputs
- run-log and backlog updates from every script
- source manifest/blocker/manual-task bookkeeping
- raw data immutability
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKING_CRS = "EPSG:32632"
WGS84 = "EPSG:4326"
OUTLET_LON = 8.82375104
OUTLET_LAT = 45.91547405
FIRE_DATE = "2019-01-03"
RUN_LOG = ROOT / "qa/audit/README.md"
BACKLOG = ROOT / "qa/audit/README.md"
EVIDENCE_README = ROOT / "qa/evidence/README.md"

MANIFEST_COLUMNS = [
    "dataset_id",
    "dataset_name",
    "role",
    "source_url",
    "access_method",
    "license_or_terms",
    "download_time_utc",
    "local_path",
    "raw_or_processed",
    "crs",
    "resolution_or_scale",
    "spatial_extent",
    "temporal_extent",
    "checksum_sha256",
    "status",
    "notes",
]

INVENTORY_COLUMNS = [
    "path",
    "file_type",
    "dataset_guess",
    "exists",
    "readable",
    "driver",
    "crs",
    "extent",
    "width",
    "height",
    "feature_count",
    "layer_names",
    "notes",
]

S2_COLUMNS = [
    "role",
    "product_id",
    "datetime",
    "cloud_cover_percent",
    "tile_id",
    "relative_orbit",
    "processing_level",
    "coverage_fraction",
    "required_bands_available",
    "product_url",
    "download_url",
    "rank_score",
    "selected",
    "notes",
]

BURN_SUMMARY_COLUMNS = [
    "class_code",
    "class_name",
    "pixel_count",
    "area_m2",
    "area_ha",
    "area_percent_of_valid",
    "threshold_rule",
    "notes",
]

RAIN_EVENT_COLUMNS = [
    "event_id",
    "start_date",
    "end_date",
    "duration_days",
    "total_precip_mm",
    "max_daily_precip_mm",
    "station_id",
    "station_name",
    "station_lat",
    "station_lon",
    "station_elevation_m",
    "distance_to_burned_area_km",
    "data_resolution",
    "source_file",
    "notes",
]

RUNOFF_UNIT_COLUMNS = [
    "unit_id",
    "area_m2",
    "area_ha",
    "burn_class",
    "landcover_class",
    "soil_group",
    "slope_mean",
    "slope_class",
    "baseline_parameter",
    "burned_parameter",
    "parameter_source",
    "notes",
]

RUNOFF_EVENT_COLUMNS = [
    "event_id",
    "scenario",
    "rainfall_total_mm",
    "runoff_total_mm",
    "runoff_volume_m3",
    "runoff_coefficient",
    "model_name",
    "parameter_set",
    "notes",
]

REQUIRED_DIRS = [
    "config",
    "scripts",
    "tests",
    "docs",
    "data/raw",
    "data/interim",
    "data/interim/dem",
    "data/interim/sentinel2",
    "data/processed",
    "data/processed/boundary",
    "data/processed/dem",
    "data/processed/burn",
    "data/processed/fire_perimeter",
    "data/processed/hydrography",
    "data/processed/landcover",
    "data/processed/soil",
    "data/processed/weather",
    "data/processed/model_inputs",
    "outputs/maps",
    "outputs/tables",
    "outputs/figures",
    "outputs/models/weppcloud",
    "qa/evidence",
    "qa/audit",
]

DEFAULT_PROJECT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "lake_varese_monte_martica_post_fire_runoff",
        "crs_working": WORKING_CRS,
        "study_area_label": "Lake Varese / Monte Martica",
        "fire_year": 2019,
        "fire_name": "Monte Martica wildfire",
        "primary_model": "simplified_event_runoff",
        "benchmark_model": "WEPPcloud-EU",
    },
    "aoi": {
        "mode": "fire_perimeter_buffer_if_available",
        "fallback_bbox_wgs84": {"west": 8.75, "south": 45.78, "east": 8.90, "north": 45.90},
        "buffer_m": 5000,
        "provisional_note": "Fallback processing mask only; not a final scientific study boundary.",
    },
    "reference_points": {
        "lake_varese_center_wgs84": {"lon": 8.74, "lat": 45.82},
        "monte_martica_center_wgs84": {"lon": 8.84, "lat": 45.88},
        "provisional_outlet_wgs84": {"lon": 8.775, "lat": 45.805},
    },
    "sentinel2": {
        "collection": "SENTINEL-2",
        "product_type": "L2A",
        "max_cloud_cover_percent": 30,
        "pre_fire_primary": {"start": "2018-12-01", "end": "2019-01-02"},
        "pre_fire_fallback": {"start": "2018-10-01", "end": "2019-01-02"},
        "post_fire_primary": {"start": "2019-01-08", "end": "2019-03-31"},
        "post_fire_fallback": {"start": "2019-01-08", "end": "2019-06-30"},
        "required_bands": ["B04", "B08", "B11", "B12", "SCL"],
        "nbr_working_resolution_m": 20,
    },
    "burn_classification": {
        "nodata": 255,
        "class_codes": {"unburned": 0, "low": 1, "moderate": 2, "high": 3},
        "dnbr_thresholds": {
            "unburned_max": 0.10,
            "low_max": 0.27,
            "moderate_max": 0.66,
            "high_min": 0.66,
        },
        "threshold_note": "Literature-standard dNBR screening thresholds; proxy only, not field-validated soil burn severity.",
    },
    "dem": {
        "preferred_local_paths": ["DTM5_RL/DTM5_RL.img", "lombardia_dtm/"],
        "stream_threshold_cells": 1000,
        "fallback_resolution_m": 100,
        "synthetic_fallback_allowed": True,
        "synthetic_fallback_note": "Only keeps the pipeline executable; replace with official/local DEM before scientific interpretation.",
    },
    "landcover": {
        "simplified_classes": ["forest", "shrub", "grassland", "agriculture", "urban", "bare_soil", "water", "other"],
        "fallback_note": "Synthetic land-cover zones are placeholders when DUSAF/CORINE/WorldCover are unavailable.",
    },
    "soil": {
        "fallback_hydrologic_soil_group": "C",
        "fallback_note": "Simplified HSG placeholder pending EU soil hydraulic data or SoilGrids-derived classes.",
    },
    "weather": {
        "event_start": "2019-01-01",
        "event_end": "2020-12-31",
        "rain_day_threshold_mm": 1.0,
        "dry_gap_days": 1,
        "design_events_when_station_data_missing": [
            {"event_id": "DESIGN_2019_02_01", "start_date": "2019-02-01", "end_date": "2019-02-01", "total_precip_mm": 20.0},
            {"event_id": "DESIGN_2019_04_12", "start_date": "2019-04-12", "end_date": "2019-04-13", "total_precip_mm": 42.0},
            {"event_id": "DESIGN_2019_11_03", "start_date": "2019-11-03", "end_date": "2019-11-04", "total_precip_mm": 65.0},
        ],
    },
    "runoff": {
        "model": "simplified_scs_cn_screening",
        "antecedent_moisture": "normal",
        "baseline_curve_numbers": {"forest": 60, "shrub": 65, "grassland": 69, "agriculture": 75, "urban": 88, "bare_soil": 82, "water": 98, "other": 74},
        "burn_curve_number_adjustment": {"0": 0, "1": 4, "2": 8, "3": 12},
        "sensitivity": {"burn_thresholds": True, "soil_grouping": True, "wetness_rule": True},
        "scientific_note": "Screening model for relative runoff change; not a calibrated hydrologic forecast.",
    },
}

DEFAULT_SOURCES_CONFIG: dict[str, Any] = {
    "sources": {
        "lombardia_geoportal_home": {
            "dataset_name": "Regione Lombardia Geoportale",
            "role": "boundary_hydrography_fire_landcover_discovery",
            "url": "https://www.geoportale.regione.lombardia.it/",
            "access_method": "HTTP service discovery",
            "license_or_terms": "Verify on source page before reuse",
        },
        "copernicus_dataspace_stac": {
            "dataset_name": "Copernicus Data Space STAC",
            "role": "sentinel2_discovery",
            "url": "https://catalogue.dataspace.copernicus.eu/stac",
            "search_url": "https://catalogue.dataspace.copernicus.eu/stac/search",
            "access_method": "STAC API search; OData download requires credentials",
            "license_or_terms": "Copernicus Sentinel data terms",
        },
        "soilgrids_api": {
            "dataset_name": "ISRIC SoilGrids API",
            "role": "soil_fallback_discovery",
            "url": "https://rest.isric.org/soilgrids/v2.0/docs",
            "access_method": "HTTP API discovery",
            "license_or_terms": "ISRIC terms; verify before derived products",
        },
        "arpa_lombardia": {
            "dataset_name": "ARPA Lombardia meteorological and lake data",
            "role": "weather_lake_quality_discovery",
            "url": "https://www.arpalombardia.it/",
            "access_method": "Website/request workflow; likely manual for station data",
            "license_or_terms": "Verify ARPA data terms/request conditions",
        },
    }
}

DEFAULT_PATHS_CONFIG: dict[str, Any] = {
    "project_root": ".",
    "data": {"raw": "data/raw", "interim": "data/interim", "processed": "data/processed", "reference": "data/reference"},
    "outputs": {"maps": "outputs/maps", "figures": "outputs/figures", "tables": "outputs/tables", "models": "outputs/models", "weppcloud": "outputs/models/weppcloud", "automation": "outputs/automation"},
    "qa": {"evidence": "qa/evidence", "audit": "qa/audit", "spatial": "qa/spatial"},
    "docs": "docs",
    "config": "config",
    "scripts": "scripts",
    "tests": "tests",
    "projects": "projects",
    "logs": "outputs/automation",
    "local_candidates": {
        "dem": ["DTM5_RL/DTM5_RL.img", "lombardia_dtm/"],
        "hydrography": ["VARESE/"],
        "legacy_zip": ["zip/"],
        "sentinel2": ["data/raw/sentinel2", "*.SAFE", "*.jp2"],
    },
}

ASSUMPTIONS = {
    "ASSUMPTION_001": {
        "description": "dNBR is used as a remote-sensing burn-severity proxy.",
        "reason": "Field-validated soil burn severity is not available in the automation scaffold.",
        "risk": "Proxy classes may not match ground conditions.",
        "mitigation": "Label outputs as proxy and replace with field/official validation where available.",
        "affected outputs": "burn_severity_proxy_uint8.tif, runoff_units.csv, runoff_event_summary.csv",
    },
    "ASSUMPTION_002": {
        "description": "Final catchment is DEM-derived, not hand drawn.",
        "reason": "Hydrologic boundary must be defensible and reproducible.",
        "risk": "Fallback synthetic DEM outputs are not final scientific boundaries.",
        "mitigation": "Use local/offical DEM and review outlet candidates against hydrography before interpretation.",
        "affected outputs": "catchment_utm32.gpkg, outlet_candidates.csv",
    },
    "ASSUMPTION_003": {
        "description": "Soil class is simplified because detailed local soil hydraulic data may be unavailable.",
        "reason": "EU/SoilGrids data access and licensing may require manual review.",
        "risk": "Runoff response uncertainty is high.",
        "mitigation": "Use sensitivity cases and replace placeholder HSG with documented soil data.",
        "affected outputs": "hydrologic_soil_group.tif, sensitivity_summary.csv",
    },
    "ASSUMPTION_004": {
        "description": "Simplified runoff model estimates relative post-fire runoff change.",
        "reason": "First model line is a screening workflow.",
        "risk": "Absolute runoff volumes are not calibrated forecasts.",
        "mitigation": "Report as relative/scenario screening and benchmark later with WEPPcloud-EU.",
        "affected outputs": "runoff_event_summary.csv, runoff_delta_by_event.csv",
    },
    "ASSUMPTION_005": {
        "description": "WEPPcloud-EU is benchmarked after local input stabilization.",
        "reason": "WEPP inputs should not be prepared from unstable placeholder data.",
        "risk": "Premature WEPP setup could encode incorrect boundary/burn/soil assumptions.",
        "mitigation": "Generate checklist only until manual data blockers are resolved.",
        "affected outputs": "qa/audit/README.md#weppcloud-input-checklist",
    },
    "ASSUMPTION_006": {
        "description": "Lake turbidity/Chl-a linkage is exploratory and event-aligned.",
        "reason": "Water-quality response is affected by many confounders.",
        "risk": "Causal overclaiming.",
        "mitigation": "Keep lake-quality tables exploratory and separate from runoff model calibration.",
        "affected outputs": "runoff_lake_quality_event_alignment.csv, qa/audit/README.md",
    },
}


@dataclass
class StepLog:
    script: str
    task: str
    inputs: Sequence[str]
    outputs: Sequence[str]
    status: str
    reason: str
    files_created: Sequence[str] = ()
    files_reused: Sequence[str] = ()
    qa_checks: Sequence[str] = ()
    next_action: str = "Continue pipeline."


def now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT.resolve()))
    except Exception:
        return str(p)


def ensure_dirs() -> list[Path]:
    created: list[Path] = []
    for item in REQUIRED_DIRS:
        p = ROOT / item
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(p)
    return created


def write_yaml_if_missing(path: Path, data: Mapping[str, Any]) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True


def load_yaml(path: Path, default: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True), encoding="utf-8")


def ensure_csv(path: Path, columns: Sequence[str]) -> bool:
    if path.exists():
        # Ensure a malformed empty file still gets a header.
        if path.stat().st_size == 0:
            path.write_text(",".join(columns) + "\n", encoding="utf-8")
            return True
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
    return True


def ensure_backlog_exists() -> bool:
    if BACKLOG.exists():
        return False
    BACKLOG.write_text(
        "# QA Audit\n\n"
        "_Consolidated automation status, run notes, QA summary, data dictionary, and scientific assumptions._\n\n"
        "---\n\n"
        "## Automation status updates\n\n"
        "Status values: `TODO`, `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`, `FAILED`, `SKIPPED`.\n\n"
        "| task_id | status | owner | note | updated_by |\n"
        "|---|---|---|---|---|\n\n"
        "## Automation run notes\n\n"
        "- Created consolidated QA audit file.\n",
        encoding="utf-8",
    )
    return True


def ensure_evidence_readme_exists() -> bool:
    if EVIDENCE_README.exists():
        return False
    EVIDENCE_README.write_text(
        "# Evidence Log\n\n"
        "_Consolidated source manifests, download blockers, and manual data tasks._\n\n"
        "---\n\n"
        "## Source tables\n\n"
        "- `source_manifest.csv`: source provenance rows\n"
        "- `local_data_inventory.csv`: local raw/archive inventory\n"
        "- `outlet_candidates.csv`: candidate outlet evidence\n\n"
        "## Download blockers\n\n"
        "No active blockers are recorded in this consolidated file.\n\n"
        "## Manual download tasks\n\n"
        "No active manual download tasks are recorded in this consolidated file.\n",
        encoding="utf-8",
    )
    return True


def ensure_text_file(path: Path, title: str, body: str = "") -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body}".rstrip() + "\n", encoding="utf-8")
    return True


def ensure_assumptions_file() -> bool:
    ensure_backlog_exists()
    text = BACKLOG.read_text(encoding="utf-8")
    if "## Scientific assumption register" in text:
        return False
    lines = ["", "## Scientific assumption register", ""]
    for key, fields in ASSUMPTIONS.items():
        lines.extend([f"### {key}", ""])
        for field, value in fields.items():
            lines.append(f"- **{field}:** {value}")
        lines.append("")
    BACKLOG.write_text(text.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")
    return True


def ensure_workspace() -> list[str]:
    created = [rel(p) for p in ensure_dirs()]
    for path, data in [
        (ROOT / "config/project.yaml", DEFAULT_PROJECT_CONFIG),
        (ROOT / "config/sources.yaml", DEFAULT_SOURCES_CONFIG),
        (ROOT / "config/paths.yaml", DEFAULT_PATHS_CONFIG),
    ]:
        if write_yaml_if_missing(path, data):
            created.append(rel(path))
    if ensure_backlog_exists():
        created.append(rel(BACKLOG))
    if ensure_evidence_readme_exists():
        created.append(rel(EVIDENCE_README))
    if ensure_csv(ROOT / "qa/evidence/source_manifest.csv", MANIFEST_COLUMNS):
        created.append("qa/evidence/source_manifest.csv")
    if ensure_csv(ROOT / "qa/evidence/local_data_inventory.csv", INVENTORY_COLUMNS):
        created.append("qa/evidence/local_data_inventory.csv")
    if ensure_assumptions_file():
        created.append("qa/audit/README.md#scientific-assumption-register")
    return created


def append_run_log(log: StepLog) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not RUN_LOG.exists():
        ensure_backlog_exists()
    block = [
        f"## {now_local()} — {log.script}",
        "",
        f"Task: {log.task}",
        f"Input: {'; '.join(log.inputs) if log.inputs else 'None'}",
        f"Output: {'; '.join(log.outputs) if log.outputs else 'None'}",
        f"Status: {log.status}",
        f"Reason: {log.reason}",
        f"Files created: {'; '.join(log.files_created) if log.files_created else 'None'}",
        f"Files reused: {'; '.join(log.files_reused) if log.files_reused else 'None'}",
        f"QA checks: {'; '.join(log.qa_checks) if log.qa_checks else 'None'}",
        f"Next action: {log.next_action}",
        "",
    ]
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(block))


def update_backlog(statuses: Mapping[str, str], note: str, script: str) -> None:
    ensure_backlog_exists()
    text = BACKLOG.read_text(encoding="utf-8")
    # Avoid downgrading useful terminal/partial states to SKIPPED on idempotent reruns.
    current_status: dict[str, str] = {}
    for match in re.finditer(r"\|\s*([A-Z]\d{3})\s*\|\s*(TODO|IN_PROGRESS|DONE|PARTIAL|BLOCKED|FAILED|SKIPPED)\s*\|", text):
        current_status[match.group(1)] = match.group(2)

    for task_id, requested in statuses.items():
        requested = requested.upper()
        old = current_status.get(task_id)
        new_status = requested
        if requested == "SKIPPED" and old in {"DONE", "PARTIAL", "BLOCKED"}:
            new_status = old
        pattern = re.compile(rf"(\|\s*{re.escape(task_id)}\s*\|\s*)(TODO|IN_PROGRESS|DONE|PARTIAL|BLOCKED|FAILED|SKIPPED)(\s*\|)")
        if pattern.search(text):
            text = pattern.sub(rf"\g<1>{new_status}\g<3>", text, count=1)
        else:
            if "## Automation status updates" not in text:
                text += "\n---\n\n## Automation status updates\n\n"
            text += f"| {task_id} | {new_status} | Added by {script} | See notes | Updated by automation |\n"
    if "## Automation run notes" not in text:
        text += "\n---\n\n## Automation run notes\n\n"
    joined = ", ".join(f"{k}={v}" for k, v in statuses.items())
    text += f"- {now_local()} — `{script}` updated {joined}. {note}\n"
    BACKLOG.write_text(text, encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: stringify(row.get(col, "")) for col in columns})


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def sha256_file(path: Path) -> str:
    if not path.exists() or path.is_dir():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_manifest(row: Mapping[str, Any], key_fields: Sequence[str] = ("dataset_id", "local_path")) -> None:
    path = ROOT / "qa/evidence/source_manifest.csv"
    ensure_csv(path, MANIFEST_COLUMNS)
    rows = read_csv_rows(path)
    normalized = {col: stringify(row.get(col, "")) for col in MANIFEST_COLUMNS}
    if not normalized.get("download_time_utc"):
        normalized["download_time_utc"] = now_utc()
    updated = False
    for idx, existing in enumerate(rows):
        if all(existing.get(k, "") == normalized.get(k, "") for k in key_fields):
            rows[idx] = {**existing, **normalized}
            updated = True
            break
    if not updated:
        rows.append(normalized)
    write_csv_rows(path, MANIFEST_COLUMNS, rows)


def add_blocker(
    blocker_id: str,
    dataset: str,
    attempted_source: str,
    command: str,
    failure_mode: str,
    why: str,
    manual_action: str,
    expected_path: str,
    affected: str,
) -> bool:
    path = EVIDENCE_README
    ensure_evidence_readme_exists()
    text = path.read_text(encoding="utf-8")
    if f"### {blocker_id}" in text:
        return False
    block = f"""
### {blocker_id}

- Dataset: {dataset}
- Attempted source: {attempted_source}
- Command or request attempted: {command}
- Failure mode: {failure_mode}
- Why automation cannot proceed safely: {why}
- Manual action required: {manual_action}
- Expected file path after manual download: {expected_path}
- Downstream scripts affected: {affected}
""".strip()
    path.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
    return True


def add_manual_task(
    task_id: str,
    dataset: str,
    reason: str,
    source_page: str,
    search_terms: str,
    required_filters: str,
    expected_files: str,
    where_to_place: str,
    rerun: str,
    downstream: str,
) -> bool:
    path = EVIDENCE_README
    ensure_evidence_readme_exists()
    text = path.read_text(encoding="utf-8")
    header = f"### {task_id} — {dataset}"
    if header in text:
        return False
    block = f"""
{header}

Reason automation stopped: {reason}
Source page: {source_page}
Exact search terms: {search_terms}
Required filters: {required_filters}
Expected files: {expected_files}
Where to place files: {where_to_place}
How to rerun after manual download: {rerun}
Downstream scripts: {downstream}
""".strip()
    path.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")
    return True


def project_config() -> dict[str, Any]:
    ensure_workspace()
    return load_yaml(ROOT / "config/project.yaml", DEFAULT_PROJECT_CONFIG)


def source_config() -> dict[str, Any]:
    ensure_workspace()
    return load_yaml(ROOT / "config/sources.yaml", DEFAULT_SOURCES_CONFIG)


def paths_config() -> dict[str, Any]:
    ensure_workspace()
    return load_yaml(ROOT / "config/paths.yaml", DEFAULT_PATHS_CONFIG)


def get_path(*parts: str) -> Path:
    """Resolve a project path from the paths config.

    Walks the config tree following each part.  If a part maps to a dict,
    the next part is looked up inside that dict.  Otherwise the part's value
    is used as a relative path segment.

    Usage:
        get_path("outputs", "maps")        → ROOT / "outputs/maps"
        get_path("qa", "spatial")         → ROOT / "qa/spatial"
        get_path("data", "processed")      → ROOT / "data/processed"
    """
    cfg = paths_config()
    node = cfg
    segments: list[str] = []
    for part in parts:
        if isinstance(node, dict) and part in node:
            val = node[part]
            if isinstance(val, dict):
                node = val
                continue
            elif isinstance(val, str):
                segments.append(val)
                node = val  # can't descend further
                continue
        # fallback: use part literally
        segments.append(part)
    return ROOT.joinpath(*segments)


def import_geo():
    import geopandas as gpd
    from pyproj import Transformer
    from shapely import affinity
    from shapely.geometry import LineString, Point, Polygon, box
    from shapely.ops import transform as shapely_transform

    return gpd, Transformer, affinity, LineString, Point, Polygon, box, shapely_transform




def working_crs_obj():
    from pyproj import CRS
    return CRS.from_user_input(WORKING_CRS)


def crs_to_epsg(crs: Any) -> int | None:
    if crs is None:
        return None
    try:
        return crs.to_epsg()
    except AttributeError:
        try:
            from pyproj import CRS
            return CRS.from_user_input(crs).to_epsg()
        except Exception:
            return None


def assert_crs_present(crs: Any, label: str) -> None:
    if crs is None:
        raise ValueError(f"{label} has no CRS metadata; refusing to assume coordinates are {WORKING_CRS}")


def bounds_to_crs(bounds: tuple[float, float, float, float], src_crs: str, dst_crs: str) -> tuple[float, float, float, float]:
    from rasterio.warp import transform_bounds
    return tuple(transform_bounds(src_crs, dst_crs, *bounds, densify_pts=21))


def read_vector_to_working(path_or_uri: Any, bbox_working: tuple[float, float, float, float] | None = None, **kwargs: Any):
    """Read a vector layer and return it in WORKING_CRS.

    `bbox_working` is always expressed in WORKING_CRS. The helper transforms that
    bbox into the source layer CRS before using it for IO filtering, avoiding the
    common error of clipping an EPSG:3003/25832/4326 layer with EPSG:32632 bounds.
    """
    gpd, *_ = import_geo()
    read_kwargs = dict(kwargs)
    if bbox_working is not None:
        probe = gpd.read_file(path_or_uri, rows=1)
        assert_crs_present(probe.crs, f"{path_or_uri}")
        src_crs = probe.crs
        if crs_to_epsg(src_crs) == crs_to_epsg(WORKING_CRS):
            read_kwargs["bbox"] = tuple(bbox_working)
        else:
            read_kwargs["bbox"] = bounds_to_crs(tuple(bbox_working), WORKING_CRS, src_crs)
    gdf = gpd.read_file(path_or_uri, **read_kwargs)
    assert_crs_present(gdf.crs, f"{path_or_uri}")
    return gdf.to_crs(WORKING_CRS)


def read_raster_window_to_working(path_or_uri: Any, bounds_working: tuple[float, float, float, float], resolution: float | None = None, nodata: float | int | None = None, resampling: Any | None = None):
    """Read a raster window reprojected to WORKING_CRS.

    The source raster may be EPSG:32632, EPSG:25832, EPSG:3003, EPSG:4326, or any
    CRS GDAL can transform. The returned array and transform are always in
    WORKING_CRS.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import from_bounds
    from rasterio.warp import calculate_default_transform

    res = float(resolution or project_config().get("dem", {}).get("fallback_resolution_m", 100))
    rsp = resampling or Resampling.bilinear
    with rasterio.open(path_or_uri) as src:
        assert_crs_present(src.crs, f"{path_or_uri}")
        src_crs = src.crs
        src_nodata = src.nodata if src.nodata is not None else nodata
        dst_nodata = nodata if nodata is not None else (src_nodata if src_nodata is not None else -9999.0)
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src.crs, WORKING_CRS, src.width, src.height, *src.bounds, resolution=res
        )
        with WarpedVRT(src, crs=WORKING_CRS, transform=dst_transform, width=dst_width, height=dst_height, resampling=rsp, src_nodata=src_nodata, nodata=dst_nodata) as vrt:
            window = from_bounds(*bounds_working, transform=vrt.transform).round_offsets().round_lengths()
            if window.width <= 0 or window.height <= 0:
                raise ValueError(f"Requested bounds {bounds_working} do not overlap raster {path_or_uri} after reprojection to {WORKING_CRS}")
            arr = vrt.read(1, window=window).astype("float32")
            transform = vrt.window_transform(window)
            return arr, transform, src_crs, vrt.crs

def import_raster():
    import rasterio
    from rasterio import features
    from rasterio.transform import from_origin

    return rasterio, features, from_origin


def fallback_bbox_wgs84() -> tuple[float, float, float, float]:
    cfg = project_config()
    bbox = cfg.get("aoi", {}).get("fallback_bbox_wgs84", DEFAULT_PROJECT_CONFIG["aoi"]["fallback_bbox_wgs84"])
    return float(bbox["west"]), float(bbox["south"]), float(bbox["east"]), float(bbox["north"])


def transformer_to_working():
    _, Transformer, *_ = import_geo()
    return Transformer.from_crs("EPSG:4326", WORKING_CRS, always_xy=True)


def project_point(lon: float, lat: float):
    gpd, Transformer, affinity, LineString, Point, Polygon, box, shapely_transform = import_geo()
    transformer = transformer_to_working()
    x, y = transformer.transform(lon, lat)
    return Point(x, y)


def fallback_aoi_geometry():
    gpd, Transformer, affinity, LineString, Point, Polygon, box, shapely_transform = import_geo()
    west, south, east, north = fallback_bbox_wgs84()
    geom_wgs84 = box(west, south, east, north)
    transformer = transformer_to_working()
    return shapely_transform(transformer.transform, geom_wgs84)



def crs_axis_label(axis: str) -> str:
    suffix = f"m, {WORKING_CRS}"
    return f"Easting ({suffix})" if axis.lower().startswith("x") else f"Northing ({suffix})"


def make_gdf(records: list[dict[str, Any]], geometries: list[Any], crs: str = WORKING_CRS):
    gpd, *_ = import_geo()
    return gpd.GeoDataFrame(records, geometry=geometries, crs=crs)


def write_gpkg(gdf: Any, path: Path, layer: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    gdf.to_file(path, layer=layer or path.stem, driver="GPKG")


def vector_valid(path: Path, required_crs: str | None = None) -> tuple[bool, list[str]]:
    checks: list[str] = []
    if not path.exists() or path.stat().st_size == 0:
        return False, ["missing_or_empty"]
    try:
        gpd, *_ = import_geo()
        gdf = gpd.read_file(path)
        checks.append(f"features={len(gdf)}")
        if len(gdf) == 0:
            return False, checks + ["empty_vector"]
        if gdf.geometry.is_empty.any():
            return False, checks + ["empty_geometry"]
        if required_crs:
            epsg = gdf.crs.to_epsg() if gdf.crs else None
            checks.append(f"crs=EPSG:{epsg}" if epsg else "crs=missing")
            if epsg != int(required_crs.split(":")[-1]):
                return False, checks + ["wrong_crs"]
        area = float(gdf.to_crs(WORKING_CRS).geometry.area.sum()) if gdf.crs else float(gdf.geometry.area.sum())
        checks.append(f"area_m2={area:.2f}")
        if area <= 0 and gdf.geom_type.isin(["Polygon", "MultiPolygon"]).any():
            return False, checks + ["zero_area"]
        return True, checks
    except Exception as exc:
        return False, checks + [f"open_error={type(exc).__name__}:{exc}"]


def raster_valid(path: Path, required_crs: str | None = None, require_valid_pixels: bool = False) -> tuple[bool, list[str]]:
    checks: list[str] = []
    if not path.exists() or path.stat().st_size == 0:
        return False, ["missing_or_empty"]
    try:
        rasterio, _, _ = import_raster()
        with rasterio.open(path) as ds:
            checks.extend([f"driver={ds.driver}", f"width={ds.width}", f"height={ds.height}"])
            if required_crs:
                epsg = ds.crs.to_epsg() if ds.crs else None
                checks.append(f"crs=EPSG:{epsg}" if epsg else "crs=missing")
                if epsg != int(required_crs.split(":")[-1]):
                    return False, checks + ["wrong_crs"]
            if ds.width <= 0 or ds.height <= 0:
                return False, checks + ["bad_dimensions"]
            if require_valid_pixels:
                arr = ds.read(1, masked=True)
                valid_count = int(arr.count())
                checks.append(f"valid_pixels={valid_count}")
                if valid_count <= 0:
                    return False, checks + ["no_valid_pixels"]
        return True, checks
    except Exception as exc:
        return False, checks + [f"open_error={type(exc).__name__}:{exc}"]


def write_raster(path: Path, array: np.ndarray, transform: Any, crs: str = WORKING_CRS, nodata: float | int | None = None, dtype: str | None = None) -> None:
    rasterio, _, _ = import_raster()
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(array)
    if arr.ndim != 2:
        raise ValueError("Only single-band 2D arrays are supported")
    out_dtype = dtype or str(arr.dtype)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=out_dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
        compress="deflate",
    ) as dst:
        dst.write(arr.astype(out_dtype), 1)


def grid_for_bounds(bounds: tuple[float, float, float, float], resolution: float | None = None) -> tuple[Any, int, int]:
    cfg = project_config()
    res = float(resolution or cfg.get("dem", {}).get("fallback_resolution_m", 100))
    xmin, ymin, xmax, ymax = bounds
    width = max(8, int(math.ceil((xmax - xmin) / res)))
    height = max(8, int(math.ceil((ymax - ymin) / res)))
    # Keep placeholder grids small and deterministic.
    width = min(width, 240)
    height = min(height, 240)
    res_x = (xmax - xmin) / width
    res_y = (ymax - ymin) / height
    rasterio, features, from_origin = import_raster()
    transform = from_origin(xmin, ymax, res_x, res_y)
    return transform, width, height


def raster_extent_string(path: Path) -> str:
    try:
        rasterio, _, _ = import_raster()
        with rasterio.open(path) as ds:
            b = ds.bounds
            return f"{b.left:.2f},{b.bottom:.2f},{b.right:.2f},{b.top:.2f}"
    except Exception:
        return ""


def vector_extent_string(path: Path) -> str:
    try:
        gpd, *_ = import_geo()
        gdf = gpd.read_file(path)
        b = gdf.total_bounds
        return f"{b[0]:.2f},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f}"
    except Exception:
        return ""


def register_generated_dataset(dataset_id: str, name: str, role: str, path: Path, kind: str, crs: str = WORKING_CRS, notes: str = "Generated by automation pipeline.") -> None:
    checksum = sha256_file(path) if path.exists() and path.is_file() else ""
    extent = raster_extent_string(path) if path.suffix.lower() in {".tif", ".tiff", ".img"} else vector_extent_string(path)
    upsert_manifest(
        {
            "dataset_id": dataset_id,
            "dataset_name": name,
            "role": role,
            "source_url": "local_pipeline_generated",
            "access_method": "generated",
            "license_or_terms": "Derived scaffold output; source terms inherit from inputs/placeholders",
            "download_time_utc": now_utc(),
            "local_path": rel(path),
            "raw_or_processed": kind,
            "crs": crs,
            "resolution_or_scale": "see file metadata",
            "spatial_extent": extent,
            "temporal_extent": "2019 workflow context",
            "checksum_sha256": checksum,
            "status": "generated",
            "notes": notes,
        }
    )


def register_blocked_dataset(dataset_id: str, name: str, role: str, source_url: str, expected_path: str, notes: str) -> None:
    upsert_manifest(
        {
            "dataset_id": dataset_id,
            "dataset_name": name,
            "role": role,
            "source_url": source_url,
            "access_method": "manual_or_authenticated_required",
            "license_or_terms": "Manual verification required",
            "download_time_utc": now_utc(),
            "local_path": expected_path,
            "raw_or_processed": "raw",
            "crs": "unknown_until_downloaded",
            "resolution_or_scale": "unknown_until_downloaded",
            "spatial_extent": "Lake Varese / Monte Martica target area",
            "temporal_extent": "2018-2020 target depending on dataset",
            "checksum_sha256": "",
            "status": "manual_required",
            "notes": notes,
        }
    )


def register_reused_dataset(dataset_id: str, name: str, role: str, path: Path, crs: str, notes: str) -> None:
    upsert_manifest(
        {
            "dataset_id": dataset_id,
            "dataset_name": name,
            "role": role,
            "source_url": "existing_local_file",
            "access_method": "reused_local",
            "license_or_terms": "Unknown; verify local dataset terms before publication",
            "download_time_utc": now_utc(),
            "local_path": rel(path),
            "raw_or_processed": "raw",
            "crs": crs,
            "resolution_or_scale": "see source metadata",
            "spatial_extent": raster_extent_string(path) if path.suffix.lower() in {".tif", ".tiff", ".img"} else vector_extent_string(path),
            "temporal_extent": "unknown_local_dataset",
            "checksum_sha256": sha256_file(path),
            "status": "reused_local",
            "notes": notes,
        }
    )


def read_first_existing_vector(paths: Sequence[Path]):
    gpd, *_ = import_geo()
    for path in paths:
        if path.exists():
            try:
                return gpd.read_file(path), path
            except Exception:
                continue
    return None, None


def mark_standard_manual_blockers() -> None:
    sources = source_config().get("sources", {})
    add_blocker(
        "BLOCKER_FIRE_PERIMETER_OFFICIAL",
        "Regione Lombardia Aree percorse dal fuoco 2019",
        sources.get("lombardia_geoportal_home", {}).get("url", "Regione Lombardia Geoportale"),
        "02_discover_sources.py / 03_download_open_data.py service discovery only",
        "Stable machine-downloadable layer name or direct file URL not confirmed safely by scaffold.",
        "Avoid guessing WFS layer names or scraping interactive portals.",
        "Manually locate/download official 2019 fire perimeter near Monte Martica, or add verified WFS layer to config/sources.yaml.",
        "data/raw/fire_perimeter/official_aree_percorse_dal_fuoco_2019.*",
        "04_prepare_spatial_frame.py, 07_prepare_burn_severity.py, 11_run_simplified_runoff.py",
    )
    add_manual_task(
        "TASK_FIRE_PERIMETER_2019",
        "Official 2019 fire perimeter",
        "Official vector service/file was not confirmed without manual portal interaction.",
        sources.get("lombardia_geoportal_home", {}).get("url", "Regione Lombardia Geoportale"),
        "Aree percorse dal fuoco Monte Martica 2019 Varese Induno Olona Valganna",
        "Year 2019; location Monte Martica / Varese / Induno Olona / Valganna; vector format preferred",
        "GeoPackage, Shapefile, or GeoJSON with perimeter polygons and year attributes",
        "data/raw/fire_perimeter/",
        "python scripts/01_inventory_existing_data.py && python scripts/run_pipeline.py --from 04 --to 12",
        "Spatial frame, burn proxy QA, runoff units",
    )
    add_blocker(
        "BLOCKER_DUSAF_2018",
        "DUSAF 6.0 2018 land cover",
        sources.get("lombardia_geoportal_home", {}).get("url", "Regione Lombardia Geoportale"),
        "02_discover_sources.py / 03_download_open_data.py service discovery only",
        "Direct stable download endpoint not configured in config/sources.yaml.",
        "Avoid accepting unknown terms or scraping dynamic portal pages.",
        "Download/register DUSAF 2018 or add a verified direct URL/API endpoint.",
        "data/raw/landcover/dusaf_2018.*",
        "08_prepare_landcover.py, 11_run_simplified_runoff.py",
    )
    add_manual_task(
        "TASK_DUSAF_2018",
        "DUSAF 2018 land cover",
        "Land-cover source requires manual endpoint verification or download selection.",
        sources.get("lombardia_geoportal_home", {}).get("url", "Regione Lombardia Geoportale"),
        "DUSAF 6.0 2018 Lombardia download shapefile gpkg",
        "DUSAF 2018; vector; Lombardia; license terms accepted by user if required",
        "Vector dataset covering Varese/Monte Martica",
        "data/raw/landcover/",
        "python scripts/01_inventory_existing_data.py && python scripts/run_pipeline.py --from 08 --to 12",
        "Land cover and runoff units",
    )
    add_blocker(
        "BLOCKER_ARPA_WEATHER",
        "ARPA Lombardia station precipitation near Varese / Monte Martica",
        sources.get("arpa_lombardia", {}).get("url", "ARPA Lombardia"),
        "02_discover_sources.py / 10_prepare_weather.py discovery only",
        "Station time series commonly require request form, human station selection, or terms review.",
        "Do not impersonate a user, bypass forms, or assume station availability.",
        "Request/download hourly or daily precipitation station data for 2019-2020 near Varese/Monte Martica.",
        "data/raw/weather/arpa_precipitation_2019_2020.csv",
        "10_prepare_weather.py, 11_run_simplified_runoff.py",
    )
    add_manual_task(
        "TASK_ARPA_WEATHER_2019_2020",
        "ARPA precipitation events",
        "Automated request/download path was not safely available in the scaffold.",
        sources.get("arpa_lombardia", {}).get("url", "ARPA Lombardia"),
        "precipitazione Varese stazione 2019 2020 ARPA Lombardia Monte Martica",
        "Hourly preferred; daily acceptable; 2019-01-01 to 2020-12-31; nearest reliable stations to burned area",
        "CSV/XLSX with date-time, precipitation amount, station id/name/coordinates/elevation",
        "data/raw/weather/",
        "python scripts/01_inventory_existing_data.py && python scripts/run_pipeline.py --from 10 --to 12",
        "Weather event extraction and runoff model",
    )
    add_blocker(
        "BLOCKER_SOIL_HYDRAULIC",
        "EU soil hydraulic properties / SoilGrids-derived HSG",
        sources.get("soilgrids_api", {}).get("url", "Soil data source"),
        "02_discover_sources.py / 03_download_open_data.py discovery only",
        "Soil source selection and license/scale assumptions require explicit review before scientific use.",
        "Avoid silently using coarse fallback data as local hydraulic truth.",
        "Download/register soil hydraulic properties or approve SoilGrids workflow and texture-to-HSG assumptions.",
        "data/raw/soil/soil_hydraulic_or_texture.*",
        "09_prepare_soil.py, 11_run_simplified_runoff.py",
    )
    add_manual_task(
        "TASK_SOIL_HYDRAULIC",
        "Soil hydraulic / texture data",
        "Soil source and derived HSG assumptions require manual approval.",
        sources.get("soilgrids_api", {}).get("url", "Soil data source"),
        "SoilGrids clay sand silt bulk density hydraulic Lombardia Varese",
        "Coverage over catchment; document resolution and depth interval; verify license",
        "GeoTIFF/NetCDF/CSV rasters or vectors usable for HSG derivation",
        "data/raw/soil/",
        "python scripts/01_inventory_existing_data.py && python scripts/run_pipeline.py --from 09 --to 12",
        "Soil processing and runoff model",
    )


def dataframe_to_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        df = pd.DataFrame(list(rows))
        df.to_csv(path, index=False)
    else:
        write_csv_rows(path, columns, rows)


def file_nonempty(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def write_markdown_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")).replace("|", "\\|") for c in columns) + " |")
    return "\n".join(lines) + "\n"

# --- Local raw ZIP/source helpers added for the 2026-05-22 improvement iteration ---
RAW_ZIP_DIR = ROOT / "data/raw/zip"


def register_raw_archive(dataset_id: str, name: str, role: str, path: Path, notes: str, temporal_extent: str = "") -> None:
    """Register an immutable local raw archive or folder in the source manifest."""
    upsert_manifest(
        {
            "dataset_id": dataset_id,
            "dataset_name": name,
            "role": role,
            "source_url": "existing_local_raw_archive",
            "access_method": "reused_local_raw_zip_or_folder",
            "license_or_terms": "Verify original source terms before publication; local copy supplied by project owner.",
            "download_time_utc": now_utc(),
            "local_path": rel(path),
            "raw_or_processed": "raw",
            "crs": "see source metadata",
            "resolution_or_scale": "see source metadata",
            "spatial_extent": "Lake Varese / Monte Martica AOI or Lombardia coverage depending on dataset",
            "temporal_extent": temporal_extent,
            "checksum_sha256": sha256_file(path) if path.is_file() else "",
            "status": "reused_local",
            "notes": notes,
        }
    )


def write_data_gap_assessment(rows: Sequence[Mapping[str, Any]]) -> Path:
    path = BACKLOG
    ensure_backlog_exists()
    lines = [
        "## Data gap assessment",
        "",
        f"Updated: {now_local()}",
        "",
        "Principle: only data required to make the first simplified event-runoff workflow scientifically defensible are treated as essential. Lake-quality linkage and WEPPcloud remain phase-2/benchmark tasks.",
        "",
        "| dataset | priority | local status | decision | path_or_next_action |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {dataset} | {priority} | {local_status} | {decision} | {path_or_next_action} |".format(
                dataset=str(row.get("dataset", "")).replace("|", "\\|"),
                priority=str(row.get("priority", "")).replace("|", "\\|"),
                local_status=str(row.get("local_status", "")).replace("|", "\\|"),
                decision=str(row.get("decision", "")).replace("|", "\\|"),
                path_or_next_action=str(row.get("path_or_next_action", "")).replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "### Resolved prior blockers",
            "",
            "- Official fire perimeter: resolved by `data/raw/zip/Aree_percorse_dal_fuoco_REGIONE_LOMBARDIA.zip`.",
            "- DUSAF land cover: resolved by `data/raw/zip/DUSAF6_REGIONE_LOMBARDIA.zip`.",
            "- Soil input: resolved for this iteration by local SoilGrids composites under `data/raw/zip/soilgrids_lake_varese/`.",
            "- Weather input: resolved for this iteration by ARPA-style RW ZIP files for station 907 / sensor 8228 for 2019-2020.",
            "- Sentinel-2 products: local SAFE ZIPs are present; JP2OpenJPEG GDAL support is unavailable, so `07_prepare_burn_severity.py` reads JP2 imagery through Pillow and georeferences it from SAFE metadata.",
            "",
            "### Remaining non-blocking limitations",
            "",
            "- DEM-derived catchment/outlet is still a candidate and must be reviewed against official hydrography before final scientific claims.",
            "- dNBR remains a remote-sensing burn-severity proxy, not field-validated soil burn severity.",
            "- Lake turbidity/chlorophyll-a linkage remains optional phase 2.",
        ]
    )
    section = "\n".join(lines) + "\n"
    text = path.read_text(encoding="utf-8")
    pattern = r"\n## Data gap assessment\n.*?(?=\n## |\Z)"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, "\n" + section.rstrip(), text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + section.rstrip()
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Canonical SCS-CN runoff equation (single source of truth for all scripts)
# ---------------------------------------------------------------------------

def scs_runoff_mm(precip_mm, curve_number):
    """SCS-CN runoff depth with standard initial abstraction λ = 0.20.

    Vectorized: accepts float or numpy array for precip_mm and curve_number.
    Returns runoff in mm.  CN is clamped to [1, 99].
    """
    cn = np.clip(np.asarray(curve_number, dtype=float), 1.0, 99.0)
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    p = np.asarray(precip_mm, dtype=float)
    return np.where(p > ia, (p - ia) ** 2 / (p + 0.8 * s), 0.0)


def scs_runoff_mm_ia(precip_mm, curve_number, lam=0.20):
    """SCS-CN runoff depth with variable initial abstraction ratio Ia = lam * S.

    λ = 0.20 → standard SCS; λ = 0.05 → alternative (Hawkins et al.).
    """
    cn = np.clip(np.asarray(curve_number, dtype=float), 1.0, 99.0)
    s = 25400.0 / cn - 254.0
    ia = lam * s
    p = np.asarray(precip_mm, dtype=float)
    return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - lam) * s), 0.0)


# ---------------------------------------------------------------------------
# Shared study-area layer loader (reduces duplicated gpd.read_file across scripts)
# ---------------------------------------------------------------------------

def load_study_layers():
    """Return a dict of pre-loaded, CRS-verified study area vector layers.

    Each call reads fresh from disk (no caching). All layers reprojected to
    WORKING_CRS (EPSG:32632).
    """
    gpd, _, _, _, Point, _, _, _ = import_geo()
    layers: dict[str, Any] = {}

    def _load(key, rel_path):
        p = ROOT / rel_path
        if p.exists():
            gdf = gpd.read_file(p)
            if gdf.crs and gdf.crs.to_epsg() != 32632:
                gdf = gdf.to_crs(WORKING_CRS)
            layers[key] = gdf
        else:
            layers[key] = None

    _load("catchment", "data/processed/boundary/catchment_utm32.gpkg")
    _load("fire", "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg")
    _load("hydro", "data/processed/hydrography/streams_lombardia_varese_utm32.gpkg")
    _load("dem_streams", "data/processed/dem/streams_from_dem.gpkg")
    _load("lake", "data/processed/boundary/lake_varese_boundary.gpkg")
    _load("aoi", "data/processed/boundary/processing_aoi_utm32.gpkg")
    _load("runoff_units", "data/processed/model_inputs/runoff_units.gpkg")
    _load("landcover", "data/processed/landcover/landcover_hydrologic_class.gpkg")

    # Outlet point from canonical coordinates
    from pyproj import Transformer
    t = Transformer.from_crs(WGS84, WORKING_CRS, always_xy=True)
    x, y = t.transform(OUTLET_LON, OUTLET_LAT)
    layers["outlet_pt"] = Point(x, y)

    return layers
