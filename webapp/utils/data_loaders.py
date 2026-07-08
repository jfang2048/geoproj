"""Central data loaders for the webapp — reads project CSV, vector, and raster outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

from webapp.utils.paths import ROOT, TABLES, DATA_PROCESSED, QA_SPATIAL, LATEX

# ── CSV table paths ──────────────────────────────────────────────────────
RUNOFF_DELTA = TABLES / "runoff_delta_by_event.csv"
RUNOFF_EVENTS = TABLES / "runoff_event_summary.csv"
RUNOFF_UNITS = TABLES / "runoff_units.csv"
RAINFALL_EVENTS = TABLES / "post_fire_rainfall_events.csv"
BURN_ENSEMBLE = TABLES / "burn_severity_ensemble_summary.csv"
BURN_AREA = TABLES / "burn_severity_area_summary.csv"
LAKE_ANOMALIES = TABLES / "lake_wq_event_anomalies.csv"
LAKE_SELECTED = TABLES / "lake_response_selected_events.csv"
LAKE_CONTEXT = TABLES / "lake_wq_analytical_context_by_period.csv"

# ── Vector paths ─────────────────────────────────────────────────────────
CATCHMENT = DATA_PROCESSED / "boundary/catchment_utm32.gpkg"
FIRE_PERIMETER = DATA_PROCESSED / "fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
HYDROGRAPHY = DATA_PROCESSED / "hydrography/streams_lombardia_varese_utm32.gpkg"
LAKE_BOUNDARY = DATA_PROCESSED / "boundary/lake_varese_boundary.gpkg"
RUNOFF_UNITS_GPKG = DATA_PROCESSED / "model_inputs/runoff_units.gpkg"
LAKE_ROIS = DATA_PROCESSED / "water_quality/lake_varese_wq_rois_utm32.gpkg"
DEM_STREAMS = DATA_PROCESSED / "dem/streams_from_dem.gpkg"

# ── Raster paths ─────────────────────────────────────────────────────────
BURN_RASTER = DATA_PROCESSED / "burn/burn_severity_proxy_uint8.tif"
DNBR_RASTER = DATA_PROCESSED / "burn/dnbr_2019_monte_martica.tif"
DEM_RASTER = DATA_PROCESSED / "dem/dem_utm32.tif"

# ── QA / metadata paths ──────────────────────────────────────────────────
QA_SPATIAL_JSON = QA_SPATIAL / "quantitative_spatial_qa_summary.json"


def load_csv_safe(path: Path) -> pd.DataFrame | None:
    """Load a CSV if it exists and is non-empty; return None otherwise."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_vector_safe(path: Path, to_crs: str = "EPSG:4326") -> gpd.GeoDataFrame | None:
    """Load a vector file, reproject to target CRS for web display. Returns None on failure."""
    if not path.exists():
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            return None
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(to_crs)
        return gdf
    except Exception:
        return None


