# GeoProject Web Interface

A local Streamlit dashboard for the Lake Varese / Monte Martica post-fire runoff screening project.

## Quick start

```bash
conda run -n geoproject-auto streamlit run webapp/app.py --server.headless true
```

Opens at `http://localhost:8501`.

## Navigation

| Section | Content |
|---|---|
| Overview | Project summary, metric cards, scientific guardrails |
| Data | Upload files, required-file status check, CRS policy, upload manifest |
| Model | Predefined safe command execution, run log viewer |
| Explore | Interactive pydeck map with base map and vector layers, parameter explorer, event charts, burn footprint explorer |
| Results | Runoff dashboard, WEPPcloud benchmark, lake WQ status, exportable data tables |

## Design

- All charts and maps generated dynamically from project CSV, GeoPackage, and raster outputs.
- Explorer always shows a base map (CARTO Positron); spatial layers appear when pipeline outputs are available.
- Only predefined commands are runnable; arbitrary shell input is blocked.
- Local Sentinel-2 L2A SAFE products are required for lake proxy analysis.

## Limitations

- Teaching/demo interface; not a production web service.
- All processing uses local input files supplied by the user.
- Lake WQ proxy anomaly charts require local Sentinel-2 event-window coverage.
