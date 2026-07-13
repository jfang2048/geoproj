# Model method

## Runtime path

```text
input selection
→ configuration
→ GIS normalization
→ response-unit construction
→ SCS-CN calculation
→ generated outputs
→ Streamlit display
```

The command-line pipeline and Streamlit **Run pipeline** button use the same backend path. Streamlit preview controls also call the backend SCS-CN implementation, but they do not overwrite generated outputs.

## GIS normalization

All spatial inputs must have a declared CRS. The pipeline reprojects vectors and rasters to the configured processing CRS, normally EPSG:32632. EPSG:4326 is used only for web maps and exchange files.

The official fire perimeter is a context layer. It is not converted into burn severity.

## Burn classes and response units

Burn severity uses integer classes:

| Code | Meaning |
|---|---|
| 0 | unburned |
| 1 | low severity |
| 2 | moderate severity |
| 3 | high severity |
| 255 | raster NoData |

Vector burn polygons are clipped to the catchment. Polygons with the same burn class may be dissolved. Overlaps between different burn classes are rejected because they would double-count area. The catchment area outside burned class 1–3 polygons is assigned `burn_class = 0`, so the final burn layer covers the catchment once.

Response units are the intersection of catchment, land cover, hydrologic soil group, and the completed burn layer. The output schema is:

```text
unit_id, landcover_class, hsg, burn_class, baseline_cn, burned_cn,
cn_adjustment, area_m2, area_ha, geometry
```

The pipeline fails if response units materially omit catchment area or double-count area.

## Land cover and HSG

Land-cover labels are normalized with:

```python
str(value).strip().lower().replace("-", "_").replace(" ", "_")
```

Supported classes are `forest`, `shrub`, `grassland`, `agriculture`, `urban`, `bare_soil`, `water`, and `other`. Aliases include `open_water → water`, `built_up → urban`, `woodland → forest`, and `cropland → agriculture`. Unknown labels raise an error unless a project-specific mapping is added under `landcover.mappings` in the YAML configuration.

Hydrologic soil groups must normalize to `A`, `B`, `C`, or `D`.

## Curve numbers and burn adjustment

Baseline AMC-II curve numbers come from the lookup table in the active YAML configuration. Burned curve numbers add the configured class increment:

```text
burned_cn = min(baseline_cn + burn_curve_number_adjustment[burn_class], 98)
```

Invalid curve numbers, rainfall depths, and initial abstraction ratios are rejected.

## SCS-CN runoff calculation

For rainfall depth `P` in millimetres and curve number `CN`:

```text
S  = 25400 / CN - 254
Ia = lambda * S
Q  = 0                                      when P <= Ia
Q  = (P - Ia)^2 / (P + (1 - lambda) * S)   when P > Ia
```

For response-unit area `A_i`:

```text
catchment runoff depth = sum(Q_i * A_i) / sum(A_i)
runoff volume          = sum((Q_i / 1000) * A_i)
delta Q                = Q_burned - Q_baseline
delta V                = V_burned - V_baseline
```

## WEPPcloud comparison

WEPPcloud is limited to a user-exported CSV import. Required columns are defined once in `postfire_runoff/backend/services/weppcloud.py` and are used by both upload checks and backend import. The normalized table is optional and is displayed as a contextual comparison, not as calibration or verification of event SCS-CN runoff.

## Future work

A future water-quality extension could combine runoff-event selection with valid Sentinel-2 reflectance data and lake regions of interest. That work is not part of the executable product until numeric optical-index calculations and input handling are implemented end to end.
