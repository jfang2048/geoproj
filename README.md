# GeoProject — Post-fire Runoff Screening

Reproducible screening-level GIS workflow for post-wildfire runoff sensitivity analysis.
Local SCS-CN event runoff model with WEPPcloud-EU sediment benchmark and Python-only
lake water-quality proxy closure.

## Quick start

```bash
conda env create -f environment.yml
conda activate geoproject
streamlit run webapp/app.py --server.headless true
```

Open `http://localhost:8501`. The web app needs no data to launch — it shows a basemap
and layer status table. Run the pipeline scripts to generate spatial layers and tables.

## How to use

### 1. Prepare data

Place input files under `data/raw/zip/`:

| Dataset | Format | Example |
|---|---|---|
| DEM | `.zip` with GeoTIFF or IMG | `DTM5_RL.zip` |
| Fire perimeter | `.zip`, `.gpkg`, `.shp` | `Aree_percorse_dal_fuoco.zip` |
| Sentinel-2 L2A | `.SAFE.zip` | `S2A_MSIL2A_20190110_*.SAFE.zip` |
| Land cover | `.zip`, `.gpkg` | `DUSAF6.zip` |
| Soil / HSG | `.tif`, `.zip` | soil grids |
| Rainfall | `.zip`, `.csv` | `RW_*.zip` |

### 2. Run the workflow

```bash
python scripts/run_pipeline.py
python scripts/lake_wq/run_compute_lake_wq.py
python scripts/lake_wq/list_required_sentinel2_windows.py
```

### 3. Explore results

The pipeline writes processed layers to `data/processed/` and tables to
`data/outputs/tables/`. Open the web interface to view maps, charts, and lake
water-quality status.

### 4. Interpret safely

All runoff outputs are screening-level and uncalibrated. dNBR is a remote-sensing
proxy, not field-validated soil burn severity. WEPPcloud is an independent benchmark,
not validation of the local SCS-CN model. Lake WQ is Python-only and requires local
Sentinel-2 L2A SAFE scenes covering event windows.

## Web interface tour

### Overview

![Overview](screenshots/01_overview.png)

The landing page shows key metric cards (catchment area, fire perimeter, dNBR proxy,
runoff delta, WEPPcloud sediment, lake WQ status) and scientific guardrails in a
collapsed section.

### Data

![Data](screenshots/02_data.png)

Upload project files into the correct directories. Check which required files are
present and which are missing. View detected local Sentinel-2 products and their
sensing dates.

### Explorer — Map

![Explorer map](screenshots/03_explorer_map.png)

Interactive pydeck map with layer toggles in the sidebar. Supported layers:
catchment boundary, official fire perimeter, lake boundary, hydrography,
DEM streams, response units, outlet point, and burn severity proxy overlay.
Layer status line shows which files are loaded or missing.

### Explorer — Parameters

![Explorer parameters](screenshots/04_explorer_params.png)

Adjust SCS-CN parameters (initial abstraction ratio, burn severity CN adjustments,
footprint scenario) and see a live sensitivity preview. The preview computes
delta Q over a range of rainfall depths without modifying official outputs.
Save presets or export to project config (with timestamped backup).

### Results — Runoff and WEPPcloud

![Results](screenshots/05_results.png)

Runoff delta tables, event scatter plots, delta Q CDF, burn footprint vs runoff
response bar chart, and WEPPcloud sediment benchmark. WEPPcloud is clearly
labeled as an independent benchmark, not SCS-CN validation.

### Results — Lake WQ

![Lake WQ](screenshots/06_lake_wq.png)

Lake water-quality closure status with event-image availability metrics.
Shows how many selected runoff events have pre-window and post-window
Sentinel-2 scenes, usable pairs count, and detailed anomaly table.
If local SAFE scenes are insufficient, reports MISSING_LOCAL_IMAGE
rather than fabricating data.

## Key results (reference project)

| Metric | Value |
|---|---|
| DEM-derived catchment | 1,311.76 ha |
| Official fire perimeter | 376.25 ha |
| Conservative dNBR burned proxy | 23.80 ha |
| Max conservative delta Q | 0.282 mm |
| Upper-bound delta Q | 5.505 mm |
| WEPPcloud sediment | 293 to 653 tonne/yr (+122.7%) |

## Documentation

| Document | Purpose |
|---|---|
| `docs/USER_MANUAL.md` | Full setup and workflow guide |
| `docs/DATA_REQUIREMENTS.md` | Required input data and formats |
| `docs/WEB_INTERFACE.md` | Web app screenshots and navigation |
| `docs/TROUBLESHOOTING.md` | Common problems and solutions |

## License

GPLv3. See [LICENSE](LICENSE).
