"""Figure 12: one available Lake Varese pre/post/delta proxy map panel."""
from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
ROOT = SCRIPTS_DIR.parent
for p in [str(SCRIPTS_DIR), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd

from lake_wq.config import SELECTED_EVENTS_PATH, INTERMEDIATE_DIR, ROI_PATH, LATEX_DIR, WORKING_CRS

OUT = LATEX_DIR / "fig12_lake_water_quality_event_panel.png"
PLACEHOLDER = "No local Sentinel-2 pre/post event pair available in current raw archive."


def _placeholder(message: str = PLACEHOLDER) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    ax.set_axis_off()
    ax.text(0.5, 0.58, message, ha="center", va="center", fontsize=12, fontweight="bold", wrap=True)
    ax.text(
        0.5,
        0.40,
        "The Python-only workflow reports this as a local data limitation rather than using GEE.",
        ha="center",
        va="center",
        fontsize=9,
        wrap=True,
    )
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> {OUT} (placeholder)")


def _candidate_triplets(event_id: str) -> list[tuple[str, list[Path]]]:
    return [
        ("NDTI", [INTERMEDIATE_DIR / f"event_{event_id}_pre_ndti.tif", INTERMEDIATE_DIR / f"event_{event_id}_post_ndti.tif", INTERMEDIATE_DIR / f"event_{event_id}_delta_ndti.tif"]),
        ("NDCI", [INTERMEDIATE_DIR / f"event_{event_id}_pre_ndci.tif", INTERMEDIATE_DIR / f"event_{event_id}_post_ndci.tif", INTERMEDIATE_DIR / f"event_{event_id}_delta_ndci.tif"]),
    ]


def _read(path: Path) -> tuple[np.ndarray, list[float], Any]:
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.crs.to_epsg() != 32632:
            raise ValueError(f"{path} is not EPSG:32632")
        arr = ds.read(1).astype("float32")
        if ds.nodata is not None:
            arr = np.where(arr == ds.nodata, np.nan, arr)
        extent = [ds.bounds.left, ds.bounds.right, ds.bounds.bottom, ds.bounds.top]
        return arr, extent, ds.transform


def main() -> None:
    if not SELECTED_EVENTS_PATH.exists() or not ROI_PATH.exists():
        _placeholder()
        return
    selected = pd.read_csv(SELECTED_EVENTS_PATH).sort_values("selection_rank")
    chosen: tuple[str, str, list[Path]] | None = None
    for _, event in selected.iterrows():
        event_id = str(event["event_id"])
        for index_name, paths in _candidate_triplets(event_id):
            if all(p.exists() and p.stat().st_size > 0 for p in paths):
                chosen = (event_id, index_name, paths)
                break
        if chosen:
            break
    if chosen is None:
        _placeholder()
        return

    event_id, index_name, paths = chosen
    try:
        arrays_extents = [_read(p) for p in paths]
    except Exception:
        _placeholder()
        return
    arrays = [x[0] for x in arrays_extents]
    extent = arrays_extents[0][1]
    if not any(np.isfinite(a).any() for a in arrays):
        _placeholder()
        return
    rois = gpd.read_file(ROI_PATH).to_crs(WORKING_CRS)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 4.0), constrained_layout=True)
    titles = [f"Pre {index_name}", f"Post {index_name}", f"Δ{index_name}"]
    cmaps = ["viridis", "viridis", "RdBu_r"]
    vlims = [(None, None), (None, None), (-0.2, 0.2)]
    for ax, arr, title, cmap, (vmin, vmax) in zip(axes, arrays, titles, cmaps, vlims):
        im = ax.imshow(arr, extent=extent, origin="upper", cmap=cmap, vmin=vmin, vmax=vmax)
        rois.boundary.plot(ax=ax, color="black", linewidth=0.6)
        ax.set_title(title)
        ax.set_xlabel(f"Easting (m, {WORKING_CRS})")
        ax.set_ylabel(f"Northing (m, {WORKING_CRS})")
        fig.colorbar(im, ax=ax, shrink=0.72)
    fig.suptitle(f"Lake Varese local Sentinel-2 proxy panel — {event_id}", fontsize=11, fontweight="bold")
    fig.text(0.5, 0.01, "Proxy anomaly only; cloud/SCL validation records and data limitations must be checked before interpretation.", ha="center", fontsize=8)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
