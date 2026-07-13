"""Results page rendering."""
from __future__ import annotations

import streamlit as st

from postfire_runoff.frontend.components.charts import (
    burn_runoff_chart,
    event_delta_cdf_chart,
    event_rainfall_scatter_chart,
    weppcloud_sediment_chart,
)
from postfire_runoff.frontend.components.formatting import fmt_number
from postfire_runoff.frontend.components.loaders import (
    BURN_AREA,
    RUNOFF_DELTA,
    RUNOFF_EVENTS,
    RUNOFF_UNITS,
    WEPP_SUMMARY,
    DataLoadError,
    core_metrics,
    load_csv,
)
from postfire_runoff.frontend.components.paths import ROOT


def render_results_page() -> None:
    tab_runoff, tab_wepp, tab_tables = st.tabs(["Runoff", "WEPPcloud", "Tables"])
    with tab_runoff:
        _render_runoff_tab()
    with tab_wepp:
        _render_wepp_tab()
    with tab_tables:
        _render_tables_tab()


def _render_runoff_tab() -> None:
    st.markdown("#### Runoff screening results")
    try:
        metrics = core_metrics()
        mc = st.columns(4)
        mc[0].metric("Max delta Q", fmt_number(metrics.get("max_delta_q_mm"), ".3f", " mm"))
        mc[1].metric("Max delta volume", fmt_number(metrics.get("max_delta_volume_m3"), ".0f", " m3"))
        mc[2].metric("Burned area", fmt_number(metrics.get("burned_area_ha"), ".1f", " ha"))
        mc[3].metric("Catchment", fmt_number(metrics.get("catchment_area_ha"), ".1f", " ha"))
        col_a, col_b = st.columns(2)
        with col_a:
            fig_scatter = event_rainfall_scatter_chart()
            if fig_scatter:
                st.plotly_chart(fig_scatter, width="stretch")
        with col_b:
            fig_cdf = event_delta_cdf_chart()
            if fig_cdf:
                st.plotly_chart(fig_cdf, width="stretch")
        fig_burn = burn_runoff_chart()
        if fig_burn:
            st.plotly_chart(fig_burn, width="stretch")
        delta = load_csv(RUNOFF_DELTA)
        if delta is not None:
            with st.expander("Full runoff delta table", expanded=False):
                st.dataframe(delta, width="stretch", hide_index=True)
    except DataLoadError as exc:
        st.error(str(exc))


def _render_wepp_tab() -> None:
    st.markdown("#### WEPPcloud comparison")
    try:
        fig = weppcloud_sediment_chart()
        if fig:
            st.plotly_chart(fig, width="stretch")
            wepp_df = load_csv(WEPP_SUMMARY)
            if wepp_df is not None:
                with st.expander("Normalized WEPPcloud export", expanded=False):
                    st.dataframe(wepp_df, width="stretch", hide_index=True)
        else:
            st.info("WEPPcloud unavailable: assign a user-exported WEPPcloud results CSV on the Data page.")
    except DataLoadError as exc:
        st.error(str(exc))
    st.info(
        "WEPPcloud is an external process-model comparison. Imported annual or period results "
        "answer a different question from event-scale SCS-CN direct runoff."
    )


def _render_tables_tab() -> None:
    st.markdown("#### Exportable project tables")
    table_paths = {
        "Runoff units": RUNOFF_UNITS,
        "Runoff delta by event": RUNOFF_DELTA,
        "Runoff event summary": RUNOFF_EVENTS,
        "Burn severity area": BURN_AREA,
        "WEPPcloud summary": WEPP_SUMMARY,
    }
    selected = st.selectbox("Select table", list(table_paths.keys()))
    path = table_paths[selected]
    try:
        df = load_csv(path)
    except DataLoadError as exc:
        st.error(str(exc))
        return
    if df is not None:
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption(f"Source: `{path.relative_to(ROOT)}`  |  Rows: {len(df)}")
    else:
        st.info(f"Table not found: `{path.relative_to(ROOT)}`")
