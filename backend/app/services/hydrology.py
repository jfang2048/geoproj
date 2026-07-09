"""Screening-level SCS-CN runoff calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd

CN_LOOKUP_SOURCE = (
    "Screening lookup adapted from USDA NRCS TR-55 curve-number tables; "
    "classes are simplified to local upload categories and must be replaced for calibrated work."
)
HSG_MAPPING_SOURCE = "Hydrologic soil group values must be A, B, C, or D, or raster codes 1=A, 2=B, 3=C, 4=D."
BURN_ADJUSTMENT_SOURCE = "Screening burn adjustment: unburned +0, low +4, moderate +8, high +12 CN points."

CN_TABLE: dict[str, dict[str, float]] = {
    "forest": {"A": 30, "B": 55, "C": 70, "D": 77},
    "shrub": {"A": 35, "B": 56, "C": 70, "D": 77},
    "grassland": {"A": 49, "B": 69, "C": 79, "D": 84},
    "agriculture": {"A": 67, "B": 78, "C": 85, "D": 89},
    "urban": {"A": 77, "B": 85, "C": 90, "D": 92},
    "bare_soil": {"A": 77, "B": 86, "C": 91, "D": 94},
    "water": {"A": 98, "B": 98, "C": 98, "D": 98},
    "other": {"A": 68, "B": 79, "C": 86, "D": 89},
}

BURN_ADJUSTMENT = {0: 0.0, 1: 4.0, 2: 8.0, 3: 12.0}
LANDCOVER_CODE_MAP = {
    1: "forest",
    2: "shrub",
    3: "grassland",
    4: "agriculture",
    5: "urban",
    6: "bare_soil",
    7: "water",
}
HSG_CODE_MAP = {1: "A", 2: "B", 3: "C", 4: "D"}
BURN_CLASS_NAME = {0: "unburned", 1: "low", 2: "moderate", 3: "high"}


def scs_runoff_mm(precip_mm, curve_number, lam: float = 0.20):
    """Return SCS-CN runoff depth in millimetres.

    CN is clamped to [1, 99]. Zero rainfall and rainfall below initial
    abstraction return zero runoff.
    """
    cn = np.clip(np.asarray(curve_number, dtype=float), 1.0, 99.0)
    p = np.asarray(precip_mm, dtype=float)
    s = 25400.0 / cn - 254.0
    ia = lam * s
    return np.where(p > ia, (p - ia) ** 2 / (p + (1.0 - lam) * s), 0.0)


def normalize_landcover(value) -> str:
    if pd.isna(value):
        return "other"
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        return LANDCOVER_CODE_MAP.get(int(value), "other")
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "woodland": "forest",
        "woods": "forest",
        "scrub": "shrub",
        "grass": "grassland",
        "pasture": "grassland",
        "crop": "agriculture",
        "cropland": "agriculture",
        "built": "urban",
        "built_up": "urban",
        "bare": "bare_soil",
        "soil": "bare_soil",
        "open_water": "water",
    }
    return aliases.get(text, text if text in CN_TABLE else "other")


def normalize_hsg(value) -> str:
    if pd.isna(value):
        return "C"
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        return HSG_CODE_MAP.get(int(value), "C")
    text = str(value).strip().upper()
    return text if text in {"A", "B", "C", "D"} else "C"


def normalize_burn_class(value) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        ivalue = int(value)
        return ivalue if ivalue in BURN_ADJUSTMENT else 0
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "none": 0,
        "unburned": 0,
        "no_burn": 0,
        "low": 1,
        "moderate": 2,
        "medium": 2,
        "high": 3,
        "severe": 3,
    }
    return aliases.get(text, 0)


def classify_dnbr(value: float) -> int:
    if value <= 0.10:
        return 0
    if value <= 0.27:
        return 1
    if value <= 0.66:
        return 2
    return 3


def baseline_cn(landcover: str, hsg: str) -> float:
    landcover_key = normalize_landcover(landcover)
    hsg_key = normalize_hsg(hsg)
    return float(CN_TABLE.get(landcover_key, CN_TABLE["other"])[hsg_key])


def burned_cn(base_cn: float, burn_class: int) -> float:
    return float(np.clip(base_cn + BURN_ADJUSTMENT.get(int(burn_class), 0.0), 1.0, 98.0))


def parameter_sources() -> dict[str, str]:
    return {
        "cn_lookup_source": CN_LOOKUP_SOURCE,
        "hsg_mapping_source": HSG_MAPPING_SOURCE,
        "burn_adjustment_source": BURN_ADJUSTMENT_SOURCE,
        "initial_abstraction_ratio": "0.20 unless changed by run parameter.",
    }
