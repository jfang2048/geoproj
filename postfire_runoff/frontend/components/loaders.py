"""Load generated project outputs for the Streamlit interface."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from postfire_runoff.frontend.components.paths import DATA_PROCESSED, OUTPUTS, TABLES

RUNOFF_DELTA = TABLES / "runoff_delta_by_event.csv"
RUNOFF_EVENTS = TABLES / "runoff_event_summary.csv"
RUNOFF_UNITS = TABLES / "runoff_units.csv"
RAINFALL_EVENTS = DATA_PROCESSED / "weather/post_fire_rainfall_events.csv"
BURN_AREA = TABLES / "burn_severity_area_summary.csv"
WEPP_SUMMARY = TABLES / "weppcloud_summary.csv"
RUN_METADATA = OUTPUTS / "run_metadata.json"

CATCHMENT = DATA_PROCESSED / "boundary/catchment_utm32.gpkg"
FIRE_PERIMETER = DATA_PROCESSED / "fire_perimeter/fire_perimeter_utm32.gpkg"
RUNOFF_UNITS_GPKG = DATA_PROCESSED / "model_inputs/runoff_units.gpkg"
BURN_RASTER = DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif"


class DataLoadError(RuntimeError):
    """Raised when an existing generated file cannot be parsed."""


def load_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise DataLoadError(f"Could not read CSV {path}: {exc}") from exc
    return None if df.empty else df


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise DataLoadError(f"Could not read JSON {path}: {exc}") from exc


def load_vector(path: Path, to_crs: str = "EPSG:4326") -> gpd.GeoDataFrame | None:
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        raise DataLoadError(f"Could not read vector {path}: {exc}") from exc
    if gdf.empty:
        return None
    if gdf.crs is None:
        raise DataLoadError(f"Vector {path} has no CRS")
    if gdf.crs.to_string() != to_crs and gdf.crs.to_epsg() != int(to_crs.split(":")[-1]):
        try:
            gdf = gdf.to_crs(to_crs)
        except Exception as exc:
            raise DataLoadError(f"Could not reproject {path} to {to_crs}: {exc}") from exc
    return gdf


def load_raster_class_table(path: Path, class_names: dict[int, str]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        with rasterio.open(path) as ds:
            arr = ds.read(1)
            pixel_area = abs(ds.transform.a * ds.transform.e)
    except Exception as exc:
        raise DataLoadError(f"Could not read raster {path}: {exc}") from exc
    valid = arr != 255
    total = int(np.count_nonzero(valid))
    rows = []
    for code, name in sorted(class_names.items()):
        count = int(np.count_nonzero(arr == code))
        denom = total if code != 255 else arr.size
        rows.append({
            "class_code": code,
            "class_name": name,
            "pixel_count": count,
            "area_ha": round(count * pixel_area / 10000.0, 2),
            "percent": round(count / denom * 100.0, 2) if denom > 0 else 0.0,
        })
    return pd.DataFrame(rows)


def burn_class_table() -> pd.DataFrame | None:
    return load_raster_class_table(BURN_RASTER, {
        0: "unburned",
        1: "low burn severity",
        2: "moderate burn severity",
        3: "high burn severity",
        255: "NoData",
    })


def core_metrics() -> dict[str, Any]:
    errors: list[str] = []
    metrics: dict[str, Any] = {
        "catchment_area_ha": _area_or_error(CATCHMENT, errors),
        "fire_perimeter_ha": _area_or_error(FIRE_PERIMETER, errors),
        "fire_inside_catchment_ha": None,
        "fire_inside_pct": None,
        "burned_area_ha": None,
        "max_delta_q_mm": None,
        "max_delta_volume_m3": None,
        "rainfall_event_count": None,
        "response_unit_count": None,
        "wepp_available": False,
        "errors": errors,
    }

    try:
        if CATCHMENT.exists() and FIRE_PERIMETER.exists():
            catchment = gpd.read_file(CATCHMENT).to_crs("EPSG:32632")
            fire = gpd.read_file(FIRE_PERIMETER).to_crs("EPSG:32632")
            fire_area = float(fire.geometry.area.sum() / 10000.0)
            inside = float(fire.geometry.intersection(catchment.geometry.union_all()).area.sum() / 10000.0)
            metrics["fire_inside_catchment_ha"] = inside
            metrics["fire_inside_pct"] = inside / fire_area * 100.0 if fire_area > 0 else None
    except Exception as exc:
        metrics["errors"].append(f"Could not summarize fire/catchment area: {exc}")

    burn_area = load_csv(BURN_AREA)
    if burn_area is not None and {"burn_class", "area_ha"}.issubset(burn_area.columns):
        burned = burn_area[pd.to_numeric(burn_area["burn_class"], errors="coerce") > 0]
        metrics["burned_area_ha"] = float(pd.to_numeric(burned["area_ha"], errors="coerce").sum()) if len(burned) else 0.0

    delta = load_csv(RUNOFF_DELTA)
    metrics["max_delta_q_mm"] = _max_or_none(delta, "delta_runoff_mm")
    metrics["max_delta_volume_m3"] = _max_or_none(delta, "delta_volume_m3")

    rain = load_csv(RAINFALL_EVENTS)
    metrics["rainfall_event_count"] = len(rain) if rain is not None else None
    units = load_csv(RUNOFF_UNITS)
    metrics["response_unit_count"] = len(units) if units is not None else None

    wepp = load_csv(WEPP_SUMMARY)
    if wepp is not None:
        metrics["wepp_available"] = True
        sed = pd.to_numeric(wepp.get("sediment_quantity"), errors="coerce") if "sediment_quantity" in wepp else pd.Series(dtype=float)
        runoff = pd.to_numeric(wepp.get("runoff_quantity"), errors="coerce") if "runoff_quantity" in wepp else pd.Series(dtype=float)
        metrics["wepp_sediment_min"] = float(sed.min()) if len(sed.dropna()) else None
        metrics["wepp_sediment_max"] = float(sed.max()) if len(sed.dropna()) else None
        metrics["wepp_runoff_min"] = float(runoff.min()) if len(runoff.dropna()) else None
        metrics["wepp_runoff_max"] = float(runoff.max()) if len(runoff.dropna()) else None
    return metrics


def _area_or_error(path: Path, errors: list[str]) -> float | None:
    try:
        return _area_ha(path)
    except DataLoadError as exc:
        errors.append(str(exc))
        return None


def _area_ha(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            raise DataLoadError(f"Vector {path} has no CRS")
        if gdf.crs.to_epsg() != 32632:
            gdf = gdf.to_crs("EPSG:32632")
        return float(gdf.geometry.area.sum() / 10000.0)
    except DataLoadError:
        raise
    except Exception as exc:
        raise DataLoadError(f"Could not calculate area for {path}: {exc}") from exc


def _max_or_none(df: pd.DataFrame | None, column: str) -> float | None:
    if df is None or column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.max()) if len(values) else None
