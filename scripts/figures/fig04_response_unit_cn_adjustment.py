"""Atomic figure: burned response-unit CN-adjustment area summary.

Single-purpose bar chart summarising the burned response units only. The map of
where those units occur is generated separately by ``fig03_response_units_cn.py``.
"""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import geopandas as gpd
import matplotlib.pyplot as plt

from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_DARK
from scripts.figures.lib.io import LATEX, WORKING_CRS, PROCESSED

OUT = LATEX / "fig04_response_unit_cn_adjustment.png"

CN_CLASS_COLORS = {3: "#fdd49e", 4: "#fdcc8a", 8: "#fc8d59", 12: "#d7301f"}

LC_NAMES = {
    "forest": "Forest",
    "shrub": "Shrub",
    "grassland": "Grassland",
    "agriculture": "Agriculture",
    "urban": "Urban",
    "water": "Water",
}
BURN_NAMES = {0: "Unburned", 1: "Low severity", 2: "Moderate severity", 3: "High severity"}


def burned_unit_summary(units: gpd.GeoDataFrame):
    grouped = units.groupby(["landcover_class", "burn_class"], dropna=False)["area_m2"].sum().reset_index()
    grouped["area_ha"] = grouped["area_m2"] / 10000.0

    def cn_delta(row) -> float:
        mask = (
            (units["landcover_class"] == row["landcover_class"])
            & (units["burn_class"] == row["burn_class"])
        )
        return float(units.loc[mask, "burned_parameter"].mean() - units.loc[mask, "baseline_parameter"].mean())

    grouped["cn_delta_avg"] = grouped.apply(cn_delta, axis=1)
    return grouped[grouped["cn_delta_avg"] > 0].sort_values(
        ["cn_delta_avg", "area_ha"], ascending=[True, True]
    )


def main() -> None:
    ru_path = PROCESSED / "model_inputs" / "runoff_units.gpkg"
    units = gpd.read_file(ru_path).to_crs(WORKING_CRS)
    burned_only = burned_unit_summary(units)

    labels = [
        f"{LC_NAMES.get(r.landcover_class, r.landcover_class)}\n{BURN_NAMES.get(int(r.burn_class), '')}"
        for r in burned_only.itertuples()
    ]
    colors = [CN_CLASS_COLORS.get(int(round(v)), "#cccccc") for v in burned_only["cn_delta_avg"].to_numpy(float)]

    apply_style()
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    y_pos = range(len(burned_only))
    ax.barh(
        y_pos,
        burned_only["area_ha"].to_numpy(float),
        height=0.62,
        color=colors,
        edgecolor="black",
        linewidth=0.25,
    )
    for i, (_, row) in enumerate(burned_only.iterrows()):
        area_label = f"{row['area_ha']:.1f} ha" if row["area_ha"] < 1 else f"{row['area_ha']:.0f} ha"
        ax.text(
            row["area_ha"] + 0.35,
            i,
            f"{area_label}, CN +{row['cn_delta_avg']:.0f}",
            va="center",
            fontsize=7,
            color=C_DARK,
        )
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Area (ha)")
    ax.set_title("Burned response units by CN adjustment", fontweight="bold")
    ax.set_xlim(0, max(12.0, float(burned_only["area_ha"].max()) * 1.22))
    ax.invert_yaxis()
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
