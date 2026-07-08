# Web interface

Streamlit dashboard with interactive maps, dynamic charts, and data tables.

```bash
streamlit run webapp/app.py --server.headless true
```

## Navigation

Overview | Data | Model | Explorer | Results

The Explorer section shows a base map. Processed spatial layers (catchment, fire, response units) appear when pipeline outputs are available. A layer status table reports which files are still needed.

All charts are generated from CSV/GeoPackage outputs. Static report figures are not used.
