# Runbook

## Backend does not start

Check dependencies:

```bash
cd backend
python -m pip install -e '.[test]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If GDAL, rasterio, Fiona, or geopandas fail to install with pip, use a conda environment with conda-forge packages.

## Frontend cannot reach API

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Confirm the backend is running:

```bash
curl http://127.0.0.1:8000/api/health
```

If the backend runs on another host or port, set `VITE_API_BASE` before `npm run dev`.

## Upload rejected

Read the error in the upload panel. Common causes:

- wrong file extension for the selected category
- missing CRS
- missing required vector attribute
- unsafe ZIP archive path
- invalid rainfall CSV columns
- negative rainfall value
- upload size limit exceeded

## Preprocessing fails

Check `runs/<run_id>/logs/run.log` and the job log under `runs/<run_id>/logs/`. Common causes:

- missing required input
- raster alignment failure
- vector geometry repair failure
- spatial layer does not overlap the boundary

## Model run fails

Common causes:

- preprocessing was not run first
- HSG is missing and no explicit fallback was selected
- land cover, burn severity, HSG, and boundary do not overlap
- rainfall CSV has no valid rows

## Outputs are missing from the map

The map lists missing layers and the reason. If it says:

```text
No output for this run yet. Run preprocessing and model calculation first.
```

run the processing steps in order.

## Recover a run

A run is filesystem-backed. Inspect:

```text
runs/<run_id>/run_manifest.json
runs/<run_id>/logs/
runs/<run_id>/outputs/
runs/<run_id>/reports/
```

You can create a new run and re-upload files if a run is not recoverable.
