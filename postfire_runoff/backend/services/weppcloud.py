"""WEPPcloud export normalizer for user-supplied comparison tables."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

WEPP_REQUIRED_COLUMNS = (
    "scenario",
    "period",
    "modeled_area",
    "modeled_area_units",
    "runoff_quantity",
    "runoff_units",
    "sediment_quantity",
    "sediment_units",
    "source_filename",
)


def validate_weppcloud_columns(columns: list[str]) -> list[str]:
    lower = {c.lower() for c in columns}
    return [c for c in WEPP_REQUIRED_COLUMNS if c not in lower]


def import_weppcloud_export(input_csv: Path, output_csv: Path) -> Path:
    if not input_csv.exists():
        raise FileNotFoundError(f"WEPPcloud export not found: {input_csv}")
    df = pd.read_csv(input_csv)
    missing = validate_weppcloud_columns(list(df.columns))
    if missing:
        raise ValueError(f"WEPPcloud export missing required columns: {', '.join(missing)}")
    lower = {c.lower(): c for c in df.columns}
    normalized = pd.DataFrame({name: df[lower[name]] for name in WEPP_REQUIRED_COLUMNS})
    for numeric_col in ("modeled_area", "runoff_quantity", "sediment_quantity"):
        normalized[numeric_col] = pd.to_numeric(normalized[numeric_col], errors="raise")
    normalized["source_role"] = "user_exported_weppcloud_result"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_csv, index=False)
    return output_csv
