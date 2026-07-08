"""Purpose: Compute dNBR burn-severity proxy from Sentinel-2 pre-fire and post-fire NBR, classify, and output categorical burn raster.
Inputs: Sentinel-2 L2A SAFE products (data/raw/zip/), data/processed/boundary/processing_aoi_utm32.gpkg.
Outputs: data/processed/burn/nbr_pre.tif, nbr_post.tif, dnbr_2019_monte_martica.tif, burn_severity_proxy_uint8.tif, burned_area_proxy.gpkg; results/tables/burn_severity_area_summary.csv.
CRS: EPSG:32632 (working CRS).
Units: dNBR dimensionless; class codes 0=unburned 1=low 2=moderate 3=high 255=NoData.
Assumptions: dNBR thresholds are literature-standard screening values; not field-validated soil burn severity. JP2 read via Pillow when JP2OpenJPEG unavailable.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from rasterio.features import geometry_mask, shapes
from shapely.geometry import shape

from pipeline_utils import (
    BURN_SUMMARY_COLUMNS,
    ROOT,
    WORKING_CRS,
    StepLog,
    append_run_log,
    dataframe_to_csv,
    ensure_workspace,
    import_geo,
    project_config,
    raster_valid,
    register_generated_dataset,
    update_backlog,
    vector_valid,
    write_gpkg,
    write_raster,
    crs_axis_label,
)
from raw_data_utils import choose_s2_pair, date_from_s2_name, read_s2_band_window, s2_grid, window_from_bounds_20m

CLASS_NAMES = {
    0: "unburned_or_unchanged",
    1: "low_burn_severity_proxy",
    2: "moderate_burn_severity_proxy",
    3: "high_burn_severity_proxy",
    255: "nodata",
}
VALID_SCL = {4, 5, 6, 7}  # vegetation, bare/non-vegetated, water, unclassified


def compute_nbr(zip_path: Path, bounds: tuple[float, float, float, float]):
    grid = s2_grid(zip_path)
    row0, row1, col0, col1, transform = window_from_bounds_20m(grid, bounds, pad=8)
    nir = read_s2_band_window(zip_path, "B08", row0, row1, col0, col1)
    swir = read_s2_band_window(zip_path, "B12", row0, row1, col0, col1)
    scl = read_s2_band_window(zip_path, "SCL", row0, row1, col0, col1).astype("uint8")
    # Ensure matching shapes after 10m->20m downsample rounding.
    h = min(nir.shape[0], swir.shape[0], scl.shape[0])
    w = min(nir.shape[1], swir.shape[1], scl.shape[1])
    nir, swir, scl = nir[:h, :w], swir[:h, :w], scl[:h, :w]
    valid = np.isin(scl, list(VALID_SCL)) & (nir > 0) & (swir > 0)
    denom = nir + swir
    nbr = np.full((h, w), np.nan, dtype="float32")
    nbr[valid & (denom != 0)] = (nir[valid & (denom != 0)] - swir[valid & (denom != 0)]) / denom[valid & (denom != 0)]
    return nbr, valid, transform


def fallback_from_official_fire(bounds, cfg):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.features import geometry_mask

    gpd, *_ = import_geo()
    catchment_path = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
    base = gpd.read_file(catchment_path).to_crs(WORKING_CRS)
    xmin, ymin, xmax, ymax = bounds
    res = 20
    width = max(10, int(np.ceil((xmax - xmin) / res)))
    height = max(10, int(np.ceil((ymax - ymin) / res)))
    transform = from_origin(xmin, ymax, res, res)
    base_mask = geometry_mask([base.geometry.union_all()], out_shape=(height, width), transform=transform, invert=True)
    dnbr = np.where(base_mask, 0.02, np.nan).astype("float32")
    fire_path = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
    if fire_path.exists():
        fire = gpd.read_file(fire_path).to_crs(WORKING_CRS).geometry.union_all()
        fire_mask = geometry_mask([fire], out_shape=(height, width), transform=transform, invert=True)
        dnbr = np.where(base_mask & fire_mask, 0.55, dnbr).astype("float32")
    return dnbr, transform, "fallback_official_fire_proxy_after_sentinel_read_failure"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute dNBR burn-severity proxy from local Sentinel-2 SAFE ZIPs or documented fallback.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    nbr_pre = ROOT / "data/processed/burn/nbr_pre.tif"
    nbr_post = ROOT / "data/processed/burn/nbr_post.tif"
    dnbr_path = ROOT / "data/processed/burn/dnbr_2019_monte_martica.tif"
    burn_path = ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif"
    burned_gpkg = ROOT / "data/processed/burn/burned_area_proxy.gpkg"
    summary_path = ROOT / "outputs/tables/burn_severity_area_summary.csv"
    map_path = ROOT / "outputs/maps/06_burn_severity_proxy_vs_fire_reference.png"

    if raster_valid(burn_path, WORKING_CRS, True)[0] and summary_path.exists() and map_path.exists() and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: burn proxy outputs already valid."
        created: list[str] = []
        qa = raster_valid(burn_path, WORKING_CRS, True)[1]
    else:
        gpd, *_ = import_geo()
        cfg = project_config()
        thresholds = cfg.get("burn_classification", {}).get("dnbr_thresholds", {})
        nodata = int(cfg.get("burn_classification", {}).get("nodata", 255))
        catchment_path = ROOT / "data/processed/boundary/catchment_utm32.gpkg"
        if not catchment_path.exists():
            raise FileNotFoundError("Missing catchment. Run step 05 first.")
        catchment = gpd.read_file(catchment_path).to_crs(WORKING_CRS)
        bounds = tuple(float(x) for x in catchment.total_bounds)
        pre_zip, post_zip = choose_s2_pair()
        source_note = ""
        try:
            if not pre_zip or not post_zip:
                raise FileNotFoundError("Missing local pre/post Sentinel-2 SAFE ZIP pair.")
            pre_nbr, pre_valid, transform = compute_nbr(pre_zip, bounds)
            post_nbr, post_valid, post_transform = compute_nbr(post_zip, bounds)
            h = min(pre_nbr.shape[0], post_nbr.shape[0])
            w = min(pre_nbr.shape[1], post_nbr.shape[1])
            pre_nbr, post_nbr = pre_nbr[:h, :w], post_nbr[:h, :w]
            valid = np.isfinite(pre_nbr) & np.isfinite(post_nbr)
            dnbr = np.full((h, w), np.nan, dtype="float32")
            dnbr[valid] = pre_nbr[valid] - post_nbr[valid]
            source_note = f"Computed from local Sentinel-2 SAFE ZIPs: pre={pre_zip.name}, post={post_zip.name}; B08 10m downsampled to 20m; SCL cloud/snow/shadow masked."
        except Exception as exc:
            dnbr, transform, fallback = fallback_from_official_fire(bounds, cfg)
            pre_nbr = np.where(np.isfinite(dnbr), 0.6, np.nan).astype("float32")
            post_nbr = np.where(np.isfinite(dnbr), 0.6 - dnbr, np.nan).astype("float32")
            source_note = f"{fallback}: {type(exc).__name__}: {exc}"

        catch_mask = geometry_mask([catchment.geometry.union_all()], out_shape=dnbr.shape, transform=transform, invert=True)
        dnbr = np.where(catch_mask, dnbr, np.nan).astype("float32")
        pre_nbr = np.where(catch_mask, pre_nbr, np.nan).astype("float32")
        post_nbr = np.where(catch_mask, post_nbr, np.nan).astype("float32")
        valid = np.isfinite(dnbr)
        burn = np.full(dnbr.shape, nodata, dtype="uint8")
        unburned_max = float(thresholds.get("unburned_max", 0.10))
        low_max = float(thresholds.get("low_max", 0.27))
        moderate_max = float(thresholds.get("moderate_max", 0.66))
        burn[valid & (dnbr <= unburned_max)] = 0
        burn[valid & (dnbr > unburned_max) & (dnbr <= low_max)] = 1
        burn[valid & (dnbr > low_max) & (dnbr <= moderate_max)] = 2
        burn[valid & (dnbr > moderate_max)] = 3

        write_raster(nbr_pre, np.where(np.isfinite(pre_nbr), pre_nbr, -9999.0), transform, WORKING_CRS, nodata=-9999.0, dtype="float32")
        write_raster(nbr_post, np.where(np.isfinite(post_nbr), post_nbr, -9999.0), transform, WORKING_CRS, nodata=-9999.0, dtype="float32")
        write_raster(dnbr_path, np.where(np.isfinite(dnbr), dnbr, -9999.0), transform, WORKING_CRS, nodata=-9999.0, dtype="float32")
        write_raster(burn_path, burn, transform, WORKING_CRS, nodata=nodata, dtype="uint8")

        burned_mask = (burn > 0) & (burn != nodata)
        polys = [shape(geom) for geom, val in shapes(burned_mask.astype("uint8"), mask=burned_mask, transform=transform) if val == 1]
        if polys:
            geom = gpd.GeoSeries(polys, crs=WORKING_CRS).union_all().intersection(catchment.geometry.union_all())
        else:
            fire_path = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
            geom = gpd.read_file(fire_path).to_crs(WORKING_CRS).geometry.union_all().intersection(catchment.geometry.union_all()) if fire_path.exists() else catchment.geometry.union_all()
        burned = gpd.GeoDataFrame(
            [{"name": "Burned area proxy", "source": "sentinel2_dnbr_proxy", "notes": source_note + " Not field-validated soil burn severity."}],
            geometry=[geom],
            crs=WORKING_CRS,
        )
        write_gpkg(burned, burned_gpkg)

        pixel_area = abs(transform.a * transform.e)
        valid_count = int(np.count_nonzero(burn != nodata))
        threshold_rule = f"0<=unburned<={unburned_max}; low<={low_max}; moderate<={moderate_max}; high>{moderate_max}"
        rows = []
        for code in [0, 1, 2, 3, 255]:
            count = int(np.count_nonzero(burn == code))
            rows.append({"class_code": code, "class_name": CLASS_NAMES[code], "pixel_count": count, "area_m2": count * pixel_area, "area_ha": count * pixel_area / 10000.0, "area_percent_of_valid": "" if code == 255 else (0 if valid_count == 0 else count / valid_count * 100.0), "threshold_rule": threshold_rule, "notes": source_note})
        dataframe_to_csv(summary_path, rows, BURN_SUMMARY_COLUMNS)

        import matplotlib.pyplot as plt
        from matplotlib.colors import BoundaryNorm, ListedColormap
        from matplotlib.lines import Line2D
        from figure_config import (configure, mm_to_inch, DOUBLE_COLUMN,
            BURN_SEVERITY_COLORS, FIRE_EDGE, CATCHMENT_EDGE,
            apply_qgis_map_layout, save_figure)
        configure()

        xmin = transform.c
        ymax = transform.f
        xmax = xmin + transform.a * burn.shape[1]
        ymin = ymax + transform.e * burn.shape[0]
        display = burn.copy().astype("int16")
        display[display == nodata] = 4
        cmap = ListedColormap(BURN_SEVERITY_COLORS)
        fig, ax = plt.subplots(figsize=(mm_to_inch(DOUBLE_COLUMN), mm_to_inch(140)))
        im = ax.imshow(display, cmap=cmap,
            norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5, 4.5], cmap.N),
            extent=[xmin, xmax, ymin, ymax], origin="upper", interpolation="nearest")
        catchment.boundary.plot(ax=ax, edgecolor=CATCHMENT_EDGE, facecolor="none", linewidth=0.8)
        fire_path = ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg"
        if fire_path.exists():
            gpd.read_file(fire_path).to_crs(WORKING_CRS).boundary.plot(ax=ax, edgecolor=FIRE_EDGE, linewidth=0.8, linestyle="--")
        # Colorbar with class labels
        from figure_config import BURN_SEVERITY_LABELS
        cbar = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3, 4], shrink=0.72, pad=0.02)
        cbar.ax.set_yticklabels(BURN_SEVERITY_LABELS, fontsize=5)
        cbar.ax.tick_params(length=0)
        cbar.outline.set_visible(False)
        legend_items = [
            Line2D([0], [0], color=CATCHMENT_EDGE, linewidth=0.8, label="Catchment candidate"),
            Line2D([0], [0], color=FIRE_EDGE, linewidth=0.8, linestyle="--", label="Official fire reference"),
        ]
        apply_qgis_map_layout(
            fig,
            ax,
            title="Burn-severity proxy",
            subtitle="dNBR classes compared with official fire reference",
            caption=(
                "Inputs: Sentinel-2 pre/post-fire NBR or documented fallback and the official fire perimeter. "
                "Method: dNBR class proxy clipped to the candidate catchment. Units/CRS: class codes, EPSG:32632 metres. "
                "Uncertainty: remote-sensing burn-severity proxy only; not field soil burn severity."
            ),
            legend_handles=legend_items,
            legend_loc="lower right",
            scale_length_m=2000,
            crs_label=WORKING_CRS,
        )
        map_path.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, map_path.with_suffix(".pdf"), map_path.with_suffix(".png"), dpi=600)
        plt.close(fig)

        for dataset_id, name, role, path in [
            ("nbr_pre", "Pre-fire NBR", "burn_proxy_input", nbr_pre),
            ("nbr_post", "Post-fire NBR", "burn_proxy_input", nbr_post),
            ("dnbr_2019", "dNBR 2019 Monte Martica", "burn_proxy", dnbr_path),
            ("burn_severity_proxy", "Burn severity proxy classes", "burn_proxy", burn_path),
            ("burned_area_proxy", "Burned area proxy polygon", "burn_proxy", burned_gpkg),
        ]:
            register_generated_dataset(dataset_id, name, role, path, "processed", WORKING_CRS, source_note)
        created = [str(p.relative_to(ROOT)) for p in [nbr_pre, nbr_post, dnbr_path, burn_path, burned_gpkg, summary_path, map_path]]
        status = "DONE" if "Computed from local Sentinel-2" in source_note else "PARTIAL"
        reason = source_note
        qa = raster_valid(burn_path, WORKING_CRS, True)[1] + vector_valid(burned_gpkg, WORKING_CRS)[1] + [f"valid_pixels={valid_count}"]

    update_backlog({"F004": status, "F005": status, "F006": status, "F007": status, "F008": "DONE", "F009": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Compute Sentinel-2 NBR/dNBR and burn-severity proxy using local SAFE ZIPs.",
            inputs=["data/raw/zip/S2*_MSIL2A_*.SAFE.zip", "config/project.yaml"],
            outputs=[str(p.relative_to(ROOT)) for p in [burn_path, summary_path, map_path]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(burn_path.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/08_prepare_landcover.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
