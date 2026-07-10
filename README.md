# Post-fire Runoff Screening Tool

A compact Python/Streamlit tool for screening-level event runoff change in a wildfire-affected catchment. The reusable model combines a supplied catchment, contextual fire perimeter, burn-severity classes, land-cover classes, hydrologic soil groups, and rainfall events into response units, then applies one documented SCS-CN implementation. The Monte Martica/Lake Varese profile is a case-study configuration; the synthetic sample is only for software verification and is not a scientific result.

## Quick start

```bash
conda env create -f environment.yml
conda activate geoproject
python sample_data/create_sample_data.py
python -m postfire_runoff.cli.run_pipeline --config config/sample.yaml --force
streamlit run postfire_runoff/frontend/app.py --server.headless true --server.port 8501
```

Open <http://127.0.0.1:8501>.

## Workflow

1. Prepare or upload input files listed in `config/project.yaml`.
2. Run the core runoff pipeline.
3. Inspect generated maps/tables in the Streamlit app.
4. Optionally import a user-exported WEPPcloud CSV or run the lake WQ availability check when real local imagery exists.

```bash
python -m postfire_runoff.cli.run_pipeline --config config/project.yaml --force
python -m postfire_runoff.cli.run_lake_wq --config config/project.yaml
```

The sample loop writes canonical processed files under `data/processed/` and tables under `outputs/tables/`.

## Input-to-output contract

`config/sample.yaml` and `config/project.yaml` map logical inputs to paths: catchment boundary, official fire perimeter, burn severity, land cover, HSG, rainfall events, optional lake inputs, and optional WEPPcloud export. Runtime outputs use:

```text
data/processed/
outputs/tables/
outputs/models/weppcloud/
outputs/run_metadata.json
```

No `runs/` selector or deleted frontend/backend stack is required.

## Documentation

- `docs/USER_MANUAL.md` — setup, UI tabs, upload, run order, and errors.
- `docs/MODEL_METHOD.md` — response units, curve numbers, SCS-CN equations, WEPPcloud/lake boundaries.
- `docs/ARCHITECTURE.md` — compact module/file architecture and schemas.
- `docs/DATA_REQUIREMENTS.md` — supported formats, fields, CRS, units.
- `docs/OUTPUTS.md` — generated files and table schemas.
- `docs/WEB_INTERFACE.md` — Streamlit pages with existing screenshots.

## Screening-level limitations

- Outputs are uncalibrated scenario estimates, not observed discharge.
- HSG and land-cover inputs must be supplied; there is no silent soil fallback.
- dNBR or supplied burn classes are remote-sensing proxies, not field soil-burn severity.
- WEPPcloud exports are contextual external model evidence, not SCS-CN validation.
- Lake NDTI/NDCI summaries are unavailable unless valid local pre/post imagery is configured.

## License

GPLv3. See [LICENSE](LICENSE).
