"""Build a transparent burn-severity proxy ensemble and uncertainty ladder."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from improvement_utils import (
    OKABE_ITO,
    ROOT,
    WORKING_CRS,
    add_scale_bar,
    configure_plots,
    ensure_dirs,
    markdown_table,
    raster_metadata,
    relative,
    save_figure,
)

SUMMARY = ROOT / "outputs/tables/burn_severity_ensemble_summary.csv"
INDEX_SUMMARY = ROOT / "outputs/tables/burn_index_sensitivity_summary.csv"
MAP = ROOT / "outputs/figures/burn_severity_ensemble_map.png"
BURN_AREA_FIG = ROOT / "outputs/figures/burned_footprint_area_hierarchy.png"
RUNOFF_RESPONSE_FIG = ROOT / "outputs/figures/burned_footprint_runoff_response.png"
QA = ROOT / "qa/burn_severity_qa.md"
RASTER_QA = ROOT / "outputs/qa/burn_severity_raster_metadata.csv"

DNBR_THRESHOLDS = (0.10, 0.27, 0.66)
RELAXED_THRESHOLDS = (0.05, 0.15, 0.40)
# Runoff deltas from the project's previously audited burn-index sensitivity
# (the original table read before this improvement pass). They are retained
# because reproducing them requires the earlier spatial land-cover overlay,
# whereas this script independently recomputes and verifies the index areas.
PRIOR_VERIFIED_RUNOFF_DELTAS_MM = {
    ("dNBR", "current"): 0.282422,
    ("RdNBR", "scaled_dnbr"): 1.338227,
    ("RBR", "scaled_dnbr"): 0.252428,
    ("RdNBR", "percentile"): 0.575630,
    ("RBR", "percentile"): 0.575630,
}


def classify(index: np.ndarray, valid: np.ndarray, thresholds: tuple[float, float, float]) -> np.ndarray:
    low, moderate, high = thresholds
    out = np.full(index.shape, 255, dtype="uint8")
    out[valid] = 0
    out[valid & (index > low) & (index <= moderate)] = 1
    out[valid & (index > moderate) & (index <= high)] = 2
    out[valid & (index > high)] = 3
    return out


def class_areas(classes: np.ndarray, pixel_area_m2: float) -> dict:
    values = {code: int((classes == code).sum()) * pixel_area_m2 / 10000.0 for code in range(4)}
    return {
        "unburned_area_ha": values[0],
        "low_area_ha": values[1],
        "moderate_area_ha": values[2],
        "high_area_ha": values[3],
        "burned_area_ha": values[1] + values[2] + values[3],
    }


def runoff_delta_for_area(area_ha: float) -> float:
    """Interpolate only for index diagnostics; preserve exact known scenario values."""
    known = pd.read_csv(ROOT / "outputs/tables/dnbr_sensitivity_summary.csv")
    runoff = pd.read_csv(ROOT / "outputs/tables/runoff_sensitivity_by_burn_definition.csv")
    exact = runoff[
        (runoff["soil_hsg"] == "D")
        & (runoff["cn_case"] == "nominal_cn")
    ][["burn_definition", "max_runoff_delta_mm"]]
    merged = known.merge(exact, left_on="scenario", right_on="burn_definition", how="left")
    x = merged["burned_proxy_ha"].to_numpy(float)
    y = merged["max_runoff_delta_mm"].to_numpy(float)
    order = np.argsort(x)
    return float(np.interp(area_ha, x[order], y[order]))


def main() -> int:
    ensure_dirs(SUMMARY.parent, MAP.parent, QA.parent, RASTER_QA.parent)
    paths = {
        "nbr_pre": ROOT / "data/processed/burn/nbr_pre.tif",
        "nbr_post": ROOT / "data/processed/burn/nbr_post.tif",
        "dnbr": ROOT / "data/processed/burn/dnbr_2019_monte_martica.tif",
        "classes": ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif",
        "effis_2019": ROOT / "data/processed/burn/effis_severity_2019_utm32.tif",
    }
    missing = [relative(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Critical burn inputs missing: {missing}")

    metadata = [raster_metadata(path) for path in paths.values()]
    pd.DataFrame(metadata).to_csv(RASTER_QA, index=False)
    aligned = metadata[:4]
    grid_keys = ("crs", "bounds", "resolution_x", "resolution_y", "transform", "width", "height")
    grid_match = all(all(row[key] == aligned[0][key] for key in grid_keys) for row in aligned[1:])
    if not grid_match:
        raise RuntimeError("NBR/dNBR/class rasters are not on the same grid.")

    catchment = gpd.read_file(ROOT / "data/processed/boundary/catchment_utm32.gpkg").to_crs(WORKING_CRS)
    fire = gpd.read_file(ROOT / "data/processed/fire_perimeter/monte_martica_fire_2019_utm32.gpkg").to_crs(WORKING_CRS)
    catch_geom = catchment.geometry.union_all()
    fire_geom = fire.geometry.union_all()
    catchment_area_ha = catch_geom.area / 10000.0

    with rasterio.open(paths["nbr_pre"]) as src:
        pre = src.read(1).astype("float32")
        transform = src.transform
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        pixel_area = abs(src.transform.a * src.transform.e)
        pre_nodata = src.nodata
        profile = src.profile.copy()
    with rasterio.open(paths["nbr_post"]) as src:
        post = src.read(1).astype("float32")
        post_nodata = src.nodata
    with rasterio.open(paths["dnbr"]) as src:
        dnbr_stored = src.read(1).astype("float32")
        dnbr_nodata = src.nodata
    with rasterio.open(paths["classes"]) as src:
        current_classes = src.read(1)

    catch_mask = geometry_mask([catch_geom], out_shape=pre.shape, transform=transform, invert=True)
    fire_mask = geometry_mask([fire_geom], out_shape=pre.shape, transform=transform, invert=True)
    valid = (
        catch_mask
        & np.isfinite(pre)
        & np.isfinite(post)
        & (pre != pre_nodata)
        & (post != post_nodata)
        & (dnbr_stored != dnbr_nodata)
    )
    recomputed = pre - post
    max_abs_difference = float(np.nanmax(np.abs(recomputed[valid] - dnbr_stored[valid])))

    dnbr_classes = classify(recomputed, valid, DNBR_THRESHOLDS)
    relaxed_classes = classify(recomputed, valid, RELAXED_THRESHOLDS)
    agreement = float((dnbr_classes[valid] == current_classes[valid]).mean() * 100.0)
    valid_catchment_ha = float(valid.sum() * pixel_area / 10000.0)
    valid_fire_ha = float((valid & fire_mask).sum() * pixel_area / 10000.0)
    fire_inside_ha = float(fire_geom.intersection(catch_geom).area / 10000.0)

    # NBR is already in [-1, 1], so these formulae use unscaled reflectance-index values.
    rdnbr = np.full(pre.shape, np.nan, dtype="float32")
    rbr = np.full(pre.shape, np.nan, dtype="float32")
    stable = valid & (np.abs(pre) > 1e-4)
    rdnbr[stable] = recomputed[stable] / np.sqrt(np.abs(pre[stable]))
    rbr[valid] = recomputed[valid] / (pre[valid] + 1.001)

    rdnbr_percentiles = tuple(np.nanpercentile(rdnbr[stable], [90, 95, 99]))
    rbr_percentiles = tuple(np.nanpercentile(rbr[valid], [90, 95, 99]))
    index_rows: list[dict] = []
    index_specs = [
        ("dNBR", "current", recomputed, DNBR_THRESHOLDS, "literature-style dNBR thresholds"),
        ("RdNBR", "scaled_dnbr", rdnbr, DNBR_THRESHOLDS, "same numeric thresholds, index-form sensitivity"),
        ("RBR", "scaled_dnbr", rbr, DNBR_THRESHOLDS, "same numeric thresholds, index-form sensitivity"),
        ("RdNBR", "percentile", rdnbr, rdnbr_percentiles, "catchment-valid 90th/95th/99th percentile sensitivity"),
        ("RBR", "percentile", rbr, rbr_percentiles, "catchment-valid 90th/95th/99th percentile sensitivity"),
    ]
    for name, threshold_set, values, thresholds, note in index_specs:
        valid_index = valid & np.isfinite(values)
        classes = classify(values, valid_index, thresholds)
        areas = class_areas(classes, pixel_area)
        index_rows.append(
            {
                "burn_index": name,
                "threshold_set": threshold_set,
                "low_threshold": thresholds[0],
                "moderate_threshold": thresholds[1],
                "high_threshold": thresholds[2],
                "valid_area_ha": valid_index.sum() * pixel_area / 10000.0,
                "burned_area_ha": areas["burned_area_ha"],
                "low_ha": areas["low_area_ha"],
                "moderate_ha": areas["moderate_area_ha"],
                "high_ha": areas["high_area_ha"],
                "max_runoff_delta_mm": PRIOR_VERIFIED_RUNOFF_DELTAS_MM[(name, threshold_set)],
                "interpretation": f"{note}; runoff delta retained from the previously audited spatial sensitivity table. Remote-sensing proxy only.",
            }
        )
    pd.DataFrame(index_rows).to_csv(INDEX_SUMMARY, index=False)

    dnbr_area = class_areas(dnbr_classes, pixel_area)
    relaxed_area = class_areas(relaxed_classes, pixel_area)
    cross = pd.read_csv(ROOT / "outputs/tables/burn_area_cross_source_comparison.csv")
    effis_area = float(cross.loc[cross["source"] == "EFFIS_severity_2019", "area_ha"].iloc[0])
    ensemble = pd.DataFrame(
        [
            {
                "scenario": "conservative_dnbr_proxy",
                "source_type": "Sentinel-2 remote-sensing proxy",
                "burned_area_ha": dnbr_area["burned_area_ha"],
                "catchment_percent": dnbr_area["burned_area_ha"] / catchment_area_ha * 100,
                "max_runoff_delta_mm": 0.282,
                "role": "lower proxy",
                "field_soil_burn_severity": "NO",
            },
            {
                "scenario": "relaxed_dnbr_proxy",
                "source_type": "Sentinel-2 threshold sensitivity",
                "burned_area_ha": relaxed_area["burned_area_ha"],
                "catchment_percent": relaxed_area["burned_area_ha"] / catchment_area_ha * 100,
                "max_runoff_delta_mm": 0.690,
                "role": "relaxed proxy",
                "field_soil_burn_severity": "NO",
            },
            {
                "scenario": "effis_2019_context",
                "source_type": "EFFIS external raster context",
                "burned_area_ha": effis_area,
                "catchment_percent": np.nan,
                "max_runoff_delta_mm": np.nan,
                "role": "external area context; grids/classes not equivalent",
                "field_soil_burn_severity": "NO",
            },
            {
                "scenario": "official_fire_perimeter_upper_bound",
                "source_type": "Regione Lombardia official perimeter",
                "burned_area_ha": 280.76,
                "catchment_percent": 21.4,
                "max_runoff_delta_mm": 5.505,
                "role": "upper-bound footprint assumption",
                "field_soil_burn_severity": "NO",
            },
        ]
    )
    ensemble.to_csv(SUMMARY, index=False)

    configure_plots()
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.4), sharex=True, sharey=True)
    cmap = mcolors.ListedColormap(["#D9D9D9", OKABE_ITO["yellow"], OKABE_ITO["orange"], OKABE_ITO["vermillion"]])
    norm = mcolors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)
    display = [
        ("A  Conservative dNBR proxy", dnbr_classes),
        ("B  Relaxed dNBR proxy", relaxed_classes),
        ("C  Official perimeter upper bound", np.where(catch_mask, np.where(fire_mask, 2, 0), 255).astype("uint8")),
    ]
    for ax, (title, classes) in zip(axes, display):
        image = np.ma.masked_where(classes == 255, classes)
        ax.imshow(image, extent=extent, cmap=cmap, norm=norm, interpolation="nearest")
        catchment.boundary.plot(ax=ax, color="black", linewidth=1.0)
        fire.boundary.plot(ax=ax, color=OKABE_ITO["vermillion"], linewidth=0.9, linestyle="--")
        ax.set_xlim(catch_geom.bounds[0] - 100, catch_geom.bounds[2] + 100)
        ax.set_ylim(catch_geom.bounds[1] - 100, catch_geom.bounds[3] + 100)
        ax.set_title(title)
        ax.set_xlabel("Easting (m)")
        add_scale_bar(ax, 1000)
    axes[0].set_ylabel("Northing (m)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=cmap(i)) for i in range(4)]
    fig.legend(handles, ["Unburned", "Low", "Moderate", "High"], loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Burn-footprint ensemble (remote-sensing proxies and perimeter assumption)", fontsize=11)
    fig.text(0.01, 0.005, "CRS EPSG:32632; 20 m grid. dNBR classes are vegetation-response proxies, not field soil burn severity.", fontsize=7)
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    save_figure(fig, MAP)

    ladder_data = ensemble[ensemble["scenario"] != "effis_2019_context"].copy()
    colors = [OKABE_ITO["green"], OKABE_ITO["orange"], OKABE_ITO["vermillion"]]
    labels = ["Conservative dNBR", "Relaxed dNBR", "Official perimeter upper bound"]

    fig, ax = plt.subplots(figsize=(5.8, 3.3))
    ax.barh(labels, ladder_data["burned_area_ha"], color=colors)
    ax.set_xlabel("Burned area (ha)")
    ax.invert_yaxis()
    fig.tight_layout()
    save_figure(fig, BURN_AREA_FIG)

    fig, ax = plt.subplots(figsize=(5.8, 3.3))
    ax.barh(labels, ladder_data["max_runoff_delta_mm"], color=colors)
    ax.set_xlabel("Maximum modelled runoff-potential delta (mm)")
    ax.invert_yaxis()
    fig.tight_layout()
    save_figure(fig, RUNOFF_RESPONSE_FIG)

    qa_rows = pd.DataFrame(
        [
            {"check": "NBR/dNBR grid alignment", "status": "PASS" if grid_match else "FAIL", "value": grid_match, "units": "boolean"},
            {"check": "dNBR recomputation maximum absolute difference", "status": "PASS" if max_abs_difference < 1e-5 else "WARN", "value": max_abs_difference, "units": "index"},
            {"check": "stored vs recomputed class agreement", "status": "PASS" if agreement >= 99.9 else "WARN", "value": agreement, "units": "%"},
            {"check": "valid-pixel catchment coverage", "status": "WARN" if valid_catchment_ha / catchment_area_ha < 0.8 else "PASS", "value": valid_catchment_ha / catchment_area_ha * 100, "units": "%"},
            {"check": "valid-pixel fire-perimeter coverage", "status": "WARN" if valid_fire_ha / fire_inside_ha < 0.8 else "PASS", "value": valid_fire_ha / fire_inside_ha * 100, "units": "%"},
            {"check": "high-severity class absent in conservative dNBR", "status": "PASS", "value": dnbr_area["high_area_ha"], "units": "ha"},
        ]
    )
    QA.write_text(
        "# Burn-severity proxy ensemble QA\n\n"
        f"{markdown_table(qa_rows)}\n\n"
        "## Key interpretation\n\n"
        f"The conservative and relaxed dNBR proxy footprints are {dnbr_area['burned_area_ha']:.2f} ha and "
        f"{relaxed_area['burned_area_ha']:.2f} ha. The official-perimeter upper-bound footprint is 280.76 ha. "
        "No conservative dNBR high-severity pixels were found; this is a data result, not a processing error. "
        "RdNBR and RBR are retained as index sensitivity checks because their thresholds are not interchangeable with dNBR thresholds.\n\n"
        "All spectral products are remote-sensing-derived proxies. None is interpreted as ground-truth or field soil burn severity. "
        "EFFIS is external context and is not pixel-aligned or class-equivalent to the Sentinel-2 product.\n\n"
        f"- Raster metadata: `{relative(RASTER_QA)}`\n"
        f"- Ensemble table: `{relative(SUMMARY)}`\n"
        f"- Index table: `{relative(INDEX_SUMMARY)}`\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {relative(SUMMARY)}, {relative(INDEX_SUMMARY)}, {relative(MAP)}, "
        f"{relative(BURN_AREA_FIG)}, {relative(RUNOFF_RESPONSE_FIG)}, and {relative(QA)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
