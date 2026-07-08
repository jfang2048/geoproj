# Project summary: Lake Varese / Monte Martica post-fire runoff screening

This repository implements a reproducible, screening-level GIS workflow for the January 2019 Monte Martica wildfire near Lake Varese, Lombardy, Italy. The local model estimates event-scale direct runoff differences with a simplified SCS-CN method; WEPPcloud-EU is used as an independent process-model benchmark for water balance, erosion, and sediment delivery.

---

## Key current results

| Metric | Current value |
|---|---:|
| Local DEM-derived catchment | 1,311.76 ha |
| Official fire perimeter | 376.25 ha |
| Official fire inside current catchment | 280.14 ha (74.5%) |
| Conservative dNBR burned proxy | 23.80 ha (1.8% of catchment) |
| Fire-perimeter upper bound | 280.76 ha (21.4% of catchment) |
| Max local SCS-CN runoff-potential change, conservative | 0.282 mm (~3,696 m³) |
| Max local SCS-CN runoff-potential change, upper bound | 5.505 mm (~72,208 m³) |
| WEPPcloud sediment discharge, undisturbed → disturbed | 293.0 → 652.6 tonne/yr (+122.7%) |
| WEPPcloud stream discharge | 2,124 → 2,125 mm/yr |

---

## Interpretation guardrails

- Local runoff outputs are screening-level, uncalibrated scenario estimates.
- dNBR is a remote-sensing burn-severity proxy, not field soil burn severity.
- The current single outlet represents one drainage area; it does not cover the whole official fire perimeter.
- WEPPcloud is a benchmark, not validation of local SCS-CN.
- No observed discharge, sediment, turbidity, chlorophyll-a, or calibrated water-quality impact is claimed.

---

## Main documents

- `docs/FINAL_PROJECT_AUDIT.md`: final status, claims, limitations.
- `docs/REPRODUCIBILITY.md`: commands, CRS policy, outputs.
- `docs/PROJECT_CN.md`: Chinese summary.
- `docs/PRESENTATION_DRAFT_CN_2H.md`: Chinese 2-hour presentation draft.

## Lake water-quality linkage

### Python-only lake water-quality closure

The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes. It does not redo the runoff model and does not alter the WEPPcloud benchmark. Active code lives under `scripts/lake_wq/`; legacy top-level scripts 16 and 17 are thin wrappers only.

`NDTI = (B4 - B3) / (B4 + B3)` is the primary lake-side response because it is closer to suspended sediment / turbidity. `NDCI = (B5 - B4) / (B5 + B4)` is secondary and indirect because chlorophyll-a depends on nutrients, light, temperature, mixing, stratification, and biological lag. Anomalies are `post_event - pre_event`.

Current selected events are `RAIN_053`, `RAIN_057`, `RAIN_083`, `RAIN_089`, `RAIN_082`, `RAIN_068`, `RAIN_046`, `RAIN_072`, `RAIN_013`, and `RAIN_067`, ranked by `delta_volume_m3`. Local SAFE ZIPs under `data/raw/zip/` now include 9 products (January 2019: 4 scenes; November 2020: 5 scenes). RAIN_089 has pre-window images but no post-window image; all other events still lack both. No complete pre/post pair exists; `MISSING_LOCAL_IMAGE` / `MISSING_POST_IMAGE` status is reported rather than filled with GEE.

Allowed wording: “The Python-only workflow attempts a screening-level linkage between event-scale runoff potential and Lake Varese water-quality proxy anomalies from local Sentinel-2 L2A scenes.” Avoid chlorophyll-a forecast language, runoff-to-chlorophyll causal attribution, calibrated-result language, WEPPcloud-as-validation language, measured-runoff-increase language, and lake-impact proof language.
