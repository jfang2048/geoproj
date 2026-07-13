"""Small display formatting helpers for Streamlit pages."""
from __future__ import annotations

import pandas as pd


def fmt_number(value, pattern: str, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"{float(value):{pattern}}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def fmt_int(value) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return str(int(value))
    except (TypeError, ValueError):
        return "N/A"


def metric_delta(value, pattern: str, suffix: str = "") -> str | None:
    formatted = fmt_number(value, pattern, suffix)
    return None if formatted == "N/A" else formatted
