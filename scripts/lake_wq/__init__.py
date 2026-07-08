"""Python-only Lake Varese water-quality closure workflow.

This package uses local Sentinel-2 L2A SAFE ZIP files only. It never calls,
creates, or relies on Google Earth Engine assets.
"""

__all__ = [
    "config",
    "io",
    "s2_safe",
    "compute_select_events",
    "compute_rois",
    "compute_s2_indices",
    "compute_zonal_anomalies",
    "compute_analytical_context",
]
