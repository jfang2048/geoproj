"""Dynamic Plotly charts built directly from project CSV outputs."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from postfire_runoff.webapp.components.data_loaders import (
    load_csv_safe, RAINFALL_EVENTS, RUNOFF_DELTA, BURN_ENSEMBLE,
    LAKE_ANOMALIES, LAKE_SELECTED,
)

BLUE = "#2b8cbe"
ORANGE = "#d95f0e"
GREEN = "#31a354"
PURPLE = "#756bb1"
RED = "#e34a33"
GREY = "#999999"
LIGHT_BLUE = "#a6cee3"


# ── Chart A: Burn footprint vs max runoff delta ─────────────────────────
def burn_footprint_runoff_chart() -> go.Figure | None:
    ens = load_csv_safe(BURN_ENSEMBLE)
    if ens is None:
        return None

    scenario_col = next((c for c in ens.columns if "scenario" in c.lower()), ens.columns[0])
    area_col = next((c for c in ens.columns if "area" in c.lower() and "ha" in c.lower()), None)
    runoff_col = next((c for c in ens.columns if "runoff" in c.lower() and "max" in c.lower()), None)

    if area_col is None or runoff_col is None:
        return None

    labels = ens[scenario_col].str.replace("_", " ").tolist()
    areas = ens[area_col].tolist()
    runoffs = ens[runoff_col].tolist()

    colors = [BLUE, ORANGE, PURPLE, GREY][:len(ens)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=runoffs,
        marker_color=colors,
        text=[f"{r:.3f} mm" for r in runoffs],
        textposition="outside",
        hovertemplate="%{x}<br>Max ΔQ: %{y:.3f} mm<br>Burned area: %{customdata:.1f} ha<extra></extra>",
        customdata=areas,
        name="Max ΔQ",
    ))
    fig.update_layout(
        title="Burn footprint controls runoff-potential response",
        yaxis_title="Max modelled runoff-potential ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=380,
    )
    return fig


def burn_footprint_area_chart() -> go.Figure | None:
    """Companion chart: burned area by scenario."""
    ens = load_csv_safe(BURN_ENSEMBLE)
    if ens is None:
        return None

    scenario_col = next((c for c in ens.columns if "scenario" in c.lower()), ens.columns[0])
    area_col = next((c for c in ens.columns if "area" in c.lower() and "ha" in c.lower()), None)
    if area_col is None:
        return None

    labels = ens[scenario_col].str.replace("_", " ").tolist()
    areas = ens[area_col].tolist()
    colors = [BLUE, ORANGE, PURPLE, GREY][:len(ens)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=areas,
        marker_color=colors,
        text=[f"{a:.1f} ha" for a in areas],
        textposition="outside",
        name="Burned area",
    ))
    fig.update_layout(
        title="Burned-footprint scenario area hierarchy",
        yaxis_title="Burned area (ha)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=350,
    )
    return fig


# ── Chart B: Rainfall event depth vs modelled ΔQ ────────────────────────
def event_rainfall_scatter_chart(highlight_event: str | None = None) -> go.Figure | None:
    delta = load_csv_safe(RUNOFF_DELTA)
    rain = load_csv_safe(RAINFALL_EVENTS)
    if delta is None:
        return None

    # Join rainfall if available
    if rain is not None:
        start_c = next((c for c in rain.columns if c in ("start_date", "event_start")), None)
        merged = rain.merge(delta, on="event_id", how="inner") if "event_id" in rain.columns else delta.copy()
    else:
        merged = delta.copy()

    x_col = "total_precip_mm" if "total_precip_mm" in merged.columns else None
    y_col = "delta_runoff_mm" if "delta_runoff_mm" in merged.columns else None
    if x_col is None or y_col is None:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged[x_col], y=merged[y_col],
        mode="markers",
        marker=dict(color=BLUE, size=8, line=dict(color="white", width=0.5)),
        text=merged.get("event_id", ""),
        hovertemplate="%{text}<br>P=%{x:.1f} mm<br>ΔQ=%{y:.4f} mm<extra></extra>",
        name="All events",
    ))

    if highlight_event and "event_id" in merged.columns and highlight_event in merged["event_id"].values:
        sel = merged[merged["event_id"] == highlight_event]
        fig.add_trace(go.Scatter(
            x=sel[x_col], y=sel[y_col],
            mode="markers",
            marker=dict(color=ORANGE, size=14, symbol="diamond", line=dict(color="black", width=1)),
            name=str(highlight_event),
            hovertemplate=f"{highlight_event}<br>P=%{{x:.1f}} mm<br>ΔQ=%{{y:.4f}} mm<extra></extra>",
        ))

    fig.update_layout(
        title="Observed rainfall events vs modelled runoff change",
        xaxis_title="Event rainfall depth (mm)",
        yaxis_title="Modelled ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=380,
    )
    return fig


# ── Chart C: Event-scale delta runoff CDF ────────────────────────────────
def event_delta_cdf_chart() -> go.Figure | None:
    delta = load_csv_safe(RUNOFF_DELTA)
    if delta is None:
        return None
    y_col = "delta_runoff_mm"
    if y_col not in delta.columns:
        return None

    vals = delta[y_col].dropna().sort_values().values
    if len(vals) < 2:
        return None
    cdf = np.arange(1, len(vals) + 1) / len(vals)

    # Ensemble max markers for context
    ens = load_csv_safe(BURN_ENSEMBLE)
    markers = []
    if ens is not None:
        sc = next((c for c in ens.columns if "scenario" in c.lower()), None)
        rc = next((c for c in ens.columns if "runoff" in c.lower() and "max" in c.lower()), None)
        if sc and rc:
            for _, row in ens.iterrows():
                markers.append((str(row[sc]).replace("_", " "), float(row[rc])))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=vals, y=cdf, mode="lines",
        line=dict(color=BLUE, width=2.5),
        name="Empirical CDF",
    ))
    marker_colors = [ORANGE, GREEN, PURPLE]
    for i, (label, mx) in enumerate(markers[:3]):
        fig.add_trace(go.Scatter(
            x=[mx, mx], y=[0, 1], mode="lines",
            line=dict(color=marker_colors[i % len(marker_colors)], dash="dash", width=1.5),
            name=f"{label} max",
        ))

    below_005 = (vals < 0.05).sum() / len(vals) * 100
    fig.update_layout(
        title=f"Distribution of event-scale runoff-potential change ({below_005:.0f}% events below 0.05 mm)",
        xaxis_title="Event ΔQ (mm)",
        yaxis_title="Cumulative fraction",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=380,
    )
    return fig


# ── Chart D: WEPPcloud sediment benchmark ────────────────────────────────
def weppcloud_sediment_chart() -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Undisturbed", "Disturbed"],
        y=[293.0, 652.6],
        marker_color=[GREY, ORANGE],
        text=["293.0", "652.6"],
        textposition="outside",
        hovertemplate="%{x}: %{y:.1f} tonne/yr<extra></extra>",
    ))
    fig.add_annotation(
        x=1, y=680,
        text="+122.7%",
        showarrow=False,
        font=dict(size=16, color=RED, family="Arial Black"),
    )
    fig.update_layout(
        title="WEPPcloud sediment signal (independent benchmark, not SCS-CN validation)",
        yaxis_title="Sediment discharge (tonne/yr)",
        template="plotly_white",
        margin=dict(t=60, b=40, l=50, r=20),
        height=380,
    )
    return fig


# ── Chart E: Lake WQ status ──────────────────────────────────────────────
def lake_wq_status_figure() -> go.Figure:
    anomalies = load_csv_safe(LAKE_ANOMALIES)
    selected = load_csv_safe(LAKE_SELECTED)

    data_limited = True
    event_count = 0
    if anomalies is not None and "quality_flag" in anomalies.columns:
        flags = set(anomalies["quality_flag"].dropna())
        data_limited = "MISSING_LOCAL_IMAGE" in flags or "PASS" not in flags
        event_count = anomalies["event_id"].nunique() if "event_id" in anomalies.columns else 0

    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.78,
        text="MISSING LOCAL IMAGE" if data_limited else "DATA AVAILABLE",
        font=dict(size=26, color=ORANGE if data_limited else GREEN, family="Arial Black"),
        showarrow=False,
    )
    fig.add_annotation(
        x=0.5, y=0.50,
        text=(
            f"{event_count} events | Local Sentinel-2 scenes do not cover selected event windows"
            if data_limited
            else f"{event_count} events with numeric proxy anomalies"
        ),
        font=dict(size=12, color=GREY),
        showarrow=False,
    )
    fig.add_annotation(
        x=0.5, y=0.28,
        text="Python-only workflow | Local Sentinel-2 inputs | Screening-level only",
        font=dict(size=10, color=GREY),
        showarrow=False,
    )
    fig.update_layout(
        title="Lake WQ closure status",
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1]),
        template="plotly_white",
        height=250,
        margin=dict(t=50, b=20, l=20, r=20),
    )
    return fig


def lake_wq_event_table() -> pd.DataFrame | None:
    """Return selected events table for display."""
    selected = load_csv_safe(LAKE_SELECTED)
    if selected is None:
        return None
    cols = ["event_id", "event_start", "event_end", "total_precip_mm", "delta_volume_m3", "selection_rank"]
    available = [c for c in cols if c in selected.columns]
    return selected[available] if available else selected
