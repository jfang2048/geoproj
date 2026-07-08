"""Purpose: Build project spatial frame — processing AOI, fire perimeter, lake boundary, and hydrography — all in working CRS.
Inputs: data/raw/zip/ fire perimeter, hydrography, and lake boundary archives.
Outputs: data/processed/boundary/processing_aoi_utm32.gpkg, lake_varese_boundary.gpkg; data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg; data/processed/hydrography/streams_lombardia_varese_utm32.gpkg.
CRS: EPSG:32632 (working CRS).
Units: metre.
Assumptions: Fire perimeter polygon selection is deterministic; verify chosen polygon is the correct Monte Martica 2019 event.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pipeline_utils import (
    ROOT,
    WORKING_CRS,
    StepLog,
    append_run_log,
    ensure_workspace,
    fallback_aoi_geometry,
    import_geo,
    make_gdf,
    project_config,
    register_generated_dataset,
    update_backlog,
    vector_valid,
    write_gpkg,
    read_vector_to_working,
    crs_axis_label,
)
from raw_data_utils import AOI_GPKG_UTM, DUSAF_ZIP, FIRE_ZIP, HYDRO_ZIP, zip_shp_uri


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Prepare processing AOI, official fire perimeter, lake boundary, and hydrography in {WORKING_CRS}.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    aoi_path = ROOT / "data/processed/boundary/processing_aoi_utm32.gpkg"
    lake_path = ROOT / "data/processed/boundary/lake_varese_boundary.gpkg"
    hydro_path = ROOT / "data/processed/hydrography/streams_lombardia_varese_utm32.gpkg"
    fire_path = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
    fire_candidates = ROOT / "qa/evidence/fire_perimeter_candidates.csv"
    map0 = ROOT / "outputs/maps/00_fire_perimeter_check.png"
    map1 = ROOT / "outputs/maps/01_processing_aoi_not_final_boundary.png"

    required_ok = vector_valid(aoi_path, WORKING_CRS)[0] and vector_valid(fire_path, WORKING_CRS)[0] and vector_valid(hydro_path, WORKING_CRS)[0] and map0.exists() and map1.exists()
    if required_ok and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: spatial frame already uses local processed outputs."
        created: list[str] = []
        qa = vector_valid(aoi_path, WORKING_CRS)[1] + vector_valid(fire_path, WORKING_CRS)[1]
    else:
        gpd, Transformer, affinity, LineString, Point, Polygon, box, shapely_transform = import_geo()
        cfg = project_config()

        if AOI_GPKG_UTM.exists():
            aoi = read_vector_to_working(AOI_GPKG_UTM)
            aoi["role"] = "processing_mask_only"
            aoi["scientific_boundary"] = "false"
            aoi["notes"] = "Project-owner supplied AOI used only as a processing mask. Final modeled boundary remains DEM-derived."
        else:
            aoi = make_gdf(
                [{"name": "Fallback processing AOI", "role": "processing_mask_only", "scientific_boundary": "false", "notes": "Fallback; replace with supplied AOI."}],
                [fallback_aoi_geometry()],
            )
        aoi_geom = aoi.geometry.union_all()
        write_gpkg(aoi, aoi_path)

        # Official 2019 fire perimeter: choose Monte Martica/Varese polygon intersecting AOI, with candidates saved.
        fire_used = False
        if FIRE_ZIP.exists():
            fire = read_vector_to_working(zip_shp_uri(FIRE_ZIP, "Aree_percorse_dal_fuoco.shp"))
            year = fire["ANNO_INCEN"].astype(str).str.strip().eq("2019") if "ANNO_INCEN" in fire else True
            candidates = fire[year & fire.intersects(aoi_geom)].copy()
            if len(candidates):
                candidates["candidate_rank"] = candidates.geometry.area.rank(method="first", ascending=False).astype(int)
                preferred = candidates[
                    candidates.get("LOCALITA", "").astype(str).str.contains("MARTICA", case=False, na=False)
                    | candidates.get("NOME", "").astype(str).str.contains("VARESE", case=False, na=False)
                ]
                selected = (preferred if len(preferred) else candidates).sort_values("SHAPE_AREA" if "SHAPE_AREA" in candidates else "candidate_rank", ascending=False).head(1).copy()
                selected["source_type"] = "official_regione_lombardia_aree_percorse_dal_fuoco"
                selected["notes"] = "Official 2019 fire perimeter selected by year, AOI intersection, and Monte Martica/Varese attributes."
                write_gpkg(selected, fire_path)
                candidates.drop(columns="geometry").to_csv(fire_candidates, index=False)
                fire_used = True
        if not fire_used:
            center = aoi_geom.centroid
            proxy = make_gdf(
                [{"name": "Fire proxy fallback", "year": 2019, "source_type": "fallback_proxy", "notes": "Official fire perimeter missing; not scientific."}],
                [center.buffer(2200)],
            )
            write_gpkg(proxy, fire_path)
            pd.DataFrame().to_csv(fire_candidates, index=False)

        # Hydrography: clip all relevant reticolo layers to AOI.
        hydro_layers = []
        if HYDRO_ZIP.exists():
            for shp in ["Corsi_acqua_AIPO.shp", "Corsi_acqua_RIB.shp", "Corsi_acqua_RIM.shp", "Corsi_acqua_RIP.shp"]:
                try:
                    layer = read_vector_to_working(zip_shp_uri(HYDRO_ZIP, shp), bbox_working=tuple(aoi.total_bounds))
                    if len(layer):
                        layer = gpd.clip(layer, aoi)
                        layer = layer[~layer.geometry.is_empty].copy()
                        layer["source_layer"] = shp.replace(".shp", "")
                        hydro_layers.append(layer)
                except Exception:
                    continue
        if hydro_layers:
            hydro = pd.concat(hydro_layers, ignore_index=True)
            hydro = gpd.GeoDataFrame(hydro, geometry="geometry", crs=WORKING_CRS)
        else:
            fire_gdf = gpd.read_file(fire_path).to_crs(WORKING_CRS)
            line = LineString([fire_gdf.geometry.union_all().centroid, aoi_geom.centroid])
            hydro = make_gdf([{"source_layer": "fallback", "notes": "No hydrography available."}], [line])
        write_gpkg(hydro, hydro_path)

        # Lake boundary from DUSAF natural water polygons; largest natural basin in AOI approximates Lake Varese.
        lake_used = False
        if DUSAF_ZIP.exists():
            try:
                dusaf = read_vector_to_working(zip_shp_uri(DUSAF_ZIP, "DUSAF6.shp"), bbox_working=tuple(aoi.total_bounds))
                dusaf = gpd.clip(dusaf, aoi)
                water = dusaf[dusaf["COD_TOT"].astype(str).str.startswith("5121")].copy()
                if len(water):
                    water["area_m2"] = water.geometry.area
                    lake = water.sort_values("area_m2", ascending=False).head(1).copy()
                    lake["name"] = "Lake Varese from DUSAF6 natural water polygon"
                    lake["role"] = "lake_boundary_for_context_and_outlet_qa"
                    lake["notes"] = "Derived from DUSAF6 class 5121; used for QA/context, not as catchment boundary."
                    write_gpkg(lake, lake_path)
                    lake_used = True
            except Exception:
                lake_used = False
        if not lake_used:
            center = aoi_geom.centroid
            lake = make_gdf([{"name": "Approximate Lake Varese fallback", "role": "auxiliary_visualization_only", "notes": "Replace with DUSAF/official lake boundary."}], [affinity.scale(center.buffer(1, resolution=96), xfact=3200, yfact=1800)])
            write_gpkg(lake, lake_path)

        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        from figure_config import (configure, mm_to_inch, DOUBLE_COLUMN,
            AOI_EDGE, WATER_FILL, WATER_EDGE, STREAM_LINE, FIRE_EDGE,
            apply_qgis_map_layout, save_figure)
        configure()

        fire_gdf = gpd.read_file(fire_path).to_crs(WORKING_CRS)
        lake_gdf = gpd.read_file(lake_path).to_crs(WORKING_CRS)
        for out, label in [(map0, "a"), (map1, "b")]:
            is_fire_map = (label == "a")

            fig, ax = plt.subplots(figsize=(mm_to_inch(DOUBLE_COLUMN), mm_to_inch(140)))

            if is_fire_map:
                # Map 0: full extent — all reference layers for spatial QA
                aoi.boundary.plot(ax=ax, color=AOI_EDGE, linewidth=0.5, linestyle="--")
                lake_gdf.plot(ax=ax, facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, alpha=0.9)
                hydro.plot(ax=ax, color=STREAM_LINE, linewidth=0.4, alpha=0.7)
                fire_gdf.boundary.plot(ax=ax, color=FIRE_EDGE, linewidth=0.8)
                legend_items = [
                    Patch(facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, label="Lake Varese"),
                    Line2D([0], [0], color=AOI_EDGE, linewidth=0.5, linestyle="--", label="Processing AOI"),
                    Line2D([0], [0], color=STREAM_LINE, linewidth=0.4, label="Hydrography"),
                    Line2D([0], [0], color=FIRE_EDGE, linewidth=0.8, label="Official 2019 fire"),
                ]
                title = "Fire perimeter check"
                subtitle = "Official 2019 fire reference with processing AOI context"
                caption = (
                    "Inputs: Regione Lombardia fire perimeter/hydrography and DUSAF lake polygon. "
                    "Method: clipped to AOI and reprojected for display. Units/CRS: metres, EPSG:32632. "
                    "Uncertainty: fire selection and AOI use remain QA/context, not calibrated runoff evidence."
                )
                scale_length_m = 2000
            else:
                # Map 1: zoomed to AOI — emphasize this is a processing mask, not a catchment
                zoom_bounds = (
                    aoi.total_bounds[0] - 500,
                    aoi.total_bounds[2] + 500,
                    aoi.total_bounds[1] - 500,
                    aoi.total_bounds[3] + 500,
                )
                ax.set_xlim(aoi.total_bounds[0] - 500, aoi.total_bounds[2] + 500)
                ax.set_ylim(aoi.total_bounds[1] - 500, aoi.total_bounds[3] + 500)
                aoi.boundary.plot(ax=ax, color=AOI_EDGE, linewidth=1.0, linestyle="--")
                lake_gdf.plot(ax=ax, facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, alpha=0.9)
                hydro.plot(ax=ax, color=STREAM_LINE, linewidth=0.4, alpha=0.7)
                ax.set_xlim(zoom_bounds[0], zoom_bounds[1])
                ax.set_ylim(zoom_bounds[2], zoom_bounds[3])
                legend_items = [
                    Patch(facecolor=WATER_FILL, edgecolor=WATER_EDGE, linewidth=0.4, label="Lake Varese"),
                    Line2D([0], [0], color=AOI_EDGE, linewidth=1.0, linestyle="--", label="Processing AOI"),
                    Line2D([0], [0], color=STREAM_LINE, linewidth=0.4, label="Hydrography"),
                ]
                title = "Processing AOI context"
                subtitle = "Processing mask only — not a final catchment boundary"
                caption = (
                    "Inputs: project AOI, DUSAF lake polygon, and clipped hydrography. Method: simple context overlay. "
                    "Units/CRS: metres, EPSG:32632. Uncertainty: boundary is for processing only; final catchment is DEM-derived."
                )
                scale_length_m = 1000

            apply_qgis_map_layout(
                fig,
                ax,
                title=title,
                subtitle=subtitle,
                caption=caption,
                legend_handles=legend_items,
                scale_length_m=scale_length_m,
                crs_label=WORKING_CRS,
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            save_figure(fig, out.with_suffix(".pdf"), out.with_suffix(".png"), dpi=600)
            plt.close(fig)

        for dataset_id, name, role, path, notes in [
            ("processing_aoi", "Processing AOI", "processing_mask", aoi_path, "Project-owner supplied processing mask; not final boundary."),
            ("fire_perimeter_2019", "Official 2019 Monte Martica fire perimeter", "official_burned_area_reference", fire_path, "Official Regione Lombardia polygon selected from local archive." if fire_used else "Fallback proxy; official fire perimeter missing."),
            ("hydrography_lombardia_varese", "Lombardia hydrography clipped to AOI", "hydrography_outlet_qa", hydro_path, "Clipped from local reticolo idrografico archive."),
            ("lake_varese_boundary", "Lake Varese boundary", "lake_context_outlet_qa", lake_path, "Derived from local DUSAF water polygon where available."),
        ]:
            register_generated_dataset(dataset_id, name, role, path, "processed", WORKING_CRS, notes)
        created = [str(p.relative_to(ROOT)) for p in [aoi_path, fire_path, hydro_path, lake_path, fire_candidates, map0, map1] if p.exists()]
        status = "DONE" if fire_used and hydro_layers else "PARTIAL"
        reason = "Prepared spatial frame from local official/source data; AOI remains processing-only and final catchment is handled by DEM step."
        qa = vector_valid(aoi_path, WORKING_CRS)[1] + vector_valid(fire_path, WORKING_CRS)[1] + vector_valid(hydro_path, WORKING_CRS)[1]

    statuses = {"D001": "DONE", "D002": "DONE", "D003": "DONE", "D004": "DONE"}
    update_backlog(statuses, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Prepare official/provisional fire perimeter, processing AOI, lake boundary, and hydrography layers.",
            inputs=["data/raw/zip/Aree_percorse_dal_fuoco_REGIONE_LOMBARDIA.zip", "data/raw/zip/reticolo_idrografico_regionale_unificato.zip", "data/raw/zip/DUSAF6_REGIONE_LOMBARDIA.zip"],
            outputs=[str(p.relative_to(ROOT)) for p in [aoi_path, fire_path, hydro_path, lake_path, map0]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(aoi_path.relative_to(ROOT)), str(fire_path.relative_to(ROOT))],
            qa_checks=qa + ["AOI marked processing_mask_only"],
            next_action="Run scripts/05_prepare_dem.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
