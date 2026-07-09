"""SCS-CN runoff equation — single source of truth.

S = 25400/CN - 254
Ia = lambda * S
Q = 0                          if P <= Ia
Q = (P - Ia)^2 / (P + (1-lambda)*S)   if P > Ia

Units: P in mm, Q in mm. CN is dimensionless, clamped to [1, 99].
"""
from __future__ import annotations

import numpy as np


def scs_runoff_mm(
    precip_mm: np.ndarray | float,
    curve_number: np.ndarray | float,
    initial_abstraction_ratio: float = 0.20,
) -> np.ndarray:
    if initial_abstraction_ratio <= 0:
        raise ValueError("Initial abstraction ratio must be positive")

    cn = np.clip(np.asarray(curve_number, dtype=float), 1.0, 99.0)
    s = 25400.0 / cn - 254.0
    ia = initial_abstraction_ratio * s
    p = np.asarray(precip_mm, dtype=float)

    # Check for negative rainfall
    if (p < 0).any():
        raise ValueError("Rainfall values must not be negative")

    return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - initial_abstraction_ratio) * s), 0.0)


def burned_cn(
    baseline_cn: float,
    burn_class: int,
    adjustments: dict[int, float] | None = None,
) -> float:
    """Apply burn severity curve number adjustment. CN is clamped at 98."""
    if adjustments is None:
        adjustments = {0: 0, 1: 4, 2: 8, 3: 12}
    if int(burn_class) not in adjustments:
        raise ValueError(f"Unknown burn class: {burn_class}. Known: {list(adjustments)}")
    return min(baseline_cn + adjustments[int(burn_class)], 98.0)
