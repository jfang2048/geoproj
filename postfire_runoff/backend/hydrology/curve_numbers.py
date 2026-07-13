"""Hydrologic land-cover/HSG curve-number mapping."""
from __future__ import annotations

from typing import Mapping

from postfire_runoff.backend.hydrology.scs_cn import burned_cn

# Screening-level AMC-II CN table adapted from common NRCS TR-55 hydrologic
# soil-cover examples. Local projects should review the selected hydrologic
# condition before interpreting case-study results.
DEFAULT_CN2_TABLE: dict[str, dict[str, float]] = {
    "forest": {"A": 30, "B": 55, "C": 70, "D": 77},
    "shrub": {"A": 35, "B": 56, "C": 70, "D": 77},
    "grassland": {"A": 39, "B": 61, "C": 74, "D": 80},
    "agriculture": {"A": 67, "B": 78, "C": 85, "D": 89},
    "urban": {"A": 77, "B": 85, "C": 90, "D": 92},
    "bare_soil": {"A": 77, "B": 86, "C": 91, "D": 94},
    "water": {"A": 98, "B": 98, "C": 98, "D": 98},
    "other": {"A": 49, "B": 69, "C": 79, "D": 84},
}

LANDCOVER_ALIASES = {
    "woods": "forest",
    "woodland": "forest",
    "conifer": "forest",
    "broadleaf": "forest",
    "scrub": "shrub",
    "brush": "shrub",
    "pasture": "grassland",
    "meadow": "grassland",
    "crop": "agriculture",
    "cropland": "agriculture",
    "farmland": "agriculture",
    "built": "urban",
    "built_up": "urban",
    "impervious": "urban",
    "bare": "bare_soil",
    "bare_soil": "bare_soil",
    "open_water": "water",
}

SUPPORTED_LANDCOVER = tuple(DEFAULT_CN2_TABLE.keys())


def normalize_label(value: object) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def normalize_landcover(value: object, aliases: Mapping[str, str] | None = None) -> str:
    label = normalize_label(value)
    lookup = dict(LANDCOVER_ALIASES)
    if aliases:
        lookup.update({normalize_label(k): normalize_label(v) for k, v in aliases.items()})
    label = lookup.get(label, label)
    if label not in DEFAULT_CN2_TABLE:
        accepted = ", ".join(SUPPORTED_LANDCOVER)
        raise ValueError(f"Unknown land-cover label {value!r}. Supported classes: {accepted}")
    return label


def normalize_hsg(value: object) -> str:
    label = str(value).strip().upper()[:1]
    if label not in {"A", "B", "C", "D"}:
        raise ValueError(f"Invalid hydrologic soil group: {value!r}")
    return label


def lookup_curve_number(
    landcover_class: object,
    hsg: object,
    table: Mapping[str, Mapping[str, float]] | None = None,
    landcover_aliases: Mapping[str, str] | None = None,
) -> float:
    lookup = table or DEFAULT_CN2_TABLE
    lc = normalize_landcover(landcover_class, landcover_aliases)
    soil = normalize_hsg(hsg)
    if lc not in lookup or soil not in lookup[lc]:
        raise ValueError(f"No CN lookup entry for land cover={lc!r}, HSG={soil!r}")
    return float(lookup[lc][soil])


def apply_burn_adjustment(
    baseline_cn: float,
    burn_class: int,
    adjustments: Mapping[int | str, float] | None = None,
) -> float:
    normalized = None
    if adjustments is not None:
        normalized = {int(k): float(v) for k, v in adjustments.items()}
    return burned_cn(baseline_cn, int(burn_class), normalized)
