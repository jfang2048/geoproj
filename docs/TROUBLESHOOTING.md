# Troubleshooting

## Map shows no layers

The Explorer shows a base map even without data. Spatial layers require pipeline outputs in `data/processed/`. Run the workflow first.

## MISSING_LOCAL_IMAGE

No matching Sentinel-2 pre/post scenes for a selected event. Run `list_required_sentinel2_windows.py` to see which windows are missing, then download additional L2A scenes from Copernicus Browser.

## Wrong product level

Workflow requires Sentinel-2 L2A (MSIL2A). L1C is not supported.

## CRS mismatch

All metric processing uses EPSG:32632. Input files must have CRS metadata.
Files without CRS cause the pipeline to fail with 'missing CRS metadata'.
