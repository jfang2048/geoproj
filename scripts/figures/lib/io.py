"""Shared I/O helpers for atomic figure scripts. Loads data; generates no figures."""
from __future__ import annotations

from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from pyproj import Transformer

try:
    from pipeline_utils import ROOT, WORKING_CRS, WGS84, OUTLET_LON, OUTLET_LAT
except ModuleNotFoundError:
    from scripts.pipeline_utils import ROOT, WORKING_CRS, WGS84, OUTLET_LON, OUTLET_LAT

TABLES = ROOT / "outputs" / "tables"
PROCESSED = ROOT / "data" / "processed"
LATEX = ROOT / "latex"


def load_vector(name: str, subdir: str = "boundary") -> gpd.GeoDataFrame:
    """Load a processed vector layer in EPSG:32632."""
    return gpd.read_file(PROCESSED / subdir / f"{name}.gpkg").to_crs(WORKING_CRS)


def load_table(name: str) -> pd.DataFrame:
    """Load a CSV table from outputs/tables/."""
    return pd.read_csv(TABLES / f"{name}.csv")


def outlet_point_utm() -> Point:
    t = Transformer.from_crs(WGS84, WORKING_CRS, always_xy=True)
    return Point(*t.transform(OUTLET_LON, OUTLET_LAT))
