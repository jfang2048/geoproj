"""Utilities for reading project-owner supplied raw ZIP datasets without modifying them."""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image
from rasterio.transform import Affine

from pipeline_utils import ROOT, RAW_ZIP_DIR, WORKING_CRS

FIRE_ZIP = RAW_ZIP_DIR / "Aree_percorse_dal_fuoco_REGIONE_LOMBARDIA.zip"
DUSAF_ZIP = RAW_ZIP_DIR / "DUSAF6_REGIONE_LOMBARDIA.zip"
HYDRO_ZIP = RAW_ZIP_DIR / "reticolo_idrografico_regionale_unificato.zip"
DTM_ZIP = RAW_ZIP_DIR / "DTM5_RL.zip"
AOI_GPKG_UTM = RAW_ZIP_DIR / "lake_varese_monte_martica_processing_aoi_files/lake_varese_monte_martica_processing_aoi_utm32n.gpkg"
SOIL_DIR = RAW_ZIP_DIR / "soilgrids_lake_varese"


def zip_shp_uri(zip_path: Path, shp_name: str) -> str:
    return f"zip://{zip_path.resolve()}!{shp_name}"


def dtm_vsi_path() -> str:
    return f"/vsizip/{DTM_ZIP.resolve()}/DTM5_RL.img"


def weather_zips() -> list[Path]:
    return sorted(RAW_ZIP_DIR.glob("RW_*.zip"))


def sentinel_zips() -> list[Path]:
    return sorted(RAW_ZIP_DIR.glob("S2*_MSIL2A_*.SAFE.zip"))


def date_from_s2_name(path: Path) -> str:
    match = re.search(r"MSIL2A_(\d{8})T", path.name)
    return match.group(1) if match else ""


def role_for_s2(path: Path) -> str:
    date = date_from_s2_name(path)
    if date and date <= "20190102":
        return "pre_fire"
    return "post_fire"


def choose_s2_pair() -> tuple[Path | None, Path | None]:
    pre = [p for p in sentinel_zips() if role_for_s2(p) == "pre_fire"]
    post = [p for p in sentinel_zips() if role_for_s2(p) == "post_fire"]
    # Closest pre-fire product at/under 2019-01-02; earliest post-fire product after 2019-01-08.
    pre_choice = sorted(pre, key=lambda p: date_from_s2_name(p), reverse=True)[0] if pre else None
    post_choice = sorted(post, key=lambda p: date_from_s2_name(p))[0] if post else None
    return pre_choice, post_choice


def read_zip_text(zip_path: Path, suffix: str) -> tuple[str, str]:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(suffix)]
        if not names:
            raise FileNotFoundError(f"No member ending {suffix} in {zip_path}")
        name = names[0]
        return name, zf.read(name).decode("utf-8", "ignore")


def s2_cloud_cover(zip_path: Path) -> float | None:
    try:
        _, text = read_zip_text(zip_path, "MTD_MSIL2A.xml")
        match = re.search(r"<Cloud_Coverage_Assessment>([^<]+)", text)
        return float(match.group(1)) if match else None
    except Exception:
        return None


@dataclass(frozen=True)
class S2Grid:
    crs: str
    transform_20m: Affine
    nrows20: int
    ncols20: int


def s2_grid(zip_path: Path) -> S2Grid:
    _, text = read_zip_text(zip_path, "MTD_TL.xml")
    root = ET.fromstring(text)
    crs = root.findtext(".//HORIZONTAL_CS_CODE") or WORKING_CRS
    nrows = ncols = None
    ulx = uly = xdim = ydim = None
    for size in root.findall(".//Size"):
        if size.attrib.get("resolution") == "20":
            nrows = int(size.findtext("NROWS"))
            ncols = int(size.findtext("NCOLS"))
    for geo in root.findall(".//Geoposition"):
        if geo.attrib.get("resolution") == "20":
            ulx = float(geo.findtext("ULX"))
            uly = float(geo.findtext("ULY"))
            xdim = float(geo.findtext("XDIM"))
            ydim = float(geo.findtext("YDIM"))
    if None in {nrows, ncols, ulx, uly, xdim, ydim}:
        raise ValueError(f"Could not parse 20 m geocoding from {zip_path}")
    return S2Grid(crs=crs, transform_20m=Affine.translation(ulx, uly) * Affine.scale(xdim, ydim), nrows20=nrows, ncols20=ncols)


def window_from_bounds_20m(grid: S2Grid, bounds: tuple[float, float, float, float], pad: int = 8) -> tuple[int, int, int, int, Affine]:
    xmin, ymin, xmax, ymax = bounds
    ulx = grid.transform_20m.c
    uly = grid.transform_20m.f
    xres = grid.transform_20m.a
    yres = abs(grid.transform_20m.e)
    col0 = max(0, int(np.floor((xmin - ulx) / xres)) - pad)
    col1 = min(grid.ncols20, int(np.ceil((xmax - ulx) / xres)) + pad)
    row0 = max(0, int(np.floor((uly - ymax) / yres)) - pad)
    row1 = min(grid.nrows20, int(np.ceil((uly - ymin) / yres)) + pad)
    transform = grid.transform_20m * Affine.translation(col0, row0)
    return row0, row1, col0, col1, transform


def s2_member(zip_path: Path, band: str, resolution: int) -> str:
    suffix = f"_{band}_{resolution}m.jp2"
    with zipfile.ZipFile(zip_path) as zf:
        matches = [n for n in zf.namelist() if "/IMG_DATA/" in n and n.endswith(suffix)]
        if not matches:
            raise FileNotFoundError(f"No Sentinel-2 member {suffix} in {zip_path.name}")
        return matches[0]


def read_s2_band_window(zip_path: Path, band: str, row0: int, row1: int, col0: int, col1: int) -> np.ndarray:
    """Read a 20 m target-grid window. B08 is cropped at 10 m then mean-downsampled."""
    if band == "B08":
        member = s2_member(zip_path, band, 10)
        crop = (col0 * 2, row0 * 2, col1 * 2, row1 * 2)
        with zipfile.ZipFile(zip_path) as zf:
            img = Image.open(BytesIO(zf.read(member)))
            arr = np.array(img.crop(crop), dtype="float32")
        h = (arr.shape[0] // 2) * 2
        w = (arr.shape[1] // 2) * 2
        arr = arr[:h, :w].reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
        return arr.astype("float32")
    member = s2_member(zip_path, band, 20)
    crop = (col0, row0, col1, row1)
    with zipfile.ZipFile(zip_path) as zf:
        img = Image.open(BytesIO(zf.read(member)))
        return np.array(img.crop(crop), dtype="float32")
