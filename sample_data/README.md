# Synthetic sample data

Run:

```bash
python sample_data/create_sample_data.py
python -m postfire_runoff.cli.run_pipeline --config config/sample.yaml --force
```

The generator creates a small synthetic EPSG:32632 catchment, contextual fire polygon, burn-severity classes, two land-cover classes, two HSG classes, and two rainfall events. It is for software verification only and is not a Monte Martica/Lake Varese result.
