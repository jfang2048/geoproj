"""Small I/O helpers for the Python-only lake WQ workflow."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Mapping, Any

import pandas as pd

from lake_wq.config import (
    ROOT,
    SELECTED_EVENTS_PATH,
    QA_SPATIAL_PATH,
    QA_OUTPUTS_PATH,
    QA_COLUMNS,
    INTERMEDIATE_DIR,
    TABLES_DIR,
    RASTER_METADATA_QA_PATH,
    RASTER_QA_COLUMNS,
)
from pipeline_utils import ensure_workspace, register_generated_dataset, WORKING_CRS


def ensure_lake_wq_dirs() -> None:
    ensure_workspace()
    for path in [INTERMEDIATE_DIR, TABLES_DIR, QA_SPATIAL_PATH.parent, QA_OUTPUTS_PATH.parent, RASTER_METADATA_QA_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)


def read_csv_required(path: Path, label: str | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing required {label or 'CSV'}: {path.relative_to(ROOT)}")
    return pd.read_csv(path)


def load_selected_events() -> pd.DataFrame:
    df = read_csv_required(SELECTED_EVENTS_PATH, "selected lake response events")
    required = {"event_id", "event_start", "event_end"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Selected event table missing required columns: {sorted(missing)}")
    return df.copy()


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for col in columns:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[columns]
    df.to_csv(path, index=False)


def write_remote_sensing_qa(qa: pd.DataFrame) -> None:
    for col in QA_COLUMNS:
        if col not in qa.columns:
            qa[col] = pd.NA
    qa = qa[QA_COLUMNS]
    QA_SPATIAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    QA_OUTPUTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    qa.to_csv(QA_SPATIAL_PATH, index=False)
    shutil.copyfile(QA_SPATIAL_PATH, QA_OUTPUTS_PATH)
    register_generated_dataset(
        "lake_wq_remote_sensing_qa",
        "Lake water-quality remote-sensing QA",
        "lake_water_quality_remote_sensing_qa",
        QA_SPATIAL_PATH,
        "processed",
        crs="n/a",
        notes="Python-only Sentinel-2 L2A SAFE availability and valid-pixel QA; no GEE fallback.",
    )


def append_raster_metadata_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    if RASTER_METADATA_QA_PATH.exists() and RASTER_METADATA_QA_PATH.stat().st_size > 0:
        existing = pd.read_csv(RASTER_METADATA_QA_PATH)
        out = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    else:
        out = pd.DataFrame(rows)
    for col in RASTER_QA_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out.drop_duplicates(subset=["path"], keep="last")
    write_csv(RASTER_METADATA_QA_PATH, out, RASTER_QA_COLUMNS)


def clear_raster_metadata_qa() -> None:
    write_csv(RASTER_METADATA_QA_PATH, pd.DataFrame(columns=RASTER_QA_COLUMNS), RASTER_QA_COLUMNS)


def raster_metadata_row(path: Path, event_id: str, index_name: str, image_role: str) -> dict[str, Any]:
    import numpy as np
    import rasterio

    with rasterio.open(path) as ds:
        arr = ds.read(1, masked=True)
        vals = arr.compressed()
        bounds = ds.bounds
        return {
            "path": str(path.relative_to(ROOT)),
            "event_id": event_id,
            "index_name": index_name,
            "image_role": image_role,
            "crs": ds.crs.to_string() if ds.crs else "",
            "bounds": f"{bounds.left:.3f},{bounds.bottom:.3f},{bounds.right:.3f},{bounds.top:.3f}",
            "resolution_x": abs(ds.transform.a),
            "resolution_y": abs(ds.transform.e),
            "transform": tuple(round(v, 9) for v in ds.transform[:6]),
            "width": ds.width,
            "height": ds.height,
            "nodata": ds.nodata,
            "dtype": ds.dtypes[0],
            "valid_pixel_count": int(vals.size),
            "min": float(vals.min()) if vals.size else "",
            "max": float(vals.max()) if vals.size else "",
            "mean": float(vals.mean()) if vals.size else "",
        }
