"""Canonical manuscript figure configuration — Lake Varese / Monte Martica.

PNG-only for Overleaf embedding. Colorblind-safe, no red-green contrasts.
"""
from __future__ import annotations
from pathlib import Path
from textwrap import fill
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Physical dimensions (mm)
# ---------------------------------------------------------------------------
SINGLE_COLUMN = 90
INTERMEDIATE  = 140
DOUBLE_COLUMN = 180
MAX_HEIGHT    = 170

def mm_to_inch(mm): return mm / 25.4

# ---------------------------------------------------------------------------
# Safe font sizes for Overleaf embedding (pt)
# ---------------------------------------------------------------------------
FS_TICK       = 7
FS_AXIS       = 8
FS_LEGEND     = 7
FS_PANEL      = 9
FS_ANNOTATION = 7
FS_COLORBAR   = 7
FS_TABLE      = 6
FS_TITLE      = 8

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
PNG_DPI          = 600
SAVE_PAD_INCHES  = 0.12
SUBPAD_LEFT      = 0.09
SUBPAD_RIGHT     = 0.95
SUBPAD_BOTTOM    = 0.11
SUBPAD_TOP       = 0.93
SUBPAD_WSPACE    = 0.30
SUBPAD_HSPACE    = 0.34

# ---------------------------------------------------------------------------
# Colorblind-safe palettes (Okabe-Ito derived)
# ---------------------------------------------------------------------------
BLUE       = "#0072B2"
ORANGE     = "#E69F00"
GREEN      = "#009E73"
PURPLE     = "#CC79A7"
SKY_BLUE   = "#56B4E9"
VERMILLION = "#D55E00"
YELLOW     = "#F0E442"
GREY       = "#999999"
CATEGORICAL = [BLUE, ORANGE, GREEN, PURPLE, SKY_BLUE, VERMILLION, YELLOW, GREY]

# Map layer colours
WATER_FILL       = "#a6cee3"
WATER_EDGE       = "#6baed6"
FIRE_EDGE        = VERMILLION
CATCHMENT_EDGE   = BLUE
CATCHMENT_FILL   = "#e3ecf4"
STREAM_LINE      = "#4575b4"
DEM_STREAM_LINE  = "#fc8d62"
AOI_EDGE         = GREY
OUTLET_POINT     = "#000000"
BACKGROUND       = "#ffffff"
OUTSIDE_FIRE_FILL = PURPLE

# Burn severity colors (sequential oranges)
BURN_LEGEND_0    = "#fef0d9"
BURN_LEGEND_1    = "#fdcc8a"
BURN_LEGEND_2    = "#fc8d59"
BURN_LEGEND_3    = "#d7301f"
BURN_LEGEND_255  = "#e0e0e0"
BURN_SEVERITY_COLORS = [
    BURN_LEGEND_0,
    BURN_LEGEND_1,
    BURN_LEGEND_2,
    BURN_LEGEND_3,
    BURN_LEGEND_255,
]
BURN_SEVERITY_LABELS = ["Unburned", "Low", "Moderate", "High", "NoData"]
RUNOFF_DELTA_CMAP = "YlOrBr"

# Model comparison colors
SCS_CN_COLOR     = BLUE
WEPP_CLOUD_COLOR = ORANGE

# ---------------------------------------------------------------------------
# Global rcParams
# ---------------------------------------------------------------------------
def configure():
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7,
        "axes.linewidth": 0.5,
        "axes.labelsize": FS_AXIS,
        "axes.titlesize": FS_TITLE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "xtick.minor.size": 1.5, "ytick.minor.size": 1.5,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.labelsize": FS_TICK, "ytick.labelsize": FS_TICK,
        "legend.fontsize": FS_LEGEND, "legend.title_fontsize": FS_LEGEND,
        "legend.frameon": True, "legend.edgecolor": "#cccccc",
        "legend.handlelength": 1.5, "legend.handletextpad": 0.5, "legend.borderpad": 0.4,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "savefig.bbox": "tight",
        "savefig.pad_inches": SAVE_PAD_INCHES,
        "lines.linewidth": 0.8, "lines.markersize": 3.0,
        "axes.grid": False, "image.interpolation": "nearest",
    })

# ---------------------------------------------------------------------------
# Panel labels — inside axes, top-left, white background
# ---------------------------------------------------------------------------
def label_panel(ax, label, x=0.02, y=0.96):
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top",
            fontsize=FS_PANEL, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.88), zorder=100)

# ---------------------------------------------------------------------------
# Safe subplots_adjust for multi-panel figures
# ---------------------------------------------------------------------------
def safe_layout(fig, left=None, right=None, bottom=None, top=None,
                wspace=None, hspace=None):
    fig.subplots_adjust(
        left=left or SUBPAD_LEFT, right=right or SUBPAD_RIGHT,
        bottom=bottom or SUBPAD_BOTTOM, top=top or SUBPAD_TOP,
        wspace=wspace or SUBPAD_WSPACE, hspace=hspace or SUBPAD_HSPACE,
    )