def load_raster_metadata(path: Path) -> dict[str, Any] | None:
    """Read raster metadata (CRS, bounds, shape, nodata) without loading full array."""
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
    """Count pixels per class in a categorical raster. Returns DataFrame with class counts."""
    if not path.exists():
        return None
    try:
        with rasterio.open(path) as ds:
            arr = ds.read(1)
            pixel_area = abs(ds.transform.a * ds.transform.e)
        total = arr.size
        rows = []
        for code, name in sorted(class_names.items()):
            count = int(np.count_nonzero(arr == code))
            rows.append({
                "class_code": code,
                "class_name": name,
                "pixel_count": count,
                "area_ha": round(count * pixel_area / 10000.0, 2),
                "percent": round(count / total * 100, 2) if total > 0 else 0,
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


# ── Core metric extractors ───────────────────────────────────────────────

def core_metrics() -> dict[str, Any]:
    """Extract key project metrics from available data. Falls back to known values."""
    metrics: dict[str, Any] = {}

    # Catchment area from vector
    catchment = load_vector_safe(CATCHMENT)
    if catchment is not None:
        gdf_utm = gpd.read_file(CATCHMENT)
        if gdf_utm.crs and gdf_utm.crs.to_epsg() != 32632:
            gdf_utm = gdf_utm.to_crs("EPSG:32632")
        metrics["catchment_area_ha"] = round(gdf_utm.geometry.area.sum() / 10000.0, 2)
    else:
        metrics["catchment_area_ha"] = 1311.76

    # Fire perimeter
    fire = load_vector_safe(FIRE_PERIMETER)
    if fire is not None:
        gdf_utm = gpd.read_file(FIRE_PERIMETER)
        if gdf_utm.crs and gdf_utm.crs.to_epsg() != 32632:
            gdf_utm = gdf_utm.to_crs("EPSG:32632")
        metrics["fire_perimeter_ha"] = round(gdf_utm.geometry.area.sum() / 10000.0, 2)
        if catchment is not None:
            fire_in = gdf_utm.geometry.intersection(
                gpd.read_file(CATCHMENT).to_crs("EPSG:32632").geometry.union_all()
            ).area.sum() / 10000.0
            metrics["fire_inside_catchment_ha"] = round(fire_in, 2)
            metrics["fire_inside_pct"] = round(fire_in / metrics["fire_perimeter_ha"] * 100, 1)
    else:
        metrics["fire_perimeter_ha"] = 376.25
        metrics["fire_inside_catchment_ha"] = 280.14
        metrics["fire_inside_pct"] = 74.5

    # Burn ensemble
    ens = load_csv_safe(BURN_ENSEMBLE)
    if ens is not None:
        scenario_col = next((c for c in ens.columns if "scenario" in c.lower()), None)
        area_col = next((c for c in ens.columns if "area" in c.lower() and "ha" in c.lower()), None)
        runoff_col = next((c for c in ens.columns if "runoff" in c.lower() and "max" in c.lower()), None)
        if scenario_col and area_col and runoff_col:
            for _, row in ens.iterrows():
                s = str(row[scenario_col])
                if "conservative" in s:
                    metrics["conservative_burned_ha"] = float(row[area_col])
                    metrics["conservative_max_dq_mm"] = float(row[runoff_col])
                elif "relaxed" in s:
                    metrics["relaxed_burned_ha"] = float(row[area_col])
                    metrics["relaxed_max_dq_mm"] = float(row[runoff_col])
                elif "upper" in s or "perimeter" in s:
                    metrics["upper_bound_burned_ha"] = float(row[area_col])
                    metrics["upper_bound_max_dq_mm"] = float(row[runoff_col])

    if "conservative_burned_ha" not in metrics:
        metrics["conservative_burned_ha"] = 23.80
        metrics["conservative_max_dq_mm"] = 0.282
        metrics["upper_bound_burned_ha"] = 280.76
        metrics["upper_bound_max_dq_mm"] = 5.505

    # Rain events count
    rain = load_csv_safe(RAINFALL_EVENTS)
    metrics["rainfall_event_count"] = len(rain) if rain is not None else 92

    # Runoff units count
    ru = load_csv_safe(RUNOFF_UNITS)
    metrics["response_unit_count"] = len(ru) if ru is not None else 11

    # WEPPcloud (fixed from benchmark)
    metrics["wepp_sediment_undisturbed"] = 293.0
    metrics["wepp_sediment_disturbed"] = 652.6
    metrics["wepp_sediment_pct_change"] = 122.7
    metrics["wepp_discharge_undisturbed"] = 2124
    metrics["wepp_discharge_disturbed"] = 2125

    # Lake WQ status
    anomalies = load_csv_safe(LAKE_ANOMALIES)
    if anomalies is not None and "quality_flag" in anomalies.columns:
        flags = set(anomalies["quality_flag"].dropna())
        metrics["lake_wq_data_limited"] = "MISSING_LOCAL_IMAGE" in flags
        metrics["lake_wq_anomaly_rows"] = len(anomalies)
    else:
        metrics["lake_wq_data_limited"] = True
        metrics["lake_wq_anomaly_rows"] = 30

    return metrics
