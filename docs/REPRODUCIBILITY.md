# Reproducibility notes

Run the current pipeline and validation checks from the repository root.

```bash
conda run -n geoproject-auto python scripts/run_pipeline.py --from 04 --to 13 --keep-going --force
/home/jfang/miniconda3/envs/geoproject-auto/bin/python scripts/14_quantitative_spatial_qa.py
/home/jfang/miniconda3/envs/geoproject-auto/bin/python -m pytest -q tests/test_quantitative_spatial_qa.py tests/test_crs.py
```

## Optional web interface

```bash
conda run -n geoproject-auto streamlit run webapp/app.py --server.headless true
```

---

## CRS policy

- Local metric processing: `EPSG:32632`.
- Browser coordinates and WEPPcloud exchange: `EPSG:4326`.
- Never compute area, distance, slope, buffer, or hydrologic routing in degrees.
- Do not use `set_crs` as reprojection.
- Use nearest-neighbour resampling for categorical rasters.

---

## Core outputs

| Group | Key files |
|---|---|
| Core model | `outputs/tables/runoff_delta_by_event.csv`, `runoff_event_summary.csv`, `runoff_units.csv`; `data/processed/boundary/catchment_utm32.gpkg`; `data/processed/burn/burn_severity_proxy_uint8.tif` |
| WEPPcloud benchmark | `outputs/models/weppcloud/WEPPcloud_vs_SCS_CN_COMPARISON.md`; `latex/fig09_weppcloud_sediment.png` |
| Lake WQ closure | `outputs/tables/lake_response_selected_events.csv`, `lake_wq_event_anomalies.csv`, `lake_wq_analytical_context_by_period.csv`; `latex/fig10`–`fig13` |
| Final figures | `latex/fig01a`–`fig13` |
| Spatial validation | `qa/spatial/quantitative_spatial_qa_summary.json` (decision: `WARN`)

---

## Spatial validation status

Current quantitative spatial validation decision: `WARN`. The model is usable as a baseline screening workflow, but whole-fire interpretation requires multiple outlet delineation and improved soil/rainfall/burn footprint evidence.

## Lake water-quality linkage

### Python-only lake water-quality closure

Run the lake-linkage module after the existing runoff outputs are available:

```bash
conda run -n geoproject-auto python scripts/lake_wq/run_compute_lake_wq.py
conda run -n geoproject-auto python scripts/lake_wq/figures/run_lake_wq_figures.py
```

The main atomic figure runner optionally calls the lake WQ figure runner:

```bash
conda run -n geoproject-auto python scripts/figures/run_all_atomic_figures.py
```

Lake WQ outputs are listed in the Core outputs table above. CRS policy remains unchanged. The workflow uses local Sentinel-2 L2A SAFE ZIPs only; if suitable local scenes are unavailable for selected event windows, the project reports `MISSING_LOCAL_IMAGE`. GEE is not used. The lake water-quality link is a screening-level proxy comparison, not calibrated prediction.
