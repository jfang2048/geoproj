"""Purpose: Run simplified SCS-CN screening model to estimate baseline and post-fire runoff for each rainfall event.
Inputs: data/processed/model_inputs/runoff_units.gpkg, data/processed/weather/post_fire_rainfall_events.csv, config/project.yaml (CN tables, burn adjustments).
Outputs: data/processed/model_inputs/runoff_units.gpkg (updated); outputs/tables/runoff_units.csv, runoff_event_summary.csv, runoff_delta_by_event.csv, sensitivity_summary.csv; outputs/maps/07_runoff_delta_event_main.png.
CRS: EPSG:32632 (working CRS).
Units: Rainfall in mm; runoff in mm and m³; area in ha.
Assumptions: SCS-CN with normal antecedent moisture; burn CN adjustments +4/+8/+12 for low/mod/high dNBR severity classes; screening model only — not calibrated discharge.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, shapes
from shapely.geometry import shape

from pipeline_utils import ROOT, RUNOFF_EVENT_COLUMNS, RUNOFF_UNIT_COLUMNS, WORKING_CRS, StepLog, append_run_log, ensure_workspace, import_geo, project_config, register_generated_dataset, update_backlog, vector_valid, write_gpkg, crs_axis_label, scs_runoff_mm


def dominant_soil_group() -> str:
    summary = ROOT / "outputs/tables/soil_summary_by_catchment.csv"
    if summary.exists():
        df = pd.read_csv(summary)
        if len(df):
            row = df.sort_values("pixel_count", ascending=False).iloc[0]
            return str(row.get("hsg_group", "C"))
    return "C"


def slope_array():
    dem_path = ROOT / "data/processed/dem/dem_utm32.tif"
    if not dem_path.exists():
        return None, None
    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype("float32")
        transform = ds.transform
        nodata = ds.nodata if ds.nodata is not None else -9999
    dem = np.where(dem == nodata, np.nan, dem)
    gy, gx = np.gradient(dem, abs(transform.e), abs(transform.a))
    slope_deg = np.degrees(np.arctan(np.sqrt(gx**2 + gy**2)))
    return slope_deg, transform


def mean_slope_for_geom(geom, slope, transform) -> float:
    if slope is None:
        return 0.0
    try:
        mask = geometry_mask([geom], out_shape=slope.shape, transform=transform, invert=True)
        vals = slope[mask & np.isfinite(slope)]
        return float(np.nanmean(vals)) if vals.size else 0.0
    except Exception:
        return 0.0


def slope_class(value: float) -> str:
    if value < 5:
        return "low"
    if value < 15:
        return "moderate"
    return "steep"


def burn_class_geometries(catchment_geom) -> dict[int, object]:
    """Return dissolved positive dNBR burn-class geometries clipped to the catchment.

    The runoff model applies curve-number increases only where the dNBR raster
    has positive severity classes. Valid unburned pixels and masked/no-data
    pixels both remain in the unadjusted class because they do not provide
    positive remote-sensing evidence for burn-related CN change.
    """
    burn_raster = ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif"
    if not burn_raster.exists():
        return {}
    gpd, *_ = import_geo()
    out: dict[int, object] = {}
    with rasterio.open(burn_raster) as ds:
        burn = ds.read(1)
        transform = ds.transform
        nodata = ds.nodata if ds.nodata is not None else 255
    for burn_class in (1, 2, 3):
        mask = burn == burn_class
        if not np.any(mask):
            continue
        polys = [
            shape(geom)
            for geom, val in shapes(burn.astype("uint8"), mask=mask, transform=transform)
            if int(val) == burn_class
        ]
        if not polys:
            continue
        geom = gpd.GeoSeries(polys, crs=WORKING_CRS).union_all().intersection(catchment_geom)
        if not geom.is_empty and geom.area > 0:
            out[burn_class] = geom
    return out


def make_units_from_inputs(cfg):
    gpd, *_ = import_geo()
    catchment = gpd.read_file(ROOT / "data/processed/boundary/catchment_utm32.gpkg").to_crs(WORKING_CRS)
    lc = gpd.read_file(ROOT / "data/processed/landcover/landcover_hydrologic_class.gpkg").to_crs(WORKING_CRS)
    lc = gpd.clip(lc, catchment)
    lc = lc[~lc.geometry.is_empty].copy()
    catchment_geom = catchment.geometry.union_all()
    positive_burn_geoms = burn_class_geometries(catchment_geom)
    all_positive_burn = (
        gpd.GeoSeries(list(positive_burn_geoms.values()), crs=WORKING_CRS).union_all()
        if positive_burn_geoms
        else None
    )
    soil = dominant_soil_group()
    slope, transform = slope_array()
    records = []
    geoms = []
    unit_id = 1
    soil_adj = {"A": -5, "B": 0, "C": 5, "D": 8}.get(soil, 5)
    baseline_cn = cfg.get("runoff", {}).get("baseline_curve_numbers", {})
    burn_adj = cfg.get("runoff", {}).get("burn_curve_number_adjustment", {})
    for cls, group in lc.groupby("hydrologic_class"):
        union_geom = group.geometry.union_all().intersection(catchment_geom)
        pieces = []
        if all_positive_burn is not None and not all_positive_burn.is_empty:
            unburned_piece = union_geom.difference(all_positive_burn)
            if not unburned_piece.is_empty and unburned_piece.area > 0:
                pieces.append((0, unburned_piece))
            for burn_class, burn_geom in sorted(positive_burn_geoms.items()):
                burned_piece = union_geom.intersection(burn_geom)
                if not burned_piece.is_empty and burned_piece.area > 0:
                    pieces.append((burn_class, burned_piece))
        else:
            pieces.append((0, union_geom))
        for burn_class, geom in pieces:
            if geom.is_empty or geom.area <= 0:
                continue
            base = float(baseline_cn.get(cls, baseline_cn.get("other", 74))) + soil_adj
            base = min(max(base, 35), 95)
            burned = min(base + float(burn_adj.get(str(burn_class), 0)), 98)
            sm = mean_slope_for_geom(geom, slope, transform)
            records.append(
                {
                    "unit_id": f"RU_{unit_id:03d}",
                    "area_m2": float(geom.area),
                    "area_ha": float(geom.area / 10000.0),
                    "burn_class": burn_class,
                    "landcover_class": cls,
                    "soil_group": soil,
                    "slope_mean": sm,
                    "slope_class": slope_class(sm),
                    "baseline_parameter": base,
                    "burned_parameter": burned,
                    "parameter_source": "DUSAF6 land cover + SoilGrids HSG + dNBR burn severity class + simplified SCS-CN screening config",
                    "notes": "Response unit dissolved by hydrologic land-cover class and positive dNBR severity class. Burn class 0 means no positive dNBR CN adjustment. Screening model only.",
                }
            )
            geoms.append(geom)
            unit_id += 1
    return gpd.GeoDataFrame(records, geometry=geoms, crs=WORKING_CRS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run simplified event-based runoff with local processed inputs.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ensure_workspace()
    units_gpkg = ROOT / "data/processed/model_inputs/runoff_units.gpkg"
    units_csv = ROOT / "outputs/tables/runoff_units.csv"
    event_summary = ROOT / "outputs/tables/runoff_event_summary.csv"
    delta_table = ROOT / "outputs/tables/runoff_delta_by_event.csv"
    sensitivity = ROOT / "outputs/tables/sensitivity_summary.csv"
    map_path = ROOT / "outputs/maps/07_runoff_delta_event_main.png"

    if event_summary.exists() and units_gpkg.exists() and map_path.exists() and not args.force:
        status = "SKIPPED"
        reason = "SKIPPED_VALID_OUTPUT_EXISTS: runoff outputs already valid."
        created: list[str] = []
        qa = [f"event_summary_rows={len(pd.read_csv(event_summary))}"] + vector_valid(units_gpkg, WORKING_CRS)[1]
    else:
        gpd, *_ = import_geo()
        cfg = project_config()
        events_path = ROOT / "data/processed/weather/post_fire_rainfall_events.csv"
        if not events_path.exists():
            raise FileNotFoundError("Missing rainfall events. Run step 10 first.")
        units = make_units_from_inputs(cfg)
        if units.empty:
            raise RuntimeError("No runoff units generated from landcover/catchment inputs.")
        write_gpkg(units, units_gpkg)
        units.drop(columns="geometry").to_csv(units_csv, index=False, columns=RUNOFF_UNIT_COLUMNS)
        events = pd.read_csv(events_path)
        rows = []
        delta_rows = []
        sens_rows = []
        total_area = float(units.geometry.area.sum())
        for _, event in events.iterrows():
            p = float(event["total_precip_mm"])
            scenario_values = {}
            for scenario, note, factor in [("baseline", "Baseline pre-fire screening parameters.", 1.0), ("burned", "Burned-condition curve-number adjustments by burn class.", 1.0), ("sensitivity_low", "Low sensitivity: 80% burn adjustment.", 0.8), ("sensitivity_high", "High sensitivity: 120% burn adjustment.", 1.2)]:
                volume = 0.0
                q_weighted = 0.0
                for _, unit in units.iterrows():
                    base = float(unit["baseline_parameter"])
                    burned = float(unit["burned_parameter"])
                    if scenario == "baseline":
                        cn = base
                    elif scenario == "burned":
                        cn = burned
                    else:
                        cn = min(base + (burned - base) * factor, 98.0)
                    q = scs_runoff_mm(p, cn)
                    area = float(unit.geometry.area)
                    volume += q * area / 1000.0
                    q_weighted += q * area
                runoff_mm = 0.0 if total_area == 0 else q_weighted / total_area
                coeff = 0.0 if p == 0 else runoff_mm / p
                rows.append({"event_id": event["event_id"], "scenario": scenario, "rainfall_total_mm": p, "runoff_total_mm": runoff_mm, "runoff_volume_m3": volume, "runoff_coefficient": coeff, "model_name": cfg.get("runoff", {}).get("model", "simplified_scs_cn_screening"), "parameter_set": "local_inputs_v2026_05_22", "notes": note + " Relative screening model; not calibrated forecast."})
                scenario_values[scenario] = (runoff_mm, volume)
            delta_rows.append({"event_id": event["event_id"], "baseline_runoff_mm": scenario_values["baseline"][0], "burned_runoff_mm": scenario_values["burned"][0], "delta_runoff_mm": scenario_values["burned"][0] - scenario_values["baseline"][0], "baseline_volume_m3": scenario_values["baseline"][1], "burned_volume_m3": scenario_values["burned"][1], "delta_volume_m3": scenario_values["burned"][1] - scenario_values["baseline"][1], "notes": "Relative change from local-input screening model."})
            sens_rows.append({"event_id": event["event_id"], "case": "burn_adjustment_range", "low_runoff_mm": scenario_values["sensitivity_low"][0], "main_runoff_mm": scenario_values["burned"][0], "high_runoff_mm": scenario_values["sensitivity_high"][0], "notes": "Sensitivity to burn curve-number adjustment."})
        event_summary_df = pd.DataFrame(rows, columns=RUNOFF_EVENT_COLUMNS)
        event_summary_df.to_csv(event_summary, index=False)
        pd.DataFrame(delta_rows).to_csv(delta_table, index=False)
        pd.DataFrame(sens_rows).to_csv(sensitivity, index=False)

        import matplotlib.pyplot as plt
        from matplotlib.colors import Normalize
        from matplotlib.lines import Line2D
        from figure_config import (configure, mm_to_inch, DOUBLE_COLUMN, RUNOFF_DELTA_CMAP,
            CATCHMENT_EDGE, apply_qgis_map_layout, save_figure)
        configure()

        plot_units = units.copy()
        plot_units["delta_cn"] = plot_units["burned_parameter"].astype(float) - plot_units["baseline_parameter"].astype(float)
        vmin = plot_units["delta_cn"].min()
        vmax = plot_units["delta_cn"].max()
        fig, ax = plt.subplots(figsize=(mm_to_inch(DOUBLE_COLUMN), mm_to_inch(140)))
        plot_units.plot(ax=ax, column="delta_cn", cmap=RUNOFF_DELTA_CMAP, legend=True,
            legend_kwds={"label": "CN adjustment", "shrink": 0.6},
            edgecolor="none", linewidth=0, norm=Normalize(vmin=vmin, vmax=vmax))
        # Add colorbar label
        if ax.get_legend():
            ax.get_legend().remove()
        cbar = ax.get_figure().axes[-1] if len(ax.get_figure().axes) > 1 else None
        if cbar is not None:
            cbar.set_ylabel("CN adjustment (dimensionless)", fontsize=6)
            cbar.tick_params(labelsize=5)
        gpd.read_file(ROOT / "data/processed/boundary/catchment_utm32.gpkg").to_crs(WORKING_CRS).boundary.plot(ax=ax, edgecolor=CATCHMENT_EDGE, facecolor="none", linewidth=0.8)
        apply_qgis_map_layout(
            fig,
            ax,
            title="Runoff response units",
            subtitle="SCS-CN curve-number adjustment for the main burned scenario",
            caption=(
                "Inputs: land-cover hydrologic classes, soil HSG proxy, dNBR burn class proxy, DEM slope, and candidate catchment. "
                "Method: simplified SCS-CN screening response units. Units/CRS: dimensionless CN adjustment, EPSG:32632 metres. "
                "Uncertainty: uncalibrated local screening model, not observed runoff."
            ),
            legend_handles=[Line2D([0], [0], color=CATCHMENT_EDGE, linewidth=0.8, label="Catchment candidate")],
            legend_loc="lower right",
            scale_length_m=2000,
            crs_label=WORKING_CRS,
        )
        map_path.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, map_path.with_suffix(".pdf"), map_path.with_suffix(".png"), dpi=600)
        plt.close(fig)
        register_generated_dataset("runoff_units", "Runoff response units", "model_input", units_gpkg, "processed", WORKING_CRS, "Generated from local DUSAF6, SoilGrids, dNBR/fire proxy, DEM slope, and catchment candidate.")
        register_generated_dataset("runoff_event_summary", "Runoff event summary", "model_output", event_summary, "processed", "tabular", "Simplified screening model with local rainfall events.")
        created = [str(p.relative_to(ROOT)) for p in [units_gpkg, units_csv, event_summary, delta_table, sensitivity, map_path]]
        status = "PARTIAL"
        reason = "Runoff screening model completed with local processed inputs; remains uncalibrated and catchment/outlet needs review."
        qa = [f"runoff_summary_rows={len(rows)}", f"units={len(units)}"] + vector_valid(units_gpkg, WORKING_CRS)[1]

    update_backlog({"J001": "DONE", "J002": "DONE", "J003": "DONE", "J004": "PARTIAL", "J005": "DONE", "J006": "DONE"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Build local-input runoff response units and run event simulations.",
            inputs=["DUSAF6 land cover", "SoilGrids HSG", "dNBR burn proxy", "rainfall events"],
            outputs=[str(p.relative_to(ROOT)) for p in [units_csv, event_summary, delta_table, sensitivity, map_path]],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[] if created else [str(event_summary.relative_to(ROOT))],
            qa_checks=qa,
            next_action="Run scripts/12_generate_outputs.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
