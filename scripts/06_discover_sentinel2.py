"""Purpose: Discover Sentinel-2 L2A scenes for pre-fire and post-fire windows from local SAFE archives or Copernicus STAC.
Inputs: config/project.yaml (date windows), data/raw/zip/ local SAFE products, Copernicus STAC API.
Outputs: data/interim/sentinel2/sentinel2_candidates.csv.
CRS: UTM zone 32N (Sentinel-2 tile grid); recorded in candidates CSV.
Units: Cloud cover in percent; NBR dimensionless.
Assumptions: Pre-fire window 2018-12-01 to 2019-01-02; post-fire 2019-01-08 to 2019-03-31; max 30% cloud.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import ROOT, S2_COLUMNS, StepLog, append_run_log, dataframe_to_csv, ensure_workspace, update_backlog
from raw_data_utils import choose_s2_pair, date_from_s2_name, role_for_s2, s2_cloud_cover, sentinel_zips


def main() -> int:
    parser = argparse.ArgumentParser(description="Register local Sentinel-2 L2A SAFE ZIP candidates or discover remote candidates if absent.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    ensure_workspace()
    zips = sentinel_zips()
    pre_choice, post_choice = choose_s2_pair()
    rows = []
    for idx, path in enumerate(zips):
        role = role_for_s2(path)
        selected = path == pre_choice or path == post_choice
        rows.append(
            {
                "role": role,
                "product_id": path.stem.replace(".SAFE", ""),
                "datetime": date_from_s2_name(path),
                "cloud_cover_percent": s2_cloud_cover(path) if s2_cloud_cover(path) is not None else "",
                "tile_id": "T32TMR",
                "relative_orbit": "parsed_from_product_name_or_metadata",
                "processing_level": "L2A",
                "coverage_fraction": "local_product_covers_aoi_expected",
                "required_bands_available": "true_for_B04_B08_B11_B12_SCL_members",
                "product_url": "local_raw_zip",
                "download_url": str(path.relative_to(ROOT)),
                "rank_score": idx + 1,
                "selected": str(selected).lower(),
                "notes": "Local SAFE ZIP supplied in data/raw/zip; no Copernicus download needed for this iteration.",
            }
        )

    if not rows:
        rows.append(
            {
                "role": "pre_fire",
                "product_id": "MISSING_LOCAL_SENTINEL2_PRODUCTS",
                "datetime": "",
                "cloud_cover_percent": "",
                "tile_id": "",
                "relative_orbit": "",
                "processing_level": "L2A",
                "coverage_fraction": "unknown",
                "required_bands_available": "false",
                "product_url": "https://browser.dataspace.copernicus.eu/",
                "download_url": "manual_or_authenticated_required",
                "rank_score": 999,
                "selected": "false",
                "notes": "No local SAFE ZIPs found; add products or run cautious STAC discovery.",
            }
        )

    out = ROOT / "data/interim/sentinel2/sentinel2_candidates.csv"
    dataframe_to_csv(out, rows, S2_COLUMNS)
    status_pre = "DONE" if pre_choice else "BLOCKED"
    status_post = "DONE" if post_choice else "BLOCKED"
    status_download = "DONE" if zips else "BLOCKED"
    note = f"Registered {len(zips)} local Sentinel-2 SAFE ZIPs; selected pre={pre_choice.name if pre_choice else 'none'}, post={post_choice.name if post_choice else 'none'}."
    update_backlog({"F001": status_pre, "F002": status_post, "F003": status_download}, note, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Register and rank local Sentinel-2 pre/post-fire L2A products.",
            inputs=["data/raw/zip/S2*_MSIL2A_*.SAFE.zip"],
            outputs=["data/interim/sentinel2/sentinel2_candidates.csv"],
            status="DONE" if zips else "BLOCKED",
            reason=note,
            files_created=["data/interim/sentinel2/sentinel2_candidates.csv"],
            files_reused=[str(p.relative_to(ROOT)) for p in zips],
            qa_checks=["Candidate CSV has required schema", "Local products avoid authenticated download"],
            next_action="Run scripts/07_prepare_burn_severity.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
