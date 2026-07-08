"""Create Lake Varese water-quality proxy ROI polygons in EPSG:32632."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from shapely.geometry import box
from shapely.ops import unary_union

from lake_wq.config import ROOT, LAKE_BOUNDARY_PATH, ROI_PATH, WORKING_CRS, ROI_NAMES
from lake_wq.io import ensure_lake_wq_dirs
from pipeline_utils import StepLog, append_run_log, import_geo, register_generated_dataset, update_backlog, write_gpkg


def _require_epsg32632(gdf: Any, label: str) -> None:
    if gdf.crs is None:
        raise ValueError(f"{label} has no CRS metadata; refusing to assume coordinates")
    if gdf.crs.to_epsg() != 32632:
        raise ValueError(f"{label} expected EPSG:32632 after reprojection, found {gdf.crs}")


def create_rois() -> Any:
    """Create whole-lake, north-shore/inflow-side, and center-control ROIs."""
    ensure_lake_wq_dirs()
    gpd, *_ = import_geo()
    if not LAKE_BOUNDARY_PATH.exists():
        raise FileNotFoundError(f"Missing lake boundary: {LAKE_BOUNDARY_PATH.relative_to(ROOT)}")
    lake = gpd.read_file(LAKE_BOUNDARY_PATH)
    if lake.empty:
        raise ValueError("Lake boundary layer is empty")
    if lake.crs is None:
        raise ValueError("Lake boundary has no CRS metadata; refusing to assume coordinates")
    lake = lake.to_crs(WORKING_CRS)
    _require_epsg32632(lake, "Lake boundary")
    if not lake.geometry.is_valid.all():
        lake = lake.copy()
        lake["geometry"] = lake.geometry.buffer(0)
    lake_geom = unary_union([geom for geom in lake.geometry if geom is not None and not geom.is_empty]).buffer(0)
    if lake_geom.is_empty or lake_geom.area <= 0:
        raise ValueError("Lake boundary geometry is empty/zero-area after repair")

    xmin, ymin, xmax, ymax = lake_geom.bounds
    width = xmax - xmin
    height = ymax - ymin
    if width <= 0 or height <= 0:
        raise ValueError("Lake boundary has invalid metric bounds")

    north_band = box(xmin - 50, ymin + 0.65 * height, xmax + 50, ymax + 50)
    near_inlet = lake_geom.intersection(north_band).buffer(0)
    if near_inlet.is_empty or near_inlet.area <= 0:
        near_inlet = lake_geom.intersection(box(xmin - 50, ymin + 0.55 * height, xmax + 50, ymax + 50)).buffer(0)

    center_point = lake_geom.representative_point()
    center_control = center_point.buffer(550).intersection(lake_geom).buffer(0)
    if center_control.is_empty or center_control.area <= 0:
        center_control = center_point.buffer(350).intersection(lake_geom).buffer(0)

    records = [
        {
            "roi_name": "whole_lake",
            "roi_class": "whole_lake",
            "roi_method_note": "Whole Lake Varese polygon from processed boundary; geometry processed in EPSG:32632.",
            "interpretation_note": "Whole-lake statistics integrate spatially heterogeneous water and atmospheric conditions.",
        },
        {
            "roi_name": "near_inlet_or_north_shore",
            "roi_class": "near_inlet_or_north_shore",
            "roi_method_note": (
                "Approximate northern 35% of Lake Varese clipped from the lake boundary in EPSG:32632. "
                "Exact inlet geometry was unavailable, so this is a transparent inflow-side/north-shore proxy ROI."
            ),
            "interpretation_note": "Use only as an approximate near-inlet/north-shore response zone, not a surveyed tributary plume footprint.",
        },
        {
            "roi_name": "lake_center_control",
            "roi_class": "lake_center_control",
            "roi_method_note": "Representative lake point buffered 550 m in EPSG:32632 and clipped to the lake polygon.",
            "interpretation_note": "Approximate lake-center control zone; not a field station footprint.",
        },
    ]
    rois = gpd.GeoDataFrame(records, geometry=[lake_geom, near_inlet, center_control], crs=WORKING_CRS)
    rois["area_m2"] = rois.geometry.area
    rois["area_ha"] = rois["area_m2"] / 10000.0
    if rois.empty or rois.geometry.is_empty.any() or not rois.geometry.is_valid.all():
        raise ValueError("Generated ROI layer failed validity checks")
    _require_epsg32632(rois, "Lake WQ ROIs")
    if set(rois["roi_name"]) != set(ROI_NAMES):
        raise ValueError("Generated ROI names do not match required classes")
    write_gpkg(rois, ROI_PATH)
    register_generated_dataset(
        "lake_varese_wq_rois_utm32",
        "Lake Varese water-quality proxy ROIs",
        "lake_water_quality_remote_sensing_roi",
        ROI_PATH,
        "processed",
        crs=WORKING_CRS,
        notes="Whole lake, approximate north-shore/inflow-side ROI, and lake-center control generated in EPSG:32632.",
    )
    update_backlog({"F017": "PARTIAL"}, "Created Python-only Lake Varese WQ ROI layer in EPSG:32632.", Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/compute_rois.py",
            task="Create Lake Varese water-quality ROI polygons.",
            inputs=[str(LAKE_BOUNDARY_PATH.relative_to(ROOT))],
            outputs=[str(ROI_PATH.relative_to(ROOT))],
            status="DONE",
            reason="ROIs generated in EPSG:32632; north-shore/inflow-side ROI is explicitly approximate.",
            files_created=[str(ROI_PATH.relative_to(ROOT))],
            qa_checks=["ROI CRS EPSG:32632", "valid_non_empty_polygons", "transparent approximate inlet-side ROI note"],
            next_action="Run Sentinel-2 local SAFE availability/index computation.",
        )
    )
    print(f"Created {len(rois)} Lake WQ ROIs -> {ROI_PATH.relative_to(ROOT)}")
    print(rois[["roi_name", "area_ha", "roi_method_note"]].to_string(index=False))
    return rois


def main() -> int:
    create_rois()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
