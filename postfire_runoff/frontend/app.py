"""GeoProject — Post-fire Runoff Screening Tool.

A bright, clean Streamlit dashboard with grouped top-level navigation.
All results are generated dynamically from project output data.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

WEBAPP_DIR = Path(__file__).resolve().parent
ROOT = WEBAPP_DIR.parent.parent  # repository root
for p in [str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
import pandas as pd
import yaml
import plotly.graph_objects as go


# Page config
st.set_page_config(
    page_title="Post-fire Runoff Screening",
    layout="wide",
)

from postfire_runoff.frontend.components.style import inject as inject_css

from postfire_runoff.frontend.components.data_loaders import (
    core_metrics, burn_class_table, load_csv_safe, load_vector_safe,
    RUNOFF_DELTA, RUNOFF_EVENTS, BURN_ENSEMBLE, BURN_AREA,
    WEPP_SUMMARY, LAKE_STATUS, LAKE_ANOMALIES, LAKE_SELECTED, LAKE_CONTEXT,
    CATCHMENT, FIRE_PERIMETER, HYDROGRAPHY, LAKE_BOUNDARY,
    RUNOFF_UNITS_GPKG, DEM_STREAMS, BURN_RASTER,
)
from postfire_runoff.frontend.components.dynamic_maps import (
    catchment_layer, fire_perimeter_layer, lake_layer,
    hydrography_layer, dem_streams_layer, runoff_units_layer,
    outlet_point_layer, burn_raster_overlay,
)
from postfire_runoff.frontend.components.dynamic_charts import (
    burn_footprint_runoff_chart, burn_footprint_area_chart,
    event_rainfall_scatter_chart, event_delta_cdf_chart,
    weppcloud_sediment_chart, lake_wq_status_figure, lake_wq_event_table,
)
from postfire_runoff.frontend.components.scs_preview import preview_metrics, preview_curve
from postfire_runoff.frontend.adapters import CATEGORY_RULES, accepted_extensions_for, outlet_lonlat, save_upload, validate_upload
from postfire_runoff.frontend.components.upload_registry import record_upload, read_manifest
from postfire_runoff.frontend.components.runner import available_commands, run_command
from postfire_runoff.frontend.components.paths import (
    DATA_RAW_ZIP, WEPPCLOUD_DOWNLOAD, resolve_safe,
    REQUIRED_CORE, REQUIRED_WEPPCLOUD, REQUIRED_LAKE_WQ, REQUIRED_FIGURES,
    WORKFLOW_PNG, TABLES, WEBAPP, ROOT as P_ROOTS,
)

inject_css()


def _fmt(value, pattern: str, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"{float(value):{pattern}}{suffix}"
    except Exception:
        return "N/A"


def _fmt_int(value) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return str(int(value))
    except Exception:
        return "N/A"


def _delta(value, pattern: str, suffix: str = "") -> str | None:
    formatted = _fmt(value, pattern, suffix)
    return None if formatted == "N/A" else formatted


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "nav" not in st.session_state:
    st.session_state.nav = "Overview"

# ---------------------------------------------------------------------------
# Top navigation
# ---------------------------------------------------------------------------
st.markdown("### Post-fire Runoff Screening Tool")
st.caption("Reproducible screening-level workflow for post-wildfire runoff sensitivity analysis.")

nav = st.radio(
    "Navigation",
    ["Overview", "Data", "Model", "Explore", "Results"],
    horizontal=True,
    label_visibility="collapsed",
    key="top_nav",
)
st.session_state.nav = nav

st.markdown("---")

# ===========================================================================
# SECTION: Overview
# ===========================================================================
if nav == "Overview":
    metrics = core_metrics()

    # -- Metric cards --
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("#### Project at a glance")

    r1 = st.columns(4)
    r1[0].metric("Catchment", _fmt(metrics.get("catchment_area_ha"), ".1f", " ha"))
    r1[1].metric("Official fire perimeter", _fmt(metrics.get("fire_perimeter_ha"), ".1f", " ha"))
    r1[2].metric("Fire inside catchment", _fmt(metrics.get("fire_inside_catchment_ha"), ".1f", " ha"), _delta(metrics.get("fire_inside_pct"), ".1f", "%"))
    r1[3].metric("Rainfall events", _fmt_int(metrics.get("rainfall_event_count")))

    r2 = st.columns(4)
    r2[0].metric("Conservative dNBR proxy", _fmt(metrics.get("conservative_burned_ha"), ".1f", " ha"))
    r2[1].metric("Max conservative delta Q", _fmt(metrics.get("conservative_max_dq_mm"), ".3f", " mm"))
    r2[2].metric("Upper-bound burned", _fmt(metrics.get("upper_bound_burned_ha"), ".1f", " ha"))
    r2[3].metric("Max upper-bound delta Q", _fmt(metrics.get("upper_bound_max_dq_mm"), ".3f", " mm"))

    r3 = st.columns(4)
    if metrics.get("wepp_available"):
        sed_min = _fmt(metrics.get("wepp_sediment_min"), ".1f")
        sed_max = _fmt(metrics.get("wepp_sediment_max"), ".1f")
        runoff_min = _fmt(metrics.get("wepp_runoff_min"), ".1f")
        runoff_max = _fmt(metrics.get("wepp_runoff_max"), ".1f")
        r3[0].metric("WEPPcloud sediment", f"{sed_min} to {sed_max}")
        r3[2].metric("WEPPcloud stream discharge", f"{runoff_min} to {runoff_max}")
    else:
        r3[0].metric("WEPPcloud sediment", "Unavailable")
        r3[2].metric("WEPPcloud stream discharge", "Unavailable")
    if metrics.get("conservative_max_dq_mm") is not None and metrics.get("catchment_area_ha") is not None:
        delta_vol = float(metrics["conservative_max_dq_mm"]) * float(metrics["catchment_area_ha"]) * 10.0
        r3[1].metric("Est. max delta volume", f"{delta_vol:.0f} m3")
    else:
        r3[1].metric("Est. max delta volume", "N/A")
    r3[3].metric("Lake WQ status", "Data-limited" if metrics.get("lake_wq_data_limited", True) else "Available")
    st.markdown("</div>", unsafe_allow_html=True)

    # -- Guardrails --
    with st.expander("Scientific guardrails", expanded=False):
        st.markdown(
            "- Local runoff outputs are screening-level, uncalibrated scenario estimates.\n"
            "- dNBR is a remote-sensing burn-severity proxy, not field soil burn severity.\n"
            "- The current single outlet does not cover the whole official fire perimeter.\n"
            "- WEPPcloud is an independent benchmark, not validation of local SCS-CN.\n"
            "- Lake WQ proxy comparison is data-limited: local Sentinel-2 scenes do not cover selected event windows.\n"
            "- Do not interpret NDCI as runoff-driven chlorophyll-a prediction."
        )

# ===========================================================================
# SECTION: Data
# ===========================================================================
elif nav == "Data":
    tab_upload, tab_check, tab_crs, tab_manifest = st.tabs([
        "Upload files", "Required files", "CRS status", "Upload manifest",
    ])

    # -- Upload tab --
    with tab_upload:
        st.markdown("#### Upload project data")
        st.caption("Files are placed in the correct project directories. Existing files are never overwritten.")

        category = st.selectbox("Data category", list(CATEGORY_RULES.keys()), key="upload_category")
        rules = CATEGORY_RULES[category]
        target_dir = ROOT / rules["target"]
        target_dir.mkdir(parents=True, exist_ok=True)
        exts = accepted_extensions_for(category)
        st.caption(f"Accepted extensions: {', '.join(exts)}  |  Target: `{rules['target']}/`")

        uploaded = st.file_uploader(
            f"Choose files for {category}",
            accept_multiple_files=True,
            type=[e.lstrip(".") for e in exts],
            key=f"up_{category}",
        )

        if uploaded:
            for uf in uploaded:
                file_bytes = uf.getvalue()
                result = save_upload(category, uf.name, file_bytes)
                if not result.valid:
                    st.error(f"{uf.name}: {result.message}")
                    continue
                dest = Path(result.saved_path)
                record_upload(category=category, original_filename=uf.name, saved_path=dest,
                              file_size_bytes=dest.stat().st_size, checksum=result.checksum,
                              warnings="; ".join(result.warnings))
                st.success(f"Saved: `{dest.relative_to(ROOT)}`")

    # -- Required files tab --
    with tab_check:
        st.markdown("#### Required file status")

        def _status_icon(exists, critical=True):
            return "OK" if exists else ("MISSING" if critical else "optional")

        def _check_group(title, items, critical=True):
            st.markdown(f"**{title}**")
            rows = []
            for label, path in items.items():
                ok = path.exists() and (path.stat().st_size > 0 if path.is_file() else True)
                rows.append({"Item": label, "Path": str(path.relative_to(ROOT)), "Status": _status_icon(ok, critical)})
            st.dataframe(rows, width="stretch", hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            _check_group("Core", REQUIRED_CORE, critical=True)
            _check_group("WEPPcloud", REQUIRED_WEPPCLOUD, critical=True)
        with c2:
            _check_group("Lake WQ", REQUIRED_LAKE_WQ, critical=True)

        st.markdown("**Figures**")
        fig_rows = []
        for label, path in REQUIRED_FIGURES.items():
            ok = path.exists() and path.stat().st_size > 0
            fig_rows.append({"Figure": label, "Status": _status_icon(ok, False)})
        st.dataframe(fig_rows, width="stretch", hide_index=True)

    # -- CRS tab --
    with tab_crs:
        st.markdown("#### CRS policy")
        st.markdown("- Local metric processing: **EPSG:32632**\n- Web display / exchange: **EPSG:4326**\n- Area, distance, slope, buffer, and hydrologic routing are never computed in degrees.\n- `set_crs` is never used as a substitute for reprojection.\n- Categorical rasters use nearest-neighbour resampling.")
        st.markdown("#### Processing notes")
        st.info("This tool uses local input files only. No external cloud services are required.")

    # -- Upload manifest tab --
    with tab_manifest:
        st.markdown("#### Upload history")
        manifest = read_manifest()
        if manifest:
            st.dataframe([dict(row) for row in manifest[-30:]], width="stretch", hide_index=True)
        else:
            st.info("No uploads recorded yet.")

# ===========================================================================
# SECTION: Model
# ===========================================================================
elif nav == "Model":
    tab_cmds, tab_logs, tab_tests = st.tabs(["Run commands", "Run logs", "Tests"])

    with tab_cmds:
        st.markdown("#### Execute predefined commands")
        st.caption("Only safe predefined commands are available. Arbitrary shell commands are not supported.")

        commands = available_commands()
        for label in commands:
            with st.expander(label, expanded=False):
                if st.button(f"Run: {label}", key=f"btn_{label}"):
                    with st.spinner(f"Running {label}..."):
                        result = run_command(label)
                    if result.returncode == 0:
                        st.success(f"Completed (exit code {result.returncode})")
                    else:
                        st.error(f"Failed (exit code {result.returncode})")
                    st.caption(f"Started: {result.started}  |  Finished: {result.finished}")
                    st.caption(f"Log: `{result.log_path.relative_to(ROOT)}`")
                    if result.stdout:
                        with st.expander("stdout"):
                            st.code(result.stdout[-4000:])
                    if result.stderr:
                        with st.expander("stderr"):
                            st.code(result.stderr[-4000:])

    with tab_logs:
        st.markdown("#### Run log files")
        log_dir = WEBAPP / "run_logs"
        if log_dir.exists():
            logs = sorted(log_dir.glob("*.log"), reverse=True)[:20]
            if logs:
                for lp in logs:
                    with st.expander(lp.name, expanded=False):
                        st.code(lp.read_text()[-3000:])
            else:
                st.info("No run logs yet.")
        else:
            st.info("No run logs yet.")

    with tab_tests:
        st.markdown("#### Minimal test suite")
        if st.button("Run tests (lake_wq_closure + CRS)", key="btn_tests"):
            result = run_command("Run minimal tests")
            if result.returncode == 0:
                st.success(f"All tests passed. (exit code {result.returncode})")
            else:
                st.error(f"Tests failed. (exit code {result.returncode})")
            if result.stdout:
                st.code(result.stdout[-3000:])

# ===========================================================================
# SECTION: Explore
# ===========================================================================
elif nav == "Explore":
    tab_map, tab_params, tab_events, tab_burn = st.tabs([
        "Map", "Parameters", "Events", "Burn footprint",
    ])

    # -- Map tab --
    with tab_map:
        st.markdown("#### Interactive study area map")
        st.caption("All layers built from vector data and reprojected to WGS84 for web display.")

        import pydeck as pdk
        import numpy as np

        col_filters, col_map = st.columns([0.24, 0.76])

        with col_filters:
            st.markdown("**Base layers**")
            show_catchment = st.checkbox("Catchment", value=True, key="mc")
            show_fire = st.checkbox("Official fire", value=True, key="mf")
            show_lake = st.checkbox("Lake boundary", value=True, key="ml")
            show_hydro = st.checkbox("Hydrography", key="mh")
            show_streams = st.checkbox("DEM streams", key="ms")
            st.markdown("**Model layers**")
            show_units = st.checkbox("Response units", value=True, key="mu")
            show_outlet = st.checkbox("Outlet", value=True, key="mo")
            show_burn_rast = st.checkbox("Burn proxy overlay", key="mbr")
            color_by = st.selectbox("Color units by", ["cn_adjustment", "burn_class", "landcover_class", "baseline_parameter", "burned_parameter"], key="mcolor")

        with col_map:
            import geopandas as gpd

            def load_geojson(path, label):
                """Load a vector file and return GeoJSON features + status note."""
                if not path.exists():
                    return None, f"{label}: file not found"
                gdf = gpd.read_file(path)
                if gdf.crs is None:
                    return None, f"{label}: no CRS"
                epsg = gdf.crs.to_epsg()
                if epsg is None:
                    return None, f"{label}: unknown CRS"
                if epsg != 4326:
                    gdf = gdf.to_crs("EPSG:4326")
                features = gdf.__geo_interface__["features"]
                return features, f"{label}: {len(features)} feature(s)"

            dp = ROOT / "data/processed"
            layers = []
            notes = []

            def add_polygon_layer(path, label, line_color, fill_color, lw=2):
                feats, note = load_geojson(path, label)
                notes.append(note)
                if feats:
                    layers.append(pdk.Layer("GeoJsonLayer",
                        data=feats, pickable=True, stroked=True, filled=True,
                        get_line_color=line_color, get_fill_color=fill_color,
                        get_line_width=lw, line_width_min_pixels=1))

            def add_line_layer(path, label, line_color, lw=1):
                feats, note = load_geojson(path, label)
                notes.append(note)
                if feats:
                    layers.append(pdk.Layer("GeoJsonLayer",
                        data=feats, pickable=False, stroked=True, filled=False,
                        get_line_color=line_color, get_line_width=lw,
                        line_width_min_pixels=1))

            if show_catchment:
                add_polygon_layer(CATCHMENT, "Catchment",
                                  [30, 60, 120, 220], [41, 80, 160, 60])
            if show_fire:
                add_polygon_layer(FIRE_PERIMETER, "Fire perimeter",
                                  [217, 95, 14, 220], [217, 95, 14, 50])
            if show_lake:
                add_polygon_layer(LAKE_BOUNDARY, "Lake boundary",
                                  [43, 140, 190, 220], [43, 140, 190, 80])
            if show_hydro:
                add_line_layer(HYDROGRAPHY, "Hydrography",
                               [49, 130, 189, 200])
            if show_streams:
                add_line_layer(DEM_STREAMS, "DEM streams",
                               [107, 174, 214, 200])
            if show_units:
                add_polygon_layer(RUNOFF_UNITS_GPKG, "Response units",
                                  [80, 80, 80, 60], [180, 200, 230, 80], lw=1)
            if show_burn_rast:
                overlay = burn_raster_overlay()
                if overlay:
                    layers.append(pdk.Layer("GeoJsonLayer",
                        data=overlay["data"], pickable=True, stroked=False, filled=True,
                        get_fill_color="[properties.color[0], properties.color[1], properties.color[2], properties.color[3]]"))
                    notes.append(f"Burn proxy overlay: {len(overlay['data'])} polygon(s)")
                else:
                    notes.append("Burn proxy overlay: file not found")
            if show_outlet:
                coords = outlet_lonlat(ROOT)
                if coords is not None:
                    layers.append(pdk.Layer("ScatterplotLayer",
                        data=[{"lon": coords[0], "lat": coords[1]}],
                        get_position=["lon", "lat"], get_radius=150,
                        get_color=[200, 50, 40, 240], pickable=True))
                    notes.append("Outlet: configured coordinate")
                else:
                    notes.append("Outlet: not configured")

            st.caption("  |  ".join(notes))

            if not layers:
                layers.append(pdk.Layer("GeoJsonLayer",
                    data={"type": "FeatureCollection", "features": []}))

            center_lat, center_lon = 45.87, 8.82
            feats, _ = load_geojson(CATCHMENT, "")
            if feats:
                from shapely.geometry import shape
                g = shape(feats[0]["geometry"])
                c = g.centroid
                center_lat, center_lon = c.y, c.x

            st.pydeck_chart(pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=12, pitch=0),
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            ))

    # -- Parameters tab --
    with tab_params:
        st.markdown("#### Parameter explorer")
        st.caption("Adjust SCS-CN and burn parameters. Preview updates immediately. Official outputs are not overwritten.")

        PARAMS_PATH = WEBAPP / "current_parameters.yaml"
        PROJECT_CONFIG = ROOT / "config/project.yaml"

        def _load_params():
            if PARAMS_PATH.exists():
                with open(PARAMS_PATH) as f:
                    return yaml.safe_load(f) or {}
            return {}

        def _save_params(d):
            PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PARAMS_PATH, "w") as f:
                yaml.safe_dump(d, f, sort_keys=False, allow_unicode=True)

        saved = _load_params()

        col_sliders, col_preview = st.columns([0.38, 0.62])

        with col_sliders:
            lam = st.slider("Initial abstraction ratio (lambda)", 0.05, 0.30, float(saved.get("scs_lambda", 0.20)), 0.01,
                            help="Standard SCS: lambda = 0.20. Lower values produce higher runoff.")
            cn_low = st.slider("CN adjustment: low severity", 0, 10, int(saved.get("cn_adjustment_low", 4)), 1)
            cn_mod = st.slider("CN adjustment: moderate severity", 0, 16, int(saved.get("cn_adjustment_moderate", 8)), 1)
            cn_high = st.slider("CN adjustment: high severity", 0, 24, int(saved.get("cn_adjustment_high", 12)), 1)
            footprint = st.selectbox("Burned-footprint scenario",
                                     ["conservative_dnbr", "relaxed_dnbr", "fire_perimeter_upper_bound"],
                                     index=["conservative_dnbr", "relaxed_dnbr", "fire_perimeter_upper_bound"].index(
                                         saved.get("burn_footprint_scenario", "conservative_dnbr")))
            factor = 1.0  # Footprint scenarios require recomputing spatial masks; do not scale CN increments.

            current = {"scs_lambda": lam, "cn_adjustment_low": cn_low, "cn_adjustment_moderate": cn_mod,
                       "cn_adjustment_high": cn_high, "burn_footprint_scenario": footprint}
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("Save preset", key="save_params"):
                    _save_params(current)
                    st.success("Preset saved.")
            with cb2:
                if st.button("Export to config", key="export_cfg"):
                    bak = PROJECT_CONFIG.with_suffix(f".yaml.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    if PROJECT_CONFIG.exists():
                        bak.write_bytes(PROJECT_CONFIG.read_bytes())
                    cfg = yaml.safe_load(PROJECT_CONFIG.read_text()) if PROJECT_CONFIG.exists() else {}
                    cfg.setdefault("runoff", {})["burn_curve_number_adjustment"] = {"0": 0, "1": cn_low, "2": cn_mod, "3": cn_high}
                    PROJECT_CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
                    st.success("Exported. Full recomputation required.")

        with col_preview:
            pv = preview_metrics(lam=lam, cn_adj_low=cn_low, cn_adj_moderate=cn_mod, cn_adj_high=cn_high,
                                 footprint_factor=factor)
            if pv["preview_possible"]:
                pc = st.columns(3)
                pc[0].metric("Preview max delta Q", f"{pv['max_delta_q_mm']:.4f} mm")
                pc[1].metric("Preview max delta V", f"{pv['max_delta_v_m3']:.1f} m3")
                pc[2].metric("Max event", pv["max_event_id"])
                curve = preview_curve(lam=lam, cn_adj_low=cn_low, cn_adj_moderate=cn_mod, cn_adj_high=cn_high,
                                      footprint_factor=factor)
                if curve:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=curve["p_range"], y=curve["delta"], mode="lines",
                                             line=dict(color="#d95f0e", width=2.5),
                                             name=f"lambda={lam:.2f}, CN base={curve['base_cn']}, burned={curve['burned_cn']}",
                                             hovertemplate="P=%{x:.0f} mm<br>delta Q=%{y:.3f} mm<extra></extra>"))
                    fig.update_layout(title=f"Preview: delta Q vs rainfall depth", xaxis_title="Rainfall (mm)",
                                      yaxis_title="delta Q (mm)", template="plotly_white", height=320,
                                      margin=dict(t=40, b=30, l=40, r=10))
                    st.plotly_chart(fig, width="stretch")
                st.caption(pv.get("note", ""))
            else:
                st.warning(pv.get("note", "Preview requires runoff_units.csv and rainfall events."))

    # -- Events tab --
    with tab_events:
        st.markdown("#### Event explorer")
        delta = load_csv_safe(RUNOFF_DELTA)
        if delta is not None:
            fig = event_rainfall_scatter_chart()
            if fig:
                st.plotly_chart(fig, width="stretch")
            cdf = event_delta_cdf_chart()
            if cdf:
                st.plotly_chart(cdf, width="stretch")
            with st.expander("Runoff delta table (top 20)", expanded=False):
                vol_col = next((c for c in delta.columns if "volume" in c.lower() and "delta" in c.lower()), None)
                top = delta.sort_values(vol_col, ascending=False).head(20) if vol_col else delta.head(20)
                st.dataframe(top, width="stretch", hide_index=True)
        else:
            st.info("Runoff delta table not available.")

    # -- Burn footprint tab --
    with tab_burn:
        st.markdown("#### Burn footprint explorer")
        fig_a = burn_footprint_runoff_chart()
        if fig_a:
            st.plotly_chart(fig_a, width="stretch")
        fig_a2 = burn_footprint_area_chart()
        if fig_a2:
            st.plotly_chart(fig_a2, width="stretch")
        bt = burn_class_table()
        if bt is not None:
            st.markdown("**Burn severity class breakdown**")
            st.dataframe(bt[["class_code", "class_name", "pixel_count", "area_ha", "percent"]], width="stretch", hide_index=True,
                         column_config={"class_code": "Code", "class_name": "Class", "pixel_count": "Pixels",
                                        "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.2f"),
                                        "percent": st.column_config.NumberColumn("%", format="%.2f")})
            st.caption("NoData (255) must not be interpreted as burned or high severity.")

# ===========================================================================
# SECTION: Results
# ===========================================================================
elif nav == "Results":
    tab_runoff, tab_wepp, tab_lake, tab_tables = st.tabs([
        "Runoff", "WEPPcloud", "Lake WQ", "Tables",
    ])

    # -- Runoff tab --
    with tab_runoff:
        st.markdown("#### Runoff screening results")
        metrics = core_metrics()
        mc = st.columns(4)
        mc[0].metric("Max conservative delta Q", _fmt(metrics.get("conservative_max_dq_mm"), ".3f", " mm"))
        mc[1].metric("Upper-bound delta Q", _fmt(metrics.get("upper_bound_max_dq_mm"), ".3f", " mm"))
        mc[2].metric("Conservative proxy area", _fmt(metrics.get("conservative_burned_ha"), ".1f", " ha"))
        mc[3].metric("Upper-bound area", _fmt(metrics.get("upper_bound_burned_ha"), ".1f", " ha"))

        col_a, col_b = st.columns(2)
        with col_a:
            fig_scatter = event_rainfall_scatter_chart()
            if fig_scatter:
                st.plotly_chart(fig_scatter, width="stretch")
        with col_b:
            fig_cdf = event_delta_cdf_chart()
            if fig_cdf:
                st.plotly_chart(fig_cdf, width="stretch")

        fig_fp = burn_footprint_runoff_chart()
        if fig_fp:
            st.plotly_chart(fig_fp, width="stretch")

        delta = load_csv_safe(RUNOFF_DELTA)
        if delta is not None:
            with st.expander("Full runoff delta table", expanded=False):
                st.dataframe(delta, width="stretch", hide_index=True)

    # -- WEPPcloud tab --
    with tab_wepp:
        st.markdown("#### WEPPcloud benchmark")
        fig_w = weppcloud_sediment_chart()
        if fig_w:
            st.plotly_chart(fig_w, width="stretch")
            wepp_df = load_csv_safe(WEPP_SUMMARY)
            if wepp_df is not None:
                with st.expander("Normalized WEPPcloud export", expanded=False):
                    st.dataframe(wepp_df, width="stretch", hide_index=True)
        else:
            st.info("WEPPcloud unavailable: configure and import a user-exported WEPPcloud results CSV.")
        st.info(
            "WEPPcloud is an external process-model comparison. Imported annual or period results "
            "answer a different question from event-scale SCS-CN direct runoff and are not validation."
        )

    # -- Lake WQ tab --
    with tab_lake:
        st.markdown("#### Lake water-quality closure")
        fig_lake = lake_wq_status_figure()
        st.plotly_chart(fig_lake, width="stretch")

        status_df = load_csv_safe(LAKE_STATUS)
        avail_path = TABLES / "lake_wq_event_image_availability.csv"
        avail_df = load_csv_safe(avail_path)

        n_events = len(avail_df) if avail_df is not None else 0
        n_with_pre = int((avail_df["pre_products_found"] > 0).sum()) if avail_df is not None and "pre_products_found" in avail_df else 0
        n_with_post = int((avail_df["post_products_found"] > 0).sum()) if avail_df is not None and "post_products_found" in avail_df else 0
        n_usable = int((avail_df["usable_pair"].astype(str).str.upper() == "YES").sum()) if avail_df is not None and "usable_pair" in avail_df else 0

        mc = st.columns(5)
        mc[0].metric("Selected events", _fmt_int(n_events) if n_events else "N/A")
        mc[1].metric("Events with pre image", _fmt_int(n_with_pre))
        mc[2].metric("Events with post image", _fmt_int(n_with_post))
        mc[3].metric("Usable pre/post pairs", _fmt_int(n_usable))
        mc[4].metric("Status", "Data-limited" if n_usable == 0 else "Partial data")

        if status_df is not None and "message" in status_df.columns:
            st.warning(str(status_df["message"].iloc[0]))
        else:
            st.info("Run the optional lake WQ command after configuring real local pre/post Sentinel-2 inputs.")

        if avail_df is not None:
            st.markdown("**Event-image availability**")
            st.dataframe(avail_df, width="stretch", hide_index=True)

        with st.expander("Detected local Sentinel-2 products", expanded=False):
            import re as _re
            zip_dir = ROOT / "data/raw"
            prods = sorted(zip_dir.rglob("*.SAFE.zip"))
            if prods:
                prod_rows = []
                dates = []
                for p in prods:
                    m = _re.search(r"MSIL2A_(\d{8})T", p.name)
                    d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}" if m else ""
                    if d:
                        dates.append(d)
                    tile_m = _re.search(r"T(\d{2}[A-Z]{3})", p.name)
                    prod_rows.append({
                        "Sensing date": d,
                        "Sensor": p.name.split("_")[0],
                        "Tile": tile_m.group(1) if tile_m else "",
                        "Product": p.name[:75],
                        "Size (MB)": round(p.stat().st_size / 1e6, 1),
                    })
                st.dataframe(prod_rows, width="stretch", hide_index=True)
                if dates:
                    st.caption(f"Archive range detected locally: {min(dates)} to {max(dates)}")
            else:
                st.info("No local Sentinel-2 SAFE products found.")

        anomalies = load_csv_safe(LAKE_ANOMALIES)
        if anomalies is not None:
            with st.expander("Anomaly table", expanded=False):
                st.dataframe(anomalies, width="stretch", hide_index=True)
                st.caption("Numeric NDTI/NDCI anomalies are shown only when valid pre/post imagery exists.")

    # -- Tables tab --
    with tab_tables:
        st.markdown("#### Exportable project tables")
        table_paths = {
            "Runoff delta by event": RUNOFF_DELTA,
            "Runoff event summary": RUNOFF_EVENTS,
            "Burn severity area": BURN_AREA,
            "WEPPcloud summary": WEPP_SUMMARY,
            "Lake WQ status": LAKE_STATUS,
            "Lake image availability": LAKE_SELECTED,
        }
        selected_table = st.selectbox("Select table", list(table_paths.keys()))
        path = table_paths[selected_table]
        df = load_csv_safe(path)
        if df is not None:
            st.dataframe(df, width="stretch", hide_index=True)
            st.caption(f"Source: `{path.relative_to(ROOT)}`  |  Rows: {len(df)}")
        else:
            st.info(f"Table not found: `{path.relative_to(ROOT)}`")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "GeoProject  |  Screening-level results  |  Local-data workflow  |  "
    "All results are screening-level, uncalibrated scenario estimates."
)
