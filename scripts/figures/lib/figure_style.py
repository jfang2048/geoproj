"""Shared figure style — journal-standard palettes, 600 DPI, colorblind-safe.

Palette rationale (journal conventions):
  Sequential:  Viridis — perceptually uniform, colorblind-safe, greyscale-compatible.
  Diverging:   BrBG (Brown-BlueGreen) — hydro-climatic anomalies (dry ↔ wet).
  Qualitative: Muted distinct tones — no red-green pairs, greyscale-distinguishable.
"""
from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt

# ---- Typography ----
FONT_FAMILY = "DejaVu Sans"
BASE_FONT_SIZE, AXIS_LABEL_SIZE = 8, 9
TICK_LABEL_SIZE, LEGEND_FONT_SIZE = 7, 6.5
TITLE_FONT_SIZE = 9
SAVE_DPI, LINE_WIDTH = 600, 0.8

# ---- Qualitative palette (muted, colorblind-safe, greyscale-distinguishable) ----
# Conservative dNBR — muted teal-blue
C_CONSERVATIVE  = "#4C9DAF"
# Relaxed dNBR — muted amber
C_RELAXED       = "#D4A24C"
# Upper bound / burned scenario — muted terracotta
C_UPPER         = "#D4725A"
C_BURNED        = "#D4725A"
# Undisturbed baseline — muted slate-blue
C_UNDISTURBED   = "#7B9EBF"
# Rainfall / water — muted sky
C_RAINFALL      = "#8CB8D4"
# Neutral accents
C_GRAY          = "#8C8C8C"
C_DARK          = "#333333"

# ---- Topographic palette (terrain — earthy greens → browns → whites) ----
TOPO_LOWLAND  = "#7DAF6E"
TOPO_MID      = "#C4B58A"
TOPO_HIGHLAND = "#D4C4A8"
TOPO_PEAK     = "#F0EDE8"


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": FONT_FAMILY, "font.size": BASE_FONT_SIZE,
        "axes.titlesize": TITLE_FONT_SIZE, "axes.labelsize": AXIS_LABEL_SIZE,
        "xtick.labelsize": TICK_LABEL_SIZE, "ytick.labelsize": TICK_LABEL_SIZE,
        "legend.fontsize": LEGEND_FONT_SIZE, "legend.frameon": False,
        "figure.dpi": 200, "savefig.dpi": SAVE_DPI,
        "lines.linewidth": LINE_WIDTH, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": False,
        "svg.fonttype": "none", "pdf.fonttype": 42,
        "savefig.bbox": "tight", "savefig.facecolor": "white",
        # Sequential default — Viridis (perceptually uniform, colorblind-safe)
        "image.cmap": "viridis",
    })


def save_atomic_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=SAVE_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
