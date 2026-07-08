"""Purpose: Reclassify DUSAF6 land cover into simplified hydrologic classes for runoff modelling.
Inputs: data/raw/zip/DUSAF6_REGIONE_LOMBARDIA.zip, data/processed/boundary/catchment_utm32.gpkg, data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg.
Outputs: data/processed/landcover/landcover_utm32.gpkg, landcover_hydrologic_class.gpkg; results/tables/landcover_summary_by_catchment.csv, landcover_summary_by_burned_area.csv.
CRS: EPSG:32632 (working CRS).
Units: Area in hectares; class codes per simplified legend (forest, shrub, grassland, agriculture, urban, bare_soil, water, other).
Assumptions: DUSAF6 2018 classes mapped to 8 hydrologic categories; nearest-neighbour resampling for any rasterization.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_utils import ROOT, WORKING_CRS, StepLog, append_run_log, ensure_workspace, import_geo, register_generated_dataset, update_backlog, vector_valid, write_gpkg, read_vector_to_working
from raw_data_utils import DUSAF_ZIP, zip_shp_uri


def hydrologic_class(code: object, descr: str = "") -> str:
    s = str(code)
    d = (descr or "").lower()
    if s.startswith("1"):
        return "urban"
    if s.startswith("2"):
        return "agriculture"
    if s.startswith("31"):
        return "forest"
    if s.startswith("32"):
        if "cespug" in d or "arbust" in d:
            return "shrub"
        return "grassland"
    if s.startswith("33"):
        return "bare_soil"
    if s.startswith("4"):
        return "grassland"
    if s.startswith("5"):
        return "water"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare DUSAF6 land cover and hydrologic reclassification.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    lc_path = ROOT / "data/processed/landcover/landcover_utm32.gpkg"
    hyd_path = ROOT / "data/processed/landcover/landcover_hydrologic_class.gpkg"
    catch_sum = ROOT / "outputs/tables/landcover_summary_by_catchment.csv"
    burn_sum = ROOT / "outputs/tables/landcover_summary_by_burned_area.csv"

    if vector_valid(hyd_path, WORKING_CRS)[0] and catch_sum.exists() and burn_sum.exists() and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: DUSAF land-cover products already valid."
        created: list[str] = []
        qa = vector_valid(hyd_path, WORKING_CRS)[1]
    else:
        gpd, *_ = import_geo()
        catchment_path = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
        if not catchment_path.exists():
            raise FileNotFoundError("Missing catchment. Run step 05 first.")
        catchment = gpd.read_file(catchment_path).to_crs(WORKING_CRS)
        if not DUSAF_ZIP.exists():
            raise FileNotFoundError("Missing DUSAF6 raw ZIP; land cover is essential/high-value for runoff units.")
        dusaf = read_vector_to_working(zip_shp_uri(DUSAF_ZIP, "DUSAF6.shp"), bbox_working=tuple(catchment.total_bounds))
        lc = gpd.clip(dusaf, catchment)
        lc = lc[~lc.geometry.is_empty].copy()
        lc["hydrologic_class"] = [hydrologic_class(c, d) for c, d in zip(lc.get("COD_TOT", ""), lc.get("DESCR", ""))]
        lc["area_m2"] = lc.geometry.area
        lc["notes"] = "DUSAF6 clipped to DEM-derived catchment candidate."
        write_gpkg(lc, lc_path)
        write_gpkg(lc, hyd_path)

        total = float(lc.geometry.area.sum())
        rows = []
        for cls, group in lc.groupby("hydrologic_class"):
            area = float(group.geometry.area.sum())
            rows.append({"hydrologic_class": cls, "area_m2": area, "area_ha": area / 10000.0, "area_percent": 0 if total == 0 else area / total * 100.0, "notes": "DUSAF6 clipped to catchment candidate."})
        pd.DataFrame(rows).sort_values("area_m2", ascending=False).to_csv(catch_sum, index=False)

        burn_path = ROOT / "data/processed/burn/burned_area_proxy.gpkg"
        burn_rows = []
        if burn_path.exists():
            burn = gpd.read_file(burn_path).to_crs(WORKING_CRS).geometry.union_all()
            for cls, group in lc.groupby("hydrologic_class"):
                area = float(group.geometry.intersection(burn).area.sum())
                if area > 0:
                    burn_rows.append({"hydrologic_class": cls, "area_m2": area, "area_ha": area / 10000.0, "notes": "DUSAF6 class intersected with dNBR burn proxy."})
        pd.DataFrame(burn_rows or [{"hydrologic_class": "none", "area_m2": 0, "area_ha": 0, "notes": "No burn proxy intersection."}]).sort_values("area_m2", ascending=False).to_csv(burn_sum, index=False)

        register_generated_dataset("landcover_utm32", "DUSAF6 clipped land cover", "landcover", lc_path, "processed", WORKING_CRS, "Clipped from local DUSAF6 raw ZIP.")
        register_generated_dataset("landcover_hydrologic", "DUSAF6 hydrologic land-cover classes", "model_input", hyd_path, "processed", WORKING_CRS, "Reclassified from DUSAF6 codes into simplified hydrologic classes.")
        created = [str(p.relative_to(ROOT)) for p in [lc_path, hyd_path, catch_sum, burn_sum]]
        status = "DONE"
        reason = "Prepared DUSAF6 land-cover hydrologic classes from local raw ZIP."
        qa = vector_valid(hyd_path, WORKING_CRS)[1] + [f"features={len(lc)}", f"classes={len(rows)}"]

    update_backlog({"G001": "DONE", "G002": "DONE", "G003": "DONE", "G004": "DONE", "G005": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Clip local DUSAF6 to catchment and reclassify hydrologic classes.",
            inputs=["data/raw/zip/DUSAF6_REGIONE_LOMBARDIA.zip", "data/processed/boundary/catchment_utm32.gpkg"],
            outputs=[str(p.relative_to(ROOT)) for p in [hyd_path, catch_sum, burn_sum]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(hyd_path.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/09_prepare_soil.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
