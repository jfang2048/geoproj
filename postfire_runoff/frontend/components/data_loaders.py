"""Frontend data loaders for the canonical output contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from postfire_runoff.frontend.components.paths import DATA_PROCESSED, OUTPUTS, ROOT, TABLES

RUNOFF_DELTA = TABLES / "runoff_delta_by_event.csv"
RUNOFF_EVENTS = TABLES / "runoff_event_summary.csv"
RUNOFF_UNITS = TABLES / "runoff_units.csv"
RAINFALL_EVENTS = DATA_PROCESSED / "weather/post_fire_rainfall_events.csv"
BURN_AREA = TABLES / "burn_severity_area_summary.csv"
BURN_ENSEMBLE = BURN_AREA  # compatibility alias; no separate ensemble table is generated.
WEPP_SUMMARY = TABLES / "weppcloud_summary.csv"
LAKE_STATUS = TABLES / "lake_wq_status.csv"
LAKE_ANOMALIES = TABLES / "lake_wq_event_anomalies.csv"
LAKE_SELECTED = TABLES / "lake_wq_event_image_availability.csv"
LAKE_CONTEXT = TABLES / "lake_wq_status.csv"
RUN_METADATA = OUTPUTS / "run_metadata.json"

CATCHMENT = DATA_PROCESSED / "boundary/catchment_utm32.gpkg"
FIRE_PERIMETER = DATA_PROCESSED / "fire_perimeter/fire_perimeter_utm32.gpkg"
HYDROGRAPHY = DATA_PROCESSED / "hydrography/streams_lombardia_varese_utm32.gpkg"
LAKE_BOUNDARY = DATA_PROCESSED / "boundary/lake_varese_boundary.gpkg"
RUNOFF_UNITS_GPKG = DATA_PROCESSED / "model_inputs/runoff_units.gpkg"
LAKE_ROIS = DATA_PROCESSED / "water_quality/lake_varese_wq_rois_utm32.gpkg"
DEM_STREAMS = DATA_PROCESSED / "dem/streams_from_dem.gpkg"
BURN_RASTER = DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif"
DNBR_RASTER = DATA_PROCESSED / "burn/dnbr_2019_monte_martica.tif"
DEM_RASTER = DATA_PROCESSED / "dem/dem_utm32.tif"


def load_csv_safe(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    return None if df.empty else df


def load_json_safe(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_vector_safe(path: Path, to_crs: str = "EPSG:4326") -> gpd.GeoDataFrame | None:
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            return None
        if gdf.crs.to_string() != to_crs and gdf.crs.to_epsg() != int(to_crs.split(":")[-1]):
            gdf = gdf.to_crs(to_crs)
        return gdf
    except Exception:
        return None


def load_raster_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with rasterio.open(path) as ds:
            return {
                "crs": str(ds.crs),
                "bounds": ds.bounds,
                "width": ds.width,
                "height": ds.height,
                "nodata": ds.nodata,
                "dtype": str(ds.dtypes[0]),
                "transform": list(ds.transform)[:6],
            }
    except Exception:
        return None


def load_raster_class_table(path: Path, class_names: dict[int, str]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        with rasterio.open(path) as ds:
            arr = ds.read(1)
            pixel_area = abs(ds.transform.a * ds.transform.e)
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
    except Exception:
        return None


def burn_class_table() -> pd.DataFrame | None:
    return load_raster_class_table(BURN_RASTER, {
        0: "unburned / unchanged",
        1: "low burn severity proxy",
        2: "moderate burn severity proxy",
        3: "high burn severity proxy",
        255: "NoData",
    })


def _area_ha(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            return None
        if gdf.crs.to_epsg() != 32632:
            gdf = gdf.to_crs("EPSG:32632")
        return float(gdf.geometry.area.sum() / 10000.0)
    except Exception:
        return None


def _max_or_none(df: pd.DataFrame | None, column: str) -> float | None:
    if df is None or column not in df.columns:
        return None
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.max()) if len(values) else None


def core_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "catchment_area_ha": _area_ha(CATCHMENT),
        "fire_perimeter_ha": _area_ha(FIRE_PERIMETER),
        "fire_inside_catchment_ha": None,
        "fire_inside_pct": None,
        "conservative_burned_ha": None,
        "conservative_max_dq_mm": None,
        "upper_bound_burned_ha": None,
        "upper_bound_max_dq_mm": None,
        "rainfall_event_count": None,
        "response_unit_count": None,
        "lake_wq_data_limited": True,
    }

    if CATCHMENT.exists() and FIRE_PERIMETER.exists():
        try:
            catchment = gpd.read_file(CATCHMENT).to_crs("EPSG:32632")
            fire = gpd.read_file(FIRE_PERIMETER).to_crs("EPSG:32632")
            fire_area = float(fire.geometry.area.sum() / 10000.0)
            inside = float(fire.geometry.intersection(catchment.geometry.union_all()).area.sum() / 10000.0)
            metrics["fire_inside_catchment_ha"] = inside
            metrics["fire_inside_pct"] = inside / fire_area * 100.0 if fire_area > 0 else None
        except Exception:
            pass

    burn_area = load_csv_safe(BURN_AREA)
    if burn_area is not None and {"burn_class", "area_ha"}.issubset(burn_area.columns):
        burned = burn_area[pd.to_numeric(burn_area["burn_class"], errors="coerce") > 0]
        metrics["conservative_burned_ha"] = float(pd.to_numeric(burned["area_ha"], errors="coerce").sum()) if len(burned) else 0.0
    delta = load_csv_safe(RUNOFF_DELTA)
    metrics["conservative_max_dq_mm"] = _max_or_none(delta, "delta_runoff_mm")
    metrics["upper_bound_burned_ha"] = None
    metrics["upper_bound_max_dq_mm"] = None

    rain = load_csv_safe(RAINFALL_EVENTS)
    metrics["rainfall_event_count"] = len(rain) if rain is not None else None
    units = load_csv_safe(RUNOFF_UNITS)
    metrics["response_unit_count"] = len(units) if units is not None else None

    wepp = load_csv_safe(WEPP_SUMMARY)
    if wepp is not None:
        metrics["wepp_available"] = True
        sed = pd.to_numeric(wepp.get("sediment_quantity"), errors="coerce") if "sediment_quantity" in wepp else pd.Series(dtype=float)
        runoff = pd.to_numeric(wepp.get("runoff_quantity"), errors="coerce") if "runoff_quantity" in wepp else pd.Series(dtype=float)
        metrics["wepp_sediment_min"] = float(sed.min()) if len(sed.dropna()) else None
        metrics["wepp_sediment_max"] = float(sed.max()) if len(sed.dropna()) else None
        metrics["wepp_runoff_min"] = float(runoff.min()) if len(runoff.dropna()) else None
        metrics["wepp_runoff_max"] = float(runoff.max()) if len(runoff.dropna()) else None
    else:
        metrics["wepp_available"] = False

    lake_status = load_csv_safe(LAKE_STATUS)
    if lake_status is not None and "status" in lake_status.columns:
        status_values = set(lake_status["status"].dropna().astype(str))
        metrics["lake_wq_data_limited"] = "available" not in status_values
    return metrics
