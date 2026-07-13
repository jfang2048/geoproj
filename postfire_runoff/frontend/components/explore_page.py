"""Exploration page for map, parameters, events, and burn classes."""
from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
import yaml

from postfire_runoff.frontend.components.charts import (
    burn_area_chart,
    burn_runoff_chart,
    event_delta_cdf_chart,
    event_rainfall_scatter_chart,
)
from postfire_runoff.frontend.components.loaders import BURN_AREA, RUNOFF_DELTA, DataLoadError, burn_class_table, load_csv
from postfire_runoff.frontend.components.maps import render_map
from postfire_runoff.frontend.components.paths import PARAMS_PATH, PROJECT_CONFIG
from postfire_runoff.frontend.components.scs_preview import preview_curve, preview_metrics


def render_explore_page() -> None:
    tab_map, tab_params, tab_events, tab_burn = st.tabs([
        "Map", "Parameters", "Events", "Burn classes",
    ])
    with tab_map:
        render_map()
    with tab_params:
        _render_parameters_tab()
    with tab_events:
        _render_events_tab()
    with tab_burn:
        _render_burn_tab()


def _render_parameters_tab() -> None:
    st.markdown("#### Parameter explorer")
    st.caption("Adjust SCS-CN and burn CN increments. Preview updates immediately; official outputs are not overwritten.")
    saved = _load_params()
    col_sliders, col_preview = st.columns([0.38, 0.62])
    with col_sliders:
        lam = st.slider(
            "Initial abstraction ratio (lambda)",
            0.05,
            0.30,
            float(saved.get("scs_lambda", 0.20)),
            0.01,
            help="Standard SCS: lambda = 0.20. Lower values produce higher runoff.",
        )
        cn_low = st.slider("CN adjustment: low severity", 0, 10, int(saved.get("cn_adjustment_low", 4)), 1)
        cn_mod = st.slider("CN adjustment: moderate severity", 0, 16, int(saved.get("cn_adjustment_moderate", 8)), 1)
        cn_high = st.slider("CN adjustment: high severity", 0, 24, int(saved.get("cn_adjustment_high", 12)), 1)
        st.caption("Footprint scenarios require separate spatial burn masks and full reruns.")

        current = {"scs_lambda": lam, "cn_adjustment_low": cn_low, "cn_adjustment_moderate": cn_mod, "cn_adjustment_high": cn_high}
        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("Save preset", key="save_params"):
                _save_params(current)
                st.success("Preset saved.")
        with cb2:
            if st.button("Export to config", key="export_cfg"):
                backup = PROJECT_CONFIG.with_suffix(f".yaml.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                if PROJECT_CONFIG.exists():
                    backup.write_bytes(PROJECT_CONFIG.read_bytes())
                cfg = yaml.safe_load(PROJECT_CONFIG.read_text()) if PROJECT_CONFIG.exists() else {}
                cfg.setdefault("runoff", {})["burn_curve_number_adjustment"] = {0: 0, 1: cn_low, 2: cn_mod, 3: cn_high}
                cfg["runoff"]["initial_abstraction_ratio"] = lam
                PROJECT_CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
                st.success("Exported. Run pipeline to recompute outputs.")
    with col_preview:
        try:
            pv = preview_metrics(lam=lam, cn_adj_low=cn_low, cn_adj_moderate=cn_mod, cn_adj_high=cn_high)
            if pv["preview_possible"]:
                pc = st.columns(3)
                pc[0].metric("Preview max delta Q", f"{pv['max_delta_q_mm']:.4f} mm")
                pc[1].metric("Preview max delta V", f"{pv['max_delta_v_m3']:.1f} m3")
                pc[2].metric("Max event", pv["max_event_id"])
                curve = preview_curve(lam=lam, cn_adj_low=cn_low, cn_adj_moderate=cn_mod, cn_adj_high=cn_high)
                if curve:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=curve["p_range"],
                        y=curve["delta"],
                        mode="lines",
                        line=dict(color="#d95f0e", width=2.5),
                        name=f"lambda={lam:.2f}, CN base={curve['base_cn']}, burned={curve['burned_cn']}",
                        hovertemplate="P=%{x:.0f} mm<br>delta Q=%{y:.3f} mm<extra></extra>",
                    ))
                    fig.update_layout(
                        title="Preview: delta Q vs rainfall depth",
                        xaxis_title="Rainfall (mm)",
                        yaxis_title="delta Q (mm)",
                        template="plotly_white",
                        height=320,
                        margin=dict(t=40, b=30, l=40, r=10),
                    )
                    st.plotly_chart(fig, width="stretch")
                st.caption(pv.get("note", ""))
            else:
                st.warning(pv.get("note", "Preview requires runoff_units.csv and rainfall events."))
        except DataLoadError as exc:
            st.error(str(exc))


def _render_events_tab() -> None:
    st.markdown("#### Event explorer")
    try:
        delta = load_csv(RUNOFF_DELTA)
        if delta is None:
            st.info("Runoff delta table not available.")
            return
        fig = event_rainfall_scatter_chart()
        if fig:
            st.plotly_chart(fig, width="stretch")
        cdf = event_delta_cdf_chart()
        if cdf:
            st.plotly_chart(cdf, width="stretch")
        with st.expander("Runoff delta table (top 20)", expanded=False):
            top = delta.sort_values("delta_volume_m3", ascending=False).head(20) if "delta_volume_m3" in delta.columns else delta.head(20)
            st.dataframe(top, width="stretch", hide_index=True)
    except DataLoadError as exc:
        st.error(str(exc))


def _render_burn_tab() -> None:
    st.markdown("#### Burn class explorer")
    try:
        fig = burn_runoff_chart()
        if fig:
            st.plotly_chart(fig, width="stretch")
        area_fig = burn_area_chart()
        if area_fig:
            st.plotly_chart(area_fig, width="stretch")
        table = burn_class_table()
        if table is not None:
            st.markdown("**Burn severity raster class breakdown**")
            st.dataframe(table, width="stretch", hide_index=True)
        summary = load_csv(BURN_AREA)
        if summary is not None:
            with st.expander("Burn area from response units", expanded=False):
                st.dataframe(summary, width="stretch", hide_index=True)
    except DataLoadError as exc:
        st.error(str(exc))


def _load_params() -> dict:
    if PARAMS_PATH.exists():
        return yaml.safe_load(PARAMS_PATH.read_text()) or {}
    return {}


def _save_params(values: dict) -> None:
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_PATH.write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True))
