"""SCS-CN runoff calculation.

For rainfall depth ``P`` in millimetres and curve number ``CN``::

    S = 25400 / CN - 254
    Ia = lambda * S
    Q = 0                                        when P <= Ia
    Q = (P - Ia)^2 / (P + (1 - lambda) * S)     when P > Ia

Response-unit aggregation uses area weighting in square metres. This module is
the single implementation used by the pipeline and the Streamlit parameter
preview.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

CN_MIN = 1.0
CN_MAX = 98.0


def _as_float_array(value: np.ndarray | float | Iterable[float], label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} must contain only finite numeric values")
    return arr


def validate_initial_abstraction(initial_abstraction_ratio: float) -> float:
    lam = float(initial_abstraction_ratio)
    if not np.isfinite(lam) or not (0.0 < lam < 1.0):
        raise ValueError("Initial abstraction ratio must satisfy 0 < lambda < 1")
    return lam


def scs_runoff_mm(
    precip_mm: np.ndarray | float | Iterable[float],
    curve_number: np.ndarray | float | Iterable[float],
    initial_abstraction_ratio: float = 0.20,
) -> np.ndarray:
    """Return SCS-CN direct runoff depth in millimetres.

    Rainfall must be non-negative and finite. Curve numbers must already be
    valid for this project (1 <= CN <= 98); invalid inputs are rejected rather
    than silently clamped.
    """
    lam = validate_initial_abstraction(initial_abstraction_ratio)
    p = _as_float_array(precip_mm, "Rainfall")
    if np.any(p < 0):
        raise ValueError("Rainfall values must not be negative")

    cn = _as_float_array(curve_number, "Curve number")
    if np.any((cn < CN_MIN) | (cn > CN_MAX)):
        raise ValueError(f"Curve numbers must be within [{CN_MIN:g}, {CN_MAX:g}]")

    s = 25400.0 / cn - 254.0
    ia = lam * s
    return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - lam) * s), 0.0)


def burned_cn(
    baseline_cn: float,
    burn_class: int,
    adjustments: dict[int, float] | None = None,
    max_cn: float = CN_MAX,
) -> float:
    """Apply a configured burn-severity CN increment to one response unit."""
    if adjustments is None:
        adjustments = {0: 0.0, 1: 4.0, 2: 8.0, 3: 12.0}
    cn = float(baseline_cn)
    if not np.isfinite(cn) or not (CN_MIN <= cn <= CN_MAX):
        raise ValueError(f"Baseline CN must be within [{CN_MIN:g}, {CN_MAX:g}]")
    cls = int(burn_class)
    if cls not in adjustments:
        raise ValueError(f"Unknown burn class: {burn_class}. Known classes: {sorted(adjustments)}")
    inc = float(adjustments[cls])
    if not np.isfinite(inc) or inc < 0:
        raise ValueError("Burn CN adjustments must be finite and non-negative")
    return min(cn + inc, float(max_cn))


@dataclass(frozen=True)
class AggregatedRunoff:
    baseline_runoff_mm: float
    burned_runoff_mm: float
    delta_runoff_mm: float
    baseline_volume_m3: float
    burned_volume_m3: float
    delta_volume_m3: float
    area_m2: float


def aggregate_response_unit_runoff(
    rainfall_mm: float,
    baseline_curve_numbers: np.ndarray | Iterable[float],
    burned_curve_numbers: np.ndarray | Iterable[float],
    areas_m2: np.ndarray | Iterable[float],
    initial_abstraction_ratio: float = 0.20,
) -> AggregatedRunoff:
    """Area-weight response-unit runoff depths and volumes for one event."""
    areas = _as_float_array(areas_m2, "Response-unit area")
    if np.any(areas <= 0):
        raise ValueError("Response-unit areas must be positive")
    area_total = float(np.sum(areas))
    q_base = scs_runoff_mm(float(rainfall_mm), baseline_curve_numbers, initial_abstraction_ratio)
    q_burn = scs_runoff_mm(float(rainfall_mm), burned_curve_numbers, initial_abstraction_ratio)
    base_depth = float(np.sum(q_base * areas) / area_total)
    burn_depth = float(np.sum(q_burn * areas) / area_total)
    base_vol = float(np.sum((q_base / 1000.0) * areas))
    burn_vol = float(np.sum((q_burn / 1000.0) * areas))
    return AggregatedRunoff(
        baseline_runoff_mm=base_depth,
        burned_runoff_mm=burn_depth,
        delta_runoff_mm=burn_depth - base_depth,
        baseline_volume_m3=base_vol,
        burned_volume_m3=burn_vol,
        delta_volume_m3=burn_vol - base_vol,
        area_m2=area_total,
    )
