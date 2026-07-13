"""Minimal CSS for a bright, clean, academic Streamlit interface."""
from __future__ import annotations

CSS = """
<style>
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    color: #1a1a2e;
}

[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.15s;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
}
[data-testid="stMetric"] label {
    font-size: 0.72rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748b;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.5rem;
    font-weight: 620;
    color: #0f172a;
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    font-size: 0.82rem;
    font-weight: 500;
}

.section-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}

.guardrail-box {
    background: #f8fafc;
    border-left: 3px solid #64748b;
    border-radius: 6px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
    font-size: 0.82rem;
    line-height: 1.6;
    color: #475569;
}
.guardrail-box ul {
    margin: 0.25rem 0 0 0;
    padding-left: 1.25rem;
}

[data-testid="stRadio"] > div {
    gap: 0;
}
[data-testid="stRadio"] label {
    padding: 0.55rem 1.3rem;
    margin: 0 0.15rem;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 520;
    color: #475569;
    cursor: pointer;
    transition: background 0.12s;
}
[data-testid="stRadio"] label:hover {
    background: #f1f5f9;
}

[data-testid="baseButton-secondary"] {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.84rem;
}

[data-testid="stExpander"] {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    box-shadow: none;
}

[data-testid="stTable"], [data-testid="stDataFrame"] {
    border-radius: 8px;
}

[data-testid="stAlert"] {
    border-radius: 8px;
    font-size: 0.84rem;
}
</style>
"""


def inject() -> None:
    """Apply the project CSS."""
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)
