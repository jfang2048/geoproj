"""Run preprocessing, runoff calculation, and report generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import DISPLAY_CRS, WORKING_CRS
from app.core.errors import DependencyMissingError, MissingRequiredInputError, ProcessingError
from app.core.logging import RunLogger
from app.gis.display import write_vector_display_geojson
from app.gis.normalize import assert_raster_alignment, normalize_raster, normalize_vector
from app.gis.validation import read_valid_rainfall_csv
from app.models.categories import CATEGORY_RULES, DataKind, InputCategory
from app.reports.run_report import write_run_report
from app.services.hydrology import (
    BURN_CLASS_NAME,
    baseline_cn,
    burned_cn,
    classify_dnbr,
    normalize_burn_class,
    normalize_hsg,
    normalize_landcover,
    parameter_sources,
    scs_runoff_mm,
)
from app.storage.manifest import (
    add_warning,
    load_manifest,
    record_output,
    record_parameters,
    write_manifest,
)
from app.storage.paths import ensure_run_layout, require_run_dir

PREPROCESS_REQUIRED = [
    InputCategory.dem,
    InputCategory.fire_perimeter,
    InputCategory.burn_severity,
    InputCategory.land_cover,
    InputCategory.rainfall,
]
MODEL_REQUIRED = PREPROCESS_REQUIRED + [InputCategory.hydrologic_soil_group]


def preprocess_run(run_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    parameters = parameters or {}
    base = ensure_run_layout(run_id)
    logger = RunLogger(run_id, base / "logs" / "run.log")
    logger.record("preprocessing", "Starting preprocessing.")
    manifest = load_manifest(run_id)
    _require_inputs(manifest, PREPROCESS_REQUIRED, step="preprocessing")
    record_parameters(run_id, {"working_crs": WORKING_CRS, "display_crs": DISPLAY_CRS, **parameters})

    normalized: dict[str, Path] = {}
    dem_input = _input_path(run_id, InputCategory.dem)
    dem_norm = base / "normalized" / "dem.tif"
    path, warnings = normalize_raster(dem_input, dem_norm, InputCategory.dem)
    normalized[InputCategory.dem.value] = path
    _record_warnings(run_id, warnings)
    record_output(run_id, "normalized_dem", path, kind="raster", description="DEM normalized to analysis CRS.")

    for category in [
        InputCategory.fire_perimeter,
        InputCategory.burn_severity,
        InputCategory.land_cover,
        InputCategory.hydrologic_soil_group,
        InputCategory.water_body,
        InputCategory.hydrography,
    ]:
        try:
            src = _input_path(run_id, category)
        except MissingRequiredInputError:
            continue
        kind = manifest["inputs"][category.value]["metadata"].get("kind")
        if kind == "vector":
            out = base / "normalized" / f"{category.value}.gpkg"
            path, warnings = normalize_vector(src, out, category)
        elif kind == "raster":
            out = base / "normalized" / f"{category.value}.tif"
            path, warnings = normalize_raster(src, out, category, reference_path=dem_norm)
        else:
            continue
        normalized[category.value] = path
        _record_warnings(run_id, warnings)
        record_output(run_id, f"normalized_{category.value}", path, kind=kind, description=f"{CATEGORY_RULES[category].label} normalized to analysis CRS.")
        display_path = _display_path(base, category.value)
        _write_display_for_normalized(category, path, kind, display_path)
        record_output(run_id, f"display_{category.value}", display_path, kind="display_layer", description=f"{CATEGORY_RULES[category].label} display layer.")

    raster_layers = [p for p in normalized.values() if p.suffix.lower() in {".tif", ".tiff"}]
    assert_raster_alignment([normalized[InputCategory.dem.value]] + [p for p in raster_layers if p != normalized[InputCategory.dem.value]])

    catchment = _make_catchment_boundary(base / "normalized" / "fire_perimeter.gpkg", base / "normalized" / "catchment_boundary.gpkg")
    record_output(run_id, "catchment_boundary", catchment, kind="vector", description="Screening catchment boundary derived from uploaded fire perimeter.")
    catchment_display = _display_path(base, "catchment_boundary")
    write_vector_display_geojson(catchment, catchment_display, properties={"layer": "catchment_boundary"})
    record_output(run_id, "display_catchment_boundary", catchment_display, kind="display_layer", description="Catchment boundary display layer.")

    rain_src = _input_path(run_id, InputCategory.rainfall)
    rain_df = read_valid_rainfall_csv(rain_src)
    rain_out = base / "normalized" / "rainfall_events.csv"
    rain_df.to_csv(rain_out, index=False)
    record_output(run_id, "rainfall_event_summary", rain_out, kind="table", description="Validated rainfall event table.")

    qa = {
        "run_id": run_id,
        "working_crs": WORKING_CRS,
        "normalized_inputs": {k: str(v.relative_to(base)) for k, v in normalized.items()},
        "warnings": load_manifest(run_id).get("warnings", []),
    }
    qa_path = base / "outputs" / "qa" / "preprocessing_qa.json"
    qa_path.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_output(run_id, "preprocessing_qa", qa_path, kind="qa", description="Preprocessing QA metadata.")
    manifest = load_manifest(run_id)
    manifest["status"] = "preprocessed"
    write_manifest(run_id, manifest)
    logger.record("preprocessing", "Preprocessing completed.", output_manifest_path=base / "run_manifest.json")
    return manifest


def run_model(run_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    parameters = parameters or {}
    base = require_run_dir(run_id)
    logger = RunLogger(run_id, base / "logs" / "run.log")
    logger.record("modeling", "Starting SCS-CN screening model.")
    manifest = load_manifest(run_id)
    explicit_hsg_fallback = parameters.get("hsg_fallback")
    if explicit_hsg_fallback and str(explicit_hsg_fallback).strip().upper() not in {"A", "B", "C", "D"}:
        raise ProcessingError("hsg_fallback must be one of A, B, C, or D.")
    if InputCategory.hydrologic_soil_group.value not in manifest.get("inputs", {}) and not explicit_hsg_fallback:
        raise MissingRequiredInputError(
            "Missing required file: hydrologic soil group. Upload HSG data or pass an explicit hsg_fallback parameter.",
            details={"category": InputCategory.hydrologic_soil_group.value},
        )
    required = MODEL_REQUIRED if not explicit_hsg_fallback else PREPROCESS_REQUIRED
    _require_inputs(manifest, required, step="modeling")
    if not (base / "normalized" / "catchment_boundary.gpkg").exists():
        raise ProcessingError("No preprocessed boundary found. Run preprocessing first.")

    record_parameters(run_id, {**parameter_sources(), **parameters, "model_scope": "screening-level SCS-CN event runoff"})
    catchment = _read_vector(base / "normalized" / "catchment_boundary.gpkg")
    land = _load_analysis_layer(base, InputCategory.land_cover, "landcover_class")
    burn = _load_analysis_layer(base, InputCategory.burn_severity, "burn_class")
    if explicit_hsg_fallback:
        hsg = catchment.copy()
        hsg["hsg"] = normalize_hsg(explicit_hsg_fallback)
        add_warning(run_id, f"Explicit HSG fallback used for this run: {hsg['hsg'].iloc[0]}.")
    else:
        hsg = _load_analysis_layer(base, InputCategory.hydrologic_soil_group, "hsg")

    catchment_geom = catchment.geometry.union_all()
    land = _clip_nonempty(land, catchment_geom)
    burn = _clip_nonempty(burn, catchment_geom)
    hsg = _clip_nonempty(hsg, catchment_geom)
    units = _build_response_units(land, burn, hsg)
    if units.empty:
        raise ProcessingError("No response units were generated. Check that land cover, burn severity, HSG, and boundary overlap.")

    units["area_m2"] = units.geometry.area.astype(float)
    units = units[units["area_m2"] > 0].copy()
    units["area_ha"] = units["area_m2"] / 10000.0
    units["unit_id"] = [f"RU_{i:04d}" for i in range(1, len(units) + 1)]
    units["landcover_class"] = units["landcover_class"].map(normalize_landcover)
    units["hsg"] = units["hsg"].map(normalize_hsg)
    units["burn_class"] = units["burn_class"].map(normalize_burn_class).astype(int)
    units["burn_class_name"] = units["burn_class"].map(BURN_CLASS_NAME)
    units["baseline_cn"] = [baseline_cn(lc, h) for lc, h in zip(units["landcover_class"], units["hsg"])]
    units["burned_cn"] = [burned_cn(base_cn, burn_cls) for base_cn, burn_cls in zip(units["baseline_cn"], units["burn_class"])]

    rainfall = pd.read_csv(base / "normalized" / "rainfall_events.csv")
    lam = float(parameters.get("initial_abstraction_ratio", 0.20))
    if not (0.0 <= lam <= 0.30):
        raise ProcessingError("initial_abstraction_ratio must be between 0.0 and 0.30.")
    baseline_rows: list[dict[str, Any]] = []
    burned_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    unit_event_rows: list[dict[str, Any]] = []
    total_area = float(units["area_m2"].sum())
    for _, event in rainfall.iterrows():
        event_id = str(event["event_id"])
        p = float(event["rainfall_mm"])
        q_base = scs_runoff_mm(p, units["baseline_cn"].to_numpy(), lam=lam).astype(float)
        q_burn = scs_runoff_mm(p, units["burned_cn"].to_numpy(), lam=lam).astype(float)
        delta = q_burn - q_base
        base_volume = float((q_base * units["area_m2"].to_numpy()).sum() / 1000.0)
        burn_volume = float((q_burn * units["area_m2"].to_numpy()).sum() / 1000.0)
        base_mm = float((q_base * units["area_m2"].to_numpy()).sum() / total_area)
        burn_mm = float((q_burn * units["area_m2"].to_numpy()).sum() / total_area)
        baseline_rows.append(_event_row(event, "baseline", base_mm, base_volume))
        burned_rows.append(_event_row(event, "burned", burn_mm, burn_volume))
        delta_rows.append(
            {
                "event_id": event_id,
                "rainfall_mm": p,
                "baseline_runoff_mm": base_mm,
                "burned_runoff_mm": burn_mm,
                "delta_runoff_mm": burn_mm - base_mm,
                "baseline_volume_m3": base_volume,
                "burned_volume_m3": burn_volume,
                "delta_volume_m3": burn_volume - base_volume,
                "units": "mm and m3",
            }
        )
        for unit, qb, qf, dq in zip(units.itertuples(), q_base, q_burn, delta):
            unit_event_rows.append(
                {
                    "event_id": event_id,
                    "unit_id": unit.unit_id,
                    "rainfall_mm": p,
                    "baseline_runoff_mm": float(qb),
                    "burned_runoff_mm": float(qf),
                    "delta_runoff_mm": float(dq),
                    "delta_volume_m3": float(dq * unit.area_m2 / 1000.0),
                }
            )
    outputs_dir = base / "outputs"
    tables_dir = outputs_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = tables_dir / "baseline_runoff.csv"
    burned_path = tables_dir / "burned_scenario_runoff.csv"
    delta_path = tables_dir / "delta_runoff.csv"
    unit_event_path = tables_dir / "unit_event_runoff.csv"
    pd.DataFrame(baseline_rows).to_csv(baseline_path, index=False)
    pd.DataFrame(burned_rows).to_csv(burned_path, index=False)
    pd.DataFrame(delta_rows).to_csv(delta_path, index=False)
    pd.DataFrame(unit_event_rows).to_csv(unit_event_path, index=False)
    for key, path, desc in [
        ("baseline_runoff_table", baseline_path, "Baseline runoff table with mm and m3 units."),
        ("burned_runoff_table", burned_path, "Burned scenario runoff table with mm and m3 units."),
        ("delta_runoff_table", delta_path, "Runoff delta table with mm and m3 units."),
        ("unit_event_runoff_table", unit_event_path, "Per-unit runoff table."),
    ]:
        record_output(run_id, key, path, kind="table", description=desc)

    units_path = outputs_dir / "response_units.gpkg"
    units.to_file(units_path, driver="GPKG")
    record_output(run_id, "response_units", units_path, kind="vector", description="Response units in analysis CRS.")
    units_display = _display_path(base, "response_units")
    units.to_crs(DISPLAY_CRS).to_file(units_display, driver="GeoJSON")
    record_output(run_id, "display_response_units", units_display, kind="display_layer", description="Response units display layer.")

    delta_display = _write_delta_display(units, pd.DataFrame(unit_event_rows), base)
    record_output(run_id, "display_runoff_delta", delta_display, kind="display_layer", description="Runoff delta display layer for the largest rainfall event.")

    qa_report = _write_model_qa(run_id, base, units, pd.DataFrame(delta_rows))
    record_output(run_id, "qa_report_json", qa_report, kind="qa", description="Model QA report.")
    report_path = write_run_report(run_id)
    record_output(run_id, "run_report", report_path, kind="report", description="Run report in Markdown.")

    manifest = load_manifest(run_id)
    manifest["status"] = "modeled"
    write_manifest(run_id, manifest)
    logger.record("modeling", "Modeling completed.", response_units=len(units), output_manifest_path=base / "run_manifest.json")
    return manifest


def generate_qa_report(run_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    base = require_run_dir(run_id)
    logger = RunLogger(run_id, base / "logs" / "run.log")
    logger.record("qa_report", "Writing QA report.")
    report_path = write_run_report(run_id)
    record_output(run_id, "run_report", report_path, kind="report", description="Run report in Markdown.")
    manifest = load_manifest(run_id)
    manifest["status"] = manifest.get("status", "qa_reported")
    write_manifest(run_id, manifest)
    return manifest


def _require_inputs(manifest: dict[str, Any], categories: list[InputCategory], *, step: str) -> None:
    inputs = manifest.get("inputs", {})
    missing = [CATEGORY_RULES[c].label for c in categories if c.value not in inputs]
    if missing:
        raise MissingRequiredInputError(
            f"Missing required file for {step}: {', '.join(missing)}.",
            details={"missing": missing},
        )


def _input_path(run_id: str, category: InputCategory) -> Path:
    base = require_run_dir(run_id)
    manifest = load_manifest(run_id)
    try:
        return base / manifest["inputs"][category.value]["path"]
    except KeyError as exc:
        raise MissingRequiredInputError(f"Missing required file: {category.value}.", details={"category": category.value}) from exc


def _record_warnings(run_id: str, warnings: list[str]) -> None:
    for warning in warnings:
        add_warning(run_id, warning)


def _display_path(base: Path, layer_id: str) -> Path:
    return base / "outputs" / "display" / f"{layer_id}.geojson"


def _write_display_for_normalized(category: InputCategory, path: Path, kind: str, output: Path) -> None:
    if kind == "vector":
        write_vector_display_geojson(path, output, properties={"layer": category.value})
    elif kind == "raster":
        _raster_to_display_polygons(path, category, output)
    else:
        raise ProcessingError(f"Unsupported display kind for {category.value}: {kind}")


def _make_catchment_boundary(fire_path: Path, output_path: Path) -> Path:
    gdf = _read_vector(fire_path)
    geom = gdf.geometry.union_all()
    if geom.is_empty:
        raise ProcessingError("Fire perimeter produced an empty boundary.")
    import geopandas as gpd

    out = gpd.GeoDataFrame(
        [{"boundary_source": "dissolved_uploaded_fire_perimeter", "notes": "Screening boundary, not a calibrated hydrologic catchment."}],
        geometry=[geom],
        crs=WORKING_CRS,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(output_path, driver="GPKG")
    return output_path


def _read_vector(path: Path):
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required for vector processing.") from exc
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ProcessingError(f"Vector layer has no CRS: {path}")
    if str(gdf.crs) != WORKING_CRS:
        gdf = gdf.to_crs(WORKING_CRS)
    return gdf


def _load_analysis_layer(base: Path, category: InputCategory, value_field: str):
    vector = base / "normalized" / f"{category.value}.gpkg"
    raster = base / "normalized" / f"{category.value}.tif"
    if vector.exists():
        gdf = _read_vector(vector)
        if value_field not in gdf.columns:
            raise ProcessingError(f"{category.value} is missing {value_field} after preprocessing.")
        return gdf[[value_field, "geometry"]].copy()
    if raster.exists():
        return _raster_to_polygons(raster, category, value_field)
    raise MissingRequiredInputError(f"Normalized {category.value} layer is missing. Run preprocessing first.")


def _clip_nonempty(gdf, geom):
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required for clipping.") from exc
    clipped = gpd.clip(gdf, geom)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()].copy()
    if clipped.empty:
        raise ProcessingError("Spatial layer does not overlap the catchment boundary.")
    return clipped


def _build_response_units(land, burn, hsg):
    try:
        import geopandas as gpd
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("geopandas is required for overlay.") from exc
    a = gpd.overlay(land[["landcover_class", "geometry"]], burn[["burn_class", "geometry"]], how="intersection", keep_geom_type=False)
    a = a[~a.geometry.is_empty & a.geometry.notna()].copy()
    b = gpd.overlay(a, hsg[["hsg", "geometry"]], how="intersection", keep_geom_type=False)
    b = b[~b.geometry.is_empty & b.geometry.notna()].copy()
    return b


def _raster_to_polygons(path: Path, category: InputCategory, value_field: str):
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import shape
    except Exception as exc:  # pragma: no cover
        raise DependencyMissingError("rasterio and geopandas are required for raster polygon conversion.") from exc
    records = []
    geoms = []
    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata
        mask = data != nodata if nodata is not None else data == data
        for geom, value in shapes(data, mask=mask, transform=src.transform):
            classified = _classify_raster_value(category, value)
            records.append({value_field: classified})
            geoms.append(shape(geom))
        crs = src.crs
    if not records:
        raise ProcessingError(f"Raster {path.name} did not produce valid polygons.")
    return gpd.GeoDataFrame(records, geometry=geoms, crs=crs).to_crs(WORKING_CRS)


def _raster_to_display_polygons(path: Path, category: InputCategory, output: Path) -> None:
    value_field = {
        InputCategory.burn_severity: "burn_class",
        InputCategory.land_cover: "landcover_class",
        InputCategory.hydrologic_soil_group: "hsg",
    }.get(category, "value")
    gdf = _raster_to_polygons(path, category, value_field)
    gdf.to_crs(DISPLAY_CRS).to_file(output, driver="GeoJSON")


def _classify_raster_value(category: InputCategory, value: Any) -> Any:
    try:
        fval = float(value)
    except Exception:
        return value
    if category == InputCategory.burn_severity:
        if fval in (0, 1, 2, 3):
            return int(fval)
        return classify_dnbr(fval)
    if category == InputCategory.land_cover:
        return normalize_landcover(fval)
    if category == InputCategory.hydrologic_soil_group:
        return normalize_hsg(fval)
    return value


def _event_row(event: pd.Series, scenario: str, runoff_mm: float, volume_m3: float) -> dict[str, Any]:
    rainfall = float(event["rainfall_mm"])
    return {
        "event_id": str(event["event_id"]),
        "scenario": scenario,
        "start_date": str(event["start_date"]),
        "end_date": str(event["end_date"]),
        "rainfall_mm": rainfall,
        "runoff_mm": runoff_mm,
        "runoff_volume_m3": volume_m3,
        "runoff_coefficient": 0.0 if rainfall == 0 else runoff_mm / rainfall,
        "units": "mm and m3",
        "model_scope": "screening-level SCS-CN event runoff; not discharge forecast",
    }


def _write_delta_display(units, unit_events: pd.DataFrame, base: Path) -> Path:
    if unit_events.empty:
        raise ProcessingError("No unit-event rows available for delta map.")
    max_event = unit_events.sort_values("rainfall_mm", ascending=False).iloc[0]["event_id"]
    selected = unit_events[unit_events["event_id"] == max_event][["unit_id", "delta_runoff_mm", "delta_volume_m3", "event_id"]]
    display = units.merge(selected, on="unit_id", how="left").to_crs(DISPLAY_CRS)
    output = _display_path(base, "runoff_delta")
    display.to_file(output, driver="GeoJSON")
    return output


def _write_model_qa(run_id: str, base: Path, units, delta: pd.DataFrame) -> Path:
    payload = {
        "run_id": run_id,
        "working_crs": WORKING_CRS,
        "area_calculation_crs": WORKING_CRS,
        "response_unit_count": int(len(units)),
        "response_unit_area_ha": float(units["area_ha"].sum()),
        "max_delta_runoff_mm": float(delta["delta_runoff_mm"].max()) if not delta.empty else 0.0,
        "warnings": load_manifest(run_id).get("warnings", []),
        "checks": [
            "All area calculations used projected CRS EPSG:32632.",
            "Display layers were written in EPSG:4326.",
            "Categorical raster resampling rule is nearest neighbor.",
            "SCS-CN parameters are recorded in run_manifest.json.",
        ],
    }
    out = base / "outputs" / "qa" / "model_qa.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
