# Final Project Audit

**Date:** 2026-07-08
**Status:** Complete — screening-level workflow with data-limited lake WQ closure.

## Active workflow

Local SCS-CN event runoff + WEPPcloud-EU sediment/water-balance benchmark + Python-only lake WQ closure.

GEE is not used.

## Main results

| Metric | Value |
|---|---|
| DEM-derived catchment | 1,311.76 ha |
| Official fire perimeter | 376.25 ha |
| Fire inside catchment | 280.14 ha (74.5%) |
| Conservative dNBR burned proxy | 23.80 ha (1.8% of catchment) |
| Fire-perimeter upper bound | 280.76 ha (21.4%) |
| Max runoff-potential change, conservative | 0.282 mm (~3,696 m³) |
| Max runoff-potential change, upper bound | 5.505 mm (~72,208 m³) |
| WEPPcloud sediment, undisturbed → disturbed | 293.0 → 652.6 tonne/yr (+122.7%) |
| WEPPcloud stream discharge | 2,124 → 2,125 mm/yr |

Spatial validation decision: `WARN` (single outlet, coarse HSG). Minimal reproducibility checks retained.

## Lake WQ status

Selected events (by `delta_volume_m3`): `RAIN_053`, `RAIN_057`, `RAIN_083`, `RAIN_089`, `RAIN_082`, `RAIN_068`, `RAIN_046`, `RAIN_072`, `RAIN_013`, `RAIN_067`.

Local Sentinel-2 SAFE ZIPs cover `2018-12-31` to `2019-01-15` only — insufficient for selected event pre/post windows (2019-04 through 2020-12). Status: `MISSING_LOCAL_IMAGE`. No fake NDTI/NDCI anomalies. No GEE fallback.

## Figures

fig01–fig09: real data. fig10–fig12: data-limited placeholders. fig13: conceptual closure diagram with data-limited annotation.

## Supported claims

- The project provides a reproducible screening-level workflow linking wildfire disturbance, event-scale runoff sensitivity, WEPPcloud sediment response, and a Python-only but data-limited lake water-quality proxy closure.
- The strongest process-model signal is WEPPcloud sediment discharge increase (+122.7%).
- Conservative local runoff response is small because the conservative dNBR footprint is small (23.80 ha).
- Burned-footprint definition dominates the uncertainty envelope.
- Turbidity proxy (NDTI) is primary; chlorophyll-a proxy (NDCI) is secondary and indirect.

## Unsupported claims

Do not claim: runoff predicts chlorophyll-a; observed post-fire runoff increase; lake impact proof; calibrated water-quality prediction; WEPPcloud validates SCS-CN; GEE was used.

## Remaining limitations

Burn footprint definition dominates uncertainty. Single outlet covers 74.5% of fire. dNBR is a remote-sensing proxy, not field soil burn severity. No observed discharge/sediment/water-quality validation data. Lake WQ cannot produce numeric proxy anomalies without additional Sentinel-2 scenes in `data/raw/zip/`.

## Final presentation sentence

> The project is complete as a screening-level post-fire runoff and sediment-risk workflow, with a transparent but data-limited lake water-quality closure.
