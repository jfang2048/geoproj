"""Overview page rendering."""
from __future__ import annotations

import streamlit as st

from postfire_runoff.frontend.components.formatting import fmt_int, fmt_number, metric_delta
from postfire_runoff.frontend.components.loaders import DataLoadError, core_metrics


def render_overview_page() -> None:
    try:
        metrics = core_metrics()
    except DataLoadError as exc:
        st.error(str(exc))
        metrics = {"errors": [str(exc)]}

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("#### Project at a glance")

    r1 = st.columns(4)
    r1[0].metric("Catchment", fmt_number(metrics.get("catchment_area_ha"), ".1f", " ha"))
    r1[1].metric("Official fire perimeter", fmt_number(metrics.get("fire_perimeter_ha"), ".1f", " ha"))
    r1[2].metric(
        "Fire inside catchment",
        fmt_number(metrics.get("fire_inside_catchment_ha"), ".1f", " ha"),
        metric_delta(metrics.get("fire_inside_pct"), ".1f", "%"),
    )
    r1[3].metric("Rainfall events", fmt_int(metrics.get("rainfall_event_count")))

    r2 = st.columns(4)
    r2[0].metric("Burned area", fmt_number(metrics.get("burned_area_ha"), ".1f", " ha"))
    r2[1].metric("Max delta Q", fmt_number(metrics.get("max_delta_q_mm"), ".3f", " mm"))
    r2[2].metric("Max delta volume", fmt_number(metrics.get("max_delta_volume_m3"), ".0f", " m3"))
    r2[3].metric("Response units", fmt_int(metrics.get("response_unit_count")))

    r3 = st.columns(4)
    if metrics.get("wepp_available"):
        sed_min = fmt_number(metrics.get("wepp_sediment_min"), ".1f")
        sed_max = fmt_number(metrics.get("wepp_sediment_max"), ".1f")
        runoff_min = fmt_number(metrics.get("wepp_runoff_min"), ".1f")
        runoff_max = fmt_number(metrics.get("wepp_runoff_max"), ".1f")
        r3[0].metric("WEPPcloud sediment", f"{sed_min} to {sed_max}")
        r3[1].metric("WEPPcloud runoff", f"{runoff_min} to {runoff_max}")
    else:
        r3[0].metric("WEPPcloud sediment", "Unavailable")
        r3[1].metric("WEPPcloud runoff", "Unavailable")
    r3[2].metric("Processing CRS", "EPSG:32632")
    r3[3].metric("Display CRS", "EPSG:4326")
    st.markdown("</div>", unsafe_allow_html=True)

    for error in metrics.get("errors", []):
        st.warning(error)

    with st.expander("Scientific scope", expanded=False):
        st.markdown(
            "The SCS-CN outputs are uncalibrated event-scale scenario estimates. "
            "Burn classes derived from remote sensing represent burn-severity proxies. "
            "WEPPcloud outputs are presented as an external comparison with different model and temporal scales."
        )
