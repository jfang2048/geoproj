"""Dynamic pydeck map layers built from project vector/raster data."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import transform_bounds

from postfire_runoff.webapp.components.data_loaders import (
    CATCHMENT, FIRE_PERIMETER, HYDROGRAPHY, LAKE_BOUNDARY,
    RUNOFF_UNITS_GPKG, DEM_STREAMS, BURN_RASTER, load_vector_safe,
)

# ── Colour palette ───────────────────────────────────────────────────────
CATCHMENT_COLOR = [0, 0, 0, 200]          # black outline
CATCHMENT_FILL = [200, 220, 240, 40]      # light blue fill
FIRE_COLOR = [217, 95, 14, 200]           # orange
FIRE_FILL = [217, 95, 14, 40]
LAKE_COLOR = [43, 140, 190, 200]          # blue
LAKE_FILL = [43, 140, 190, 60]
HYDRO_COLOR = [49, 130, 189, 180]         # steel blue
STREAM_COLOR = [107, 174, 214, 160]       # lighter blue
OUTLET_COLOR = [227, 74, 51, 255]         # red
CN_ADJ_COLORS = {
    0: [150, 150, 150, 200],
    4: [254, 196, 79, 220],
    8: [217, 95, 14, 220],
    12: [227, 74, 51, 220],
}
BURN_CLASS_COLORS = {
    0: [220, 220, 220, 180],
    1: [254, 235, 156, 220],
    2: [253, 174, 97, 220],
    3: [227, 74, 51, 220],
}


def _to_geojson_features(gdf: gpd.GeoDataFrame, properties: list[str] | None = None) -> list[dict]:
    """Convert a GeoDataFrame to a list of GeoJSON-like feature dicts for pydeck."""
    result = gdf.__geo_interface__
    features = []
    for feat in result["features"]:
        props = feat.get("properties", {})
        if properties is not None:
            props = {k: props.get(k, "") for k in properties}
        features.append({
            "type": "Feature",
            "geometry": feat["geometry"],
            "properties": props,
        })
    return features


def catchment_layer(visible: bool = True) -> dict | None:
    gdf = load_vector_safe(CATCHMENT)
    if gdf is None:
        return None
    return {
        "name": "Catchment",
        "visible": visible,
        "data": _to_geojson_features(gdf, ["fid"]),
        "pickable": True,
    }


def fire_perimeter_layer(visible: bool = True) -> dict | None:
    gdf = load_vector_safe(FIRE_PERIMETER)
    if gdf is None:
        return None
    return {
        "name": "Official Fire",
        "visible": visible,
        "data": _to_geojson_features(gdf),
        "pickable": True,
    }


def lake_layer(visible: bool = True) -> dict | None:
    gdf = load_vector_safe(LAKE_BOUNDARY)
    if gdf is None:
        return None
    return {
        "name": "Lake boundary",
        "visible": visible,
        "data": _to_geojson_features(gdf),
        "pickable": True,
    }


def hydrography_layer(visible: bool = False) -> dict | None:
    gdf = load_vector_safe(HYDROGRAPHY)
    if gdf is None:
        return None
    return {
        "name": "Hydrography",
        "visible": visible,
        "data": _to_geojson_features(gdf),
        "pickable": False,
    }


def dem_streams_layer(visible: bool = False) -> dict | None:
    gdf = load_vector_safe(DEM_STREAMS)
    if gdf is None:
        return None
    return {
        "name": "DEM Streams",
        "visible": visible,
        "data": _to_geojson_features(gdf),
        "pickable": False,
    }


def runoff_units_layer(color_by: str = "cn_adjustment", visible: bool = True) -> tuple[dict | None, str]:
    """Build a response-units layer. Returns (layer_dict, tooltip_html)."""
    gdf_utm = None
    if RUNOFF_UNITS_GPKG.exists():
        try:
            gdf_utm = gpd.read_file(RUNOFF_UNITS_GPKG)
        except Exception:
            return None, ""
    if gdf_utm is None:
        return None, ""

    if gdf_utm.crs and gdf_utm.crs.to_epsg() != 4326:
        gdf = gdf_utm.to_crs("EPSG:4326")
    else:
        gdf = gdf_utm

    # Compute CN adjustment if not already present
    if "baseline_parameter" in gdf.columns and "burned_parameter" in gdf.columns:
        gdf["cn_adjustment"] = gdf["burned_parameter"].astype(float) - gdf["baseline_parameter"].astype(float)
    elif color_by == "cn_adjustment":
        color_by = "burn_class"

    # Map color column
    color_col = color_by
    if color_by == "cn_adjustment":
        # Bin into categories
        def _cn_color(v):
            v = float(v)
            for threshold, color in sorted(CN_ADJ_COLORS.items(), reverse=True):
                if v >= threshold:
                    return color
            return CN_ADJ_COLORS[0]
        gdf["_color"] = gdf["cn_adjustment"].apply(_cn_color)
    elif color_by in ("burn_class",):
        gdf["_color"] = gdf[color_by].apply(
            lambda v: BURN_CLASS_COLORS.get(int(v), [150, 150, 150, 200])
        )
    else:
        # Numeric column: use a simple gradient
        if color_by in gdf.columns:
            vals = gdf[color_by].astype(float)
            vmin, vmax = vals.min(), vals.max()
            if vmax > vmin:
                norm = (vals - vmin) / (vmax - vmin)
                gdf["_color"] = norm.apply(
                    lambda n: [int(43 + n * 174), int(140 - n * 97), int(190 - n * 140), 220]
                )
            else:
                gdf["_color"] = [[43, 140, 190, 220]] * len(gdf)
        else:
            gdf["_color"] = [[200, 200, 200, 200]] * len(gdf)

    features = _to_geojson_features(gdf, [
        "unit_id", "landcover_class", "burn_class", "area_ha",
        "baseline_parameter", "burned_parameter", "cn_adjustment", "soil_group",
    ])

    geom_types = set(gdf.geometry.geom_type.unique())
    if "Polygon" in geom_types or "MultiPolygon" in geom_types:
        layer = {
            "name": "Response Units",
            "visible": visible,
            "data": features,
            "pickable": True,
            "stroked": True,
            "getLineColor": [80, 80, 80, 80],
            "getLineWidth": 20,
            "lineWidthMinPixels": 0.5,
        }
    else:
        layer = {
            "name": "Response Units",
            "visible": visible,
            "data": features,
            "pickable": True,
        }

    tooltip = (
        "Land cover: {landcover_class}<br>"
        "Burn class: {burn_class}<br>"
        "Area: {area_ha} ha<br>"
        "Baseline CN: {baseline_parameter}<br>"
        "Burned CN: {burned_parameter}<br>"
        "CN adjustment: {cn_adjustment}"
    )
    return layer, tooltip


def outlet_point_layer() -> dict | None:
    """Create an outlet point layer from canonical coordinates."""
    from pyproj import Transformer
    from shapely.geometry import Point
    OUTLET_LON, OUTLET_LAT = 8.82375104, 45.91547405
    pt = Point(OUTLET_LON, OUTLET_LAT)
    gdf = gpd.GeoDataFrame([{"name": "Candidate Outlet"}], geometry=[pt], crs="EPSG:4326")
    return {
        "name": "Outlet",
        "visible": True,
        "data": _to_geojson_features(gdf),
        "pickable": True,
    }


def compute_center(gdfs: list[gpd.GeoDataFrame]) -> tuple[float, float]:
    """Compute a reasonable center lat/lon from a list of GeoDataFrames."""
    lons, lats = [], []
    for gdf in gdfs:
        bounds = gdf.total_bounds
        lons.extend([bounds[0], bounds[2]])
        lats.extend([bounds[1], bounds[3]])
    if lons and lats:
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    return (45.86, 8.78)  # fallback: Lake Varese


def burn_raster_overlay() -> dict | None:
    """Read burn raster, convert low-res class polygons for pydeck overlay."""
    if not BURN_RASTER.exists():
        return None
    try:
        with rasterio.open(BURN_RASTER) as ds:
            arr = ds.read(1)
            # Downsample for web display
            factor = max(1, min(arr.shape) // 200)
            arr_ds = arr[::factor, ::factor]
            transform = ds.transform * ds.transform.scale(factor, factor)
            bounds = ds.bounds
            # Convert bounds to WGS84
            wgs84_bounds = transform_bounds(ds.crs, "EPSG:4326", *bounds)

        features = []
        for class_val in [1, 2, 3]:
            mask = arr_ds == class_val
            if not np.any(mask):
                continue
            from rasterio.features import shapes as rio_shapes
            from shapely.geometry import shape as shp_shape
            color = BURN_CLASS_COLORS.get(class_val, [200, 200, 200, 180])
            for geom, val in rio_shapes(arr_ds.astype("uint8"), mask=mask, transform=transform):
                if int(val) == class_val:
                    features.append({
                        "type": "Feature",
                        "geometry": geom,
                        "properties": {"burn_class": int(class_val), "color": color},
                    })

        if not features:
            return None
        return {
            "name": "Burn Severity Proxy",
            "visible": False,
            "data": features,
            "pickable": True,
            "stroked": False,
        }
    except Exception:
        return None
