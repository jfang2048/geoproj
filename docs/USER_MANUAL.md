# User manual

## Setup

```bash
conda env create -f environment.yml
conda activate geoproject
streamlit run postfire_runoff/frontend/app.py --server.headless true --server.port 8501
```

For a complete demonstration run first:

```bash
python sample_data/create_sample_data.py
python -m postfire_runoff.cli.run_pipeline --config config/sample.yaml --force
```

## Navigation

The Streamlit app has the fixed top navigation: **Overview**, **Data**, **Model**, **Explore**, and **Results**.

### Overview

Shows metric cards from generated outputs. Missing outputs appear as `N/A` or unavailable rather than fabricated case-study values.

### Data

The **Upload files** tab stores supported local files. Categories are catchment boundary, fire perimeter, burn severity, land cover, soil/HSG, rainfall/weather, lake water quality, and WEPPcloud output. Supported extensions are intentionally narrow: GeoPackage/GeoJSON for vectors, GeoTIFF for burn rasters, and CSV for rainfall/WEPPcloud tables. Content validation checks readable files, CRS for GIS files, and required rainfall fields.

The **Required files** tab shows the canonical processed outputs and optional WEPPcloud/lake status files. The **CRS status** tab states the CRS policy: process in EPSG:32632 and use EPSG:4326 only for web display/exchange. The **Upload manifest** tab lists browser uploads.

### Model

**Run pipeline** calls `python -m postfire_runoff.cli.run_pipeline --force` against `config/project.yaml`. Configure the logical input paths before using it for a real case. **Run lake WQ compute** records unavailable status unless real local pre/post imagery and a lake boundary are configured. **Run minimal tests** runs the focused project tests.

### Explore

**Map** displays available catchment, fire perimeter, lake, hydrography, DEM-stream, response-unit, outlet, and burn-proxy layers. The basemap loads even when project layers are absent.

**Parameters** previews SCS-CN sensitivity in memory. It uses the backend SCS-CN function and does not overwrite official output files. Footprint scenarios are labels for spatial recomputation; the preview does not scale CN increments by a footprint multiplier.

**Events** and **Burn footprint** show charts from generated CSVs when available.

### Results

**Runoff** shows event runoff deltas and tables from `outputs/tables/`. **WEPPcloud** is unavailable until a valid user-exported WEPPcloud CSV is imported. **Lake WQ** shows status and image availability; it does not emit numeric NDTI/NDCI anomalies without valid pre/post imagery. **Tables** displays generated CSVs.

## Common errors

- `Required input file(s) missing`: fill `inputs.*` in the selected YAML config.
- `missing CRS`: re-export the vector/raster with a declared CRS instead of assigning coordinates by assumption.
- `no overlap with catchment`: verify all required layers cover the same area after reprojection to EPSG:32632.
- Lake WQ exit code `2`: optional stage lacks real imagery; the core runoff run can still be complete.
