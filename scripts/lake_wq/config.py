"""Configuration for the Python-only Lake Varese water-quality closure."""
from __future__ import annotations

from pathlib import Path
import sys

PACKAGE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PACKAGE_DIR.parent
ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_utils import WORKING_CRS, WGS84  # noqa: E402

RAW_SAFE_GLOB = ROOT / "data/raw/zip"
DELTA_PATH = ROOT / "outputs/tables/runoff_delta_by_event.csv"
RAINFALL_EVENTS_PATH = ROOT / "outputs/tables/post_fire_rainfall_events.csv"
SELECTED_EVENTS_PATH = ROOT / "outputs/tables/lake_response_selected_events.csv"
LAKE_BOUNDARY_PATH = ROOT / "data/processed/boundary/lake_varese_boundary.gpkg"
ROI_PATH = ROOT / "data/processed/water_quality/lake_varese_wq_rois_utm32.gpkg"
ARPA_WQ_PATH = ROOT / "data/processed/water_quality/lake_varese_analytical_dati_2019-2022_varese.csv"
INTERMEDIATE_DIR = ROOT / "outputs/intermediate/lake_wq"
TABLES_DIR = ROOT / "outputs/tables"
QA_SPATIAL_PATH = ROOT / "qa/spatial/lake_wq_remote_sensing_qa.csv"
QA_OUTPUTS_PATH = ROOT / "outputs/qa/lake_wq_remote_sensing_qa.csv"
RASTER_METADATA_QA_PATH = ROOT / "outputs/qa/lake_wq_raster_metadata_qa.csv"
IMAGE_METADATA_PATH = INTERMEDIATE_DIR / "lake_wq_event_image_metadata.csv"
ANOMALIES_PATH = TABLES_DIR / "lake_wq_event_anomalies.csv"
CONTEXT_PATH = TABLES_DIR / "lake_wq_analytical_context_by_period.csv"
LATEX_DIR = ROOT / "latex"

TARGET_RESOLUTION_M = 20
NODATA_FLOAT = -9999.0
CLEAR_SCL_CLASSES = {4, 5, 6, 7}  # vegetation, bare, water, unclassified; cloud/shadow/snow excluded
WATER_SCL_CLASS = 6
MIN_VALID_ROI_PIXELS = 1

ROI_NAMES = ["whole_lake", "near_inlet_or_north_shore", "lake_center_control"]

SELECTED_EVENT_COLUMNS = [
    "event_id",
    "event_start",
    "event_end",
    "total_precip_mm",
    "delta_runoff_mm",
    "delta_volume_m3",
    "baseline_runoff_mm",
    "burned_runoff_mm",
    "selection_rank",
    "selection_reason",
]

QA_COLUMNS = [
    "event_id",
    "event_start",
    "event_end",
    "safe_zip",
    "image_date",
    "image_role",
    "sensor",
    "crs",
    "resolution_m",
    "valid_lake_pixels",
    "roi_name",
    "valid_roi_pixels",
    "scl_used",
    "cloud_mask_note",
    "quality_flag",
    "quality_note",
]

ALLOWED_QA_FLAGS = {"PASS", "WARN", "FAIL", "MISSING_LOCAL_IMAGE", "INSUFFICIENT_VALID_PIXELS"}

IMAGE_METADATA_COLUMNS = [
    "event_id",
    "event_start",
    "event_end",
    "image_pre_date",
    "image_post_turbidity_date",
    "image_post_chla_date",
    "pre_safe_zip",
    "post_turbidity_safe_zip",
    "post_chla_safe_zip",
    "quality_flag",
    "quality_note",
]

ANOMALY_COLUMNS = [
    "event_id",
    "event_start",
    "event_end",
    "roi_name",
    "total_precip_mm",
    "delta_runoff_mm",
    "delta_volume_m3",
    "image_pre_date",
    "image_post_turbidity_date",
    "image_post_chla_date",
    "ndti_pre_mean",
    "ndti_post_mean",
    "delta_ndti_mean",
    "ndti_pre_median",
    "ndti_post_median",
    "delta_ndti_median",
    "ndci_pre_mean",
    "ndci_post_mean",
    "delta_ndci_mean",
    "ndci_pre_median",
    "ndci_post_median",
    "delta_ndci_median",
    "valid_pixels_pre",
    "valid_pixels_post",
    "quality_flag",
    "quality_note",
    "data_source",
]

CONTEXT_COLUMNS = [
    "period",
    "parameter_group",
    "parameter",
    "unit",
    "station_names",
    "station_codes",
    "depth_descriptions",
    "sample_count",
    "date_min",
    "date_max",
    "value_min",
    "value_median",
    "value_mean",
    "value_max",
    "context_note",
]

RASTER_QA_COLUMNS = [
    "path",
    "event_id",
    "index_name",
    "image_role",
    "crs",
    "bounds",
    "resolution_x",
    "resolution_y",
    "transform",
    "width",
    "height",
    "nodata",
    "dtype",
    "valid_pixel_count",
    "min",
    "max",
    "mean",
]