# ---------------------------------------------------------------------------
# Map decorators — scale bar, CRS label, simple QGIS-like layout
# ---------------------------------------------------------------------------
def add_scale_bar(ax, length_m, label=None, x=0.04, y=0.06,
                  linewidth=0.6, color="#333333", fontsize=7,
                  height=0.012, segments=2):
    if length_m >= 5000:
        nice = round(length_m / 1000) * 1000; label = label or f"{nice // 1000} km"
    elif length_m >= 1000:
        nice = round(length_m / 500) * 500
        label = label or (f"{nice / 1000:.1f} km" if nice >= 1000 else f"{nice} m")
    elif length_m >= 100:
        nice = round(length_m / 100) * 100; label = label or f"{nice} m"
    else:
        nice = round(length_m / 10) * 10; label = label or f"{nice} m"
    xlim = ax.get_xlim()
    span = xlim[1] - xlim[0]
    if span <= 0:
        return
    frac = min(nice / span, 0.35)
    from matplotlib.patches import Rectangle
    for i in range(max(1, segments)):
        face = "black" if i % 2 == 0 else "white"
        rect = Rectangle(
            (x + i * frac / segments, y),
            frac / segments,
            height,
            transform=ax.transAxes,
            facecolor=face,
            edgecolor=color,
            linewidth=linewidth,
            clip_on=False,
            zorder=120,
        )
        ax.add_patch(rect)
    ax.text(x + frac / 2, y + height + 0.006, label, transform=ax.transAxes,
            fontsize=fontsize, ha="center", va="bottom", color=color, clip_on=False)

def add_crs_label(ax, crs_label="EPSG:32632", x=0.97, y=0.02, fontsize=6, color="#777777"):
    ax.text(x, y, crs_label, transform=ax.transAxes, fontsize=fontsize,
            ha="right", va="bottom", color=color, style="italic", clip_on=False)

def add_map_caption(fig, caption, fontsize=6, color="#555555"):
    """Add a compact caption below the map, similar to a simple QGIS layout."""
    if not caption:
        return
    fig.text(
        0.02,
        0.015,
        fill(str(caption), width=145),
        ha="left",
        va="bottom",
        fontsize=fontsize,
        color=color,
    )

def apply_qgis_map_layout(
    fig,
    ax,
    *,
    title,
    subtitle=None,
    caption=None,
    legend_handles=None,
    legend_title="Layers",
    legend_loc="lower right",
    scale_length_m=2000,
    crs_label="EPSG:32632",
):
    """Use a plain QGIS-style export frame for diagnostic maps.

    The helper intentionally stays simple: no coordinate tick clutter, one map
    frame, optional legend/colorbar, a scale bar, CRS tag, and a
    short uncertainty-aware caption.
    """
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    ax.set_facecolor("#fafafa")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#444444")
        spine.set_linewidth(0.6)
    if title:
        fig.text(
            0.02,
            0.975,
            title,
            ha="left",
            va="top",
            fontsize=FS_TITLE + 2,
            fontweight="bold",
            color="#111111",
        )
    if subtitle:
        fig.text(
            0.02,
            0.944,
            subtitle,
            ha="left",
            va="top",
            fontsize=FS_ANNOTATION,
            color="#555555",
        )
    if legend_handles:
        legend = ax.legend(
            handles=legend_handles,
            loc=legend_loc,
            title=legend_title,
            fontsize=FS_LEGEND,
            title_fontsize=FS_LEGEND,
            frameon=True,
            fancybox=False,
            framealpha=0.92,
            facecolor="white",
            edgecolor="#777777",
        )
        legend.set_zorder(130)
    if scale_length_m:
        add_scale_bar(ax, scale_length_m, fontsize=FS_LEGEND)
    add_crs_label(ax, crs_label, fontsize=FS_LEGEND - 1)
    add_map_caption(fig, caption)
    fig.subplots_adjust(
        left=0.02,
        right=0.98,
        bottom=0.14 if caption else 0.04,
        top=0.86 if subtitle else 0.89,
    )

# ---------------------------------------------------------------------------
# Axis formatters
# ---------------------------------------------------------------------------
def format_utm_axes(ax):
    from matplotlib.ticker import FuncFormatter
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x / 1000:.0f}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x / 1000:.0f}"))

# ---------------------------------------------------------------------------
# Export — PNG-only
# ---------------------------------------------------------------------------
def save_png(fig, output_path, dpi=PNG_DPI):
    png = Path(output_path)
    if png.suffix.lower() != ".png": png = png.with_suffix(".png")
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(png), format="png", dpi=dpi, bbox_inches="tight",
                pad_inches=SAVE_PAD_INCHES, facecolor="white", edgecolor="white",
                transparent=False)
    return png

def save_figure(fig, output_path, *args, **kwargs):
    """Compatibility wrapper.

    Older scripts passed ``(pdf_path, png_path, dpi=...)`` even though the
    project now keeps PNG-only map outputs. Prefer the explicit PNG argument
    when present, otherwise coerce the first path to ``.png``.
    """
    dpi = kwargs.get("dpi", PNG_DPI)
    target = args[0] if args else output_path
    return save_png(fig, target, dpi=dpi)
