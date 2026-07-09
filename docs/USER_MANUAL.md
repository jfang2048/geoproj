# User manual

## Start

1. Start the backend API.
2. Start the frontend.
3. Open the frontend URL in a browser.

## Create or select a run

Use the **Project/run** panel. A run is an isolated workspace under `runs/<run_id>/`. Each run has its own inputs, normalized files, outputs, logs, reports, and manifest.

## Upload data

Use **Upload data** for normal operation. Do not place files in `data/raw` for standard use.

For each file:

1. Choose the data category.
2. Select the file from your computer.
3. Click **Upload and validate**.
4. Read the validation result.

Rejected files are not accepted into the run input set. Accepted files are stored under `runs/<run_id>/inputs/<category>/` and recorded in the manifest.

## Validate inputs

Use **Validation status**. Required files show either **Accepted** or **Missing required file**. Warnings are shown when geometry repair, missing NoData, or other non-fatal issues are detected.

## Run processing

Run the steps in order:

1. **Run preprocessing**: normalizes accepted spatial inputs to EPSG:32632, repairs invalid vector geometries when possible, checks raster alignment, writes display layers in EPSG:4326, and prepares rainfall events.
2. **Run runoff model**: creates response units and runoff tables using SCS-CN event logic.
3. **Write QA report**: writes or refreshes the run report.

If HSG is missing, model processing stops unless you choose an explicit HSG fallback in the processing panel. The chosen fallback is recorded in the manifest.

## View map outputs

The map opens with a basemap. Rendered layers appear only when files exist. Missing layers are listed with the reason they are missing.

Available map layers include uploaded previews, catchment boundary, fire perimeter, burn severity, land cover, HSG, response units, runoff delta, water body, and hydrography when present.

Click features to inspect attributes. Use layer checkboxes to toggle rendered layers.

## Download outputs

Use **Download outputs**. The panel lists generated files only. If no outputs exist, run preprocessing and model calculation first.

## Read the run report

Use **Run report** after model calculation or QA report generation. The report states inputs, parameters, outputs, warnings, fatal errors, and interpretation limits.
