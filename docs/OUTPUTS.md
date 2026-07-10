# Outputs

The core pipeline writes the following canonical files.

| Path | Description |
|---|---|
| `data/processed/boundary/catchment_utm32.gpkg` | Catchment normalized to EPSG:32632. |
| `data/processed/fire_perimeter/fire_perimeter_utm32.gpkg` | Official fire perimeter normalized to EPSG:32632. |
| `data/processed/burn/burn_severity_proxy_uint8.tif` | Rasterized burn classes over the catchment extent; 255 is NoData. |
| `data/processed/model_inputs/runoff_units.gpkg` | Spatial response units with CN fields and areas. |
| `data/processed/weather/post_fire_rainfall_events.csv` | Normalized rainfall events using `rainfall_mm`. |
| `outputs/tables/runoff_units.csv` | Non-spatial response-unit attributes. |
| `outputs/tables/runoff_event_summary.csv` | Baseline/burned runoff depth and volume by event. |
| `outputs/tables/runoff_delta_by_event.csv` | Event runoff deltas consumed by UI charts. |
| `outputs/tables/burn_severity_area_summary.csv` | Burn-class area summary from response units. |
| `outputs/tables/weppcloud_summary.csv` | Optional normalized user-exported WEPPcloud CSV. |
| `outputs/tables/lake_wq_status.csv` | Optional lake-stage availability/status. |
| `outputs/run_metadata.json` | Reproducibility metadata, warnings, and optional-stage states. |

Generated sample outputs are verification artifacts and should not be interpreted as Monte Martica findings.
