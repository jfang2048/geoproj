# Web interface

Streamlit dashboard with interactive map, dynamic charts, and data tables.

```bash
streamlit run webapp/app.py --server.headless true
```

Opens at `http://localhost:8501`.

## Navigation

Overview | Data | Model | Explorer | Results

## Screenshots

### Overview

![Overview](../screenshots/01_overview.png)

Project summary with key metric cards and scientific guardrails.

### Data

![Data](../screenshots/02_data.png)

Upload files, check required-file status, and view detected Sentinel-2 products.

### Explorer — Map

![Explorer map](../screenshots/03_explorer_map.png)

Interactive pydeck map with vector layers (catchment, fire perimeter, lake boundary,
hydrography, response units, outlet). Layer toggles in sidebar.

### Explorer — Parameters

![Explorer parameters](../screenshots/04_explorer_params.png)

SCS-CN parameter sliders with live sensitivity preview. Move the sliders and the
chart updates instantly — no need to re-run the pipeline.

### Results

![Results](../screenshots/05_results.png)

Runoff delta tables, WEPPcloud benchmark chart, and lake WQ availability status.

### Lake WQ

![Lake WQ](../screenshots/06_lake_wq.png)

Lake water-quality closure status with event-image availability table and anomaly data.
