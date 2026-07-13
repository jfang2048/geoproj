"""Response-unit construction from catchment, land cover, HSG, and burn classes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import geopandas as gpd
import numpy as np
import pandas as pd

from postfire_runoff.backend.gis.normalize import SpatialInputError, normalize_polygons
from postfire_runoff.backend.hydrology.curve_numbers import (
    DEFAULT_CN2_TABLE,
    apply_burn_adjustment,
    lookup_curve_number,
    normalize_hsg,
    normalize_landcover,
)

RESPONSE_UNIT_COLUMNS = [
    "unit_id",
    "landcover_class",
    "hsg",
    "burn_class",
    "baseline_cn",
    "burned_cn",
    "cn_adjustment",
    "area_m2",
    "area_ha",
    "geometry",
]


@dataclass(frozen=True)
class ResponseUnitDiagnostics:
    catchment_area_m2: float
    covered_area_m2: float
    uncovered_area_m2: float
    overlap_error_m2: float
    burn_covered_area_m2: float
    burn_unburned_area_m2: float
    burn_overlap_error_m2: float


def _clip_to_catchment(layer: gpd.GeoDataFrame, catchment: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    clipped = gpd.overlay(layer, catchment[["geometry"]], how="intersection", keep_geom_type=True)
    clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()
    if clipped.empty:
        raise SpatialInputError(f"{label}: no overlap with catchment")
    return clipped


def _single_catchment(catchment: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    geom = catchment.geometry.union_all()
    if geom.is_empty:
        raise SpatialInputError("catchment: empty union geometry")
    return gpd.GeoDataFrame([{"geometry": geom}], crs=catchment.crs)


def _validate_burn_overlap(burn: gpd.GeoDataFrame, tolerance_m2: float) -> float:
    overlap_error = 0.0
    for i, left in burn.reset_index(drop=True).iterrows():
        for j in range(i + 1, len(burn)):
            right = burn.iloc[j]
            inter = left.geometry.intersection(right.geometry)
            area = float(inter.area) if not inter.is_empty else 0.0
            if area <= tolerance_m2:
                continue
            overlap_error += area
            if int(left["burn_class"]) != int(right["burn_class"]):
                raise SpatialInputError(
                    "burn severity: overlapping polygons with different burn classes "
                    f"cover {area:.3f} m². Resolve overlaps before running."
                )
    return overlap_error


def complete_burn_coverage(
    burn: gpd.GeoDataFrame,
    catchment: gpd.GeoDataFrame,
    min_area_m2: float = 1.0,
) -> tuple[gpd.GeoDataFrame, dict[str, float]]:
    catchment_one = _single_catchment(catchment)
    catchment_area = float(catchment_one.geometry.iloc[0].area)
    tolerance = max(min_area_m2, catchment_area * 1e-8)

    burn_clip = _clip_to_catchment(burn[["burn_class", "geometry"]], catchment_one, "burn severity")
    try:
        burn_clip["burn_class"] = burn_clip["burn_class"].astype(int)
    except (TypeError, ValueError) as exc:
        raise SpatialInputError(f"burn severity: burn_class must contain 0, 1, 2, or 3: {exc}") from exc
    invalid = sorted(set(burn_clip.loc[~burn_clip["burn_class"].isin([0, 1, 2, 3]), "burn_class"].tolist()))
    if invalid:
        raise SpatialInputError(f"burn severity: unsupported burn_class values: {invalid}")

    raw_overlap = _validate_burn_overlap(burn_clip, tolerance)
    burned = burn_clip[burn_clip["burn_class"] > 0].copy()
    pieces: list[dict] = []
    burned_union = None
    if not burned.empty:
        for cls, group in burned.groupby("burn_class"):
            geom = group.geometry.union_all()
            if not geom.is_empty and geom.area >= min_area_m2:
                pieces.append({"burn_class": int(cls), "geometry": geom})
        burned_union = burned.geometry.union_all()

    catchment_geom = catchment_one.geometry.iloc[0]
    unburned_geom = catchment_geom.difference(burned_union) if burned_union is not None else catchment_geom
    if not unburned_geom.is_empty and unburned_geom.area >= min_area_m2:
        pieces.append({"burn_class": 0, "geometry": unburned_geom})
    if not pieces:
        raise SpatialInputError("burn severity: no burn coverage could be built inside catchment")

    coverage = gpd.GeoDataFrame(pieces, crs=catchment.crs)
    coverage = coverage.explode(index_parts=False).reset_index(drop=True)
    coverage["area_m2"] = coverage.geometry.area.astype(float)
    coverage = coverage[coverage["area_m2"] >= min_area_m2].drop(columns="area_m2").copy()

    covered_area = float(coverage.geometry.union_all().area)
    sum_area = float(coverage.geometry.area.sum())
    final_overlap = max(0.0, sum_area - covered_area)
    uncovered = max(0.0, catchment_area - covered_area)
    coverage_tolerance = max(min_area_m2, catchment_area * 1e-6)
    if final_overlap > coverage_tolerance:
        raise SpatialInputError(f"burn severity: final burn layer overlaps itself by {final_overlap:.3f} m²")
    if uncovered > coverage_tolerance:
        raise SpatialInputError(f"burn severity: final burn layer leaves {uncovered:.3f} m² of catchment uncovered")

    diagnostics = {
        "burn_covered_area_m2": covered_area,
        "burn_unburned_area_m2": float(coverage.loc[coverage["burn_class"] == 0, "geometry"].area.sum()),
        "burn_overlap_error_m2": raw_overlap + final_overlap,
    }
    return coverage[["burn_class", "geometry"]], diagnostics


def build_response_units(
    catchment: gpd.GeoDataFrame,
    landcover: gpd.GeoDataFrame,
    hsg: gpd.GeoDataFrame,
    burn: gpd.GeoDataFrame,
    landcover_column: str = "landcover_class",
    hsg_column: str = "hsg",
    burn_adjustments: Mapping[int | str, float] | None = None,
    cn_lookup: Mapping[str, Mapping[str, float]] | None = None,
    landcover_aliases: Mapping[str, str] | None = None,
    min_area_m2: float = 1.0,
) -> tuple[gpd.GeoDataFrame, ResponseUnitDiagnostics]:
    catchment = normalize_polygons(catchment, "catchment")
    landcover = normalize_polygons(landcover, "land cover")
    hsg = normalize_polygons(hsg, "HSG")
    burn = normalize_polygons(burn, "burn severity")
    working_crs = catchment.crs
    for label, layer in (("land cover", landcover), ("HSG", hsg), ("burn severity", burn)):
        if layer.crs != working_crs:
            raise SpatialInputError(f"{label}: CRS does not match catchment")

    if landcover_column not in landcover.columns:
        raise SpatialInputError(f"land cover: missing configured column '{landcover_column}'")
    if hsg_column not in hsg.columns:
        raise SpatialInputError(f"HSG: missing configured column '{hsg_column}'")
    if "burn_class" not in burn.columns:
        raise SpatialInputError("burn severity: missing normalized burn_class column")

    catchment_one = _single_catchment(catchment)
    lc = _clip_to_catchment(landcover[[landcover_column, "geometry"]], catchment_one, "land cover")
    try:
        lc["landcover_class"] = lc[landcover_column].apply(lambda value: normalize_landcover(value, landcover_aliases))
    except ValueError as exc:
        raise SpatialInputError(f"land cover: {exc}") from exc

    soil = _clip_to_catchment(hsg[[hsg_column, "geometry"]], catchment_one, "HSG")
    try:
        soil["hsg"] = soil[hsg_column].apply(normalize_hsg)
    except ValueError as exc:
        raise SpatialInputError(f"HSG: {exc}") from exc

    burn_coverage, burn_diag = complete_burn_coverage(burn, catchment_one, min_area_m2)

    units = gpd.overlay(lc[["landcover_class", "geometry"]], soil[["hsg", "geometry"]], how="intersection", keep_geom_type=True)
    units = gpd.overlay(units, burn_coverage[["burn_class", "geometry"]], how="intersection", keep_geom_type=True)
    units = units[units.geometry.notna() & ~units.geometry.is_empty].copy()
    if units.empty:
        raise SpatialInputError("Response-unit overlay produced no units")

    units["area_m2"] = units.geometry.area.astype(float)
    units = units[units["area_m2"] >= min_area_m2].copy()
    if units.empty:
        raise SpatialInputError("Response-unit overlay produced only negligible-area fragments")

    lookup = cn_lookup or DEFAULT_CN2_TABLE
    try:
        units["baseline_cn"] = [
            lookup_curve_number(lc_value, hsg_value, lookup, landcover_aliases)
            for lc_value, hsg_value in zip(units["landcover_class"], units["hsg"])
        ]
        units["burned_cn"] = [
            apply_burn_adjustment(cn, burn_class, burn_adjustments)
            for cn, burn_class in zip(units["baseline_cn"], units["burn_class"])
        ]
    except ValueError as exc:
        raise SpatialInputError(str(exc)) from exc

    units["cn_adjustment"] = units["burned_cn"] - units["baseline_cn"]
    units["area_ha"] = units["area_m2"] / 10000.0
    units = units.reset_index(drop=True)
    units["unit_id"] = [f"RU_{i + 1:04d}" for i in range(len(units))]
    units = units[RESPONSE_UNIT_COLUMNS]

    catchment_area = float(catchment_one.geometry.iloc[0].area)
    covered_union_area = float(units.geometry.union_all().area)
    sum_area = float(units["area_m2"].sum())
    overlap_error = max(0.0, sum_area - covered_union_area)
    tolerance = max(min_area_m2, catchment_area * 1e-6)
    if overlap_error > tolerance:
        raise SpatialInputError(
            f"Response units double-count area: sum exceeds union by {overlap_error:.3f} m²"
        )
    uncovered = max(0.0, catchment_area - covered_union_area)
    if uncovered > tolerance:
        raise SpatialInputError(
            f"Response units leave {uncovered:.3f} m² of catchment uncovered after normalization"
        )

    diagnostics = ResponseUnitDiagnostics(
        catchment_area_m2=catchment_area,
        covered_area_m2=covered_union_area,
        uncovered_area_m2=uncovered,
        overlap_error_m2=overlap_error,
        burn_covered_area_m2=burn_diag["burn_covered_area_m2"],
        burn_unburned_area_m2=burn_diag["burn_unburned_area_m2"],
        burn_overlap_error_m2=burn_diag["burn_overlap_error_m2"],
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
