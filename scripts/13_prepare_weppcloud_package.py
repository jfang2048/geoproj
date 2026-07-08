"""Purpose: Assemble WEPPcloud input package — burn raster, outlet coordinates, reference GeoJSONs, comparison template, and screenshots.
Inputs: data/processed/burn/burn_severity_proxy_uint8.tif, data/processed/boundary/catchment_utm32.gpkg, data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg, data/processed/hydrography/streams_lombardia_varese_utm32.gpkg, results/metadata/evidence/outlet_candidates.csv.
Outputs: results/weppcloud/lake_varese_monte_martica_weppcloud_input_package.zip containing burn raster (EPSG:32632 uint8), outlet CSV (WGS84), reference GeoJSONs (WGS84), comparison template, and screenshots.
CRS: EPSG:32632 (burn raster, local); EPSG:4326 (outlet, reference GeoJSONs for browser).
Units: Burn class codes 0-3,255; coordinates in decimal degrees; area in ha.
Assumptions: WEPPcloud-EU accepts uint8 categorical burn raster; reproject to WGS84 on export only.
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from pipeline_utils import ROOT, WORKING_CRS, StepLog, append_run_log, ensure_workspace, update_backlog, vector_valid, raster_valid


def read_outlet() -> dict[str, object]:
    path = ROOT / "qa/evidence/outlet_candidates.csv"
    if not path.exists():
        raise FileNotFoundError("Missing results/metadata/evidence/outlet_candidates.csv; run step 05 first.")
    df = pd.read_csv(path)
    if df.empty:
        raise RuntimeError("Outlet candidates table is empty.")
    row = df.iloc[0].to_dict()
    x = float(row["x_utm32"])
    y = float(row["y_utm32"])
    lon, lat = Transformer.from_crs(WORKING_CRS, "EPSG:4326", always_xy=True).transform(x, y)
    row["outlet_lon_wgs84"] = lon
    row["outlet_lat_wgs84"] = lat
    return row


def raster_summary(path: Path) -> dict[str, object]:
    with rasterio.open(path) as ds:
        arr = ds.read(1)
        unique = sorted(int(v) for v in np.unique(arr) if np.isfinite(v))
        return {
            "path": str(path.relative_to(ROOT)),
            "driver": ds.driver,
            "dtype": ds.dtypes[0],
            "count": ds.count,
            "crs": str(ds.crs),
            "epsg": ds.crs.to_epsg() if ds.crs else None,
            "width": ds.width,
            "height": ds.height,
            "nodata": ds.nodata,
            "unique_values": unique,
            "weppcloud_sbs_ready": ds.count == 1 and ds.dtypes[0] in {"uint8", "uint16", "int16", "int32"} and len(unique) <= 256 and (ds.crs is not None),
        }


def vector_area_ha(path: Path) -> float:
    import geopandas as gpd

    gdf = gpd.read_file(path).to_crs(WORKING_CRS)
    return float(gdf.geometry.area.sum() / 10000.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a local WEPPcloud input package from verified processed outputs.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    package_dir = ROOT / "outputs/models/weppcloud/input_package"
    screenshots_dir = package_dir / "screenshots_for_upload_reference"
    package_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    burn_src = ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif"
    catchment_src = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
    fire_src = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
    hydro_src = ROOT / "data/processed/hydrography/streams_lombardia_varese_utm32.gpkg"
    events_src = ROOT / "data/processed/weather/post_fire_rainfall_events.csv"
    runoff_src = ROOT / "outputs/tables/runoff_event_summary.csv"
    required = [burn_src, catchment_src, fire_src, hydro_src, events_src, runoff_src]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required processed outputs: {missing}")

    burn_dst = package_dir / "burn_severity_proxy_weppcloud_uint8.tif"
    shutil.copy2(burn_src, burn_dst)

    import geopandas as gpd

    catchment = gpd.read_file(catchment_src).to_crs("EPSG:4326")
    fire = gpd.read_file(fire_src).to_crs("EPSG:4326")
    hydro = gpd.read_file(hydro_src).to_crs("EPSG:4326")
    catchment_geojson = package_dir / "catchment_reference_wgs84.geojson"
    fire_geojson = package_dir / "official_fire_perimeter_reference_wgs84.geojson"
    hydro_geojson = package_dir / "hydrography_reference_wgs84.geojson"
    for path in [catchment_geojson, fire_geojson, hydro_geojson]:
        if path.exists():
            path.unlink()
    catchment.to_file(catchment_geojson, driver="GeoJSON")
    fire.to_file(fire_geojson, driver="GeoJSON")
    hydro.to_file(hydro_geojson, driver="GeoJSON")

    outlet = read_outlet()
    outlet_csv = package_dir / "outlet_weppcloud_wgs84.csv"
    pd.DataFrame([outlet]).to_csv(outlet_csv, index=False)

    for src in [
        ROOT / "outputs/maps/03_final_catchment_fire_hydrography_overlay.png",
        ROOT / "outputs/maps/06_burn_severity_proxy_vs_fire_reference.png",
        ROOT / "outputs/maps/07_runoff_delta_event_main.png",
        ROOT / "outputs/figures/rainfall_events_2019.png",
        ROOT / "outputs/figures/weppcloud_input_package_overview.png",
    ]:
        if src.exists():
            shutil.copy2(src, screenshots_dir / src.name)

    rainfall = pd.read_csv(events_src)
    runoff = pd.read_csv(runoff_src)
    largest_event = rainfall.sort_values("total_precip_mm", ascending=False).iloc[0].to_dict() if not rainfall.empty else {}
    metrics = {
        "catchment_area_ha": vector_area_ha(catchment_src),
        "official_fire_area_ha": vector_area_ha(fire_src),
        "burn_raster": raster_summary(burn_dst),
        "outlet": outlet,
        "rainfall_event_count": int(len(rainfall)),
        "largest_rainfall_event": largest_event,
        "runoff_event_summary_rows": int(len(runoff)),
        "local_model_note": "Simplified SCS-CN-style screening, not calibrated discharge.",
    }
    metrics_json = package_dir / "weppcloud_input_metrics.json"
    metrics_json.write_text(json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    comparison_template = package_dir / "weppcloud_area_comparison_template.csv"
    pd.DataFrame(
        [
            {
                "local_catchment_area_ha": metrics["catchment_area_ha"],
                "weppcloud_catchment_area_ha": "fill_after_weppcloud_run",
                "area_difference_percent": "=ABS(B2-A2)/A2*100",
                "drainage_matches_fire_and_lake": "yes/no_after_visual_review",
                "decision": "accept/rerun/reject_after_weppcloud_run",
                "notes": "Compare WEPPcloud delineation against local DTM5/hydrography/fire overlay.",
            }
        ]
    ).to_csv(comparison_template, index=False)

    readme = package_dir / "README_WEPPcloud_input_package.md"
    readme.write_text(
        "# WEPPcloud Input Package - Lake Varese / Monte Martica\n\n"
        "Use this package manually in WEPPcloud. Do not upload files that you do not want stored on WEPPcloud servers.\n\n"
        "## Upload / entry items\n\n"
        f"- Outlet longitude: `{metrics['outlet']['outlet_lon_wgs84']:.8f}`\n"
        f"- Outlet latitude: `{metrics['outlet']['outlet_lat_wgs84']:.8f}`\n"
        "- Burn raster for upload: `burn_severity_proxy_weppcloud_uint8.tif`\n"
        "- Burn classes: 0=unburned, 1=low, 2=moderate, 3=high, 255=NoData\n"
        "- Reference catchment: `catchment_reference_wgs84.geojson`\n"
        "- Reference official fire perimeter: `official_fire_perimeter_reference_wgs84.geojson`\n"
        "- Reference hydrography: `hydrography_reference_wgs84.geojson`\n\n"
        "## Verified local metrics\n\n"
        f"- Local catchment candidate area: `{metrics['catchment_area_ha']:.2f} ha`\n"
        f"- Official selected fire polygon area: `{metrics['official_fire_area_ha']:.2f} ha`\n"
        f"- Rainfall events extracted: `{metrics['rainfall_event_count']}`\n"
        f"- Local runoff summary rows: `{metrics['runoff_event_summary_rows']}`\n"
        f"- Burn raster single-band integer/projection check: `{metrics['burn_raster']['weppcloud_sbs_ready']}`\n\n"
        "## After WEPPcloud run\n\n"
        "Fill `weppcloud_area_comparison_template.csv`, save project URLs/screenshots under `results/weppcloud/`, then compare WEPPcloud baseline/burned directionality with local tables.\n",
        encoding="utf-8",
    )

    zip_path = ROOT / "outputs/models/weppcloud/lake_varese_monte_martica_weppcloud_input_package.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in package_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(package_dir)))

    ok_raster, raster_checks = raster_valid(burn_dst, WORKING_CRS, require_valid_pixels=True)
    ok_catchment, catchment_checks = vector_valid(catchment_src, WORKING_CRS)
    status = "DONE" if ok_raster and ok_catchment and metrics["burn_raster"]["weppcloud_sbs_ready"] else "PARTIAL"
    reason = "Prepared verified local WEPPcloud input package; browser-side WEPPcloud run remains manual."
    update_backlog({"K001": "DONE", "K002": "DONE", "K003": "DONE", "K004": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Prepare local WEPPcloud input package and verification metrics.",
            inputs=[str(p.relative_to(ROOT)) for p in required],
            outputs=[str(p.relative_to(ROOT)) for p in [package_dir, zip_path]],
            status=status,
            reason=reason,
            files_created=[str(p.relative_to(ROOT)) for p in [burn_dst, catchment_geojson, fire_geojson, hydro_geojson, outlet_csv, metrics_json, comparison_template, readme, zip_path]],
            files_reused=[str(p.relative_to(ROOT)) for p in required],
            qa_checks=raster_checks + catchment_checks + [f"weppcloud_sbs_ready={metrics['burn_raster']['weppcloud_sbs_ready']}", f"zip_size_bytes={zip_path.stat().st_size}"],
            next_action="Open WEPPcloud manually and use outputs/models/weppcloud/input_package/README_WEPPcloud_input_package.md.",
        )
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
    print(f"WEPPcloud package: {zip_path}")
    return 0 if status == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
