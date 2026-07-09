# Web GIS runoff screening tool

This repository contains a standalone Web GIS application for post-fire runoff screening over a burned catchment. The application uses browser upload as the primary data input workflow. Manual folder placement is secondary and is intended for recovery or controlled test setup only.

The tool validates GIS and rainfall inputs, stores accepted files under an isolated run directory, runs preprocessing and a screening-level SCS-CN runoff calculation, and displays generated layers on a browser map.

This is not a calibrated hydrologic model. Outputs are screening-level unless a calibrated model and verified local parameters are added.

## What the tool does

- Upload GIS and rainfall files through the browser.
- Validate CRS, geometry, raster metadata, rainfall columns, and archive safety before accepting files.
- Store accepted files under `runs/<run_id>/inputs/`.
- Normalize spatial inputs to EPSG:32632 for analysis.
- Use EPSG:4326 display layers only for the browser map.
- Run a documented SCS-CN event runoff calculation.
- Write tables, display layers, QA files, a run report, and `run_manifest.json`.

## What the tool does not do

- It does not forecast discharge.
- It does not replace field-validated burn severity, soil, or hydrologic calibration.
- It does not fabricate production input data when required files are missing.
- It does not use GitHub Actions or workflow files.

## Repository layout

```text
backend/      FastAPI application and GIS processing services
frontend/     React + Vite browser application with Leaflet map
docs/         User and operator documentation
sample_data/  Small sample-data generator for local checks
tests/        Pytest tests for backend validation and model logic
runs/         Local run storage; generated at runtime
```

## Run the backend

Use Python 3.11 or newer with GDAL-compatible wheels or a conda environment.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API health check is available at:

```text
http://127.0.0.1:8000/api/health
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/api` requests to `http://127.0.0.1:8000`.

## Upload-first workflow

1. Open the web app.
2. Create a run or select an existing run.
3. Upload each required file through **Upload data**.
4. Review **Validation status**.
5. Run **Run preprocessing**.
6. Run **Run runoff model**.
7. Inspect generated layers in **Map viewer**.
8. Download outputs and read the run report.

Required production inputs are DEM, fire perimeter or burned area, burn severity, land cover, hydrologic soil group, and rainfall events. HSG may be supplied by an explicit per-run fallback only when the user chooses it; the fallback is recorded in the manifest and report.

## Run tests locally

```bash
cd backend
source .venv/bin/activate
cd ..
pytest
```

Raster tests require `rasterio`. If rasterio is not installed, those tests are skipped by pytest.

## Runtime storage

Every run writes:

```text
runs/<run_id>/
  inputs/
  normalized/
  outputs/
  logs/
  reports/
  run_manifest.json
```

`run_manifest.json` records input filenames, checksums, CRS, raster resolution, bounds, NoData, selected parameters, generated outputs, output checksums, warnings, and fatal errors.
