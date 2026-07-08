"""Purpose: Derive hydrologic soil group (HSG) from SoilGrids topsoil composites and classify for runoff modelling.
Inputs: data/raw/zip/soilgrids_lake_varese/ SoilGrids composite rasters, data/processed/boundary/catchment_utm32.gpkg.
Outputs: data/processed/soil/soil_texture_or_hydraulic_utm32.tif, hydrologic_soil_group.tif, soil_hydraulic_summary.gpkg; results/tables/soil_summary_by_catchment.csv.
CRS: EPSG:32632 (working CRS).
Units: HSG classes A/B/C/D; texture fractions in percent.
Assumptions: SoilGrids 250 m resolution is coarse; HSG derived from simplified texture-to-HSG lookup; not field-validated. Replace with local soil hydraulic data when available.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from pipeline_utils import ROOT, WORKING_CRS, StepLog, append_run_log, ensure_workspace, import_geo, raster_valid, register_generated_dataset, update_backlog, write_gpkg, write_raster, read_raster_window_to_working
from raw_data_utils import SOIL_DIR


def classify_hsg(sand: np.ndarray, clay: np.ndarray, valid: np.ndarray) -> np.ndarray:
    hsg = np.zeros(sand.shape, dtype="uint8")
    # Simplified texture-to-HSG screening rule. Full HSG needs local hydraulic validation.
    hsg[valid] = 3  # default C
    hsg[valid & (sand >= 70) & (clay < 15)] = 1  # A
    hsg[valid & (sand >= 50) & (clay < 30)] = 2  # B
    hsg[valid & ((clay >= 40) | (sand < 35))] = 4  # D
    return hsg


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive simplified HSG from local SoilGrids Lake Varese composites.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    texture_path = ROOT / "data/processed/soil/soil_texture_or_hydraulic_utm32.tif"
    hsg_path = ROOT / "data/processed/soil/hydrologic_soil_group.tif"
    summary_path = ROOT / "outputs/tables/soil_summary_by_catchment.csv"
    soil_gpkg = ROOT / "data/processed/soil/soil_hydraulic_summary.gpkg"

    if raster_valid(hsg_path, WORKING_CRS, True)[0] and summary_path.exists() and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: SoilGrids-derived HSG already valid."
        created: list[str] = []
        qa = raster_valid(hsg_path, WORKING_CRS, True)[1]
    else:
        gpd, *_ = import_geo()
        catchment_path = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
        if not catchment_path.exists():
            raise FileNotFoundError("Missing catchment. Run step 05 first.")
        if not SOIL_DIR.exists():
            raise FileNotFoundError("Missing local SoilGrids composites directory.")
        sand_path = SOIL_DIR / "sand_0-30cm_weighted_mean_utm32.tif"
        clay_path = SOIL_DIR / "clay_0-30cm_weighted_mean_utm32.tif"
        silt_path = SOIL_DIR / "silt_0-30cm_weighted_mean_utm32.tif"
        for p in [sand_path, clay_path, silt_path]:
            if not p.exists():
                raise FileNotFoundError(f"Missing required soil composite: {p}")
        catchment = gpd.read_file(catchment_path).to_crs(WORKING_CRS)
        geom = catchment.geometry.union_all()
        sand, transform, sand_src_crs, _ = read_raster_window_to_working(sand_path, tuple(catchment.total_bounds), resolution=250, nodata=-9999.0)
        clay, _, clay_src_crs, _ = read_raster_window_to_working(clay_path, tuple(catchment.total_bounds), resolution=250, nodata=-9999.0)
        silt, _, silt_src_crs, _ = read_raster_window_to_working(silt_path, tuple(catchment.total_bounds), resolution=250, nodata=-9999.0)
        nodata = -9999.0
        valid = (sand != nodata) & (clay != nodata) & (silt != nodata) & np.isfinite(sand) & np.isfinite(clay) & np.isfinite(silt)
        catch_mask = geometry_mask([geom], out_shape=sand.shape, transform=transform, invert=True)
        valid &= catch_mask
        hsg = classify_hsg(sand, clay, valid)
        # Texture raster stores dominant texture proxy code from HSG rule for reproducibility.
        write_raster(texture_path, np.where(valid, clay, -9999.0).astype("float32"), transform, WORKING_CRS, nodata=-9999.0, dtype="float32")
        write_raster(hsg_path, hsg, transform, WORKING_CRS, nodata=0, dtype="uint8")
        pixel_area = abs(transform.a * transform.e)
        names = {1: "A", 2: "B", 3: "C", 4: "D"}
        rows = []
        for code in [1, 2, 3, 4]:
            count = int(np.count_nonzero(hsg == code))
            if count:
                rows.append({"hsg_code": code, "hsg_group": names[code], "pixel_count": count, "area_m2": count * pixel_area, "area_ha": count * pixel_area / 10000.0, "notes": "Simplified SoilGrids texture-to-HSG screen; validate with local hydraulic data before final interpretation."})
        pd.DataFrame(rows).to_csv(summary_path, index=False)
        dominant = max(rows, key=lambda r: r["pixel_count"])["hsg_group"] if rows else "unknown"
        summary = catchment.copy()
        summary["soil_source"] = "SoilGrids local 0-30 cm weighted composites"
        summary["dominant_hsg"] = dominant
        summary["notes"] = "Simplified HSG derived from sand/clay thresholds; uncertainty documented."
        write_gpkg(summary, soil_gpkg)
        register_generated_dataset("soil_texture_proxy", "SoilGrids clay 0-30 cm clipped", "soil_input", texture_path, "processed", WORKING_CRS, f"Local SoilGrids composite clipped to catchment; source_crs={clay_src_crs}; reprojected_to={WORKING_CRS}.")
        register_generated_dataset("hydrologic_soil_group", "Hydrologic soil group", "model_input", hsg_path, "processed", WORKING_CRS, f"Simplified HSG derived from local SoilGrids sand/clay composites; source_crs={sand_src_crs}/{clay_src_crs}/{silt_src_crs}; reprojected_to={WORKING_CRS}.")
        register_generated_dataset("soil_hydraulic_summary", "Soil hydraulic summary", "soil_summary", soil_gpkg, "processed", WORKING_CRS, "Dominant HSG summary from SoilGrids-derived screen.")
        created = [str(p.relative_to(ROOT)) for p in [texture_path, hsg_path, summary_path, soil_gpkg]]
        status = "DONE"
        reason = "Derived simplified HSG from local SoilGrids Lake Varese composites."
        qa = raster_valid(hsg_path, WORKING_CRS, True)[1] + [f"summary_rows={len(rows)}", f"dominant_hsg={dominant}"]

    update_backlog({"H001": "DONE", "H002": "DONE", "H003": "PARTIAL", "H004": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Clip local SoilGrids composites and derive simplified HSG classes.",
            inputs=["data/raw/zip/soilgrids_lake_varese/*weighted_mean_utm32.tif", "data/processed/boundary/catchment_utm32.gpkg"],
            outputs=[str(p.relative_to(ROOT)) for p in [hsg_path, summary_path]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(hsg_path.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/10_prepare_weather.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
