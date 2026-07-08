"""Atomic figure: regional context map for the Lake Varese / Monte Martica study area.

Output:
    docs/latex/fig01a_north_Italy.png

Design:
    EPSG:4326 geographic coordinates.
    No compass.
    No raster post-processing.
    Manual label placement to avoid overlap around Lake Varese, Varese, and the study area.
"""

from __future__ import annotations

from pathlib import Path
import math
import sys
import urllib.request

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse, Rectangle
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.figures.lib.io import LATEX  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
OUT = LATEX / "fig01a_north_Italy.png"

CACHE = ROOT / "data" / "external" / "naturalearth"
COUNTRIES_ZIP = CACHE / "ne_10m_admin_0_countries.zip"
LAKES_ZIP = CACHE / "ne_10m_lakes.zip"

COUNTRIES_URL = (
    "https://naturalearth.s3.amazonaws.com/"
    "10m_cultural/ne_10m_admin_0_countries.zip"
)
LAKES_URL = (
    "https://naturalearth.s3.amazonaws.com/"
    "10m_physical/ne_10m_lakes.zip"
)

# WGS84 / EPSG:4326.
# Project AOI used in the report.
STUDY_BOUNDS = (8.70, 45.78, 8.92, 45.94)  # xmin, ymin, xmax, ymax

# Regional map extent.
MAP_EXTENT = (5.0, 20.0, 36.7, 47.5)  # xmin, xmax, ymin, ymax


