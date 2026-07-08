"""Purpose: Scan local raw data directories and record file metadata into local_data_inventory.csv.
Inputs: data/raw/zip/ contents; local raster and vector files.
Outputs: results/metadata/evidence/local_data_inventory.csv.
CRS: Detected from source files; source CRS recorded, not transformed.
Units: As reported by source file metadata.
Assumptions: All files in data/raw/zip/ are project-owner-supplied and immutable.
"""
from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

from pipeline_utils import (
    INVENTORY_COLUMNS,
    ROOT,
    StepLog,
    append_run_log,
    dataframe_to_csv,
    ensure_workspace,
    import_geo,
    import_raster,
    register_reused_dataset,
    update_backlog,
)

GEOSPATIAL_SUFFIXES = {".tif", ".tiff", ".img", ".gpkg", ".shp", ".geojson", ".json", ".jp2", ".zip"}
IGNORE_DIRS = {".omx", ".git", "__pycache__", ".pytest_cache"}


def classify(path: Path) -> str:
    lower = str(path).lower()
    if path.suffix.lower() == ".zip":
        if "sentinel" in lower or "msil2a" in lower or "safe" in lower:
            return "sentinel2_archive"
        if "dtm" in lower:
            return "dem_archive"
        if "dusaf" in lower:
            return "landcover_archive"
        if "fuoco" in lower or "aree_percorse" in lower:
            return "fire_perimeter_archive"
        if "reticolo" in lower or "idrograf" in lower:
            return "hydrography_archive"
        if "soil" in lower:
            return "soil_archive"
        if path.name.startswith("RW_"):
            return "weather_archive"
        return "zip_archive"
    if "dtm" in lower or path.suffix.lower() in {".img", ".tif", ".tiff"}:
        return "dem_or_raster"
    if "varese" in lower or path.suffix.lower() in {".shp", ".gpkg", ".geojson", ".json"}:
        return "hydrography_or_vector"
    if lower.endswith(".safe") or ".safe" in lower or path.suffix.lower() == ".jp2":
        return "sentinel2"
    if "soil" in lower:
        return "soil"
    if "land" in lower or "dusaf" in lower:
        return "landcover"
    return "unknown_geospatial"


def inspect_path(path: Path) -> dict[str, str]:
    row = {
        "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
        "file_type": "directory" if path.is_dir() else path.suffix.lower().lstrip(".") or "missing_expected",
        "dataset_guess": classify(path),
        "exists": str(path.exists()),
        "readable": "False",
        "driver": "",
        "crs": "",
        "extent": "",
        "width": "",
        "height": "",
        "feature_count": "",
        "layer_names": "",
        "notes": "",
    }
    if not path.exists():
        row["notes"] = "Expected local candidate not found."
        return row
    try:
        if path.is_dir():
            safe_files = list(path.glob("**/*.SAFE"))
            geofiles = [p for p in path.glob("**/*") if p.suffix.lower() in GEOSPATIAL_SUFFIXES]
            row.update({"readable": "True", "feature_count": str(len(geofiles)), "layer_names": ";".join(str(p.relative_to(ROOT)) for p in geofiles[:20])})
            if safe_files:
                row["dataset_guess"] = "sentinel2"
            row["notes"] = "Directory scanned for geospatial candidates."
            return row
        suffix = path.suffix.lower()
        if suffix == ".zip":
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
                    geonames = [n for n in names if Path(n).suffix.lower() in {".shp", ".gpkg", ".geojson", ".tif", ".img", ".jp2", ".csv"} or n.endswith(".SAFE/")]
                row.update({"readable": "True", "driver": "ZIP", "feature_count": str(len(names)), "layer_names": ";".join(geonames[:30]), "notes": "Immutable raw ZIP archive inventoried by member names."})
            else:
                row["notes"] = "File has .zip suffix but is not a valid ZIP archive."
            return row
        if suffix in {".tif", ".tiff", ".img", ".jp2"}:
            rasterio, _, _ = import_raster()
            with rasterio.open(path) as ds:
                b = ds.bounds
                row.update(
                    {
                        "readable": "True",
                        "driver": ds.driver,
                        "crs": str(ds.crs) if ds.crs else "",
                        "extent": f"{b.left:.3f},{b.bottom:.3f},{b.right:.3f},{b.top:.3f}",
                        "width": str(ds.width),
                        "height": str(ds.height),
                    }
                )
        elif suffix in {".gpkg", ".shp", ".geojson", ".json"}:
            gpd, *_ = import_geo()
            try:
                import fiona

                layers = fiona.listlayers(path) if suffix == ".gpkg" else [path.stem]
            except Exception:
                layers = [path.stem]
            gdf = gpd.read_file(path, layer=layers[0] if layers else None)
            b = gdf.total_bounds if len(gdf) else ["", "", "", ""]
            row.update(
                {
                    "readable": "True",
                    "driver": suffix.lstrip("."),
                    "crs": str(gdf.crs) if gdf.crs else "",
                    "extent": ",".join(str(x) for x in b),
                    "feature_count": str(len(gdf)),
                    "layer_names": ";".join(layers),
                }
            )
        else:
            row["readable"] = "True"
            row["notes"] = "Existing non-geospatial file recorded only if matched by known local-data name."
    except Exception as exc:
        row["notes"] = f"Inspection failed: {type(exc).__name__}: {exc}"
    return row


