"""Lightweight SCS-CN sensitivity preview — reads existing outputs, applies
parameter changes in-memory only. Never writes to official output tables."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from geoproject.webapp.components.data_loaders import load_csv_safe, RUNOFF_UNITS, RAINFALL_EVENTS, RUNOFF_DELTA


def scs_runoff(precip_mm: np.ndarray, cn: np.ndarray, lam: float = 0.20) -> np.ndarray:
    """Canonical SCS-CN runoff equation. Vectorized."""
    cn = np.clip(np.asarray(cn, dtype=float), 1.0, 99.0)
    s = 25400.0 / cn - 254.0
    ia = lam * s
    p = np.asarray(precip_mm, dtype=float)
    return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - lam) * s), 0.0)


def preview_metrics(
    lam: float = 0.20,
    cn_adj_low: float = 4,
    cn_adj_moderate: float = 8,
    cn_adj_high: float = 12,
    footprint_factor: float = 1.0,
) -> dict[str, Any]:
    """Compute preview max ΔQ and ΔV from existing response units and rainfall events."""

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

    p_col = "total_precip_mm"
    if p_col not in rain.columns:
        result["note"] = "Rainfall events missing total_precip_mm column."
        return result

    events = rain.copy()
    events[p_col] = pd.to_numeric(events[p_col], errors="coerce")

    # Build CN adjustment map
    cn_adj_map = {0: 0, 1: cn_adj_low * footprint_factor, 2: cn_adj_moderate * footprint_factor, 3: cn_adj_high * footprint_factor}

    total_area = float(units["area_m2"].sum())
    if total_area <= 0:
        result["note"] = "Zero total response unit area."
        return result

    # Per-unit baseline and burned CN
    baseline_cns = units["baseline_parameter"].astype(float).values
    burn_classes = units["burn_class"].astype(int).values
    areas = units["area_m2"].astype(float).values
    burned_cns = np.array([
        min(b + cn_adj_map.get(int(bc), 0), 98.0)
        for b, bc in zip(baseline_cns, burn_classes)
    ])

    max_dq, max_dv, max_eid = 0.0, 0.0, ""
    for _, event in events.iterrows():
        p = float(event[p_col])
        if p <= 0 or np.isnan(p):
            continue
        q_base = scs_runoff(p, baseline_cns, lam)
        q_burned = scs_runoff(p, burned_cns, lam)
        dq_per_unit = q_burned - q_base
        dq_weighted = np.sum(dq_per_unit * areas) / total_area if total_area > 0 else 0.0
        dv = np.sum(dq_per_unit * areas) / 1000.0  # mm * m2 → m3
        if dq_weighted > max_dq:
            max_dq, max_dv = dq_weighted, dv
            max_eid = str(event.get("event_id", ""))

    result["preview_possible"] = True
    result["max_delta_q_mm"] = round(max_dq, 5)
    result["max_delta_v_m3"] = round(max_dv, 2)
    result["max_event_id"] = max_eid
    result["event_count"] = len(events)
    result["unit_count"] = len(units)
    result["note"] = "Preview only — not an official result. Click Run Model for full recomputation."

    return result


def preview_curve(
    lam: float = 0.20,
    cn_adj_low: float = 4,
    cn_adj_moderate: float = 8,
    cn_adj_high: float = 12,
    footprint_factor: float = 1.0,
) -> dict[str, Any] | None:
    """Generate a preview ΔQ curve over a range of precipitation depths."""

    units = load_csv_safe(RUNOFF_UNITS)
    if units is None:
        return None

    cn_adj_map = {0: 0, 1: cn_adj_low * footprint_factor, 2: cn_adj_moderate * footprint_factor, 3: cn_adj_high * footprint_factor}

    # Use median baseline CN from units
    base_cn = float(units["baseline_parameter"].median())
    burn_class_mode = int(units["burn_class"].mode().iloc[0]) if "burn_class" in units.columns and len(units) > 0 else 1
    burned_cn = min(base_cn + cn_adj_map.get(burn_class_mode, cn_adj_low * footprint_factor), 98.0)

    p_range = np.linspace(5, 250, 100)
    q_base = scs_runoff(p_range, base_cn, lam)
    q_burned = scs_runoff(p_range, burned_cn, lam)
    delta = q_burned - q_base

    return {
        "p_range": p_range.tolist(),
        "delta": delta.tolist(),
        "base_cn": round(base_cn, 1),
        "burned_cn": round(burned_cn, 1),
        "lam": lam,
    }
