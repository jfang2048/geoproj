"""Data upload and file-status page."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from postfire_runoff.backend.services.uploads import (
    CATEGORY_RULES,
    accepted_extensions_for,
    handle_upload,
    read_input_assignments,
)
from postfire_runoff.frontend.components.paths import PROJECT_CONFIG, REQUIRED_CORE, REQUIRED_WEPPCLOUD, ROOT
from postfire_runoff.frontend.components.upload_manifest import read_manifest, record_upload


def render_data_page() -> None:
    tab_upload, tab_check, tab_crs, tab_manifest = st.tabs([
        "Upload files", "Required files", "CRS status", "Upload manifest",
    ])
    with tab_upload:
        _render_upload_tab()
    with tab_check:
        _render_required_files_tab()
    with tab_crs:
        st.markdown("#### CRS policy")
        st.markdown(
            "- Local metric processing: **EPSG:32632**\n"
            "- Web display and geographic exchange: **EPSG:4326**\n"
            "- Area and distance are computed only in the metric processing CRS.\n"
            "- Categorical rasters use nearest-neighbour resampling."
        )
    with tab_manifest:
        st.markdown("#### Upload history")
        manifest = read_manifest()
        if manifest:
            st.dataframe([dict(row) for row in manifest[-30:]], width="stretch", hide_index=True)
        else:
            st.info("No uploads recorded yet.")


def _render_upload_tab() -> None:
    st.markdown("#### Upload project data")
    st.caption("Uploaded files are saved under data/raw and assigned to config/project.yaml. Existing files are not overwritten.")
    assignments = read_input_assignments(PROJECT_CONFIG, ROOT)
    rows = []
    for category, rules in CATEGORY_RULES.items():
        key = str(rules["config_key"])
        assigned = assignments.get(key, "")
        exists = bool(assigned) and (ROOT / assigned).exists()
        rows.append({"Input": category, "Config key": f"inputs.{key}", "Assigned file": assigned or "", "Exists": exists})
    st.dataframe(rows, width="stretch", hide_index=True)

    category = st.selectbox("Data category", list(CATEGORY_RULES.keys()), key="upload_category")
    rules = CATEGORY_RULES[category]
    key = str(rules["config_key"])
    exts = accepted_extensions_for(category)
    current = assignments.get(key, "")
    st.caption(f"Accepted extensions: {', '.join(exts)}  |  Assigned key: `inputs.{key}`")
    st.caption(f"Current assignment: `{current or 'not assigned'}`")

    uploaded = st.file_uploader(
        f"Choose file for {category}",
        accept_multiple_files=False,
        type=[e.lstrip(".") for e in exts],
        key=f"up_{category}",
    )
    if uploaded is None:
        return
    if st.button("Save upload and assign", key=f"assign_{category}"):
        file_bytes = uploaded.getvalue()
        result = handle_upload(category, uploaded.name, file_bytes, root=ROOT, config_path=PROJECT_CONFIG)
        if not result.valid:
            st.error(f"{uploaded.name}: {result.message}")
            return
        dest = Path(result.saved_path)
        record_upload(
            category=category,
            config_key=result.assigned_config_key,
            original_filename=uploaded.name,
            saved_path=dest,
            file_size_bytes=dest.stat().st_size,
            checksum=result.checksum,
            warnings="; ".join(result.warnings),
        )
        st.success(f"Saved `{dest.relative_to(ROOT)}` and assigned `{result.assigned_config_key}`.")
        st.rerun()


def _render_required_files_tab() -> None:
    st.markdown("#### Generated file status")
    col1, col2 = st.columns(2)
    with col1:
        _check_group("Core outputs", REQUIRED_CORE, critical=True)
    with col2:
        _check_group("Optional WEPPcloud import", REQUIRED_WEPPCLOUD, critical=False)


def _check_group(title: str, items: dict[str, Path], critical: bool) -> None:
    st.markdown(f"**{title}**")
    rows = []
    for label, path in items.items():
        ok = path.exists() and (path.stat().st_size > 0 if path.is_file() else True)
        rows.append({"Item": label, "Path": str(path.relative_to(ROOT)), "Status": "OK" if ok else ("MISSING" if critical else "optional")})
    st.dataframe(rows, width="stretch", hide_index=True)
