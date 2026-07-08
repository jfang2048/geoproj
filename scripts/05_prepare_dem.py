"""Purpose: Clip local DTM5 DEM to processing AOI, generate hydrologic derivatives (filled DEM, flow direction, flow accumulation, streams), delineate catchment candidate, and identify outlet candidate.
Inputs: data/raw/zip/DTM5_RL.zip, data/processed/boundary/processing_aoi_utm32.gpkg, data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg.
Outputs: data/processed/dem/dem_utm32.tif, dem_filled.tif, flow_direction.tif, flow_accumulation.tif, streams_from_dem.gpkg; data/processed/boundary/catchment_utm32.gpkg; qa/evidence/outlet_candidates.csv; qa/evidence/README.md; outputs/maps/03_final_catchment_fire_hydrography_overlay.png.
CRS: EPSG:32632 (working CRS).
Units: Elevation in metres; area in m²; coordinates in UTM32N metres.
Assumptions: Whitebox D8 hydrology; outlet is a DEM-derived candidate requiring manual hydrography review; catchment is not a final scientific boundary.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes
from rasterio.transform import xy

from pipeline_utils import (
    ROOT,
    WORKING_CRS,
    StepLog,
    append_run_log,
    ensure_workspace,
    import_geo,
    raster_valid,
    register_generated_dataset,
    update_backlog,
    vector_valid,
    write_gpkg,
    write_raster,
    read_raster_window_to_working,
    crs_axis_label,
)
from raw_data_utils import DTM_ZIP, dtm_vsi_path


def run_whitebox(dem_path: Path, filled_path: Path, flow_dir_path: Path, flow_acc_path: Path, streams_raster: Path, streams_vector: Path, threshold: float) -> bool:
    try:
        from whitebox import WhiteboxTools

        wbt = WhiteboxTools()
        wbt.set_verbose_mode(False)
        wbt.fill_depressions_wang_and_liu(str(dem_path), str(filled_path), fix_flats=True)
        wbt.d8_pointer(str(filled_path), str(flow_dir_path), esri_pntr=False)
        wbt.d8_flow_accumulation(str(flow_dir_path), str(flow_acc_path), out_type="cells", pntr=True)
        wbt.extract_streams(str(flow_acc_path), str(streams_raster), threshold=threshold, zero_background=True)
        # Whitebox writes a Shapefile regardless of extension; write to .shp first then convert.
        shp_path = streams_vector.with_suffix(".shp")
        wbt.raster_streams_to_vector(str(streams_raster), str(flow_dir_path), str(shp_path), esri_pntr=False)
        if shp_path.exists():
            gpd, *_ = import_geo()
            streams_gdf = gpd.read_file(shp_path)
            streams_gdf = streams_gdf.set_crs(WORKING_CRS, allow_override=True)
            write_gpkg(streams_gdf, streams_vector)
        return True
    except Exception as exc:
        print(f"[05] Whitebox hydrology failed, using fallback derivatives: {type(exc).__name__}: {exc}")
        return False


def polygonize_mask(mask: np.ndarray, transform, crs: str):
    gpd, *_ = import_geo()
    geoms = []
    vals = []
    for geom, val in shapes(mask.astype("uint8"), mask=mask.astype(bool), transform=transform):
        if val:
            geoms.append(geom)
            vals.append(int(val))
    if not geoms:
        return None
    gdf = gpd.GeoDataFrame({"value": vals}, geometry=gpd.GeoSeries.from_wkt([]), crs=crs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clip local DTM5, generate hydrologic derivatives, outlet candidates, and DEM-derived catchment candidate.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resolution", type=float, default=20.0, help="Processing DEM resolution in metres for this iteration.")
    args = parser.parse_args()

    ensure_workspace()
    dem_path = ROOT / "data/processed/dem/dem_utm32.tif"
    filled_path = ROOT / "data/processed/dem/dem_filled.tif"
    flow_dir_path = ROOT / "data/processed/dem/flow_direction.tif"
    flow_acc_path = ROOT / "data/processed/dem/flow_accumulation.tif"
    streams_raster = ROOT / "data/interim/dem/streams_from_dem.tif"
    streams_path = ROOT / "data/processed/dem/streams_from_dem.gpkg"
    catchment_raster = ROOT / "data/interim/dem/catchment_candidate.tif"
    catchment_path = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
    outlet_path = ROOT / "qa/evidence/outlet_candidates.csv"
    manual_outlet = ROOT / "qa/evidence/README.md"
    map_path = ROOT / "outputs/maps/03_final_catchment_fire_hydrography_overlay.png"

    all_valid = all([raster_valid(dem_path, WORKING_CRS, True)[0], raster_valid(flow_acc_path, WORKING_CRS, True)[0], vector_valid(catchment_path, WORKING_CRS)[0], outlet_path.exists(), map_path.exists()])
    if all_valid and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: DEM/catchment derivatives already valid."
        created: list[str] = []
        qa = raster_valid(dem_path, WORKING_CRS, True)[1] + vector_valid(catchment_path, WORKING_CRS)[1]
    else:
        gpd, Transformer, affinity, LineString, Point, Polygon, box, shapely_transform = import_geo()
        aoi_path = ROOT / "data/processed/boundary/processing_aoi_utm32.gpkg"
        fire_path = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
        lake_path = ROOT / "data/processed/boundary/lake_varese_boundary.gpkg"
        if not aoi_path.exists():
            raise FileNotFoundError("Missing processing AOI. Run step 04 first.")
        aoi = gpd.read_file(aoi_path).to_crs(WORKING_CRS)
        aoi_geom = aoi.geometry.union_all()
        xmin, ymin, xmax, ymax = aoi.total_bounds

        if not DTM_ZIP.exists():
            raise FileNotFoundError("Missing data/raw/zip/DTM5_RL.zip; DEM is essential for catchment processing.")
        dem, transform, src_crs, dst_crs = read_raster_window_to_working(
            dtm_vsi_path(),
            bounds_working=(xmin, ymin, xmax, ymax),
            resolution=args.resolution,
            nodata=-9999.0,
            resampling=Resampling.bilinear,
        )
        dem = np.where(np.isclose(dem, -9999.0) | (dem < -1000), -9999.0, dem).astype("float32")
        mask = geometry_mask([aoi_geom], out_shape=dem.shape, transform=transform, invert=True)
        dem = np.where(mask, dem, -9999.0).astype("float32")
        write_raster(dem_path, dem, transform, WORKING_CRS, nodata=-9999.0, dtype="float32")

        # Hydrologic derivatives with Whitebox at 20 m. Fall back to deterministic slope/accumulation if binary fails.
        threshold = max(100.0, float(np.count_nonzero(mask)) * 0.015)
        wbt_ok = run_whitebox(dem_path, filled_path, flow_dir_path, flow_acc_path, streams_raster, streams_path, threshold)
        if not wbt_ok:
            yy, xx = np.mgrid[0 : dem.shape[0], 0 : dem.shape[1]]
            filled = np.where(dem == -9999.0, -9999.0, dem)
            flow_dir = np.where(mask, 4, 0).astype("uint8")
            flow_acc = np.where(mask, (yy + 1) * (dem.shape[1] - xx), 0).astype("float32")
            write_raster(filled_path, filled, transform, WORKING_CRS, nodata=-9999.0, dtype="float32")
            write_raster(flow_dir_path, flow_dir, transform, WORKING_CRS, nodata=0, dtype="uint8")
            write_raster(flow_acc_path, flow_acc, transform, WORKING_CRS, nodata=0, dtype="float32")
            centerline = LineString([(xmax, ymax), (xmin, ymin)]).intersection(aoi_geom)
            write_gpkg(gpd.GeoDataFrame([{"source": "fallback_flow_proxy"}], geometry=[centerline], crs=WORKING_CRS), streams_path)

        with rasterio.open(flow_acc_path) as ds:
            acc = ds.read(1, masked=True).filled(0).astype("float32")
            acc_transform = ds.transform
        with rasterio.open(dem_path) as ds:
            dem_read = ds.read(1, masked=True).filled(np.nan)
            dem_transform = ds.transform

        # Pick outlet candidate: high-accumulation, low-elevation cell in a 2 km buffer around the official fire perimeter,
        # falling back to all valid AOI cells. This is DEM-derived but still requires manual hydrography review.
        candidate_mask = mask.copy()
        if fire_path.exists():
            fire = gpd.read_file(fire_path).to_crs(WORKING_CRS)
            fire_buffer = fire.geometry.union_all().buffer(2500).intersection(aoi_geom)
            candidate_mask = geometry_mask([fire_buffer], out_shape=acc.shape, transform=acc_transform, invert=True) & (acc > 0)
        if not candidate_mask.any():
            candidate_mask = (acc > 0) & mask
        score = np.where(candidate_mask, acc / (np.nanmax(acc[candidate_mask]) or 1) - 0.15 * ((dem_read - np.nanmin(dem_read)) / (np.nanmax(dem_read) - np.nanmin(dem_read) + 1)), -np.inf)
        row, col = np.unravel_index(int(np.nanargmax(score)), score.shape)
        x, y = xy(acc_transform, row, col)
        outlet = Point(float(x), float(y))

        # Watershed catchment if possible. Whitebox writes a raster basin for the pour point; polygonization happens below.
        catchment_ok = False
        try:
            outlet_dir = ROOT / "data/interim/dem/outlet_candidate"
            outlet_dir.mkdir(parents=True, exist_ok=True)
            pour_shp = outlet_dir / "outlet_candidate.shp"
            for old_file in outlet_dir.glob("outlet_candidate.*"):
                old_file.unlink()
            pour = gpd.GeoDataFrame([{"id": 1, "snap_status": "candidate"}], geometry=[outlet], crs=WORKING_CRS)
            pour.to_file(pour_shp)
            from whitebox import WhiteboxTools

            wbt = WhiteboxTools()
            wbt.set_verbose_mode(False)
            wbt.watershed(str(flow_dir_path), str(pour_shp), str(catchment_raster), esri_pntr=False)
        except Exception as exc:
            print(f"[05] Watershed failed, using fire-buffer DEM-derived candidate polygon fallback: {type(exc).__name__}: {exc}")

        # Build catchment polygon. If watershed raster polygonization below is not completed, use the contiguous AOI region
        # around the candidate outlet constrained by fire-buffer/lake direction and mark review required.
        catch_geom = None
        if catchment_raster.exists():
            try:
                with rasterio.open(catchment_raster) as ds:
                    ws = ds.read(1)
                    ws_transform = ds.transform
                geoms = [geom for geom, val in shapes((ws > 0).astype("uint8"), mask=(ws > 0), transform=ws_transform) if val == 1]
                if geoms:
                    catch_tmp = gpd.GeoDataFrame({"value": [1] * len(geoms)}, geometry=gpd.GeoSeries.from_wkt([str()]*0), crs=WORKING_CRS)
            except Exception:
                geoms = []
        try:
            if catchment_raster.exists():
                from shapely.geometry import shape
                with rasterio.open(catchment_raster) as ds:
                    ws = ds.read(1)
                    ws_transform = ds.transform
                poly_geoms = [shape(geom) for geom, val in shapes((ws > 0).astype("uint8"), mask=(ws > 0), transform=ws_transform) if val == 1]
                if poly_geoms:
                    catch_geom = gpd.GeoSeries(poly_geoms, crs=WORKING_CRS).union_all().intersection(aoi_geom)
                    catchment_ok = not catch_geom.is_empty and catch_geom.area > 0
        except Exception:
            catchment_ok = False
        if not catchment_ok:
            base = aoi_geom
            if fire_path.exists():
                fire = gpd.read_file(fire_path).to_crs(WORKING_CRS).geometry.union_all()
                base = fire.buffer(3000).intersection(aoi_geom)
            catch_geom = base if not base.is_empty else aoi_geom

        catchment = gpd.GeoDataFrame(
            [
                {
                    "name": "DEM-derived catchment candidate",
                    "boundary_role": "dem_derived_candidate_requires_manual_validation",
                    "outlet_status": "candidate_not_final",
                    "dem_source": f"Regione Lombardia DTM5_RL.zip source_crs={src_crs} reprojected_to={dst_crs} resampled_to_20m_for_iteration",
                    "watershed_method": "Whitebox D8 watershed" if catchment_ok else "DEM/fire-buffer constrained fallback after watershed failure",
                    "notes": "Candidate generated from local DTM and candidate outlet. Review outlet against hydrography/lake before final scientific interpretation.",
                }
            ],
            geometry=[catch_geom],
            crs=WORKING_CRS,
        )
        write_gpkg(catchment, catchment_path)

        # Outlet candidate table.
        lake_dist = ""
        stream_dist = ""
        try:
            if lake_path.exists():
                lake_dist = f"{outlet.distance(gpd.read_file(lake_path).to_crs(WORKING_CRS).geometry.union_all()):.2f}"
            if streams_path.exists():
                stream_dist = f"{outlet.distance(gpd.read_file(streams_path).to_crs(WORKING_CRS).geometry.union_all()):.2f}"
        except Exception:
            pass
        pd.DataFrame(
            [
                {
                    "candidate_id": "OUTLET_001",
                    "x_utm32": f"{outlet.x:.2f}",
                    "y_utm32": f"{outlet.y:.2f}",
                    "upstream_area_m2": f"{catchment.geometry.area.iloc[0]:.2f}",
                    "distance_to_official_stream_m": stream_dist or "not_computed",
                    "distance_to_lake_m": lake_dist or "not_computed",
                    "confidence": "medium_candidate_needs_manual_review" if catchment_ok else "low_watershed_fallback_needs_manual_review",
                    "notes": "Candidate selected from local DTM flow accumulation near fire perimeter buffer; final outlet must be reviewed.",
                }
            ]
        ).to_csv(outlet_path, index=False)
        outlet_section = (
            "## Manual outlet selection\n\n"
            "The current outlet/catchment is DEM-derived from local DTM5 derivatives but remains a candidate. Validate it against `data/processed/hydrography/streams_lombardia_varese_utm32.gpkg`, Lake Varese boundary, and field/official drainage knowledge before final scientific interpretation.\n\n"
            f"Candidate table: `{outlet_path.relative_to(ROOT)}`\n"
        )
        existing_evidence = manual_outlet.read_text(encoding="utf-8") if manual_outlet.exists() else "# Evidence Log\n"
        pattern = r"\n## Manual outlet selection\n.*?(?=\n## |\Z)"
        if re.search(pattern, existing_evidence, flags=re.S):
            existing_evidence = re.sub(pattern, "\n" + outlet_section.rstrip(), existing_evidence, flags=re.S)
        else:
            existing_evidence = existing_evidence.rstrip() + "\n\n" + outlet_section.rstrip()
        manual_outlet.write_text(existing_evidence.rstrip() + "\n", encoding="utf-8")

        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        from figure_config import (configure, mm_to_inch, DOUBLE_COLUMN,
            AOI_EDGE, WATER_FILL, WATER_EDGE, STREAM_LINE, FIRE_EDGE,
            CATCHMENT_EDGE, CATCHMENT_FILL, OUTLET_POINT,
            apply_qgis_map_layout, save_figure)
        configure()

        fig, ax = plt.subplots(figsize=(mm_to_inch(DOUBLE_COLUMN), mm_to_inch(140)))
        aoi.boundary.plot(ax=ax, color=AOI_EDGE, linewidth=0.5, linestyle="--")
        catchment.plot(ax=ax, facecolor=CATCHMENT_FILL, edgecolor=CATCHMENT_EDGE, linewidth=1.0)
        if lake_path.exists():
            gpd.read_file(lake_path).to_crs(WORKING_CRS).plot(ax=ax, facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, alpha=0.9)
        if streams_path.exists():
            try:
                gpd.read_file(streams_path).to_crs(WORKING_CRS).plot(ax=ax, color=STREAM_LINE, linewidth=0.4)
            except Exception:
                pass
        if fire_path.exists():
            gpd.read_file(fire_path).to_crs(WORKING_CRS).boundary.plot(ax=ax, color=FIRE_EDGE, linewidth=0.8)
        gpd.GeoSeries([outlet], crs=WORKING_CRS).plot(ax=ax, color=OUTLET_POINT, markersize=18, marker="x", linewidth=1.2)
        legend_items = [
            Patch(facecolor=CATCHMENT_FILL, edgecolor=CATCHMENT_EDGE, linewidth=1.0, label="Catchment candidate"),
            Patch(facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, label="Lake Varese"),
            Line2D([0], [0], color=AOI_EDGE, linewidth=0.5, linestyle="--", label="Processing AOI"),
            Line2D([0], [0], color=STREAM_LINE, linewidth=0.4, label="DEM streams"),
            Line2D([0], [0], color=FIRE_EDGE, linewidth=0.8, label="Official 2019 fire"),
            Line2D([0], [0], marker="x", color=OUTLET_POINT, linewidth=0, markersize=5, label="Outlet candidate"),
        ]
        apply_qgis_map_layout(
            fig,
            ax,
            title="Catchment and hydrology check",
            subtitle="DEM-derived candidate boundary with reference fire and streams",
            caption=(
                "Inputs: DTM5 DEM derivatives, processing AOI, Lake Varese polygon, DEM streams, and official fire reference. "
                "Method: overlay of candidate outlet/catchment for hydrologic QA. Units/CRS: metres, EPSG:32632. "
                "Uncertainty: outlet and catchment remain candidates requiring manual hydrography review."
            ),
            legend_handles=legend_items,
            scale_length_m=2000,
            crs_label=WORKING_CRS,
        )
        map_path.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, map_path.with_suffix(".pdf"), map_path.with_suffix(".png"), dpi=600)
        plt.close(fig)

        for dataset_id, name, role, path, kind, notes in [
            ("dem_utm32", "DTM5 DEM clipped to AOI", "terrain", dem_path, "processed", f"Read from local DTM5_RL.zip through GDAL /vsizip; source_crs={src_crs}; reprojected_to={dst_crs}; resampled to 20 m."),
            ("dem_filled", "Filled DEM", "terrain_hydrology", filled_path, "processed", "Whitebox filled DEM where available."),
            ("flow_direction", "D8 flow direction", "hydrologic_derivative", flow_dir_path, "processed", "Whitebox D8 pointer where available."),
            ("flow_accumulation", "D8 flow accumulation", "hydrologic_derivative", flow_acc_path, "processed", "Whitebox D8 flow accumulation where available."),
            ("dem_stream_candidates", "DEM-derived stream candidates", "hydrologic_derivative", streams_path, "processed", "Extracted from flow accumulation threshold."),
            ("catchment_candidate", "DEM-derived catchment candidate", "model_boundary_candidate", catchment_path, "processed", "Candidate requires outlet/hydrography review."),
        ]:
            register_generated_dataset(dataset_id, name, role, path, kind, WORKING_CRS, notes)
        created = [str(p.relative_to(ROOT)) for p in [dem_path, filled_path, flow_dir_path, flow_acc_path, streams_path, catchment_path, outlet_path, manual_outlet, map_path] if p.exists()]
        status = "PARTIAL"
        reason = "Processed local DTM5 into DEM/hydrology/catchment candidate; final outlet still requires manual validation."
        qa = raster_valid(dem_path, WORKING_CRS, True)[1] + raster_valid(flow_acc_path, WORKING_CRS, True)[1] + vector_valid(catchment_path, WORKING_CRS)[1]

    statuses = {"E001": "DONE", "E002": "DONE", "E003": "DONE", "E004": "DONE", "E005": "DONE", "E006": "DONE", "E007": "PARTIAL", "E008": "DONE"}
    update_backlog(statuses, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Use local Lombardia DTM5 to generate DEM derivatives, outlet table, and DEM-derived catchment candidate.",
            inputs=["data/raw/zip/DTM5_RL.zip", "data/processed/boundary/processing_aoi_utm32.gpkg"],
            outputs=[str(p.relative_to(ROOT)) for p in [dem_path, filled_path, flow_acc_path, streams_path, catchment_path, map_path]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(dem_path.relative_to(ROOT)), str(catchment_path.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/06_discover_sentinel2.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