def find_candidates() -> list[Path]:
    explicit = [ROOT / "DTM5_RL" / "DTM5_RL.img", ROOT / "DTM5_RL" / "DTM5_RL.ige", ROOT / "lombardia_dtm", ROOT / "VARESE", ROOT / "zip"]
    found: set[Path] = {p for p in explicit}
    for base in ROOT.iterdir():
        if base.name in IGNORE_DIRS:
            continue
        if base.is_file() and (base.suffix.lower() in GEOSPATIAL_SUFFIXES or base.name.endswith(".SAFE")):
            found.add(base)
        elif base.is_dir() and base.name not in {"scripts", "config", "tests", "docs", "logs", "results"}:
            if base.name.startswith("data"):
                search_base = base
            else:
                search_base = base
            for p in search_base.rglob("*"):
                if any(part in IGNORE_DIRS for part in p.parts):
                    continue
                if p.is_file() and (p.suffix.lower() in GEOSPATIAL_SUFFIXES or p.name.endswith(".SAFE")):
                    found.add(p)
                if p.is_dir() and p.name.endswith(".SAFE"):
                    found.add(p)
    return sorted(found, key=lambda p: str(p))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory existing local geospatial datasets before any downloads.")
    parser.add_argument("--max-rows", type=int, default=10000, help="Maximum inventory rows to write.")
    args = parser.parse_args()

    ensure_workspace()
    rows = [inspect_path(path) for path in find_candidates()[: args.max_rows]]
    out = ROOT / "qa/evidence/local_data_inventory.csv"
    dataframe_to_csv(out, rows, INVENTORY_COLUMNS)

    readable_dem = 0
    readable_hydro = 0
    sentinel = 0
    for row in rows:
        path = ROOT / row["path"] if row["path"] and not Path(row["path"]).is_absolute() else Path(row["path"])
        if row["readable"] == "True" and row["dataset_guess"] == "dem_or_raster" and path.suffix.lower() in {".tif", ".tiff", ".img"}:
            readable_dem += 1
            register_reused_dataset("local_dem", "Existing local DEM/raster candidate", "dem", path, row.get("crs", ""), "Detected during local inventory; verify source/license before publication.")
        if row["readable"] == "True" and row["dataset_guess"] == "hydrography_or_vector" and path.suffix.lower() in {".gpkg", ".shp", ".geojson", ".json"}:
            readable_hydro += 1
            register_reused_dataset("local_hydrography_or_vector", "Existing local vector candidate", "hydrography_or_boundary", path, row.get("crs", ""), "Detected during local inventory; verify role/source before scientific use.")
        if "sentinel2" in row["dataset_guess"]:
            sentinel += 1

    statuses = {
        "B001": "DONE",
        "B002": "DONE" if readable_dem else "SKIPPED",
        "B003": "DONE" if readable_hydro else "SKIPPED",
        "B004": "DONE" if sentinel else "SKIPPED",
    }
    note = f"Inventory wrote {len(rows)} rows; readable DEM candidates={readable_dem}; readable vector/hydro candidates={readable_hydro}; Sentinel-2 candidates={sentinel}."
    update_backlog(statuses, note, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Scan project root for existing DEM, VARESE hydrography, GeoPackage/Shapefile/GeoTIFF/Sentinel-2 files before downloads.",
            inputs=["project root"],
            outputs=["qa/evidence/local_data_inventory.csv", "qa/evidence/source_manifest.csv"],
            status="DONE" if rows else "PARTIAL",
            reason=note if rows else "No local geospatial data found; expected local candidates recorded as missing.",
            files_created=["qa/evidence/local_data_inventory.csv"],
            files_reused=[row["path"] for row in rows if row.get("readable") == "True"],
            qa_checks=["Inventory CSV has required columns", f"Rows={len(rows)}"],
            next_action="Run scripts/02_discover_sources.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
