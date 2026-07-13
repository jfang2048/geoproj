"""Model execution page."""
from __future__ import annotations

import streamlit as st

from postfire_runoff.frontend.components.paths import ROOT, RUN_LOGS
from postfire_runoff.frontend.components.runner import available_commands, run_command


def render_model_page() -> None:
    tab_cmds, tab_logs = st.tabs(["Run commands", "Run logs"])
    with tab_cmds:
        st.markdown("#### Execute pipeline")
        st.caption("Run pipeline uses config/project.yaml, including files assigned on the Data page.")
        commands = available_commands()
        if not commands:
            st.error("No runnable project commands found.")
        for label in commands:
            with st.expander(label, expanded=True):
                if st.button(f"Run: {label}", key=f"btn_{label}"):
                    with st.spinner(f"Running {label}..."):
                        result = run_command(label)
                    if result.returncode == 0:
                        st.success(f"Completed (exit code {result.returncode})")
                    else:
                        st.error(f"Failed (exit code {result.returncode})")
                    st.caption(f"Started: {result.started}  |  Finished: {result.finished}")
                    if result.log_path:
                        st.caption(f"Log: `{result.log_path.relative_to(ROOT)}`")
                    if result.stdout:
                        with st.expander("stdout"):
                            st.code(result.stdout[-4000:])
                    if result.stderr:
                        with st.expander("stderr"):
                            st.code(result.stderr[-4000:])
    with tab_logs:
        st.markdown("#### Run log files")
        if RUN_LOGS.exists():
            logs = sorted(RUN_LOGS.glob("*.log"), reverse=True)[:20]
            if logs:
                for log_path in logs:
                    with st.expander(log_path.name, expanded=False):
                        st.code(log_path.read_text()[-3000:])
            else:
                st.info("No run logs yet.")
        else:
            st.info("No run logs yet.")