def ensure_download(url: str, path: Path) -> None:
    """Download Natural Earth data once and keep it in the project cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    try:
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, path)
    except Exception as exc:
        raise RuntimeError(
            f"Could not download required Natural Earth layer:\n"
            f"  {url}\n"
            f"Expected local path:\n"
            f"  {path}\n"
            f"Check internet access, or download the zip manually to this path."
        ) from exc


def read_natural_earth(zip_path: Path) -> gpd.GeoDataFrame:
    """Read a Natural Earth zipped shapefile as EPSG:4326."""
    gdf = gpd.read_file(f"zip://{zip_path}")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


def add_scale_bar(
    ax: plt.Axes,
    x0: float = 5.42,
    y0: float = 37.05,
    total_km: int = 500,
    segments: int = 4,
) -> None:
    """Draw an approximate longitude scale bar at the given latitude."""
    segment_km = total_km / segments
    km_per_degree_lon = 111.32 * math.cos(math.radians(y0))
    segment_deg = segment_km / km_per_degree_lon
    bar_h = 0.12

    for i in range(segments):
        ax.add_patch(
            Rectangle(
                (x0 + i * segment_deg, y0),
                segment_deg,
                bar_h,
                facecolor="black" if i % 2 == 0 else "white",
                edgecolor="black",
                linewidth=0.6,
                zorder=20,
            )
        )

    for i in range(segments + 1):
        value = int(i * segment_km)
        label = f"{value}" if i < segments else f"{value} km"
        ax.text(
            x0 + i * segment_deg,
            y0 + bar_h + 0.08,
            label,
            ha="center",
            va="bottom",
            fontsize=7.5,
            zorder=21,
        )


def label(
    ax: plt.Axes,
    text: str,
    xy: tuple[float, float],
    *,
    fontsize: float = 8.5,
    color: str = "black",
    weight: str = "normal",
    style: str = "normal",
    ha: str = "center",
    va: str = "center",
    zorder: int = 30,
    bbox: bool = True,
) -> None:
    """Place text with a small white halo box to prevent visual collisions."""
    box_style = (
        dict(
            facecolor="white",
            edgecolor="none",
            alpha=0.72,
            boxstyle="round,pad=0.12",
        )
        if bbox
        else None
    )

    ax.text(
        xy[0],
        xy[1],
        text,
        fontsize=fontsize,
        color=color,
        fontweight=weight,
        fontstyle=style,
        ha=ha,
        va=va,
        zorder=zorder,
        bbox=box_style,
    )


def main() -> None:
    ensure_download(COUNTRIES_URL, COUNTRIES_ZIP)
    ensure_download(LAKES_URL, LAKES_ZIP)

    countries = read_natural_earth(COUNTRIES_ZIP)
    lakes = read_natural_earth(LAKES_ZIP)

    xmin, xmax, ymin, ymax = MAP_EXTENT
    extent_geom = box(xmin, ymin, xmax, ymax)

    countries = countries[countries.intersects(extent_geom)].copy()
    lakes = lakes[lakes.intersects(extent_geom)].copy()

    name_col = "NAME_EN" if "NAME_EN" in countries.columns else "ADMIN"

    fig, ax = plt.subplots(figsize=(9.2, 6.7), dpi=300)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor("#eaf4fb")

    # Land and borders.
    countries.plot(
        ax=ax,
        facecolor="#f7f7f2",
        edgecolor="#b9b9b9",
        linewidth=0.45,
        zorder=2,
    )

    italy = countries[countries[name_col].eq("Italy")]
    if not italy.empty:
        italy.plot(
            ax=ax,
            facecolor="#fbfbf7",
            edgecolor="#777777",
            linewidth=0.65,
            zorder=3,
        )

    # Lakes. Natural Earth does not always include small Lake Varese, so it is added manually below.
    if not lakes.empty:
        lakes.plot(
            ax=ax,
            facecolor="#cfe7f5",
            edgecolor="#90bdd4",
            linewidth=0.35,
            zorder=4,
        )

    # Lake Varese, manually approximated for a regional context figure.
    ax.add_patch(
        Ellipse(
            (8.735, 45.815),
            width=0.18,
            height=0.065,
            angle=-12,
            facecolor="#cfe7f5",
            edgecolor="#76aac5",
            linewidth=0.45,
            zorder=6,
        )
    )

    # Study area box. No opaque fill: this avoids the old overlay problem.
    sx0, sy0, sx1, sy1 = STUDY_BOUNDS
    ax.add_patch(
        Rectangle(
            (sx0, sy0),
            sx1 - sx0,
            sy1 - sy0,
            facecolor="none",
            edgecolor="#d62728",
            linewidth=1.25,
            zorder=12,
        )
    )

    # Varese city marker and label, placed outside the AOI box to avoid collision.
    ax.plot(8.825, 45.820, marker="o", markersize=2.2, color="black", zorder=13)
    label(ax, "Varese", (9.07, 45.72), fontsize=8.0, ha="left")

    # Study area annotation placed east of the AOI, not on top of Varese or Lake Varese.
    ax.annotate(
        "Study area",
        xy=((sx0 + sx1) / 2, (sy0 + sy1) / 2),
        xytext=(10.15, 46.18),
        fontsize=8.2,
        color="#d62728",
        ha="left",
        va="center",
        arrowprops=dict(
            arrowstyle="-",
            color="#d62728",
            linewidth=0.9,
            shrinkA=2,
            shrinkB=2,
        ),
        zorder=25,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.78, pad=1.0),
    )

    # Country and regional labels.
    label(ax, "Italy", (12.35, 42.35), fontsize=12.0, weight="bold", bbox=False)
    label(ax, "France", (6.85, 44.25), fontsize=8.5)
    label(ax, "Switzerland", (9.00, 46.98), fontsize=8.0)
    label(ax, "Austria", (14.55, 46.98), fontsize=8.0)
    label(ax, "Slovenia", (14.65, 46.05), fontsize=8.0)
    label(ax, "Croatia", (16.10, 44.90), fontsize=8.0)
    label(ax, "Lombardy", (10.10, 45.28), fontsize=7.2, style="italic", color="#333333")

    # Water labels.
    label(ax, "Lake\nVarese", (8.48, 45.78), fontsize=6.8, color="#1f5d8a", style="italic")
    label(ax, "Ligurian Sea", (8.55, 43.25), fontsize=7.0, color="#245a93", style="italic", bbox=False)
    label(ax, "Adriatic Sea", (15.25, 42.40), fontsize=7.0, color="#245a93", style="italic", bbox=False)
    label(ax, "Tyrrhenian Sea", (11.10, 39.55), fontsize=7.0, color="#245a93", style="italic", bbox=False)
    label(ax, "Mediterranean Sea", (10.25, 36.98), fontsize=6.8, color="#245a93", style="italic", bbox=False)
    label(ax, "Ionian Sea", (17.10, 37.50), fontsize=7.0, color="#245a93", style="italic", bbox=False)

    # Graticule.
    xticks = np.arange(6, 21, 2)
    yticks = np.arange(37, 48, 1)
    ax.set_xticks(xticks)
    ax.set_yticks(yticks)
    ax.set_xticklabels([f"{int(x)}°E" for x in xticks], fontsize=8)
    ax.set_yticklabels([f"{int(y)}°N" for y in yticks], fontsize=8)

    ax.tick_params(
        axis="both",
        which="both",
        direction="out",
        top=True,
        bottom=True,
        left=True,
        right=True,
        labeltop=True,
        labelbottom=True,
        labelleft=True,
        labelright=True,
        length=2.5,
        width=0.6,
    )

    ax.grid(
        True,
        which="major",
        color="#d2d2d2",
        linestyle=":",
        linewidth=0.55,
        zorder=1,
    )

    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#4d4d4d")

    add_scale_bar(ax)

    ax.text(
        xmax - 0.25,
        ymin + 0.12,
        "CRS: EPSG:4326",
        ha="right",
        va="bottom",
        fontsize=6.8,
        color="#555555",
        zorder=30,
    )

    ax.set_title("Location of the study area in Italy", fontsize=13.0, pad=10)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)

    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
