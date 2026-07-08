"""Compute Lake Varese NDTI/NDCI rasters from local Sentinel-2 L2A SAFE ZIPs.

Missing local event coverage is recorded as a data limitation. No GEE fallback is
created or used.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rasterio.features import geometry_mask

from lake_wq.config import (
    ROOT,
    ROI_PATH,
    INTERMEDIATE_DIR,
    IMAGE_METADATA_PATH,
    IMAGE_METADATA_COLUMNS,
    QA_COLUMNS,
    WORKING_CRS,
    TARGET_RESOLUTION_M,
    NODATA_FLOAT,
    MIN_VALID_ROI_PIXELS,
)
from lake_wq.io import (
    ensure_lake_wq_dirs,
    load_selected_events,
    write_csv,
    write_remote_sensing_qa,
    clear_raster_metadata_qa,
    append_raster_metadata_rows,
    raster_metadata_row,
)
from lake_wq.s2_safe import SafeProduct, SceneIndices, list_safe_products, read_scene_indices
from pipeline_utils import StepLog, append_run_log, import_geo, register_generated_dataset, update_backlog, write_raster


def event_windows(event_start: Any, event_end: Any) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    start = pd.to_datetime(event_start)
    end = pd.to_datetime(event_end)
    return {
        "pre": (start - pd.Timedelta(days=10), start - pd.Timedelta(days=1)),
        "post_turbidity": (end + pd.Timedelta(days=1), end + pd.Timedelta(days=7)),
        "post_chla": (end + pd.Timedelta(days=3), end + pd.Timedelta(days=14)),
    }


def choose_product(products: list[SafeProduct], start: pd.Timestamp, end: pd.Timestamp) -> SafeProduct | None:
    candidates = [p for p in products if start.strftime("%Y-%m-%d") <= p.acquisition_date <= end.strftime("%Y-%m-%d")]
    if not candidates:
        return None
    center = start + (end - start) / 2
    return sorted(
        candidates,
        key=lambda p: (
            9999.0 if p.cloud_cover_percent is None else p.cloud_cover_percent,
            abs((pd.to_datetime(p.acquisition_date) - center).days),
            p.acquisition_date,
        ),
    )[0]


def _load_rois() -> Any:
    gpd, *_ = import_geo()
    if not ROI_PATH.exists():
        raise FileNotFoundError(f"Missing ROI layer: {ROI_PATH.relative_to(ROOT)}; run compute_rois.py first")
    rois = gpd.read_file(ROI_PATH)
    if rois.empty:
        raise ValueError("Lake WQ ROI layer is empty")
    if rois.crs is None:
        raise ValueError("Lake WQ ROI layer has no CRS metadata")
    rois = rois.to_crs(WORKING_CRS)
    if rois.crs.to_epsg() != 32632:
        raise ValueError("Lake WQ ROI layer is not EPSG:32632 after reprojection")
    if rois.geometry.is_empty.any() or not rois.geometry.is_valid.all():
        raise ValueError("Lake WQ ROI layer contains invalid or empty geometries")
    return rois


def _safe_rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _roi_valid_pixels(scene: SceneIndices, geom: Any, arr: np.ndarray | None = None) -> int:
    target = scene.ndti if arr is None else arr
    mask = geometry_mask([geom], out_shape=target.shape, transform=scene.transform, invert=True)
    return int(np.count_nonzero(mask & scene.valid_mask & np.isfinite(target)))


def _qa_rows_for_scene(event: pd.Series, role: str, scene: SceneIndices, rois: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid_lake = int(scene.metadata.get("valid_lake_pixels", 0))
    for _, roi in rois.iterrows():
        valid_roi = _roi_valid_pixels(scene, roi.geometry)
        if valid_roi < MIN_VALID_ROI_PIXELS:
            flag = "INSUFFICIENT_VALID_PIXELS"
            note = "SCL/reflectance mask left no valid index pixels in this ROI."
        elif valid_lake < MIN_VALID_ROI_PIXELS:
            flag = "INSUFFICIENT_VALID_PIXELS"
            note = "SCL/reflectance mask left no valid lake pixels."
        else:
            flag = "PASS"
            note = "Local Sentinel-2 L2A SAFE image read on 20 m target grid; SCL mask applied where available."
        rows.append(
            {
                "event_id": event.get("event_id", ""),
                "event_start": event.get("event_start", ""),
                "event_end": event.get("event_end", ""),
                "safe_zip": _safe_rel(scene.product.path),
                "image_date": scene.product.acquisition_date,
                "image_role": role,
                "sensor": scene.product.sensor,
                "crs": scene.crs,
                "resolution_m": scene.resolution_m,
                "valid_lake_pixels": valid_lake,
                "roi_name": roi.get("roi_name", ""),
                "valid_roi_pixels": valid_roi,
                "scl_used": bool(scene.metadata.get("scl_used", False)),
                "cloud_mask_note": scene.metadata.get("cloud_mask_note", ""),
                "quality_flag": flag,
                "quality_note": note,
            }
        )
    return rows


def _qa_rows_for_missing(event: pd.Series, role: str, rois: Any, note: str, product: SafeProduct | None = None) -> list[dict[str, Any]]:
    if product is None:
        flag = "MISSING_LOCAL_IMAGE"
        safe_zip = ""
        image_date = ""
        sensor = "Sentinel-2 L2A"
    else:
        flag = "WARN"
        safe_zip = _safe_rel(product.path)
        image_date = product.acquisition_date
        sensor = product.sensor
    return [
        {
            "event_id": event.get("event_id", ""),
            "event_start": event.get("event_start", ""),
            "event_end": event.get("event_end", ""),
            "safe_zip": safe_zip,
            "image_date": image_date,
            "image_role": role,
            "sensor": sensor,
            "crs": WORKING_CRS,
            "resolution_m": TARGET_RESOLUTION_M,
            "valid_lake_pixels": "",
            "roi_name": roi.get("roi_name", ""),
            "valid_roi_pixels": "",
            "scl_used": "",
            "cloud_mask_note": "No local complete pre/post event pair; no fallback to GEE.",
            "quality_flag": flag,
            "quality_note": note,
        }
        for _, roi in rois.iterrows()
    ]


def _write_index(path: Path, arr: np.ndarray, transform: Any) -> None:
    safe = np.where(np.isfinite(arr), arr, NODATA_FLOAT).astype("float32")
    write_raster(path, safe, transform, WORKING_CRS, nodata=NODATA_FLOAT, dtype="float32")


def _write_event_rasters(event_id: str, pre: SceneIndices, post_t: SceneIndices, post_c: SceneIndices) -> list[Path]:
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        f"event_{event_id}_pre_ndti.tif": (pre.ndti, pre.transform, "ndti", "pre"),
        f"event_{event_id}_post_ndti.tif": (post_t.ndti, post_t.transform, "ndti", "post_turbidity"),
        f"event_{event_id}_delta_ndti.tif": (post_t.ndti - pre.ndti, pre.transform, "delta_ndti", "delta"),
        f"event_{event_id}_pre_ndci.tif": (pre.ndci, pre.transform, "ndci", "pre"),
        f"event_{event_id}_post_ndci.tif": (post_c.ndci, post_c.transform, "ndci", "post_chla"),
        f"event_{event_id}_delta_ndci.tif": (post_c.ndci - pre.ndci, pre.transform, "delta_ndci", "delta"),
    }
    written: list[Path] = []
    qa_rows: list[dict[str, Any]] = []
    for name, (arr, transform, index_name, image_role) in outputs.items():
        path = INTERMEDIATE_DIR / name
        _write_index(path, arr, transform)
        written.append(path)
        qa_rows.append(raster_metadata_row(path, event_id, index_name, image_role))
    append_raster_metadata_rows(qa_rows)
    return written


def _grids_match(*scenes: SceneIndices) -> bool:
    first = scenes[0]
    for scene in scenes[1:]:
        if scene.crs != first.crs:
            return False
        if scene.ndti.shape != first.ndti.shape:
            return False
        if tuple(scene.transform) != tuple(first.transform):
            return False
    return True


def _clear_stale_rasters() -> None:
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    for pattern in ["event_*_ndti.tif", "event_*_ndci.tif", "event_*_delta_*.tif", "event_*_pre_*.tif", "event_*_post_*.tif"]:
        for path in INTERMEDIATE_DIR.glob(pattern):
            if path.is_file():
                path.unlink()


def compute_s2_indices() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_lake_wq_dirs()
    _clear_stale_rasters()
    clear_raster_metadata_qa()
    events = load_selected_events()
    rois = _load_rois()
    lake_geom = rois.loc[rois["roi_name"] == "whole_lake"].geometry.iloc[0]
    lake_bounds = tuple(float(x) for x in rois.loc[rois["roi_name"] == "whole_lake"].total_bounds)
    products = list_safe_products()
    qa_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    complete_events = 0

    archive_dates = [p.acquisition_date for p in products]
    archive_note = ""
    if archive_dates:
        archive_note = f" Local SAFE archive date range: {min(archive_dates)} to {max(archive_dates)}."
    else:
        archive_note = " No local Sentinel-2 L2A SAFE ZIPs were found under data/raw/zip/."

    for _, event in events.iterrows():
        event_id = str(event["event_id"])
        windows = event_windows(event["event_start"], event["event_end"])
        chosen = {role: choose_product(products, start, end) for role, (start, end) in windows.items()}
        missing_roles = [role for role, product in chosen.items() if product is None]
        base_meta = {
            "event_id": event_id,
            "event_start": event.get("event_start", ""),
            "event_end": event.get("event_end", ""),
            "image_pre_date": chosen["pre"].acquisition_date if chosen["pre"] else "",
            "image_post_turbidity_date": chosen["post_turbidity"].acquisition_date if chosen["post_turbidity"] else "",
            "image_post_chla_date": chosen["post_chla"].acquisition_date if chosen["post_chla"] else "",
            "pre_safe_zip": _safe_rel(chosen["pre"].path) if chosen["pre"] else "",
            "post_turbidity_safe_zip": _safe_rel(chosen["post_turbidity"].path) if chosen["post_turbidity"] else "",
            "post_chla_safe_zip": _safe_rel(chosen["post_chla"].path) if chosen["post_chla"] else "",
        }
        if missing_roles:
            missing_text = "; ".join(
                f"{role} window {windows[role][0].strftime('%Y-%m-%d')} to {windows[role][1].strftime('%Y-%m-%d')}"
                for role in missing_roles
            )
            note = f"No suitable local Sentinel-2 L2A SAFE ZIP for {missing_text}.{archive_note} Reported as data limitation; no GEE fallback."
            for role in ["pre", "post_turbidity", "post_chla"]:
                product = chosen[role]
                role_note = note if product is None else "Image exists for this role, but no complete event pre/post set exists; no rasters generated. No GEE fallback."
                qa_rows.extend(_qa_rows_for_missing(event, role, rois, role_note, product=product if product is not None and missing_roles else None))
            metadata_rows.append({**base_meta, "quality_flag": "MISSING_LOCAL_IMAGE", "quality_note": note})
            continue

        try:
            pre = read_scene_indices(chosen["pre"], lake_geom, lake_bounds)  # type: ignore[arg-type]
            post_t = read_scene_indices(chosen["post_turbidity"], lake_geom, lake_bounds)  # type: ignore[arg-type]
            post_c = read_scene_indices(chosen["post_chla"], lake_geom, lake_bounds)  # type: ignore[arg-type]
            if not _grids_match(pre, post_t, post_c):
                raise ValueError("Selected local SAFE windows have incompatible CRS/shape/transform; no silent resampling")
            written = _write_event_rasters(event_id, pre, post_t, post_c)
            complete_events += 1
            qa_rows.extend(_qa_rows_for_scene(event, "pre", pre, rois))
            qa_rows.extend(_qa_rows_for_scene(event, "post_turbidity", post_t, rois))
            qa_rows.extend(_qa_rows_for_scene(event, "post_chla", post_c, rois))
            metadata_rows.append({**base_meta, "quality_flag": "PASS", "quality_note": f"Generated {len(written)} local NDTI/NDCI rasters on 20 m grid."})
        except Exception as exc:
            note = f"Local SAFE read/index computation failed for event {event_id}: {type(exc).__name__}: {exc}. No GEE fallback."
            for role in ["pre", "post_turbidity", "post_chla"]:
                qa_rows.extend(_qa_rows_for_missing(event, role, rois, note, product=None))
            metadata_rows.append({**base_meta, "quality_flag": "FAIL", "quality_note": note})

    qa = pd.DataFrame(qa_rows, columns=QA_COLUMNS)
    metadata = pd.DataFrame(metadata_rows, columns=IMAGE_METADATA_COLUMNS)
    write_remote_sensing_qa(qa)
    write_csv(IMAGE_METADATA_PATH, metadata, IMAGE_METADATA_COLUMNS)
    register_generated_dataset(
        "lake_wq_event_image_metadata",
        "Lake water-quality Sentinel-2 local image metadata",
        "lake_water_quality_remote_sensing_metadata",
        IMAGE_METADATA_PATH,
        "processed",
        crs="n/a",
        notes="Python-only local SAFE image selection metadata for selected runoff events; no GEE fallback.",
    )
    status = "DONE" if complete_events else "PARTIAL"
    reason = (
        f"Generated NDTI/NDCI rasters for {complete_events} event(s)."
        if complete_events
        else "No complete selected-event local Sentinel-2 pre/post image pairs; QA records MISSING_LOCAL_IMAGE."
    )
    update_backlog({"F017": status}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/compute_s2_indices.py",
            task="Compute local Sentinel-2 NDTI/NDCI rasters for selected lake-response events.",
            inputs=[str(ROI_PATH.relative_to(ROOT)), str(IMAGE_METADATA_PATH.relative_to(ROOT))],
            outputs=[str(INTERMEDIATE_DIR.relative_to(ROOT)), str(IMAGE_METADATA_PATH.relative_to(ROOT)), str((ROOT / 'qa/spatial/lake_wq_remote_sensing_qa.csv').relative_to(ROOT))],
            status=status,
            reason=reason,
            files_created=[str(IMAGE_METADATA_PATH.relative_to(ROOT)), "qa/spatial/lake_wq_remote_sensing_qa.csv", "outputs/qa/lake_wq_remote_sensing_qa.csv"],
            qa_checks=["20 m target grid documented", "SCL cloud mask when available", "missing local imagery recorded as MISSING_LOCAL_IMAGE", "no GEE fallback"],
            next_action="Run compute_zonal_anomalies.py.",
        )
    )
    print(f"Local SAFE products found: {len(products)}")
    if products:
        print("SAFE dates:", ", ".join(p.acquisition_date for p in products))
    print(f"Complete local event pairs: {complete_events}/{len(events)}")
    print(f"QA rows: {len(qa)} -> qa/spatial/lake_wq_remote_sensing_qa.csv and outputs/qa/lake_wq_remote_sensing_qa.csv")
    return metadata, qa


def main() -> int:
    compute_s2_indices()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
