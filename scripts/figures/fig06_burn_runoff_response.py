"""Atomic figure: maximum modelled runoff response by burned-footprint scenario."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib.pyplot as plt

from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_CONSERVATIVE, C_RELAXED, C_UPPER, C_DARK
from scripts.figures.lib.io import load_table, LATEX

OUT = LATEX / "fig06_burn_runoff_response.png"
SCENARIO_LABELS = {
    "conservative_dnbr_proxy": "Conservative dNBR",
    "relaxed_dnbr_proxy": "Relaxed dNBR",
    "official_fire_perimeter_upper_bound": "Official perimeter\nupper bound",
}
SCENARIO_COLORS = {
    "conservative_dnbr_proxy": C_CONSERVATIVE,
    "relaxed_dnbr_proxy": C_RELAXED,
    "official_fire_perimeter_upper_bound": C_UPPER,
}
ORDER = list(SCENARIO_LABELS)


def main() -> None:
    ensemble = load_table("burn_severity_ensemble_summary")
    data = ensemble[ensemble["scenario"].isin(ORDER)].copy()
    data["scenario"] = data["scenario"].astype(str)
    data["order"] = data["scenario"].map({name: i for i, name in enumerate(ORDER)})
    data = data.sort_values("order")

    labels = [SCENARIO_LABELS[s] for s in data["scenario"]]
    colors = [SCENARIO_COLORS[s] for s in data["scenario"]]
    values = data["max_runoff_delta_mm"].to_numpy(float)

    apply_style()
    fig, ax = plt.subplots(figsize=(5.8, 3.3))
    bars = ax.barh(labels, values, color=colors, edgecolor="black", linewidth=0.25)
    for bar, value in zip(bars, values):
        ax.text(value + 0.08, bar.get_y() + bar.get_height() / 2, f"{value:.3g} mm", va="center", fontsize=7, color=C_DARK)
    ax.set_xlabel("Maximum modelled event ΔQ (mm)")
    ax.set_xlim(0, max(values) * 1.18)
    ax.invert_yaxis()
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
