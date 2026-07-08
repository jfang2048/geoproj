"""Atomic figure: Sensitivity hierarchy tornado/range plot. One PNG output."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import matplotlib.pyplot as plt
from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_CONSERVATIVE, C_UPPER, C_UNDISTURBED
from scripts.figures.lib.io import load_table, LATEX

OUT = LATEX / "fig08_sensitivity_hierarchy.png"

def main() -> None:
    burn = load_table("burn_severity_ensemble_summary")
    burn_range = (burn["max_runoff_delta_mm"].min(), burn["max_runoff_delta_mm"].max())
    index = load_table("burn_index_sensitivity_summary")
    index_range = (index["max_runoff_delta_mm"].min(), index["max_runoff_delta_mm"].max())
    rain = load_table("rainfall_station_sensitivity")
    rain_range = (rain["maximum_modelled_runoff_delta_mm"].min(), rain["maximum_modelled_runoff_delta_mm"].max())
    soil = load_table("soil_hsg_ensemble_summary")
    soil = soil[soil["burn_definition"] == "current_conservative"]
    soil_range = (soil["max_runoff_delta_mm"].min(), soil["max_runoff_delta_mm"].max())
    ia = load_table("scs_initial_abstraction_sensitivity")
    ia_max = ia.groupby("lambda")["delta_mm"].max()
    ia_range = (ia_max.min(), ia_max.max())

    categories = ["Burned footprint", "Burn index", "Rainfall station/IDW", "Initial abstraction", "Soil/HSG-CN"]
    ranges = [burn_range, index_range, rain_range, ia_range, soil_range]

    apply_style()
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    y = np.arange(len(categories))
    for iy, (lo, hi) in enumerate(ranges):
        ax.plot([lo, hi], [iy, iy], color=C_UNDISTURBED, linewidth=4, solid_capstyle="round")
        ax.scatter([lo, hi], [iy, iy], color=[C_CONSERVATIVE, C_UPPER], s=28, zorder=3)
        ax.text(hi + 0.06, iy, f"{lo:.3f}–{hi:.3f}", va="center", fontsize=7)

    ax.set_yticks(y, categories)
    ax.invert_yaxis()
    ax.set_xlabel("Max modelled runoff-potential ΔQ (mm)")
    ax.set_xlim(left=0)
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")

if __name__ == "__main__":
    main()
