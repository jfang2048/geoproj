# Lake WQ Closure Change Log

Date: 2026-07-08

## Direction change

The lake water-quality closure is Python-only. GEE / Google Earth Engine is not used.

## Active implementation

- `scripts/lake_wq/__init__.py`
- `scripts/lake_wq/config.py`
- `scripts/lake_wq/io.py`
- `scripts/lake_wq/s2_safe.py`
- `scripts/lake_wq/compute_select_events.py`
- `scripts/lake_wq/compute_rois.py`
- `scripts/lake_wq/compute_s2_indices.py`
- `scripts/lake_wq/compute_zonal_anomalies.py`
- `scripts/lake_wq/compute_analytical_context.py`
- `scripts/lake_wq/run_compute_lake_wq.py`
- `scripts/lake_wq/figures/*.py`

Legacy top-level scripts 16 and 17 are thin wrappers only.

## Selected events

Selected by primary ranking metric `delta_volume_m3`: `RAIN_053`, `RAIN_057`, `RAIN_083`, `RAIN_089`, `RAIN_082`, `RAIN_068`, `RAIN_046`, `RAIN_072`, `RAIN_013`, and `RAIN_067`.

## Sentinel-2 availability

Local Sentinel-2 L2A SAFE ZIPs under `data/raw/zip/` currently cover `2018-12-31`, `2019-01-02`, `2019-01-10`, and `2019-01-15`. They are not sufficient for the selected high-runoff event windows. The validation record therefore stores `MISSING_LOCAL_IMAGE`; no fake anomaly values are generated and no GEE fallback is used.

## Supported claim

“The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes.”

Turbidity proxy is the primary lake-side response; chlorophyll-a proxy is treated as delayed and indirect.

## Unsupported claims

- Runoff predicts chlorophyll-a.
- GEE was used in the active workflow.
- The water-quality response is calibrated.
- The model proves post-fire lake impact.
- WEPPcloud validates the SCS-CN runoff model.
- Observed post-fire runoff increase has been demonstrated.
