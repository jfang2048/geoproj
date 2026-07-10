"""Core runoff pipeline for the canonical data/output contract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import numpy as np
import pandas as pd

from postfire_runoff.backend.config import ConfigError, LoadedConfig, load_config
from postfire_runoff.backend.gis.burn_severity import load_burn_polygons, write_burn_raster
from postfire_runoff.backend.gis.normalize import SpatialInputError, read_vector, save_vector, to_working_crs, require_overlap
from postfire_runoff.backend.gis.response_units import build_response_units, summarize_burn_area
from postfire_runoff.backend.hydrology.curve_numbers import DEFAULT_CN2_TABLE
from postfire_runoff.backend.hydrology.scs_cn import aggregate_response_unit_runoff, validate_initial_abstraction
from postfire_runoff.backend.io.checksums import sha256_file
from postfire_runoff.backend.io.manifest import add_error, add_input, add_output, add_warning, create_run_manifest, set_succeeded, write_manifest
from postfire_runoff.backend.io.paths import ensure_runtime_dirs
from postfire_runoff.backend.services.weppcloud import import_weppcloud_export


@dataclass(frozen=True)
class PipelineResult:
    status: str
    metadata_path: Path
    outputs: dict[str, Path]
    warnings: list[str]


class PipelineError(RuntimeError):
    """Raised when required runoff processing cannot be completed."""


def run_pipeline(
    config_path: str | Path = "config/project.yaml",
    project_root: str | Path | None = None,
    force: bool = False,
) -> PipelineResult:
    cfg = load_config(config_path, project_root)
    dirs = ensure_runtime_dirs(cfg.root)
    metadata_path = cfg.root / "outputs/run_metadata.json"
    manifest = create_run_manifest(parameters={
        "config": str(cfg.path),
        "force": bool(force),
        "working_crs": cfg.get("project", "crs_working", default="EPSG:32632"),
    })
    outputs: dict[str, Path] = {}

    try:
        result = _run_pipeline(cfg, manifest, force=force)
        outputs.update(result)
        set_succeeded(manifest)
    except Exception as exc:
        add_error(manifest, str(exc))
        write_manifest(manifest, metadata_path)
        raise PipelineError(str(exc)) from exc

    for name, path in outputs.items():
        add_output(manifest, name, path, _checksum_if_file(path))
    write_manifest(manifest, metadata_path)
    return PipelineResult(status=manifest["status"], metadata_path=metadata_path, outputs=outputs, warnings=manifest["warnings"])


def _run_pipeline(cfg: LoadedConfig, manifest: dict[str, Any], force: bool) -> dict[str, Path]:
    working_crs = cfg.get("project", "crs_working", default="EPSG:32632")
    inputs = _required_inputs(cfg)
    for name, path in inputs.items():
        add_input(manifest, name, path, _checksum_if_file(path))

    catchment = to_working_crs(read_vector(inputs["catchment_boundary"], "catchment boundary"), working_crs)
    fire = to_working_crs(read_vector(inputs["fire_perimeter"], "official fire perimeter"), working_crs)
    landcover = to_working_crs(read_vector(inputs["land_cover"], "land cover"), working_crs)
    hsg = to_working_crs(read_vector(inputs["hsg"], "hydrologic soil group"), working_crs)
    burn = load_burn_polygons(
        inputs["burn_severity"],
        column=cfg.get("burn_classification", "column", default="burn_class"),
        working_crs=working_crs,
    )

    for label, layer in (("official fire perimeter", fire), ("land cover", landcover), ("hydrologic soil group", hsg), ("burn severity", burn)):
        require_overlap(layer, catchment, label, "catchment")

    paths = _output_paths(cfg.root)
    if force:
        _remove_known_outputs(paths)

    catchment_out = save_vector(catchment, paths["catchment"])
    fire_out = save_vector(fire, paths["fire_perimeter"])

    burn_adjustments = {int(k): float(v) for k, v in (cfg.get("runoff", "burn_curve_number_adjustment", default={0: 0, 1: 4, 2: 8, 3: 12}) or {}).items()}
    cn_lookup = cfg.get("runoff", "cn2_lookup", default=None) or DEFAULT_CN2_TABLE
    units, diagnostics = build_response_units(
        catchment=catchment,
        landcover=landcover,
        hsg=hsg,
        burn=burn,
        landcover_column=cfg.get("landcover", "column", default="landcover_class"),
        hsg_column=cfg.get("soil", "hsg_column", default="hsg"),
        burn_adjustments=burn_adjustments,
        cn_lookup=cn_lookup,
    )
    if diagnostics.uncovered_area_m2 > max(1.0, diagnostics.catchment_area_m2 * 0.01):
        add_warning(
            manifest,
            f"Response-unit inputs cover {diagnostics.covered_area_m2:.2f} m² of "
            f"{diagnostics.catchment_area_m2:.2f} m² catchment; uncovered area is "
            f"{diagnostics.uncovered_area_m2:.2f} m².",
        )
    manifest["spatial_metadata"] = {
        "catchment_area_m2": diagnostics.catchment_area_m2,
        "response_unit_covered_area_m2": diagnostics.covered_area_m2,
        "response_unit_uncovered_area_m2": diagnostics.uncovered_area_m2,
        "response_unit_overlap_error_m2": diagnostics.overlap_error_m2,
    }

    save_vector(units, paths["runoff_units_gpkg"])
    units_csv = units.drop(columns="geometry").copy()
    units_csv.to_csv(paths["runoff_units_csv"], index=False)

    raster_resolution = float(cfg.get("processing", "burn_raster_resolution_m", default=30.0))
    burn_raster = write_burn_raster(burn, catchment, paths["burn_raster"], resolution_m=raster_resolution)

    rainfall = normalize_rainfall(inputs["rainfall_events"])
    paths["rainfall_processed"].parent.mkdir(parents=True, exist_ok=True)
    rainfall.to_csv(paths["rainfall_processed"], index=False)

    lam = validate_initial_abstraction(float(cfg.get("runoff", "initial_abstraction_ratio", default=0.20)))
    event_summary = compute_event_summary(rainfall, units, lam)
    event_summary.to_csv(paths["runoff_event_summary"], index=False)
    delta_cols = [
        "event_id", "start_date", "end_date", "rainfall_mm", "baseline_runoff_mm", "burned_runoff_mm",
        "delta_runoff_mm", "baseline_volume_m3", "burned_volume_m3", "delta_volume_m3", "response_unit_area_m2",
    ]
    event_summary[delta_cols].to_csv(paths["runoff_delta_by_event"], index=False)

    burn_area = summarize_burn_area(units, diagnostics.catchment_area_m2)
    burn_area.to_csv(paths["burn_area_summary"], index=False)

    optional = manifest.setdefault("optional_stages", {})
    wepp_export = cfg.input_path("weppcloud_export", required=False)
    if wepp_export is not None and wepp_export.exists():
        try:
            import_weppcloud_export(wepp_export, paths["weppcloud_summary"])
            optional["weppcloud"] = {"status": "available", "normalized_table": str(paths["weppcloud_summary"])}
        except Exception as exc:
            optional["weppcloud"] = {"status": "invalid_export", "message": str(exc)}
            add_warning(manifest, f"WEPPcloud export was not imported: {exc}")
    else:
        optional["weppcloud"] = {"status": "unavailable", "message": "No configured WEPPcloud user export."}

    optional.setdefault("lake_wq", {"status": "unavailable", "message": "Run optional lake stage when local pre/post imagery is configured."})

    return {
        "catchment": catchment_out,
        "fire_perimeter": fire_out,
        "burn_raster": burn_raster,
        "runoff_units_gpkg": paths["runoff_units_gpkg"],
        "rainfall_processed": paths["rainfall_processed"],
        "runoff_units_csv": paths["runoff_units_csv"],
        "runoff_event_summary": paths["runoff_event_summary"],
        "runoff_delta_by_event": paths["runoff_delta_by_event"],
        "burn_area_summary": paths["burn_area_summary"],
        **({"weppcloud_summary": paths["weppcloud_summary"]} if paths["weppcloud_summary"].exists() else {}),
    }


def _required_inputs(cfg: LoadedConfig) -> dict[str, Path]:
    names = ["catchment_boundary", "fire_perimeter", "burn_severity", "land_cover", "hsg", "rainfall_events"]
    resolved = {name: cfg.input_path(name, required=True) for name in names}
    missing = [name for name, path in resolved.items() if path is None or not path.exists()]
    if missing:
        detail = ", ".join(f"inputs.{name}" for name in missing)
        raise ConfigError(f"Required input file(s) missing or unmapped: {detail}")
    return {k: v for k, v in resolved.items() if v is not None}


def _output_paths(root: Path) -> dict[str, Path]:
    return {
        "catchment": root / "data/processed/boundary/catchment_utm32.gpkg",
        "fire_perimeter": root / "data/processed/fire_perimeter/fire_perimeter_utm32.gpkg",
        "burn_raster": root / "data/processed/burn/burn_severity_proxy_uint8.tif",
        "runoff_units_gpkg": root / "data/processed/model_inputs/runoff_units.gpkg",
        "rainfall_processed": root / "data/processed/weather/post_fire_rainfall_events.csv",
        "runoff_units_csv": root / "outputs/tables/runoff_units.csv",
        "runoff_event_summary": root / "outputs/tables/runoff_event_summary.csv",
        "runoff_delta_by_event": root / "outputs/tables/runoff_delta_by_event.csv",
        "burn_area_summary": root / "outputs/tables/burn_severity_area_summary.csv",
        "weppcloud_summary": root / "outputs/tables/weppcloud_summary.csv",
    }


def _remove_known_outputs(paths: Mapping[str, Path]) -> None:
    for path in paths.values():
        if path.exists() and path.is_file():
            path.unlink()


def normalize_rainfall(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Rainfall event table not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("Rainfall event table is empty")
    aliases = {
        "rainfall_mm": "rainfall_mm",
        "total_precip_mm": "rainfall_mm",
        "precip_mm": "rainfall_mm",
        "precipitation_mm": "rainfall_mm",
        "event_start": "start_date",
        "event_end": "end_date",
    }
    rename = {c: aliases[c] for c in df.columns if c in aliases and c != aliases[c]}
    df = df.rename(columns=rename)
    required = ["event_id", "start_date", "end_date", "rainfall_mm"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Rainfall event table missing columns: {', '.join(missing)}")
    out = df[required].copy()
    out["event_id"] = out["event_id"].astype(str)
    if out["event_id"].duplicated().any():
        raise ValueError("Rainfall event IDs must be unique")
    out["start_date"] = pd.to_datetime(out["start_date"], errors="raise").dt.date.astype(str)
    out["end_date"] = pd.to_datetime(out["end_date"], errors="raise").dt.date.astype(str)
    out["rainfall_mm"] = pd.to_numeric(out["rainfall_mm"], errors="raise")
    if not np.all(np.isfinite(out["rainfall_mm"])) or (out["rainfall_mm"] < 0).any():
        raise ValueError("Rainfall depths must be finite and non-negative")
    return out


def compute_event_summary(rainfall: pd.DataFrame, units: gpd.GeoDataFrame, lam: float) -> pd.DataFrame:
    baseline = units["baseline_cn"].astype(float).to_numpy()
    burned = units["burned_cn"].astype(float).to_numpy()
    areas = units["area_m2"].astype(float).to_numpy()
    rows = []
    for _, event in rainfall.iterrows():
        agg = aggregate_response_unit_runoff(float(event["rainfall_mm"]), baseline, burned, areas, lam)
        rows.append({
            "event_id": event["event_id"],
            "start_date": event["start_date"],
            "end_date": event["end_date"],
            "rainfall_mm": float(event["rainfall_mm"]),
            "baseline_runoff_mm": agg.baseline_runoff_mm,
            "burned_runoff_mm": agg.burned_runoff_mm,
            "delta_runoff_mm": agg.delta_runoff_mm,
            "baseline_volume_m3": agg.baseline_volume_m3,
            "burned_volume_m3": agg.burned_volume_m3,
            "delta_volume_m3": agg.delta_volume_m3,
            "response_unit_area_m2": agg.area_m2,
            "initial_abstraction_ratio": lam,
        })
    return pd.DataFrame(rows)


def _checksum_if_file(path: Path) -> str:
    try:
        return sha256_file(path) if path.exists() and path.is_file() else ""
    except Exception:
        return ""
