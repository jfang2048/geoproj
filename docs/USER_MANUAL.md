# User manual

## Setup

Place input data under `data/raw/zip/`. Copy `config/example_project.yaml` to `config/project.yaml`.

## Run the workflow

```bash
python scripts/run_pipeline.py
python scripts/lake_wq/run_compute_lake_wq.py
python scripts/list_required_sentinel2_windows.py
```

## Launch web interface

```bash
streamlit run webapp/app.py --server.headless true
```

## Interpreting results

All runoff outputs are screening-level and uncalibrated. dNBR is a remote-sensing proxy, not field soil burn severity. WEPPcloud is a benchmark, not validation of local SCS-CN. Lake WQ is Python-only; NDTI is the primary turbidity proxy, NDCI is secondary and indirect.
