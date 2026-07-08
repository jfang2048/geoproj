"""Atomic figure: WEPPcloud sediment discharge comparison. One PNG output."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import matplotlib.pyplot as plt
from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_UNDISTURBED, C_BURNED
from scripts.figures.lib.io import LATEX

OUT = LATEX / "fig09_weppcloud_sediment.png"

def main() -> None:
    labels = ["Undisturbed\nBaseline", "Burned\nScenario"]
    sediment = [293.0, 652.6]
    colors = [C_UNDISTURBED, C_BURNED]

    apply_style()
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    bars = ax.bar(labels, sediment, color=colors, width=0.4)
    ax.set_ylabel("Sediment discharge (tonne/yr)")
    for bar, val in zip(bars, sediment):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 12, f"{val:.0f}", ha="center", fontsize=9, fontweight="bold")
    ax.text(0.5, max(sediment) * 1.10, "+122.7%", ha="center", fontweight="bold", fontsize=10, color=C_BURNED)
    ax.set_ylim(0, max(sediment) * 1.18)
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")

if __name__ == "__main__":
    main()
