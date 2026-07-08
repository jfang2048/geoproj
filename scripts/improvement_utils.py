"""Shared helpers for the 2026 scientific-improvement audit.

Imports canonical constants and SCS-CN equation from pipeline_utils.
Figure styling imports from figure_config.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import yaml
from pyproj import Transformer
from rasterio.features import geometry_mask
from shapely.geometry import Point

# Canonical constants and model functions — single source of truth
from pipeline_utils import ROOT, WORKING_CRS, WGS84, OUTLET_LON, OUTLET_LAT, scs_runoff_mm

FIRE_DATE = pd.Timestamp("2019-01-03")

# Journal-standard muted palette (colorblind-safe, greyscale-compatible)
OKABE_ITO = {
    "orange":    "#D4A24C",  # muted amber
    "sky":       "#8CB8D4",  # muted sky
    "green":     "#4C9DAF",  # muted teal
    "yellow":    "#E8D586",  # muted gold
    "blue":      "#7B9EBF",  # muted slate
    "vermillion":"#D4725A",  # muted terracotta
    "purple":    "#B39EB5",  # muted lavender
    "black":     "#333333",  # dark gray (softer than pure black)
    "gray":      "#8C8C8C",  # neutral gray
}


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


# --- Figure helpers (improvement-script style; pipeline scripts use figure_config directly) ---

def configure_plots() -> None:
    """Apply unified figure style from scientific_fig_style."""
    try:
        from scripts.utilities.scientific_fig_style import apply_style
        apply_style()
    except ImportError:
        plt.rcParams.update(
            {
                "font.family": "DejaVu Sans",
                "font.size": 8,
                "axes.titlesize": 9,
                "axes.labelsize": 8,
                "xtick.labelsize": 7,
                "ytick.labelsize": 7,
                "legend.fontsize": 7,
                "figure.dpi": 150,
                "savefig.dpi": 300,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "axes.grid": False,
            }
        )


def save_figure(fig: plt.Figure, path: Path, dpi: int = 300) -> None:
    ensure_dirs(path.parent)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def add_scale_bar(ax, length_m: float = 1000.0) -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x0 = xmin + 0.06 * (xmax - xmin)
    y0 = ymin + 0.06 * (ymax - ymin)
    ax.plot([x0, x0 + length_m], [y0, y0], color="black", linewidth=2)
    ax.text(x0 + length_m / 2, y0 + 0.015 * (ymax - ymin), f"{length_m / 1000:g} km", ha="center")


def load_yaml(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


# configure_plots, scs_runoff_mm, save_figure, add_scale_bar
# are imported from figure_config and pipeline_utils at module top — see imports.


def response_unit_runoff(precip_mm: Iterable[float]) -> pd.DataFrame:
    """Run the existing response units for arbitrary event rainfall totals."""
    units = gpd.read_file(ROOT / "data/processed/model_inputs/runoff_units.gpkg")
    areas = units["area_m2"].to_numpy(float)
    weights = areas / areas.sum()
    baseline_cn = units["baseline_parameter"].to_numpy(float)
    burned_cn = units["burned_parameter"].to_numpy(float)
    rows: list[dict] = []
    for value in precip_mm:
        p = float(value)
        q0 = float(np.sum(scs_runoff_mm(p, baseline_cn) * weights))
        q1 = float(np.sum(scs_runoff_mm(p, burned_cn) * weights))
        rows.append(
            {
                "rainfall_total_mm": p,
                "baseline_runoff_mm": q0,
                "burned_runoff_mm": q1,
                "runoff_delta_mm": q1 - q0,
                "runoff_delta_volume_m3": (q1 - q0) / 1000.0 * areas.sum(),
            }
        )
    return pd.DataFrame(rows)


def outlet_point_utm() -> Point:
    transformer = Transformer.from_crs(WGS84, WORKING_CRS, always_xy=True)
    return Point(*transformer.transform(OUTLET_LON, OUTLET_LAT))


def raster_metadata(path: Path, include_stats: bool = True) -> dict:
    with rasterio.open(path) as src:
        row = {
            "path": relative(path),
            "crs": str(src.crs),
            "bounds": ",".join(f"{v:.6f}" for v in src.bounds),
            "resolution_x": float(src.res[0]),
            "resolution_y": float(src.res[1]),
            "transform": ",".join(f"{v:.9g}" for v in tuple(src.transform)[:6]),
            "width": int(src.width),
            "height": int(src.height),
            "nodata": src.nodata,
            "dtype": src.dtypes[0],
            "band_count": int(src.count),
        }
        if include_stats:
            arr = src.read(1, masked=True)
            values = arr.compressed()
            row.update(
                {
                    "valid_pixel_count": int(values.size),
                    "minimum": float(np.min(values)) if values.size else math.nan,
                    "maximum": float(np.max(values)) if values.size else math.nan,
                    "mean": float(np.mean(values)) if values.size else math.nan,
                }
            )
        return row


def vector_metadata(path: Path) -> dict:
    frame = gpd.read_file(path)
    bounds = frame.total_bounds if len(frame) else [math.nan] * 4
    return {
        "path": relative(path),
        "crs": str(frame.crs),
        "feature_count": int(len(frame)),
        "empty_geometry_count": int(frame.geometry.is_empty.sum()) if len(frame) else 0,
        "invalid_geometry_count": int((~frame.geometry.is_valid).sum()) if len(frame) else 0,
        "bounds": ",".join(f"{v:.6f}" for v in bounds),
        "geometry_types": ",".join(sorted(frame.geom_type.unique())) if len(frame) else "",
    }


def mask_for_geometry(path: Path, geometry) -> tuple[np.ndarray, rasterio.Affine]:
    with rasterio.open(path) as src:
        mask = geometry_mask(
            [geometry],
            out_shape=(src.height, src.width),
            transform=src.transform,
            invert=True,
        )
        return mask, src.transform


def copy_if_different(source: Path, destination: Path) -> None:
    ensure_dirs(destination.parent)
    if not destination.exists() or sha256(source) != sha256(destination):
        shutil.copy2(source, destination)


def write_json(path: Path, payload: dict | list) -> None:
    ensure_dirs(path.parent)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    clean = frame.astype(object).where(pd.notna(frame), "")
    headers = [str(column).replace("|", "\\|") for column in clean.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in clean.itertuples(index=False, name=None):
        values = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)
