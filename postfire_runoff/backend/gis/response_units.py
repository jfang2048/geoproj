"""Response-unit construction from catchment, land cover, HSG, and burn classes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import geopandas as gpd
import numpy as np
import pandas as pd

from postfire_runoff.backend.gis.normalize import SpatialInputError, canonicalize_polygons
from postfire_runoff.backend.hydrology.curve_numbers import (
    DEFAULT_CN2_TABLE,
    apply_burn_adjustment,
    lookup_curve_number,
    normalize_hsg,
    normalize_landcover,
)


@dataclass(frozen=True)
class ResponseUnitDiagnostics:
    catchment_area_m2: float
    covered_area_m2: float
    uncovered_area_m2: float
    overlap_error_m2: float


def _clip_to_catchment(layer: gpd.GeoDataFrame, catchment: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    clipped = gpd.overlay(layer, catchment[["geometry"]], how="intersection", keep_geom_type=True)
    clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()
    if clipped.empty:
        raise SpatialInputError(f"{label}: no overlap with catchment")
    return clipped


def build_response_units(
    catchment: gpd.GeoDataFrame,
    landcover: gpd.GeoDataFrame,
    hsg: gpd.GeoDataFrame,
    burn: gpd.GeoDataFrame,
    landcover_column: str = "landcover_class",
    hsg_column: str = "hsg",
    burn_adjustments: Mapping[int | str, float] | None = None,
    cn_lookup: Mapping[str, Mapping[str, float]] | None = None,
    min_area_m2: float = 1.0,
) -> tuple[gpd.GeoDataFrame, ResponseUnitDiagnostics]:
    catchment = canonicalize_polygons(catchment, "catchment")
    landcover = canonicalize_polygons(landcover, "land cover")
    hsg = canonicalize_polygons(hsg, "HSG")
    burn = canonicalize_polygons(burn, "burn severity")
    working_crs = catchment.crs
    for label, layer in (("land cover", landcover), ("HSG", hsg), ("burn severity", burn)):
        if layer.crs != working_crs:
            raise SpatialInputError(f"{label}: CRS does not match catchment")

    if landcover_column not in landcover.columns:
        candidates = [c for c in ("landcover_class", "land_cover", "class", "label") if c in landcover.columns]
        if not candidates:
            raise SpatialInputError(f"land cover: missing column '{landcover_column}'")
        landcover_column = candidates[0]
    if hsg_column not in hsg.columns:
        candidates = [c for c in ("hsg", "soil_group", "hydrologic_soil_group") if c in hsg.columns]
        if not candidates:
            raise SpatialInputError(f"HSG: missing column '{hsg_column}'")
        hsg_column = candidates[0]
    if "burn_class" not in burn.columns:
        raise SpatialInputError("burn severity: missing normalized burn_class column")

    lc = _clip_to_catchment(landcover[[landcover_column, "geometry"]], catchment, "land cover")
    lc["landcover_class"] = lc[landcover_column].apply(normalize_landcover)
    soil = _clip_to_catchment(hsg[[hsg_column, "geometry"]], catchment, "HSG")
    soil["hsg"] = soil[hsg_column].apply(normalize_hsg)
    burn_clip = _clip_to_catchment(burn[["burn_class", "geometry"]], catchment, "burn severity")
    burn_clip["burn_class"] = burn_clip["burn_class"].astype(int)

    units = gpd.overlay(lc[["landcover_class", "geometry"]], soil[["hsg", "geometry"]], how="intersection", keep_geom_type=True)
    units = gpd.overlay(units, burn_clip[["burn_class", "geometry"]], how="intersection", keep_geom_type=True)
    units = units[units.geometry.notna() & ~units.geometry.is_empty].copy()
    if units.empty:
        raise SpatialInputError("Response-unit overlay produced no units")

    units["area_m2"] = units.geometry.area.astype(float)
    units = units[units["area_m2"] >= min_area_m2].copy()
    if units.empty:
        raise SpatialInputError("Response-unit overlay produced only negligible-area fragments")

    lookup = cn_lookup or DEFAULT_CN2_TABLE
    units["baseline_cn"] = [
        lookup_curve_number(lc_value, hsg_value, lookup)
        for lc_value, hsg_value in zip(units["landcover_class"], units["hsg"])
    ]
    units["burned_cn"] = [
        apply_burn_adjustment(cn, burn_class, burn_adjustments)
        for cn, burn_class in zip(units["baseline_cn"], units["burn_class"])
    ]
    units["cn_adjustment"] = units["burned_cn"] - units["baseline_cn"]
    units["soil_group"] = units["hsg"]
    units["baseline_parameter"] = units["baseline_cn"]
    units["burned_parameter"] = units["burned_cn"]
    units["area_ha"] = units["area_m2"] / 10000.0
    units = units.reset_index(drop=True)
    units["unit_id"] = [f"RU_{i + 1:04d}" for i in range(len(units))]
    units = units[[
        "unit_id",
        "landcover_class",
        "hsg",
        "soil_group",
        "burn_class",
        "baseline_cn",
        "burned_cn",
        "baseline_parameter",
        "burned_parameter",
        "cn_adjustment",
        "area_m2",
        "area_ha",
        "geometry",
    ]]

    catchment_area = float(catchment.geometry.union_all().area)
    covered_union_area = float(units.geometry.union_all().area)
    sum_area = float(units["area_m2"].sum())
    overlap_error = max(0.0, sum_area - covered_union_area)
    tolerance = max(1.0, covered_union_area * 1e-6)
    if overlap_error > tolerance:
        raise SpatialInputError(
            f"Response units appear double-counted: sum area exceeds union by {overlap_error:.3f} m²"
        )
    diagnostics = ResponseUnitDiagnostics(
        catchment_area_m2=catchment_area,
        covered_area_m2=covered_union_area,
        uncovered_area_m2=max(0.0, catchment_area - covered_union_area),
        overlap_error_m2=overlap_error,
    )
    return units, diagnostics


def summarize_burn_area(units: gpd.GeoDataFrame, catchment_area_m2: float) -> pd.DataFrame:
    grouped = units.groupby("burn_class", as_index=False).agg(area_m2=("area_m2", "sum"), unit_count=("unit_id", "count"))
    covered = float(grouped["area_m2"].sum())
    labels = {0: "unburned", 1: "low", 2: "moderate", 3: "high"}
    grouped["burn_label"] = grouped["burn_class"].map(labels).fillna("unknown")
    grouped["area_ha"] = grouped["area_m2"] / 10000.0
    grouped["pct_of_covered"] = np.where(covered > 0, grouped["area_m2"] / covered * 100.0, 0.0)
    grouped["pct_of_catchment"] = np.where(catchment_area_m2 > 0, grouped["area_m2"] / catchment_area_m2 * 100.0, 0.0)
    return grouped[["burn_class", "burn_label", "area_m2", "area_ha", "pct_of_covered", "pct_of_catchment", "unit_count"]]
