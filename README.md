# GeoProject — Post-fire Runoff Screening Tool

A reproducible, screening-level GIS workflow for post-wildfire runoff sensitivity
analysis. Provide your own input data, run the pipeline, and explore results through
the web interface.

## Quick start

```bash
conda env create -f environment.yml
conda activate geoproject
streamlit run webapp/app.py --server.headless true
```

Open `http://localhost:8501`.

## How to prepare your data

Place input files under `data/raw/zip/` in your project directory. The tool expects:

| Dataset | Accepted formats | Notes |
|---|---|---|
| DEM / DTM | `.zip` (GeoTIFF or IMG inside) | Required for catchment delineation and hydrology |
| Fire perimeter | `.zip`, `.gpkg`, `.shp` | Official burned area polygon for your study region |
| Sentinel-2 L2A | `.SAFE.zip` | Must be L2A (MSIL2A), not L1C. Needed for dNBR burn proxy and lake water-quality indices |
| Land cover | `.zip`, `.gpkg` | Vector land cover map, reclassified to hydrologic classes |
| Soil / HSG | `.tif`, `.zip`, `.csv` | Hydrologic soil group or texture data for curve number assignment |
| Rainfall | `.zip`, `.csv` | Hourly or daily precipitation time series |

## How to upload data through the web interface

1. Launch the web app and go to the **Data** tab.

![Data page](screenshots/02_data.png)

2. Select a data category from the dropdown (DEM, fire perimeter, Sentinel-2, land cover, soil, or rainfall).

3. Click the file uploader to choose files from your computer. The tool accepts only the correct file extensions for each category.

4. Click Upload. Files are saved into `data/raw/zip/` with no overwrite — if a file with the same name exists, a timestamp suffix is added.

5. Switch to the **Required files** subtab to see which files are present and which are still missing.

6. Switch to the **Detected products** subtab to verify your Sentinel-2 SAFE files are recognized with correct sensing dates.

After uploading all required data, run the pipeline from the **Model** tab or the command line:

```bash
python scripts/run_pipeline.py
python scripts/lake_wq/run_compute_lake_wq.py
```

## Web interface

### Overview

![Overview](screenshots/01_overview.png)

Landing page with metric cards populated from your pipeline outputs. A collapsed
scientific guardrails section explains the limits of screening-level analysis.

### Data — upload and check

![Data page](screenshots/02_data.png)

Upload files, check what is present, and view detected Sentinel-2 products.
The tool validates file extensions and rejects unexpected formats.

### Explorer — interactive map

![Explorer map](screenshots/03_explorer_map.png)

pydeck map with toggleable vector layers (catchment, fire perimeter, lake boundary,
hydrography, DEM streams, response units, outlet). A layer status line shows which
files are loaded and which are missing. The basemap always renders even without data.

### Explorer — parameter sensitivity

![Explorer parameters](screenshots/04_explorer_params.png)

Adjust SCS-CN parameters (initial abstraction ratio, burn severity CN adjustments,
footprint scenario) and see a live sensitivity preview. Preview is in-memory only
and does not overwrite pipeline outputs. Save presets or export to project config.

### Results — runoff and WEPPcloud

![Results](screenshots/05_results.png)

Runoff delta tables, event scatter and CDF charts, burn footprint vs runoff response
bar chart, and WEPPcloud sediment benchmark. WEPPcloud is an independent benchmark,
not validation of the local SCS-CN model.

### Results — lake water quality

![Lake WQ](screenshots/06_lake_wq.png)

Lake water-quality closure status. Shows which runoff events have pre-window and
post-window Sentinel-2 scenes available. If local SAFE coverage is insufficient,
reports `MISSING_LOCAL_IMAGE` rather than generating fake data.

## Scientific guardrails

- All runoff outputs are screening-level, uncalibrated scenario estimates.
- dNBR is a remote-sensing burn-severity proxy, not field-validated soil burn severity.
- WEPPcloud is an independent benchmark, not validation of the local SCS-CN model.
- Lake water-quality indices (NDTI, NDCI) are screening-level optical proxies.
- NDTI is the primary turbidity proxy; NDCI is secondary and indirect.
- The tool uses local input files only. No external cloud services are called.

## Documentation

| Document | Purpose |
|---|---|
| `docs/USER_MANUAL.md` | Full setup and workflow guide |
| `docs/DATA_REQUIREMENTS.md` | Required input data and formats |
| `docs/WEB_INTERFACE.md` | Web app screenshots and navigation |
| `docs/TROUBLESHOOTING.md` | Common problems and solutions |

## License

GPLv3. See [LICENSE](LICENSE).
