"""In-memory SCS-CN sensitivity preview.

The preview reads generated response units and rainfall events, calls the backend
canonical SCS-CN implementation, and never writes official output tables.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from postfire_runoff.backend.hydrology.curve_numbers import apply_burn_adjustment
from postfire_runoff.backend.hydrology.scs_cn import aggregate_response_unit_runoff, scs_runoff_mm
from postfire_runoff.frontend.components.data_loaders import RAINFALL_EVENTS, RUNOFF_UNITS, load_csv_safe


def preview_metrics(
    lam: float = 0.20,
    cn_adj_low: float = 4,
    cn_adj_moderate: float = 8,
    cn_adj_high: float = 12,
    footprint_factor: float = 1.0,
) -> dict[str, Any]:
    units = load_csv_safe(RUNOFF_UNITS)
    rain = load_csv_safe(RAINFALL_EVENTS)
    result: dict[str, Any] = {
        "preview_possible": False,
        "max_delta_q_mm": 0.0,
        "max_delta_v_m3": 0.0,
        "max_event_id": "",
        "event_count": 0,
        "unit_count": 0,
        "note": "",
    }
    if units is None or rain is None:
        result["note"] = "Missing runoff_units.csv or rainfall events; cannot preview."
        return result
    required = {"baseline_parameter", "burn_class", "area_m2"}
    if not required.issubset(units.columns):
        result["note"] = f"Runoff units missing required columns. Need: {required}"
        return result
    if "rainfall_mm" not in rain.columns:
        result["note"] = "Rainfall events missing rainfall_mm column."
        return result
    adjustments = {0: 0.0, 1: float(cn_adj_low), 2: float(cn_adj_moderate), 3: float(cn_adj_high)}
    try:
        baseline_cns = units["baseline_parameter"].astype(float).to_numpy()
        burn_classes = units["burn_class"].astype(int).to_numpy()
        burned_cns = np.array([apply_burn_adjustment(cn, cls, adjustments) for cn, cls in zip(baseline_cns, burn_classes)])
        areas = units["area_m2"].astype(float).to_numpy()
    except Exception as exc:
        result["note"] = f"Preview input error: {exc}"
        return result

    max_dq, max_dv, max_eid = 0.0, 0.0, ""
    events = rain.copy()
    events["rainfall_mm"] = pd.to_numeric(events["rainfall_mm"], errors="coerce")
    for _, event in events.dropna(subset=["rainfall_mm"]).iterrows():
        try:
            agg = aggregate_response_unit_runoff(float(event["rainfall_mm"]), baseline_cns, burned_cns, areas, lam)
        except Exception as exc:
            result["note"] = f"Preview calculation error: {exc}"
            return result
        if agg.delta_runoff_mm > max_dq:
            max_dq, max_dv = agg.delta_runoff_mm, agg.delta_volume_m3
            max_eid = str(event.get("event_id", ""))
    result.update({
        "preview_possible": True,
        "max_delta_q_mm": round(max_dq, 5),
        "max_delta_v_m3": round(max_dv, 2),
        "max_event_id": max_eid,
        "event_count": len(events),
        "unit_count": len(units),
        "note": "Preview only — official outputs are unchanged. Footprint scenarios require recomputing spatial masks, not scaling CN increments.",
    })
    return result


def preview_curve(
    lam: float = 0.20,
    cn_adj_low: float = 4,
    cn_adj_moderate: float = 8,
    cn_adj_high: float = 12,
    footprint_factor: float = 1.0,
) -> dict[str, Any] | None:
    units = load_csv_safe(RUNOFF_UNITS)
    if units is None or "baseline_parameter" not in units.columns:
        return None
    adjustments = {0: 0.0, 1: float(cn_adj_low), 2: float(cn_adj_moderate), 3: float(cn_adj_high)}
    base_cn = float(units["baseline_parameter"].median())
    burn_class_mode = int(units["burn_class"].mode().iloc[0]) if "burn_class" in units.columns and len(units) else 1
    burned = apply_burn_adjustment(base_cn, burn_class_mode, adjustments)
    p_range = np.linspace(5, 250, 100)
    q_base = scs_runoff_mm(p_range, base_cn, lam)
    q_burned = scs_runoff_mm(p_range, burned, lam)
    return {
        "p_range": p_range.tolist(),
        "delta": (q_burned - q_base).tolist(),
        "base_cn": round(base_cn, 1),
        "burned_cn": round(burned, 1),
        "lam": lam,
    }
