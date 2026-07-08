"""Read local Sentinel-2 L2A SAFE ZIP files for lake WQ proxy indices.

The workflow uses a documented 20 m target grid: B5 and SCL are native 20 m,
and B3/B4 are read from SAFE R20m products when present. If a SAFE archive lacks
R20m B3/B4, 10 m B3/B4 are downsampled to the 20 m target window with bilinear
resampling because they are continuous reflectance bands. Categorical SCL is
never resampled with bilinear/cubic.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

import numpy as np
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.transform import Affine

from lake_wq.config import (
    RAW_SAFE_GLOB,
    WORKING_CRS,
    TARGET_RESOLUTION_M,
    CLEAR_SCL_CLASSES,
    WATER_SCL_CLASS,
)


@dataclass(frozen=True)
class SafeProduct:
    path: Path
    acquisition_date: str
    sensor: str
    cloud_cover_percent: float | None


@dataclass(frozen=True)
class S2Grid:
    crs: str
    transform_20m: Affine
    nrows20: int
    ncols20: int


@dataclass
class SceneIndices:
    product: SafeProduct
    ndti: np.ndarray
    ndci: np.ndarray
    scl: np.ndarray | None
    valid_mask: np.ndarray
    lake_mask: np.ndarray
    transform: Affine
    crs: str
    resolution_m: int
    metadata: dict[str, Any]


def find_safe_zips(search_dir: Path = RAW_SAFE_GLOB) -> list[Path]:
    """Find local Sentinel-2 L2A SAFE ZIPs without modifying `data/raw/`."""
    return sorted(search_dir.glob("*.SAFE.zip"))


def parse_acquisition_date(path: Path | str) -> str | None:
    """Parse YYYY-MM-DD acquisition date from Sentinel-2 filename."""
    name = Path(path).name
    match = re.search(r"MSIL2A_(\d{8})T", name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _read_zip_text(zip_path: Path, suffix: str) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        matches = [n for n in zf.namelist() if n.endswith(suffix)]
        if not matches:
            raise FileNotFoundError(f"No member ending {suffix} in {zip_path.name}")
        return zf.read(matches[0]).decode("utf-8", "ignore")


def _cloud_cover(zip_path: Path) -> float | None:
    try:
        text = _read_zip_text(zip_path, "MTD_MSIL2A.xml")
        match = re.search(r"<Cloud_Coverage_Assessment>([^<]+)", text)
        return float(match.group(1)) if match else None
    except Exception:
        return None


def list_safe_products(search_dir: Path = RAW_SAFE_GLOB) -> list[SafeProduct]:
    products: list[SafeProduct] = []
    for path in find_safe_zips(search_dir):
        date = parse_acquisition_date(path)
        if date is None:
            continue
        sensor = path.name.split("_")[0]
        products.append(SafeProduct(path=path, acquisition_date=date, sensor=sensor, cloud_cover_percent=_cloud_cover(path)))
    return sorted(products, key=lambda p: p.acquisition_date)


def sentinel2_grid(zip_path: Path) -> S2Grid:
    """Parse the SAFE 20 m grid from tile metadata."""
    text = _read_zip_text(zip_path, "MTD_TL.xml")
    root = ET.fromstring(text)
    crs = root.findtext(".//HORIZONTAL_CS_CODE") or WORKING_CRS
    nrows = ncols = None
    ulx = uly = xdim = ydim = None
    for size in root.findall(".//Size"):
        if size.attrib.get("resolution") == str(TARGET_RESOLUTION_M):
            nrows = int(size.findtext("NROWS"))
            ncols = int(size.findtext("NCOLS"))
    for geo in root.findall(".//Geoposition"):
        if geo.attrib.get("resolution") == str(TARGET_RESOLUTION_M):
            ulx = float(geo.findtext("ULX"))
            uly = float(geo.findtext("ULY"))
            xdim = float(geo.findtext("XDIM"))
            ydim = float(geo.findtext("YDIM"))
    if None in {nrows, ncols, ulx, uly, xdim, ydim}:
        raise ValueError(f"Could not parse 20 m geocoding from {zip_path.name}")
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
    if row1 <= row0 or col1 <= col0:
        raise ValueError("Requested lake bounds do not overlap Sentinel-2 20 m tile grid")
    transform = grid.transform_20m * Affine.translation(col0, row0)
    return row0, row1, col0, col1, transform


def find_measurement_member(zip_path: Path, band: str, resolution_m: int) -> str | None:
    suffix = f"_{band}_{resolution_m}m.jp2"
    with zipfile.ZipFile(zip_path) as zf:
        matches = [n for n in zf.namelist() if "/IMG_DATA/" in n and n.endswith(suffix)]
    return sorted(matches)[0] if matches else None


def _read_member_array(zip_path: Path, member: str, crop: tuple[int, int, int, int]) -> np.ndarray:
    with zipfile.ZipFile(zip_path) as zf:
        img = Image.open(BytesIO(zf.read(member)))
        return np.array(img.crop(crop))


def read_band_on_20m_grid(zip_path: Path, band: str, row0: int, row1: int, col0: int, col1: int) -> tuple[np.ndarray, str]:
    """Read one band on the 20 m target grid.

    Continuous reflectance bands use SAFE R20m members when present. If B3/B4
    R20m members are absent, the 10 m member is cropped and bilinearly
    downsampled to the 20 m target window. SCL is categorical and must be read
    from native 20 m only.
    """
    width = col1 - col0
    height = row1 - row0
    member20 = find_measurement_member(zip_path, band, TARGET_RESOLUTION_M)
    if member20 is not None:
        arr = _read_member_array(zip_path, member20, (col0, row0, col1, row1))
        return arr, "native_or_SAFE_R20m"
    if band == "SCL":
        raise FileNotFoundError(f"No native 20 m SCL member in {zip_path.name}")
    member10 = find_measurement_member(zip_path, band, 10)
    if member10 is None:
        raise FileNotFoundError(f"No {band} 20 m or 10 m member in {zip_path.name}")
    with zipfile.ZipFile(zip_path) as zf:
        img = Image.open(BytesIO(zf.read(member10)))
        crop10 = img.crop((col0 * 2, row0 * 2, col1 * 2, row1 * 2))
        resampling = getattr(Image, "Resampling", Image).BILINEAR
        down = crop10.resize((width, height), resample=resampling)
        return np.array(down), "10m_to_20m_bilinear"


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.full(numerator.shape, np.nan, dtype="float32")
    mask = valid & np.isfinite(numerator) & np.isfinite(denominator) & (denominator != 0)
    out[mask] = (numerator[mask] / denominator[mask]).astype("float32")
    return out


def read_scene_indices(product: SafeProduct, lake_geom: Any, bounds: tuple[float, float, float, float]) -> SceneIndices:
    """Read B3/B4/B5/SCL from a local SAFE ZIP and compute NDTI/NDCI.

    Returned arrays are clipped/masked to the supplied Lake Varese geometry on a
    20 m EPSG:32632 grid.
    """
    grid = sentinel2_grid(product.path)
    if grid.crs.upper() != WORKING_CRS.upper() and not grid.crs.upper().endswith("32632"):
        raise ValueError(f"Sentinel-2 tile CRS {grid.crs} is not {WORKING_CRS}; no silent reprojection is allowed")
    row0, row1, col0, col1, transform = window_from_bounds_20m(grid, bounds, pad=8)
    b3, b3_source = read_band_on_20m_grid(product.path, "B03", row0, row1, col0, col1)
    b4, b4_source = read_band_on_20m_grid(product.path, "B04", row0, row1, col0, col1)
    b5, b5_source = read_band_on_20m_grid(product.path, "B05", row0, row1, col0, col1)
    try:
        scl, scl_source = read_band_on_20m_grid(product.path, "SCL", row0, row1, col0, col1)
        scl = scl.astype("uint8")
        scl_used = True
        clear_mask = np.isin(scl, list(CLEAR_SCL_CLASSES))
    except FileNotFoundError:
        scl = None
        scl_source = "missing"
        scl_used = False
        clear_mask = np.ones(b5.shape, dtype=bool)

    b3 = b3.astype("float32")
    b4 = b4.astype("float32")
    b5 = b5.astype("float32")
    h = min(b3.shape[0], b4.shape[0], b5.shape[0], clear_mask.shape[0])
    w = min(b3.shape[1], b4.shape[1], b5.shape[1], clear_mask.shape[1])
    b3, b4, b5, clear_mask = b3[:h, :w], b4[:h, :w], b5[:h, :w], clear_mask[:h, :w]
    scl = scl[:h, :w] if scl is not None else None
    lake_mask = geometry_mask([lake_geom], out_shape=(h, w), transform=transform, invert=True)
    valid = lake_mask & clear_mask & (b3 > 0) & (b4 > 0) & (b5 > 0)
    ndti = _safe_divide(b4 - b3, b4 + b3, valid)
    ndci = _safe_divide(b5 - b4, b5 + b4, valid)
    metadata = {
        "safe_zip": str(product.path),
        "safe_name": product.path.name,
        "image_date": product.acquisition_date,
        "sensor": product.sensor,
        "cloud_cover_percent": product.cloud_cover_percent,
        "target_resolution_m": TARGET_RESOLUTION_M,
        "chosen_resolution_note": "20 m target grid; B5/SCL native 20 m; B3/B4 SAFE R20m preferred, bilinear 10→20 m fallback only if needed.",
        "b3_source": b3_source,
        "b4_source": b4_source,
        "b5_source": b5_source,
        "scl_source": scl_source,
        "scl_used": scl_used,
        "cloud_mask_note": "SCL classes 4,5,6,7 retained; cloud shadow/cloud/cirrus/snow/no-data classes excluded." if scl_used else "SCL missing; no categorical cloud mask was applied.",
        "water_scl_pixels": int(np.count_nonzero(lake_mask & (scl == WATER_SCL_CLASS))) if scl is not None else "",
        "valid_lake_pixels": int(np.count_nonzero(lake_mask & valid & np.isfinite(ndti))),
    }
    return SceneIndices(
        product=product,
        ndti=ndti,
        ndci=ndci,
        scl=scl,
        valid_mask=valid,
        lake_mask=lake_mask,
        transform=transform,
        crs=WORKING_CRS,
        resolution_m=TARGET_RESOLUTION_M,
        metadata=metadata,
    )
