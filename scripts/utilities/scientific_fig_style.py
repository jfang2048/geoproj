"""Unified figure style for the Lake Varese / Monte Martica final report.

Apply to all publication figures (maps and charts) to produce a visually
coherent figure suite for Overleaf embedding.

Usage:
    from scripts.utilities.scientific_fig_style import apply_style
    apply_style()
    fig, ax = plt.subplots(...)
    # ... plotting ...
    save_figure(fig, path)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── Unified styling constants ──────────────────────────────────────────
FONT_FAMILY = "DejaVu Sans"
BASE_FONT_SIZE = 8
AXIS_LABEL_SIZE = 8
TICK_LABEL_SIZE = 7
LEGEND_FONT_SIZE = 6.5
TITLE_FONT_SIZE = 8
SUPTITLE_FONT_SIZE = 9
FIGURE_DPI = 200       # screen rendering
SAVE_DPI = 600          # final PNG export (Nature-compatible)
LINE_WIDTH = 0.8
MARKER_SIZE = 5
GRID_ALPHA = 0.15
GRID_LINEWIDTH = 0.4

# Colour palette — Okabe-Ito colourblind-safe
COLOURS = {
    "orange":     "#E69F00",
    "sky":        "#56B4E9",
    "green":      "#009E73",
    "yellow":     "#F0E442",
    "blue":       "#0072B2",
    "vermillion": "#D55E00",
    "purple":     "#CC79A7",
    "black":      "#000000",
    "gray":       "#7F7F7F",
    "dark_gray":  "#404040",
}

# Semantic colour mapping (consistent across all figures)
SEMANTIC = {
    "conservative_dnbr":   COLOURS["green"],
    "relaxed_dnbr":        COLOURS["orange"],
    "upper_bound":         COLOURS["vermillion"],
    "undisturbed":         COLOURS["blue"],
    "burned":              COLOURS["vermillion"],
    "station_907":         COLOURS["vermillion"],
    "other_station":       COLOURS["blue"],
    "lake":                COLOURS["sky"],
    "lake_edge":           "#2B5C8F",
    "hydrography":         "#1F78B4",
    "dem_streams":         "#E31A1C",
    "catchment_edge":      COLOURS["black"],
    "fire_fill":           COLOURS["vermillion"],
    "excluded_fire":       COLOURS["vermillion"],
    "outlet_candidate":    COLOURS["orange"],
    "outlet_alternative":  COLOURS["purple"],
    "basin":               COLOURS["gray"],
}


def apply_style() -> None:
    """Set global matplotlib rcParams for consistent figure styling."""
    plt.rcParams.update({
        "font.family":      FONT_FAMILY,
        "font.size":        BASE_FONT_SIZE,
        "axes.titlesize":   TITLE_FONT_SIZE,
        "axes.labelsize":   AXIS_LABEL_SIZE,
        "xtick.labelsize":  TICK_LABEL_SIZE,
        "ytick.labelsize":  TICK_LABEL_SIZE,
        "legend.fontsize":  LEGEND_FONT_SIZE,
        "figure.titlesize": SUPTITLE_FONT_SIZE,
        "figure.dpi":       FIGURE_DPI,
        "savefig.dpi":      SAVE_DPI,
        "lines.linewidth":  LINE_WIDTH,
        "lines.markersize": MARKER_SIZE,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.grid":          False,
        "legend.frameon":     False,
        "svg.fonttype":       "none",
        "pdf.fonttype":       42,
        "grid.alpha":         GRID_ALPHA,
        "grid.linewidth":     GRID_LINEWIDTH,
        "savefig.bbox":       "tight",
        "savefig.facecolor":  "white",
    })


def save_figure(fig: plt.Figure, path: Path, dpi: int = SAVE_DPI) -> None:
    """Save figure with consistent settings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def add_segmented_scale_bar(ax, length_m: float = 2000.0, n_segments: int = 4) -> None:
    """Draw a segmented graphic scale bar (map coordinates)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sb_x = x0 + 0.06 * (x1 - x0)
    sb_y = y0 + 0.05 * (y1 - y0)
    seg_len = length_m / n_segments
    bar_height = 0.018 * (y1 - y0)
    for i in range(n_segments):
        color = "black" if i % 2 == 0 else "white"
        rect = plt.Rectangle(
            (sb_x + i * seg_len, sb_y), seg_len, bar_height,
            facecolor=color, edgecolor="black", linewidth=0.5, zorder=11,
        )
        ax.add_patch(rect)
    ax.text(sb_x + length_m / 2, sb_y + 0.025 * (y1 - y0),
            f"{length_m / 1000:g} km", ha="center", fontsize=TICK_LABEL_SIZE, zorder=11)


def format_utm_axes(ax) -> None:
    """Remove scientific notation offset; use plain UTM metre tick labels."""
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
    ax.yaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
    ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE)


def panel_label(ax, label: str, loc: str = "upper left") -> None:
    """Add a small bold panel label (A, B, C...)."""
    x_pos = 0.03 if "left" in loc else 0.97
    y_pos = 0.96 if "upper" in loc else 0.04
    ha = "left" if "left" in loc else "right"
    ax.text(x_pos, y_pos, label, transform=ax.transAxes,
            fontsize=BASE_FONT_SIZE + 1, fontweight="bold", ha=ha, va="top")
