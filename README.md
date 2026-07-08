# GeoProject — Post-fire Runoff Screening

This folder is a code-only public export of the GeoProject workflow.
It does not include raw data, processed outputs, LaTeX files, generated figures, or presentations.

To reproduce results, place required input data in `data/raw/zip/` and run the workflow.

## Quick start

```bash
conda env create -f environment.yml
conda activate geoproject
streamlit run webapp/app.py --server.headless true
```

## Documentation

See `docs/` for user manual, data requirements, web interface guide, and troubleshooting.
