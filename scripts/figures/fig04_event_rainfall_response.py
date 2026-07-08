"""Atomic figure: Rainfall event depth vs modelled runoff response.
Scatter plot with event labels. Links rainfall forcing to model response;
does not represent an observed hydrograph."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scripts.figures.lib.figure_style import (apply_style, save_atomic_figure,
    C_CONSERVATIVE, C_UPPER, C_RAINFALL, C_DARK, C_GRAY)
from scripts.figures.lib.io import LATEX, TABLES, PROCESSED

OUT = LATEX / "fig04_event_rainfall_response.png"

def main() -> None:
    events = pd.read_csv(PROCESSED / "weather" / "post_fire_rainfall_events.csv")
    runoff = pd.read_csv(TABLES / "runoff_delta_by_event.csv")
    merged = events.merge(runoff, on="event_id", how="inner")

    x = merged["total_precip_mm"].values
    y = merged["delta_runoff_mm"].values
    event_ids = merged["event_id"].values

    apply_style()
    fig, ax = plt.subplots(figsize=(6.8, 5.2))

    is_053 = event_ids == "RAIN_053"
    ax.scatter(x[~is_053], y[~is_053], s=28, c=C_CONSERVATIVE, edgecolors="black",
               linewidths=0.28, alpha=0.82, zorder=3,
               label="Modelled event (conservative dNBR)")
    ax.scatter(x[is_053], y[is_053], s=120, c=C_UPPER, edgecolors="black",
               linewidths=0.8, marker="D", zorder=5,
               label="RAIN_053 (238.6 mm, 11 days)")

    ax.annotate("RAIN_053", xy=(x[is_053][0], y[is_053][0]),
                xytext=(x[is_053][0] + 18, y[is_053][0] + 0.025),
                fontsize=7.5, fontweight="bold", color=C_UPPER,
                arrowprops=dict(arrowstyle="->", color=C_UPPER, lw=1.1))

    ax.set_xlabel("Event rainfall depth (mm)", fontsize=9)
    ax.set_ylabel("Modelled Delta Q (mm)", fontsize=9)
    ax.set_xlim(left=-5)

    ax.text(0.97, 0.95, "77 percent of events: Delta Q below 0.05 mm\nLargest event gives the maximum modelled Delta Q",
            transform=ax.transAxes, fontsize=7, color=C_DARK,
            ha="right", va="top", fontstyle="italic")
    ax.text(0.03, 0.04, "Modelled response, not observed discharge",
            transform=ax.transAxes, fontsize=6.5, color=C_GRAY,
            ha="left", va="bottom")

    ax.legend(loc="upper left", frameon=False, fontsize=7)
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")

if __name__ == "__main__":
    main()
