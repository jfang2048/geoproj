"""Visualization helpers for the Parameters and Visualization page."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from webapp.utils.paths import ROOT, TABLES, LATEX


# ---------------------------------------------------------------------------
# Colour-blind-safe palette
# ---------------------------------------------------------------------------
BLUE = "#2b8cbe"
ORANGE = "#d95f0e"
GREEN = "#31a354"
PURPLE = "#756bb1"
RED = "#e34a33"
GREY = "#999999"


def _load_csv(path: Path) -> pd.DataFrame | None:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return None


# ---------------------------------------------------------------------------
# Burned-footprint vs runoff-potential bar chart
# ---------------------------------------------------------------------------
def burn_footprint_bar() -> go.Figure | None:
    path = TABLES / "burn_severity_ensemble_summary.csv"
    df = _load_csv(path)
    if df is None:
        return None
    # Expects columns: scenario, burned_area_ha, max_runoff_delta_mm (or similar)
    area_col = next((c for c in df.columns if "area" in c.lower()), None)
    runoff_col = next((c for c in df.columns if "runoff" in c.lower() and "delta" in c.lower() and "max" in c.lower()), None)
    scenario_col = next((c for c in df.columns if "scenario" in c.lower()), df.columns[0])
    if area_col is None or runoff_col is None:
        return None

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[scenario_col].str.replace("_", " "),
        y=df[runoff_col],
        marker_color=[BLUE, ORANGE, PURPLE][:len(df)],
        text=df[runoff_col].round(3),
        textposition="outside",
    ))
    fig.update_layout(
        title="Burn footprint controls runoff-potential response",
        yaxis_title="Max modelled runoff-potential ΔQ (mm)",
        xaxis_title="Burned-footprint scenario",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Rainfall-event depth vs modelled delta runoff scatter
# ---------------------------------------------------------------------------
def event_rainfall_scatter(selected_event: str | None = None) -> go.Figure | None:
    delta = _load_csv(TABLES / "runoff_delta_by_event.csv")
    events = _load_csv(TABLES / "post_fire_rainfall_events.csv")
    if delta is None or events is None:
        return None
    start_c = next((c for c in events.columns if c in ("start_date", "event_start")), None)
    end_c = next((c for c in events.columns if c in ("end_date", "event_end")), None)
    merged = events.merge(delta, on="event_id", how="inner")
    if "total_precip_mm" not in merged.columns or "delta_runoff_mm" not in merged.columns:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged["total_precip_mm"],
        y=merged["delta_runoff_mm"],
        mode="markers",
        marker=dict(color=BLUE, size=8, line=dict(color="white", width=0.5)),
        text=merged["event_id"],
        hovertemplate="%{text}<br>P=%{x:.1f} mm<br>ΔQ=%{y:.4f} mm<extra></extra>",
        name="Events",
    ))
    if selected_event and selected_event in merged["event_id"].values:
        sel = merged[merged["event_id"] == selected_event]
        fig.add_trace(go.Scatter(
            x=sel["total_precip_mm"],
            y=sel["delta_runoff_mm"],
            mode="markers",
            marker=dict(color=ORANGE, size=14, symbol="diamond", line=dict(color="black", width=1)),
            name=selected_event,
            hovertemplate=f"{selected_event}<br>P=%{{x:.1f}} mm<br>ΔQ=%{{y:.4f}} mm<extra></extra>",
        ))
    fig.update_layout(
        title="Observed rainfall events vs modelled runoff change",
        xaxis_title="Event rainfall depth (mm)",
        yaxis_title="Modelled ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# CDF of event-scale delta runoff
# ---------------------------------------------------------------------------
def event_delta_cdf() -> go.Figure | None:
    delta = _load_csv(TABLES / "runoff_delta_by_event.csv")
    if delta is None or "delta_runoff_mm" not in delta.columns:
        return None
    vals = delta["delta_runoff_mm"].dropna().sort_values().values
    if len(vals) < 2:
        return None
    cdf = np.arange(1, len(vals) + 1) / len(vals)

    # Add ensemble max markers if available
    ensemble = _load_csv(TABLES / "burn_severity_ensemble_summary.csv")
    markers = []
    if ensemble is not None:
        runoff_col = next((c for c in ensemble.columns if "runoff" in c.lower() and "max" in c.lower()), None)
        if runoff_col is not None:
            for _, row in ensemble.iterrows():
                markers.append((row.get("scenario", ""), float(row[runoff_col])))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=vals, y=cdf, mode="lines", name="Event CDF",
        line=dict(color=BLUE, width=2),
    ))
    colors = [ORANGE, GREEN, PURPLE]
    for i, (label, mx) in enumerate(markers[:len(colors)]):
        fig.add_trace(go.Scatter(
            x=[mx, mx], y=[0, 1], mode="lines",
            line=dict(color=colors[i], dash="dash", width=1.5),
            name=f"{label} max",
        ))
    fig.update_layout(
        title="Event-scale delta runoff distribution",
        xaxis_title="Event ΔQ (mm)",
        yaxis_title="Cumulative fraction",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# WEPPcloud sediment bar chart
# ---------------------------------------------------------------------------
def weppcloud_sediment_bar() -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Undisturbed", "Disturbed"],
        y=[293.0, 652.6],
        marker_color=[GREY, ORANGE],
        text=["293.0", "652.6"],
        textposition="outside",
    ))
    fig.update_layout(
        title="WEPPcloud sediment signal",
        yaxis_title="Sediment discharge (tonne/yr)",
        xaxis_title="Scenario",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Lake WQ status card (plotly indicator or empty figure with text)
# ---------------------------------------------------------------------------
def lake_wq_status_card() -> go.Figure:
    anomalies = _load_csv(TABLES / "lake_wq_event_anomalies.csv")
    data_limited = True
    if anomalies is not None and "quality_flag" in anomalies.columns:
        flags = anomalies["quality_flag"].dropna().unique()
        if "PASS" in flags:
            data_limited = False

    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.7,
        text="MISSING_LOCAL_IMAGE" if data_limited else "DATA AVAILABLE",
        font=dict(size=28, color=ORANGE if data_limited else GREEN),
        showarrow=False,
    )
    fig.add_annotation(
        x=0.5, y=0.35,
        text=(
            "Lake WQ closure: local Sentinel-2 event coverage missing."
            if data_limited
            else "Lake WQ proxy anomalies available."
        ),
        font=dict(size=14, color=GREY),
        showarrow=False,
    )
    fig.update_layout(
        title="Lake WQ closure status",
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1]),
        template="plotly_white",
        height=220,
        margin=dict(t=50, b=20, l=20, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Lightweight sensitivity preview (does NOT write to official outputs)
# ---------------------------------------------------------------------------
def sensitivity_preview(
    lam: float = 0.20,
    cn_low: float = 4,
    cn_moderate: float = 8,
    cn_high: float = 12,
    rainfall_threshold: float = 1.0,
    dry_gap: int = 1,
    footprint_scenario: str = "conservative_dnbr",
) -> go.Figure | None:
    """Use existing SCS-CN equation to compute a quick preview for a few CN values."""
    # Map footprint scenario to approximate CN adjustments
    footprint_factors = {
        "conservative_dnbr": 1.0,
        "relaxed_dnbr": 1.5,
        "fire_perimeter_upper_bound": 3.0,
    }
    factor = footprint_factors.get(footprint_scenario, 1.0)

    # Use the canonical SCS-CN formula from pipeline_utils
    def scs_runoff(precip_mm, cn):
        cn = np.clip(np.asarray(cn, dtype=float), 1.0, 99.0)
        s = 25400.0 / cn - 254.0
        ia = lam * s
        p = np.asarray(precip_mm, dtype=float)
        return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - lam) * s), 0.0)

    # Representative CNs for illustration
    land_covers = ["Forest", "Shrub", "Grassland", "Agriculture", "Urban", "Bare soil"]
    baseline_cns = [60, 65, 69, 75, 88, 82]
    burned_cns = [
        min(b + (cn_low * factor), 98)  # low severity proxy
        for b in baseline_cns
    ]

    precip_range = np.linspace(10, 240, 50)
    # Use a mid-range CN for the preview curve
    base_cn = 68  # forest + HSG adjustment
    burned_cn = min(base_cn + cn_low * factor, 98)

    q_base = scs_runoff(precip_range, base_cn)
    q_burned = scs_runoff(precip_range, burned_cn)
    delta = q_burned - q_base

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=precip_range, y=delta, mode="lines",
        line=dict(color=ORANGE, width=2),
        name=f"ΔQ (base CN={base_cn}, burned CN={burned_cn:.0f})",
        hovertemplate="P=%{x:.0f} mm<br>ΔQ=%{y:.2f} mm<extra></extra>",
    ))
    fig.update_layout(
        title=f"Sensitivity preview: λ={lam:.2f}, CN adj={cn_low:.0f}/{cn_moderate:.0f}/{cn_high:.0f}, footprint={footprint_scenario}",
        xaxis_title="Rainfall depth (mm)",
        yaxis_title="Modelled ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=60, b=40, l=50, r=20),
    )
    return fig
