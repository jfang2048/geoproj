# Outputs

Outputs are written under `runs/<run_id>/outputs/`, `runs/<run_id>/reports/`, and `runs/<run_id>/run_manifest.json`.

## Spatial outputs

| Output | Path | CRS | Notes |
|---|---|---|---|
| Catchment boundary | `outputs/display/catchment_boundary.geojson`, `normalized/catchment_boundary.gpkg` | GeoJSON EPSG:4326; GPKG EPSG:32632 | Derived from dissolved uploaded fire perimeter for screening. |
| Fire perimeter | `outputs/display/fire_perimeter.geojson` | EPSG:4326 | Display layer from normalized input. |
| Burn severity | `outputs/display/burn_severity.geojson` | EPSG:4326 | Display layer. dNBR-derived uploads should be interpreted as a proxy. |
| Land cover | `outputs/display/land_cover.geojson` | EPSG:4326 | Display layer. |
| Response units | `outputs/response_units.gpkg`, `outputs/display/response_units.geojson` | GPKG EPSG:32632; GeoJSON EPSG:4326 | Overlay of land cover, burn severity, HSG, and boundary. |
| Runoff delta | `outputs/display/runoff_delta.geojson` | EPSG:4326 | Delta layer for the largest rainfall event in the uploaded CSV. |

## Tables

| Output | Path | Units |
|---|---|---|
| Rainfall event summary | `normalized/rainfall_events.csv` | mm |
| Baseline runoff table | `outputs/tables/baseline_runoff.csv` | mm, m³ |
| Burned scenario runoff table | `outputs/tables/burned_scenario_runoff.csv` | mm, m³ |
| Delta runoff table | `outputs/tables/delta_runoff.csv` | mm, m³ |
| Per-unit runoff table | `outputs/tables/unit_event_runoff.csv` | mm, m³ |

## QA and manifest

| Output | Path |
|---|---|
| Preprocessing QA | `outputs/qa/preprocessing_qa.json` |
| Model QA | `outputs/qa/model_qa.json` |
| Run report | `reports/run_report.md` |
| Run manifest | `run_manifest.json` |

## Interpretation limits

- SCS-CN outputs are event-screening estimates.
- The model does not produce a discharge hydrograph.
- Burn severity may be a proxy if derived from dNBR.
- CN lookup values and burn adjustments are recorded in the manifest.
- HSG fallback values must be user-selected and are not used silently.
