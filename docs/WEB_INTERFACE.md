# Web interface

Launch with:

```bash
streamlit run postfire_runoff/frontend/app.py --server.headless true --server.port 8501
```

The app keeps the existing top navigation and visual style.

## Overview

![Overview](../screenshots/01_overview.png)

Metric cards load generated outputs. Missing optional results show unavailable states.

## Data

![Data page](../screenshots/02_data.png)

Upload supported files, inspect required canonical outputs, review CRS policy, and view the upload manifest.

## Explore — Map

![Explorer map](../screenshots/03_explorer_map.png)

The pydeck map renders a basemap in a clean clone and overlays available processed layers.

## Explore — Parameters

![Explorer parameters](../screenshots/04_explorer_params.png)

The preview calls the backend SCS-CN function and does not overwrite official outputs.

## Results

![Results](../screenshots/05_results.png)

Runoff charts and tables are read from `outputs/tables/`. WEPPcloud appears only after a valid user-exported CSV is imported.

## Lake WQ

![Lake WQ](../screenshots/06_lake_wq.png)

The lake panel reports missing imagery/status and avoids numeric optical-proxy anomalies unless valid local pre/post imagery exists.
