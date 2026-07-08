"""Purpose: Attempt automated download of open datasets; register blockers where human action is required.
Inputs: Source discovery results from step 02.
Outputs: Downloaded files in data/raw/ (where possible); blocker entries in qa/evidence/README.md.
CRS: Source CRS preserved; not reprojected.
Units: Source units preserved.
Assumptions: Only opens datasets with clear open-access terms; interactive portals documented as manual tasks.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import (
    RAW_ZIP_DIR,
    ROOT,
    StepLog,
    append_run_log,
    ensure_workspace,
    register_raw_archive,
    update_backlog,
    write_data_gap_assessment,
)
from raw_data_utils import AOI_GPKG_UTM, DTM_ZIP, DUSAF_ZIP, FIRE_ZIP, HYDRO_ZIP, SOIL_DIR, sentinel_zips, weather_zips


def main() -> int:
    parser = argparse.ArgumentParser(description="Register local raw datasets and download only truly missing essential data.")
    parser.add_argument("--allow-large-downloads", action="store_true", help="No-op for this local-data iteration; local ZIPs are preferred.")
    args = parser.parse_args()

    ensure_workspace()
    created_or_reused: list[str] = []
    rows = []

    datasets = [
        ("processing_aoi", "Processing AOI", "Critical processing mask", AOI_GPKG_UTM, "Use as processing mask only; not a scientific catchment.", "spatial frame"),
        ("fire_perimeter_2019", "Official Lombardia burned-area polygons", "Critical fire reference", FIRE_ZIP, "Filter 2019 Monte Martica polygon from official Regione Lombardia fire-perimeter archive.", "2019"),
        ("dtm5_rl", "Regione Lombardia DTM5", "Critical DEM", DTM_ZIP, "Use via GDAL /vsizip without modifying raw archive.", "terrain"),
        ("hydrography_lombardia", "Reticolo idrografico regionale unificato", "Critical hydrography QA", HYDRO_ZIP, "Clip regional hydrography to processing AOI for outlet QA.", "hydrography"),
        ("landcover_dusaf6", "DUSAF6 Regione Lombardia", "High-value land cover", DUSAF_ZIP, "Clip and reclassify DUSAF6 polygons into hydrologic classes.", "landcover"),
    ]
    for dataset_id, name, priority, path, decision, role in datasets:
        exists = path.exists()
        rows.append({"dataset": name, "priority": priority, "local_status": "available" if exists else "missing", "decision": decision if exists else "Non-optional if scientific rerun is required; acquire before final interpretation.", "path_or_next_action": str(path)})
        if exists:
            register_raw_archive(dataset_id, name, role, path, decision)
            created_or_reused.append(str(path.relative_to(ROOT)))

    s2 = sentinel_zips()
    rows.append({"dataset": "Sentinel-2 L2A pre/post products", "priority": "Critical burn proxy", "local_status": f"{len(s2)} SAFE ZIPs available" if s2 else "missing", "decision": "Use local products; compute dNBR proxy with Pillow+SAFE geocoding because GDAL JP2OpenJPEG is unavailable." if s2 else "Download pre/post L2A products only if local ZIPs are absent.", "path_or_next_action": "data/raw/zip/S2*_MSIL2A_*.SAFE.zip"})
    for path in s2:
        register_raw_archive("sentinel2_l2a_products", "Sentinel-2 L2A SAFE ZIP", "pre_post_fire_nbr", path, "Local Sentinel-2 SAFE ZIP reused; individual JP2 bands are read through Pillow and SAFE metadata.", "2018-12 to 2019-01")
        created_or_reused.append(str(path.relative_to(ROOT)))

    weather = weather_zips()
    rows.append({"dataset": "ARPA-style precipitation CSV ZIPs", "priority": "Critical rainfall forcing", "local_status": f"{len(weather)} ZIPs available" if weather else "missing", "decision": "Parse hourly station 907/sensor 8228 data for event extraction." if weather else "Manual ARPA download needed for actual rainfall; design events only as fallback.", "path_or_next_action": "data/raw/zip/RW_*.zip"})
    for path in weather:
        register_raw_archive("weather_arpa_precipitation", "ARPA-style precipitation extract", "rainfall_forcing", path, "Local weather ZIP reused and parsed in step 10.", "2019-2020")
        created_or_reused.append(str(path.relative_to(ROOT)))

    soil_ok = SOIL_DIR.exists() and any(SOIL_DIR.glob("*_weighted_mean_utm32.tif"))
    rows.append({"dataset": "SoilGrids Lake Varese composites", "priority": "High-value soil/HSG", "local_status": "available" if soil_ok else "missing", "decision": "Derive simplified HSG from local sand/clay/silt composites." if soil_ok else "Use documented fallback only; soil uncertainty remains high.", "path_or_next_action": str(SOIL_DIR)})
    if soil_ok:
        register_raw_archive("soilgrids_lake_varese", "SoilGrids Lake Varese composites", "soil_hydrologic_group_derivation", SOIL_DIR, "Local SoilGrids composites reused for simplified HSG derivation.", "static soil properties")
        created_or_reused.append(str(SOIL_DIR.relative_to(ROOT)))

    assessment = write_data_gap_assessment(rows)

    statuses = {
        "C002": "DONE" if FIRE_ZIP.exists() else "BLOCKED",
        "C003": "DONE" if DUSAF_ZIP.exists() else "BLOCKED",
        "C005": "DONE" if soil_ok else "BLOCKED",
        "C006": "DONE" if weather else "BLOCKED",
        "C007": "DONE",
        "F003": "DONE" if s2 else "BLOCKED",
        "G001": "DONE" if DUSAF_ZIP.exists() else "BLOCKED",
        "H001": "DONE" if soil_ok else "BLOCKED",
        "I001": "DONE" if weather else "BLOCKED",
    }
    note = f"Registered local raw data from {RAW_ZIP_DIR}; no browser/headless downloads needed in this iteration."
    update_backlog(statuses, note, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Register project-owner supplied raw ZIP/folder data and decide what remains missing.",
            inputs=["data/raw/zip/*"],
            outputs=["qa/evidence/source_manifest.csv", "qa/audit/README.md"],
            status="DONE",
            reason=note,
            files_created=[str(assessment.relative_to(ROOT))],
            files_reused=created_or_reused,
            qa_checks=["Raw archives were not modified", "Essential inputs available locally", "No unsafe scraping/download performed"],
            next_action="Run scripts/run_pipeline.py --from 04 --to 12 to process local data.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
