"""Dynamic Plotly charts built from canonical output CSVs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from postfire_runoff.frontend.components.data_loaders import (
    BURN_AREA,
    LAKE_SELECTED,
    LAKE_STATUS,
    RAINFALL_EVENTS,
    RUNOFF_DELTA,
    WEPP_SUMMARY,
    load_csv_safe,
)

BLUE = "#2b8cbe"
ORANGE = "#d95f0e"
GREEN = "#31a354"
PURPLE = "#756bb1"
RED = "#e34a33"
GREY = "#999999"


def burn_footprint_runoff_chart() -> go.Figure | None:
    delta = load_csv_safe(RUNOFF_DELTA)
    burn_area = load_csv_safe(BURN_AREA)
    if delta is None or "delta_runoff_mm" not in delta.columns:
        return None
    max_delta = float(pd.to_numeric(delta["delta_runoff_mm"], errors="coerce").max())
    burned_ha = None
    if burn_area is not None and {"burn_class", "area_ha"}.issubset(burn_area.columns):
        burned = burn_area[pd.to_numeric(burn_area["burn_class"], errors="coerce") > 0]
        burned_ha = float(pd.to_numeric(burned["area_ha"], errors="coerce").sum())
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["configured burn classification"],
        y=[max_delta],
        marker_color=[ORANGE],
        text=[f"{max_delta:.3f} mm"],
        textposition="outside",
        customdata=[burned_ha if burned_ha is not None else np.nan],
        hovertemplate="%{x}<br>Max ΔQ: %{y:.3f} mm<br>Burned area: %{customdata:.2f} ha<extra></extra>",
        name="Max ΔQ",
    ))
    fig.update_layout(
        title="Configured burn classification controls runoff-potential response",
        yaxis_title="Max modelled runoff-potential ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=380,
    )
    return fig


def burn_footprint_area_chart() -> go.Figure | None:
    area = load_csv_safe(BURN_AREA)
    if area is None or not {"burn_label", "area_ha"}.issubset(area.columns):
        return None
    colors = {"unburned": GREY, "low": BLUE, "moderate": ORANGE, "high": RED}
    labels = area["burn_label"].astype(str).tolist()
    areas = pd.to_numeric(area["area_ha"], errors="coerce").fillna(0).tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=areas,
        marker_color=[colors.get(label, PURPLE) for label in labels],
        text=[f"{a:.2f} ha" for a in areas],
        textposition="outside",
        name="Area",
    ))
    fig.update_layout(
        title="Burn-severity area from generated response units",
        yaxis_title="Area (ha)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=350,
    )
    return fig


def event_rainfall_scatter_chart(highlight_event: str | None = None) -> go.Figure | None:
    delta = load_csv_safe(RUNOFF_DELTA)
    if delta is None:
        return None
    x_col = "rainfall_mm" if "rainfall_mm" in delta.columns else None
    y_col = "delta_runoff_mm" if "delta_runoff_mm" in delta.columns else None
    if x_col is None or y_col is None:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=delta[x_col],
        y=delta[y_col],
        mode="markers",
        marker=dict(color=BLUE, size=8, line=dict(color="white", width=0.5)),
        text=delta.get("event_id", ""),
        hovertemplate="%{text}<br>P=%{x:.1f} mm<br>ΔQ=%{y:.4f} mm<extra></extra>",
        name="All events",
    ))
    if highlight_event and "event_id" in delta.columns and highlight_event in delta["event_id"].values:
        sel = delta[delta["event_id"] == highlight_event]
        fig.add_trace(go.Scatter(
            x=sel[x_col], y=sel[y_col], mode="markers",
            marker=dict(color=ORANGE, size=14, symbol="diamond", line=dict(color="black", width=1)),
            name=str(highlight_event),
            hovertemplate=f"{highlight_event}<br>P=%{{x:.1f}} mm<br>ΔQ=%{{y:.4f}} mm<extra></extra>",
        ))
    fig.update_layout(
        title="Rainfall events vs modelled runoff change",
        xaxis_title="Event rainfall depth (mm)",
        yaxis_title="Modelled ΔQ (mm)",
        template="plotly_white",
        margin=dict(t=50, b=40, l=50, r=20),
        height=380,
    )
    return fig


def event_delta_cdf_chart() -> go.Figure | None:
    delta = load_csv_safe(RUNOFF_DELTA)
    if delta is None or "delta_runoff_mm" not in delta.columns:
        return None
    vals = pd.to_numeric(delta["delta_runoff_mm"], errors="coerce").dropna().sort_values().values
    if len(vals) < 2:
        return None
    cdf = np.arange(1, len(vals) + 1) / len(vals)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=vals, y=cdf, mode="lines", line=dict(color=BLUE, width=2.5), name="Empirical CDF"))
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


def weppcloud_sediment_chart() -> go.Figure | None:
    wepp = load_csv_safe(WEPP_SUMMARY)
    if wepp is None or not {"scenario", "sediment_quantity"}.issubset(wepp.columns):
        return None
    y = pd.to_numeric(wepp["sediment_quantity"], errors="coerce")
    if y.dropna().empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=wepp["scenario"].astype(str),
        y=y,
        marker_color=[GREY, ORANGE, BLUE, PURPLE][: len(wepp)],
        text=[f"{v:.2f}" if np.isfinite(v) else "N/A" for v in y],
        textposition="outside",
        hovertemplate="%{x}: %{y:.2f}<extra></extra>",
    ))
    units = str(wepp["sediment_units"].iloc[0]) if "sediment_units" in wepp.columns and len(wepp) else "reported units"
    fig.update_layout(
        title="WEPPcloud sediment signal (imported external export, not SCS-CN validation)",
        yaxis_title=f"Sediment ({units})",
        template="plotly_white",
        margin=dict(t=60, b=40, l=50, r=20),
        height=380,
    )
    return fig


def lake_wq_status_figure() -> go.Figure:
    status = load_csv_safe(LAKE_STATUS)
    data_limited = True
    message = "Run optional lake stage after configuring local imagery"
    if status is not None:
        row = status.iloc[0]
        data_limited = str(row.get("status", "missing_input")) != "available"
        message = str(row.get("message", message))
    fig = go.Figure()
    fig.add_annotation(
        x=0.5,
        y=0.72,
        text="UNAVAILABLE" if data_limited else "DATA AVAILABLE",
        font=dict(size=26, color=ORANGE if data_limited else GREEN, family="Arial Black"),
        showarrow=False,
    )
    fig.add_annotation(x=0.5, y=0.42, text=message[:160], font=dict(size=12, color=GREY), showarrow=False)
    fig.add_annotation(
        x=0.5,
        y=0.20,
        text="NDTI/NDCI are optical proxies only; no numeric anomalies are emitted without valid pre/post imagery.",
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
    selected = load_csv_safe(LAKE_SELECTED)
    if selected is None:
        return None
    cols = ["event_id", "pre_products_found", "post_products_found", "usable_pair", "status"]
    available = [c for c in cols if c in selected.columns]
    return selected[available] if available else selected
