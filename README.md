# GeoProject — Post-fire Runoff Screening

Reproducible screening-level GIS workflow for post-wildfire runoff sensitivity analysis.

## Web interface

![Explorer map](screenshots/03_explorer_map.png)

The Streamlit dashboard provides interactive maps, dynamic charts, parameter
exploration, and result tables. See `docs/WEB_INTERFACE.md` for a full screenshot tour.

## Key results (reference project)

| Metric | Value |
|---|---|
| DEM-derived catchment | 1,311.76 ha |
| Conservative dNBR burned proxy | 23.80 ha |
| Max conservative delta Q | 0.282 mm |
| Upper-bound delta Q | 5.505 mm |
| WEPPcloud sediment | +122.7% |

Burned-footprint definition dominates the uncertainty envelope.

## Quick start

```bash
conda env create -f environment.yml
conda activate geoproject
streamlit run webapp/app.py --server.headless true
```

## Documentation

| Document | Purpose |
|---|---|
| `docs/USER_MANUAL.md` | Setup and workflow overview |
| `docs/DATA_REQUIREMENTS.md` | Required input data and formats |
| `docs/WEB_INTERFACE.md` | Web app guide with screenshots |
| `docs/TROUBLESHOOTING.md` | Common problems and solutions |

## Scientific guardrails

- Local runoff outputs are screening-level, uncalibrated scenario estimates.
- dNBR is a remote-sensing burn-severity proxy, not field soil burn severity.
- WEPPcloud is a benchmark, not validation of local SCS-CN.
- Lake WQ is Python-only; NDTI is primary (turbidity), NDCI is secondary and indirect.
- All processing uses local data.
