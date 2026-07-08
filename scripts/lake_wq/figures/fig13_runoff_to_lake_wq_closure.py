"""Figure 13: conceptual runoff-to-lake-WQ proxy closure diagram."""
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
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import pandas as pd

from lake_wq.config import ANOMALIES_PATH, QA_SPATIAL_PATH, LATEX_DIR

OUT = LATEX_DIR / "fig13_runoff_to_lake_wq_closure.png"


def _data_limited() -> bool:
    if not ANOMALIES_PATH.exists() or ANOMALIES_PATH.stat().st_size == 0:
        return True
    df = pd.read_csv(ANOMALIES_PATH)
    numeric = False
    for col in ["delta_ndti_mean", "delta_ndci_mean"]:
        if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().any():
            numeric = True
    if not numeric:
        return True
    if QA_SPATIAL_PATH.exists():
        qa = pd.read_csv(QA_SPATIAL_PATH)
        if "MISSING_LOCAL_IMAGE" in set(qa.get("quality_flag", [])):
            return True
    return False


def _box(ax, x, y, w, h, text, color, text_color="white"):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.03", facecolor=color, edgecolor="#333333", linewidth=0.9)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8, color=text_color, wrap=True)
    return patch


def _arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13, linewidth=1.1, color="#333333"))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    limited = _data_limited()
    fig, ax = plt.subplots(figsize=(9.2, 4.4), constrained_layout=True)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    xs = [0.03, 0.22, 0.42, 0.62, 0.81]
    y = 0.50
    w = 0.15
    h = 0.27
    labels = [
        "Fire severity /\nCN adjustment\n(dNBR proxy)",
        "Event runoff\nΔQ / ΔV\n(SCS-CN screening)",
        "Sediment / runoff\nrisk context\n(WEPPcloud benchmark)",
        "Sentinel-2\nNDTI / NDCI\nproxy anomaly" + ("\n(data-limited)" if limited else ""),
        "ARPA lake\nanalytical context\n(not calibration)",
    ]
    colors = ["#756bb1", "#2b8cbe", "#31a354", "#d95f0e" if limited else "#3182bd", "#d9d9d9"]
    text_colors = ["white", "white", "white", "white", "#333333"]
    patches = [_box(ax, x, y, w, h, lab, col, tc) for x, lab, col, tc in zip(xs, labels, colors, text_colors)]
    for i in range(len(patches) - 1):
        _arrow(ax, (xs[i] + w + 0.01, y + h / 2), (xs[i + 1] - 0.01, y + h / 2))
    ax.text(
        0.5,
        0.90,
        "Python-only lake water-quality closure: screening-level linkage, not calibrated prediction",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="#222222",
    )
    ax.text(
        0.5,
        0.28,
        "The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes.",
        ha="center",
        va="center",
        fontsize=8,
        color="#222222",
        wrap=True,
    )
    ax.text(
        0.5,
        0.16,
        "Turbidity proxy (NDTI) is primary; chlorophyll-a proxy (NDCI) is delayed and indirect. No causality, calibration, or observed runoff increase is claimed.",
        ha="center",
        va="center",
        fontsize=8,
        color="#444444",
        wrap=True,
    )
    if limited:
        ax.text(
            0.5,
            0.06,
            "Current local Sentinel-2 archive is insufficient for selected event pre/post pairs; the gap is reported rather than filled with GEE.",
            ha="center",
            va="center",
            fontsize=7.5,
            color="#a63603",
            style="italic",
            wrap=True,
        )
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
