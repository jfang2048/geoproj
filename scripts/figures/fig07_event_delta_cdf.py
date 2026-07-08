"""Atomic figure: Empirical CDF of event-scale ΔQ. One PNG output."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import matplotlib.pyplot as plt
from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_CONSERVATIVE, C_RELAXED, C_UPPER
from scripts.figures.lib.io import load_table, LATEX

OUT = LATEX / "fig07_event_delta_cdf.png"

def main() -> None:
    deltas = load_table("runoff_delta_by_event")
    col = "delta_runoff_mm"
    vals = deltas[col].dropna().sort_values()
    n = len(vals)
    pct_lt_005 = (vals < 0.05).mean() * 100

    ensemble = load_table("burn_severity_ensemble_summary")

    apply_style()
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    cdf = np.arange(1, n + 1) / n
    ax.plot(vals, cdf, color=C_CONSERVATIVE, linewidth=1.8, label=f"Conservative dNBR (n={n})")
    ax.axvline(vals.max(), color=C_CONSERVATIVE, linestyle="--", alpha=0.4, linewidth=0.8, label=f"Max: {vals.max():.3f} mm")
    ax.axvline(0.05, color="gray", linestyle=":", alpha=0.3, linewidth=0.6)
    ax.text(0.05, 0.15, f"{pct_lt_005:.0f}% < 0.05 mm", fontsize=7, color="gray", rotation=90, va="bottom")

    for _, row in ensemble.iterrows():
        s, m = row.get("scenario", ""), row["max_runoff_delta_mm"]
        if "relaxed" in str(s).lower():
            ax.axvline(m, color=C_RELAXED, linestyle=":", alpha=0.5, linewidth=0.8, label=f"Relaxed: {m:.3f}")
        elif "perimeter" in str(s).lower() or "upper" in str(s).lower():
            ax.axvline(m, color=C_UPPER, linestyle=":", alpha=0.5, linewidth=0.8, label=f"Upper bound: {m:.3f}")

    ax.set_xlabel("Event ΔQ (mm)")
    ax.set_ylabel("Cumulative fraction")
    ax.legend(fontsize=6, loc="lower right")
    ax.set_xlim(left=0)
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")

if __name__ == "__main__":
    main()
