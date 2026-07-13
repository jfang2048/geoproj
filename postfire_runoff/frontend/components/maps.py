"""Pydeck map rendering for processed runoff layers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pydeck as pdk
import rasterio
import yaml
from affine import Affine
from rasterio.features import shapes as raster_shapes
from rasterio.warp import transform_geom

from postfire_runoff.frontend.components.loaders import (
    BURN_RASTER,
    CATCHMENT,
    FIRE_PERIMETER,
    RUNOFF_UNITS_GPKG,
    DataLoadError,
    load_vector,
)
from postfire_runoff.frontend.components.paths import PROJECT_CONFIG

BASEMAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

BURN_CLASS_COLORS = {
    0: [220, 220, 220, 165],
    1: [254, 235, 156, 220],
    2: [253, 174, 97, 220],
    3: [227, 74, 51, 220],
}
LANDCOVER_COLORS = {
    "forest": [35, 139, 69, 210],
    "shrub": [116, 196, 118, 210],
    "grassland": [173, 221, 142, 210],
    "agriculture": [255, 237, 160, 210],
    "urban": [117, 107, 177, 210],
    "bare_soil": [217, 95, 14, 210],
    "water": [43, 140, 190, 210],
    "other": [150, 150, 150, 210],
}
PALETTE = [
    [43, 140, 190, 210],
    [49, 163, 84, 210],
    [217, 95, 14, 210],
    [117, 107, 177, 210],
    [231, 41, 138, 210],
    [102, 102, 102, 210],
]


def render_map() -> None:
    import streamlit as st

    st.markdown("#### Interactive study area map")
    st.caption("Processed layers are reprojected to EPSG:4326 for web display.")

    col_filters, col_map = st.columns([0.24, 0.76])
    with col_filters:
        st.markdown("**Base layers**")
        show_catchment = st.checkbox("Catchment", value=True, key="mc")
        show_fire = st.checkbox("Official fire", value=True, key="mf")
        st.markdown("**Model layers**")
        show_units = st.checkbox("Response units", value=True, key="mu")
        show_outlet = st.checkbox("Outlet", value=True, key="mo")
        show_burn = st.checkbox("Burn raster overlay", key="mbr")
        color_by = st.selectbox(
            "Color units by",
            ["cn_adjustment", "burn_class", "landcover_class", "baseline_cn", "burned_cn"],
            key="mcolor",
        )

    layers: list[pdk.Layer] = []
    notes: list[str] = []
    center = (45.86, 8.78)
    tooltip = {"html": "{tooltip}", "style": {"fontSize": "12px"}}

    with col_map:
        try:
            if show_catchment:
                layer, count, gdf = polygon_layer(CATCHMENT, "Catchment", [30, 60, 120, 220], [41, 80, 160, 50])
                if layer:
                    layers.append(layer)
                    center = center_from_gdf(gdf)
                notes.append(f"Catchment: {count} feature(s)" if count else "Catchment: unavailable")
            if show_fire:
                layer, count, _ = polygon_layer(FIRE_PERIMETER, "Official fire", [217, 95, 14, 220], [217, 95, 14, 45])
                if layer:
                    layers.append(layer)
                notes.append(f"Official fire: {count} feature(s)" if count else "Official fire: unavailable")
            if show_units:
                layer, count = response_units_layer(color_by)
                if layer:
                    layers.append(layer)
                notes.append(f"Response units: {count} unit(s)" if count else "Response units: unavailable")
            if show_burn:
                features = burn_raster_features()
                if features:
                    layers.append(pdk.Layer(
                        "GeoJsonLayer",
                        data=features,
                        pickable=True,
                        stroked=False,
                        filled=True,
                        get_fill_color="[properties.fill_color[0], properties.fill_color[1], properties.fill_color[2], properties.fill_color[3]]",
                    ))
                notes.append(f"Burn raster overlay: {len(features)} polygon(s)" if features else "Burn raster overlay: unavailable")
            if show_outlet:
                coords = outlet_lonlat()
                if coords is not None:
                    layers.append(pdk.Layer(
                        "ScatterplotLayer",
                        data=[{"lon": coords[0], "lat": coords[1], "tooltip": "Outlet"}],
                        get_position="[lon, lat]",
                        get_radius=150,
                        get_color=[200, 50, 40, 240],
                        pickable=True,
                    ))
                    notes.append("Outlet: configured coordinate")
                else:
                    notes.append("Outlet: not configured")
        except DataLoadError as exc:
            st.error(str(exc))

        st.caption("  |  ".join(notes) if notes else "No processed project layers found; basemap only.")
        st.pydeck_chart(pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=center[0], longitude=center[1], zoom=12, pitch=0),
            map_style=BASEMAP,
            tooltip=tooltip,
        ))


def polygon_layer(path: Path, label: str, line_color: list[int], fill_color: list[int]) -> tuple[pdk.Layer | None, int, gpd.GeoDataFrame | None]:
    gdf = load_vector(path)
    if gdf is None:
        return None, 0, None
    gdf = gdf.copy()
    gdf["tooltip"] = label
    features = _features(gdf)
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=features,
        pickable=True,
        stroked=True,
        filled=True,
        get_line_color=line_color,
        get_fill_color=fill_color,
        get_line_width=2,
        line_width_min_pixels=1,
    )
    return layer, len(features), gdf


def response_units_layer(color_by: str = "cn_adjustment") -> tuple[pdk.Layer | None, int]:
    gdf = load_vector(RUNOFF_UNITS_GPKG)
    if gdf is None:
        return None, 0
    gdf = gdf.copy()
    if color_by not in gdf.columns:
        color_by = "cn_adjustment" if "cn_adjustment" in gdf.columns else "burn_class"
    gdf["fill_color"] = _response_unit_colors(gdf, color_by)
    gdf["tooltip"] = gdf.apply(_unit_tooltip, axis=1)
    properties = [
        "unit_id",
        "landcover_class",
        "hsg",
        "burn_class",
        "baseline_cn",
        "burned_cn",
        "cn_adjustment",
        "area_ha",
        "fill_color",
        "tooltip",
    ]
    features = _features(gdf, properties)
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=features,
        pickable=True,
        stroked=True,
        filled=True,
        get_line_color=[80, 80, 80, 80],
        get_fill_color="[properties.fill_color[0], properties.fill_color[1], properties.fill_color[2], properties.fill_color[3]]",
        get_line_width=20,
        line_width_min_pixels=0.5,
    )
    return layer, len(features)


def _response_unit_colors(gdf: gpd.GeoDataFrame, color_by: str) -> list[list[int]]:
    if color_by == "burn_class":
        return [BURN_CLASS_COLORS.get(_safe_int(v), [150, 150, 150, 210]) for v in gdf[color_by]]
    if color_by == "landcover_class":
        values = [str(v) for v in gdf[color_by]]
        extra = {value: PALETTE[i % len(PALETTE)] for i, value in enumerate(sorted(set(values)))}
        return [LANDCOVER_COLORS.get(value, extra[value]) for value in values]
    values = np.asarray(gdf[color_by], dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return [[180, 180, 180, 210] for _ in values]
    vmin, vmax = float(finite.min()), float(finite.max())
    if vmax <= vmin:
        return [[43, 140, 190, 210] for _ in values]
    colors = []
    for value in values:
        if not np.isfinite(value):
            colors.append([180, 180, 180, 210])
            continue
        n = (float(value) - vmin) / (vmax - vmin)
        colors.append([int(43 + n * 184), int(140 - n * 66), int(190 - n * 139), 220])
    return colors


def burn_raster_features(path: Path = BURN_RASTER) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise DataLoadError(f"Raster {path} has no CRS")
            arr = ds.read(1)
            factor = max(1, min(arr.shape) // 200)
            arr_ds = arr[::factor, ::factor]
            transform = ds.transform * Affine.scale(factor, factor)
            source_crs = ds.crs
    except DataLoadError:
        raise
    except Exception as exc:
        raise DataLoadError(f"Could not read burn raster {path}: {exc}") from exc

    features: list[dict[str, Any]] = []
    for class_val in (1, 2, 3):
        mask = arr_ds == class_val
        if not np.any(mask):
            continue
        color = BURN_CLASS_COLORS.get(class_val, [200, 200, 200, 180])
        for geom, value in raster_shapes(arr_ds.astype("uint8"), mask=mask, transform=transform):
            if int(value) != class_val:
                continue
            wgs84 = transform_geom(source_crs, "EPSG:4326", geom, precision=6)
            features.append({
                "type": "Feature",
                "geometry": wgs84,
                "properties": {"burn_class": int(class_val), "fill_color": color, "tooltip": f"Burn class: {class_val}"},
            })
    return features


def validate_geographic_features(features: list[dict[str, Any]]) -> bool:
    for feature in features:
        for lon, lat in _iter_positions(feature.get("geometry", {})):
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                return False
    return True


def center_from_gdf(gdf: gpd.GeoDataFrame | None) -> tuple[float, float]:
    if gdf is None or gdf.empty:
        return (45.86, 8.78)
    geom = gdf.geometry.union_all()
    centroid = geom.centroid
    return (float(centroid.y), float(centroid.x))


def outlet_lonlat(config_path: Path = PROJECT_CONFIG) -> tuple[float, float] | None:
    if not config_path.exists():
        return None
    try:
        data = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return None
    points = data.get("reference_points", {}) or {}
    outlet = points.get("provisional_outlet_wgs84") or points.get("outlet_wgs84")
    if isinstance(outlet, dict) and outlet.get("lon") is not None and outlet.get("lat") is not None:
        try:
            return float(outlet["lon"]), float(outlet["lat"])
        except (TypeError, ValueError):
            return None
    return None


def _features(gdf: gpd.GeoDataFrame, properties: list[str] | None = None) -> list[dict[str, Any]]:
    features = []
    for feature in gdf.__geo_interface__["features"]:
        props = feature.get("properties", {}) or {}
        if properties is not None:
            props = {key: _json_value(props.get(key, "")) for key in properties}
        features.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
    return features


def _unit_tooltip(row: Any) -> str:
    return (
        f"Unit: {row.get('unit_id', '')}<br>"
        f"Land cover: {row.get('landcover_class', '')}<br>"
        f"HSG: {row.get('hsg', '')}<br>"
        f"Burn class: {row.get('burn_class', '')}<br>"
        f"CN: {row.get('baseline_cn', '')} → {row.get('burned_cn', '')}<br>"
        f"ΔCN: {row.get('cn_adjustment', '')}<br>"
        f"Area: {float(row.get('area_ha', 0.0)):.2f} ha"
    )


def _iter_positions(geometry: dict[str, Any]):
    coords = geometry.get("coordinates", [])
    geom_type = geometry.get("type")
    if geom_type == "Point":
        yield coords
    elif geom_type in {"LineString", "MultiPoint"}:
        yield from coords
    elif geom_type in {"Polygon", "MultiLineString"}:
        for part in coords:
            yield from part
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                yield from ring
    elif geom_type == "GeometryCollection":
        for geom in geometry.get("geometries", []):
            yield from _iter_positions(geom)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and np.isnan(value):
        return ""
    return value
