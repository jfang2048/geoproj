"""Compute ROI zonal statistics for local Sentinel-2 NDTI/NDCI anomaly rasters."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from lake_wq.config import (
    ROOT,
    ROI_PATH,
    INTERMEDIATE_DIR,
    IMAGE_METADATA_PATH,
    IMAGE_METADATA_COLUMNS,
    ANOMALIES_PATH,
    ANOMALY_COLUMNS,
    WORKING_CRS,
)
from lake_wq.io import ensure_lake_wq_dirs, load_selected_events, write_csv
from pipeline_utils import StepLog, append_run_log, import_geo, register_generated_dataset, update_backlog


def _load_rois() -> Any:
    gpd, *_ = import_geo()
    if not ROI_PATH.exists():
        raise FileNotFoundError(f"Missing ROI layer: {ROI_PATH.relative_to(ROOT)}")
    rois = gpd.read_file(ROI_PATH)
    if rois.empty:
        raise ValueError("Lake WQ ROI layer is empty")
    if rois.crs is None:
        raise ValueError("Lake WQ ROI layer has no CRS metadata")
    rois = rois.to_crs(WORKING_CRS)
    if rois.crs.to_epsg() != 32632:
        raise ValueError("Lake WQ ROI layer is not EPSG:32632")
    if not rois.geometry.is_valid.all() or rois.geometry.is_empty.any():
        raise ValueError("Lake WQ ROI layer contains invalid/empty geometries")
    return rois


def _raster_paths(event_id: str) -> dict[str, Path]:
    return {
        "ndti_pre": INTERMEDIATE_DIR / f"event_{event_id}_pre_ndti.tif",
        "ndti_post": INTERMEDIATE_DIR / f"event_{event_id}_post_ndti.tif",
        "delta_ndti": INTERMEDIATE_DIR / f"event_{event_id}_delta_ndti.tif",
        "ndci_pre": INTERMEDIATE_DIR / f"event_{event_id}_pre_ndci.tif",
        "ndci_post": INTERMEDIATE_DIR / f"event_{event_id}_post_ndci.tif",
        "delta_ndci": INTERMEDIATE_DIR / f"event_{event_id}_delta_ndci.tif",
    }


def _read_raster(path: Path) -> tuple[np.ndarray, Any, Any, Any]:
    with rasterio.open(path) as ds:
        if ds.crs is None or ds.crs.to_epsg() != 32632:
            raise ValueError(f"{path.relative_to(ROOT)} is not EPSG:32632")
        arr = ds.read(1).astype("float32")
        if ds.nodata is not None:
            arr = np.where(arr == ds.nodata, np.nan, arr)
        return arr, ds.transform, ds.crs, ds.nodata


def _stats(arr: np.ndarray, mask: np.ndarray) -> dict[str, float | int | None]:
    vals = arr[mask & np.isfinite(arr)]
    if vals.size == 0:
        return {"mean": None, "median": None, "valid_pixels": 0}
    return {"mean": float(np.mean(vals)), "median": float(np.median(vals)), "valid_pixels": int(vals.size)}


def _metadata_by_event(events: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if IMAGE_METADATA_PATH.exists() and IMAGE_METADATA_PATH.stat().st_size > 0:
        df = pd.read_csv(IMAGE_METADATA_PATH)
    else:
        df = pd.DataFrame(columns=IMAGE_METADATA_COLUMNS)
    out: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        out[str(row.get("event_id", ""))] = row.to_dict()
    for _, event in events.iterrows():
        out.setdefault(
            str(event["event_id"]),
            {
                "event_id": event.get("event_id", ""),
                "event_start": event.get("event_start", ""),
                "event_end": event.get("event_end", ""),
                "image_pre_date": "",
                "image_post_turbidity_date": "",
                "image_post_chla_date": "",
                "quality_flag": "MISSING_LOCAL_IMAGE",
                "quality_note": "No local Sentinel-2 event-pair metadata was available; no GEE fallback.",
            },
        )
    return out


def _placeholder_rows(event: pd.Series, rois: Any, meta: dict[str, Any], flag: str, note: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, roi in rois.iterrows():
        row = {col: "" for col in ANOMALY_COLUMNS}
        row.update(
            {
                "event_id": event.get("event_id", ""),
                "event_start": event.get("event_start", ""),
                "event_end": event.get("event_end", ""),
                "roi_name": roi.get("roi_name", ""),
                "total_precip_mm": event.get("total_precip_mm", ""),
                "delta_runoff_mm": event.get("delta_runoff_mm", ""),
                "delta_volume_m3": event.get("delta_volume_m3", ""),
                "image_pre_date": meta.get("image_pre_date", ""),
                "image_post_turbidity_date": meta.get("image_post_turbidity_date", ""),
                "image_post_chla_date": meta.get("image_post_chla_date", ""),
                "valid_pixels_pre": 0,
                "valid_pixels_post": 0,
                "quality_flag": flag,
                "quality_note": note,
                "data_source": "local_sentinel2_safe_zip_search",
            }
        )
        rows.append(row)
    return rows


def compute_zonal_anomalies() -> pd.DataFrame:
    ensure_lake_wq_dirs()
    events = load_selected_events()
    rois = _load_rois()
    metadata = _metadata_by_event(events)
    rows: list[dict[str, Any]] = []
    complete_events = 0

    for _, event in events.iterrows():
        event_id = str(event["event_id"])
        rasters = _raster_paths(event_id)
        meta = metadata.get(event_id, {})
        missing = [name for name, path in rasters.items() if not path.exists() or path.stat().st_size == 0]
        if missing:
            flag = str(meta.get("quality_flag", "MISSING_LOCAL_IMAGE")) or "MISSING_LOCAL_IMAGE"
            if flag not in {"MISSING_LOCAL_IMAGE", "FAIL", "INSUFFICIENT_VALID_PIXELS"}:
                flag = "MISSING_LOCAL_IMAGE"
            note = str(meta.get("quality_note", "")) or f"Missing local raster set for event {event_id}: {', '.join(missing)}. No GEE fallback."
            rows.extend(_placeholder_rows(event, rois, meta, flag, note))
            continue

        try:
            arrays: dict[str, np.ndarray] = {}
            transforms = []
            crs_values = []
            nodata_values = []
            shapes = []
            for name, path in rasters.items():
                arr, transform, crs, nodata = _read_raster(path)
                arrays[name] = arr
                transforms.append(tuple(transform))
                crs_values.append(crs.to_string())
                nodata_values.append(nodata)
                shapes.append(arr.shape)
            if len(set(transforms)) != 1 or len(set(crs_values)) != 1 or len(set(shapes)) != 1:
                raise ValueError("Event rasters do not share CRS, transform, and shape")
            if len(set(str(v) for v in nodata_values)) != 1:
                raise ValueError("Event rasters do not share nodata policy")
            with rasterio.open(rasters["ndti_pre"]) as ref:
                transform = ref.transform
            complete_events += 1
        except Exception as exc:
            note = f"Raster QA/read failed for event {event_id}: {type(exc).__name__}: {exc}."
            rows.extend(_placeholder_rows(event, rois, meta, "FAIL", note))
            continue

        for _, roi in rois.iterrows():
            mask = geometry_mask([roi.geometry], out_shape=arrays["ndti_pre"].shape, transform=transform, invert=True)
            ndti_pre = _stats(arrays["ndti_pre"], mask)
            ndti_post = _stats(arrays["ndti_post"], mask)
            ndti_delta = _stats(arrays["delta_ndti"], mask)
            ndci_pre = _stats(arrays["ndci_pre"], mask)
            ndci_post = _stats(arrays["ndci_post"], mask)
            ndci_delta = _stats(arrays["delta_ndci"], mask)
            valid_pre = min(int(ndti_pre["valid_pixels"]), int(ndci_pre["valid_pixels"]))
            valid_post = min(int(ndti_post["valid_pixels"]), int(ndci_post["valid_pixels"]))
            if valid_pre <= 0 or valid_post <= 0:
                flag = "INSUFFICIENT_VALID_PIXELS"
                note = "At least one pre/post ROI statistic has zero valid local Sentinel-2 pixels after masking."
            else:
                flag = "PASS"
                note = "Local Sentinel-2 SAFE-derived NDTI/NDCI zonal anomaly computed on matching EPSG:32632 20 m grids."
            rows.append(
                {
                    "event_id": event_id,
                    "event_start": event.get("event_start", ""),
                    "event_end": event.get("event_end", ""),
                    "roi_name": roi.get("roi_name", ""),
                    "total_precip_mm": event.get("total_precip_mm", ""),
                    "delta_runoff_mm": event.get("delta_runoff_mm", ""),
                    "delta_volume_m3": event.get("delta_volume_m3", ""),
                    "image_pre_date": meta.get("image_pre_date", ""),
                    "image_post_turbidity_date": meta.get("image_post_turbidity_date", ""),
                    "image_post_chla_date": meta.get("image_post_chla_date", ""),
                    "ndti_pre_mean": ndti_pre["mean"],
                    "ndti_post_mean": ndti_post["mean"],
                    "delta_ndti_mean": ndti_delta["mean"],
                    "ndti_pre_median": ndti_pre["median"],
                    "ndti_post_median": ndti_post["median"],
                    "delta_ndti_median": ndti_delta["median"],
                    "ndci_pre_mean": ndci_pre["mean"],
                    "ndci_post_mean": ndci_post["mean"],
                    "delta_ndci_mean": ndci_delta["mean"],
                    "ndci_pre_median": ndci_pre["median"],
                    "ndci_post_median": ndci_post["median"],
                    "delta_ndci_median": ndci_delta["median"],
                    "valid_pixels_pre": valid_pre,
                    "valid_pixels_post": valid_post,
                    "quality_flag": flag,
                    "quality_note": note,
                    "data_source": "local_sentinel2_safe_zip",
                }
            )

    out = pd.DataFrame(rows, columns=ANOMALY_COLUMNS)
    write_csv(ANOMALIES_PATH, out, ANOMALY_COLUMNS)
    register_generated_dataset(
        "lake_wq_event_anomalies",
        "Lake water-quality proxy anomalies by event and ROI",
        "lake_water_quality_remote_sensing_output",
        ANOMALIES_PATH,
        "processed",
        crs="n/a",
        notes="Python-only NDTI/NDCI anomaly table; missing local event coverage is a data limitation, not a GEE fallback.",
    )
    status = "DONE" if complete_events else "PARTIAL"
    reason = f"Computed zonal anomalies for {complete_events} complete local Sentinel-2 event pair(s); {len(out)} table rows written."
    update_backlog({"F017": status}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script="scripts/lake_wq/compute_zonal_anomalies.py",
            task="Calculate Lake Varese ROI zonal statistics for NDTI/NDCI event anomalies.",
            inputs=[str(INTERMEDIATE_DIR.relative_to(ROOT)), str(ROI_PATH.relative_to(ROOT)), "outputs/tables/lake_response_selected_events.csv"],
            outputs=[str(ANOMALIES_PATH.relative_to(ROOT))],
            status=status,
            reason=reason,
            files_created=[str(ANOMALIES_PATH.relative_to(ROOT))],
            qa_checks=["raster grids must match before algebra/statistics", "ROI CRS EPSG:32632", "MISSING_LOCAL_IMAGE placeholders when rasters unavailable"],
            next_action="Run compute_analytical_context.py and lake WQ figures.",
        )
    )
    print(f"Zonal anomaly rows: {len(out)} -> {ANOMALIES_PATH.relative_to(ROOT)}")
    return out


def main() -> int:
    compute_zonal_anomalies()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
