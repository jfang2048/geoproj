# Data requirements

All paths in `config/project.yaml` should be relative to the repository root. Uploads from the Streamlit **Data** page are saved under `data/raw/<input-name>/` and assigned to the matching `inputs.*` key automatically.

## Inputs

| Logical input | Config key | Formats | Required fields |
|---|---|---|---|
| Catchment boundary | `inputs.catchment_boundary` | `.gpkg`, `.geojson`, `.json` | polygon geometry with CRS |
| Official fire perimeter | `inputs.fire_perimeter` | `.gpkg`, `.geojson`, `.json` | polygon geometry with CRS |
| Burn severity | `inputs.burn_severity` | `.gpkg`, `.geojson`, `.json`, `.tif`, `.tiff` | vector `burn_class` or raster values 0–3 with NoData 255 |
| Land cover | `inputs.land_cover` | `.gpkg`, `.geojson`, `.json` | configured land-cover column, default `landcover_class` |
| Hydrologic soil group | `inputs.hsg` | `.gpkg`, `.geojson`, `.json` | configured HSG column, default `hsg` |
| Rainfall events | `inputs.rainfall_events` | `.csv` | `event_id`, `start_date`, `end_date`, and `rainfall_mm` or supported rainfall alias |
| WEPPcloud output | `inputs.weppcloud_export` | `.csv` | optional user export with the required WEPPcloud columns |

Unsupported archive or spreadsheet formats are not accepted by the end-to-end workflow.

## Rainfall table

Required output columns after normalization:

```text
event_id,start_date,end_date,rainfall_mm
```

Supported rainfall-depth aliases are `total_precip_mm`, `precip_mm`, and `precipitation_mm`.

## WEPPcloud table

Required import columns:

```text
scenario,period,modeled_area,modeled_area_units,runoff_quantity,
runoff_units,sediment_quantity,sediment_units,source_filename
```

## Generated tables

`outputs/tables/runoff_units.csv`:

```text
unit_id,landcover_class,hsg,burn_class,baseline_cn,burned_cn,
cn_adjustment,area_m2,area_ha
```

`outputs/tables/runoff_event_summary.csv`:

```text
event_id,start_date,end_date,rainfall_mm,baseline_runoff_mm,
burned_runoff_mm,delta_runoff_mm,baseline_volume_m3,burned_volume_m3,
delta_volume_m3,response_unit_area_m2,initial_abstraction_ratio
```

`outputs/run_metadata.json` records run ID, timestamp, status, configuration path, processing CRS, input paths, model parameters, output paths, spatial coverage diagnostics, warnings, and errors.
