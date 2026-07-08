"""Figure 10: runoff-potential change vs Lake Varese NDTI anomaly."""
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
import pandas as pd

from lake_wq.config import ANOMALIES_PATH, LATEX_DIR

OUT = LATEX_DIR / "fig10_runoff_vs_lake_turbidity_proxy.png"
PLACEHOLDER = "Insufficient local Sentinel-2 event coverage for NDTI anomaly scatter."
COLORS = {
    "whole_lake": "#2b8cbe",
    "near_inlet_or_north_shore": "#d95f0e",
    "lake_center_control": "#31a354",
}


def _placeholder(message: str = PLACEHOLDER) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    ax.set_axis_off()
    ax.text(0.5, 0.58, message, ha="center", va="center", fontsize=12, fontweight="bold", wrap=True)
    ax.text(
        0.5,
        0.40,
        "Python-only workflow: missing local Sentinel-2 pre/post event pairs are reported as a data gap, not filled with GEE.",
        ha="center",
        va="center",
        fontsize=9,
        wrap=True,
    )
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> {OUT} (placeholder)")


def main() -> None:
    if not ANOMALIES_PATH.exists() or ANOMALIES_PATH.stat().st_size == 0:
        _placeholder()
        return
    df = pd.read_csv(ANOMALIES_PATH)
    x_col = "delta_volume_m3" if "delta_volume_m3" in df.columns and pd.to_numeric(df["delta_volume_m3"], errors="coerce").notna().any() else "delta_runoff_mm"
    required = {x_col, "delta_ndti_mean", "roi_name"}
    if not required.issubset(df.columns):
        _placeholder()
        return
    df[x_col] = pd.to_numeric(df[x_col], errors="coerce")
    df["delta_ndti_mean"] = pd.to_numeric(df["delta_ndti_mean"], errors="coerce")
    valid = df.dropna(subset=[x_col, "delta_ndti_mean"])
    if len(valid) < 1:
        _placeholder()
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    for roi, sub in valid.groupby("roi_name"):
        ax.scatter(
            sub[x_col],
            sub["delta_ndti_mean"],
            s=50,
            label=str(roi).replace("_", " "),
            color=COLORS.get(str(roi), "#7f7f7f"),
            edgecolor="black",
            linewidth=0.35,
            alpha=0.88,
        )
    ax.axhline(0, color="#777777", lw=0.8, ls="--")
    ax.set_xlabel("Event runoff-potential ΔV (m³)" if x_col == "delta_volume_m3" else "Event runoff-potential ΔQ (mm)")
    ax.set_ylabel("ΔNDTI mean (post - pre)")
    ax.set_title("Runoff-potential change vs lake turbidity proxy anomaly")
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=7)
    ax.text(
        0.01,
        0.02,
        "Screening-level proxy anomaly comparison; NDTI is not calibrated turbidity.",
        transform=ax.transAxes,
        fontsize=7,
        ha="left",
        va="bottom",
    )
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
