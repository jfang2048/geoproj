"""Atomic figure: Local analytical domain map. One PNG output."""
from __future__ import annotations
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal
from matplotlib.colors import LightSource
from shapely.ops import nearest_points
from scripts.figures.lib.figure_style import apply_style, save_atomic_figure, C_CONSERVATIVE, C_RELAXED, C_UPPER, C_UNDISTURBED, C_BURNED, C_RAINFALL, C_GRAY, C_DARK
from scripts.figures.lib.io import load_vector, outlet_point_utm, LATEX, WORKING_CRS

OUT = LATEX / "fig01c_local_domain.png"

def main() -> None:
    catchment = load_vector("catchment_utm32", "boundary")
    fire = load_vector("monte_martica_fire_2019_utm32", "fire_perimeter")
    streams = load_vector("streams_lombardia_varese_utm32", "hydrography")
    lake = load_vector("lake_varese_boundary", "boundary")
    outlet = outlet_point_utm()
    dem_path = Path(__file__).resolve().parents[2] / "data/processed/dem/dem_utm32.tif"
    dem_streams_path = Path(__file__).resolve().parents[2] / "data/processed/dem/dem_streams_utm32.gpkg"
    dem_streams = gpd.read_file(dem_streams_path).to_crs(WORKING_CRS) if dem_streams_path.exists() else None
    fire_outside = fire.overlay(catchment, how="difference")

    apply_style()
    fig, ax = plt.subplots(figsize=(7.5, 6.5))

    if dem_path.exists():
        ds = gdal.Open(str(dem_path))
        dem = ds.GetRasterBand(1).ReadAsArray()
        ndv = ds.GetRasterBand(1).GetNoDataValue()
        gt = ds.GetGeoTransform()
        extent = [gt[0], gt[0] + gt[1] * ds.RasterXSize, gt[3] + gt[5] * ds.RasterYSize, gt[3]]
        dem_m = np.where((dem == ndv) | np.isnan(dem), np.nan, dem)
        valid = dem_m[~np.isnan(dem_m)]
        ls = LightSource(azdeg=315, altdeg=45)
        hs = ls.hillshade(np.nan_to_num(dem_m, nan=np.median(valid) if len(valid) else 500), vert_exag=2)
        ax.imshow(hs, extent=extent, cmap="Greys", alpha=0.45, zorder=1)
        ax.imshow(dem_m, extent=extent, cmap="terrain", alpha=0.20, zorder=2)
        ds = None

    lake.plot(ax=ax, color=C_RAINFALL, edgecolor="#2B5C8F", linewidth=0.8, alpha=0.75, zorder=3, label="Lake Varese")
    streams.plot(ax=ax, color="#1F78B4", linewidth=0.6, alpha=0.85, zorder=4, label="Official hydrography")
    if dem_streams is not None and len(dem_streams) > 0:
        dem_streams.plot(ax=ax, color="#E31A1C", linewidth=0.7, linestyle="--", alpha=0.6, zorder=4, label="DEM-derived streams")
    catchment.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=1.6, zorder=5, label="Candidate subcatchment")
    fire.plot(ax=ax, facecolor=C_UPPER, alpha=0.22, edgecolor=C_UPPER, linewidth=1.0, zorder=5, label="Official fire perimeter")
    if not fire_outside.empty:
        fire_outside.plot(ax=ax, facecolor="none", edgecolor=C_UPPER, linewidth=0.8, linestyle=":", hatch="///", alpha=0.7, zorder=6, label="Excluded fire (25.5%)")
    ax.scatter(outlet.x, outlet.y, marker="*", s=140, color=C_RELAXED, edgecolor="black", linewidth=0.8, zorder=10, label="Candidate outlet")
    hydro_geom = streams.geometry.union_all()
    nearest_pt = nearest_points(outlet, hydro_geom)[1]
    ax.scatter(nearest_pt.x, nearest_pt.y, marker="s", s=50, color=C_DARK, edgecolor="black", linewidth=0.5, zorder=10, label="Hydro-snapped alternative")

    bounds = catchment.geometry.union_all().union(lake.geometry.union_all()).bounds
    ax.set_xlim(bounds[0] - 800, bounds[2] + 800)
    ax.set_ylim(bounds[1] - 800, bounds[3] + 800)
    ax.set_xlabel("Easting (m, UTM Zone 32N)")
    ax.set_ylabel("Northing (m, UTM Zone 32N)")
    ax.ticklabel_format(style="plain", useOffset=False)

    # Scale bar
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    sb_x, sb_len, n = x0 + 0.72 * (x1 - x0), 2000, 4
    for i in range(n):
        c = "black" if i % 2 == 0 else "white"
        ax.add_patch(plt.Rectangle((sb_x + i * sb_len / n, y0 + 0.07 * (y1 - y0)), sb_len / n, 0.018 * (y1 - y0), facecolor=c, edgecolor="black", linewidth=0.5, zorder=11))
    ax.text(sb_x + sb_len / 2, y0 + 0.095 * (y1 - y0), "2 km", ha="center", fontsize=7, zorder=11)
    ax.legend(loc="upper left", frameon=False, fontsize=6.5, ncol=2)
    fig.tight_layout()
    save_atomic_figure(fig, OUT)
    print(f"  -> {OUT}")

if __name__ == "__main__":
    main()
