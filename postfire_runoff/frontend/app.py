"""Streamlit entry point for the post-fire runoff screening tool."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from postfire_runoff.frontend.components.data_page import render_data_page
from postfire_runoff.frontend.components.explore_page import render_explore_page
from postfire_runoff.frontend.components.model_page import render_model_page
from postfire_runoff.frontend.components.overview_page import render_overview_page
from postfire_runoff.frontend.components.results_page import render_results_page
from postfire_runoff.frontend.components.style import inject as inject_css

st.set_page_config(page_title="Post-fire Runoff Screening", layout="wide")
inject_css()

st.markdown("### Post-fire Runoff Screening Tool")
st.caption("Reproducible screening-level workflow for post-wildfire runoff sensitivity analysis.")

nav = st.radio(
    "Navigation",
    ["Overview", "Data", "Model", "Explore", "Results"],
    horizontal=True,
    label_visibility="collapsed",
    key="top_nav",
)

st.markdown("---")

if nav == "Overview":
    render_overview_page()
elif nav == "Data":
    render_data_page()
elif nav == "Model":
    render_model_page()
elif nav == "Explore":
    render_explore_page()
elif nav == "Results":
    render_results_page()

st.markdown("---")
st.caption("GeoProject  |  Screening-level results  |  Local-data workflow")
