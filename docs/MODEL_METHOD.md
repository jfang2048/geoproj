# Model method

## Inputs and normalization

The core model requires an explicit catchment boundary, official fire perimeter, burn-severity classes or a burn-class raster, land-cover polygons, hydrologic soil group polygons, and a rainfall event CSV. Vectors are read with their declared CRS, reprojected to EPSG:32632, and rejected if they are missing CRS, invalid, empty, unreadable, or non-overlapping. The official fire perimeter is contextual; it is not converted into measured burn severity.

Rainfall is normalized once to `event_id`, `start_date`, `end_date`, and `rainfall_mm`. Supported aliases such as `total_precip_mm` are converted at input. Downstream code uses `rainfall_mm` only.

## Response units

Response units are produced by intersecting the catchment, land-cover layer, HSG layer, and burn-severity layer. Each unit stores land-cover class, HSG, burn class, area in square metres/hectares, baseline CN, burned CN, and CN adjustment. The pipeline records covered and uncovered catchment area in `outputs/run_metadata.json` and rejects double-counted units.

## Curve numbers

Land-cover labels are normalized to documented hydrologic classes: forest, shrub, grassland, agriculture, urban, bare soil, water, or other. HSG is normalized to A/B/C/D. Baseline AMC-II `CN2` is read from the two-dimensional lookup table in the selected config, with defaults adapted from common NRCS TR-55 hydrologic soil-cover examples. The selected hydrologic condition is a screening assumption and should be reviewed for local case use.

Burn-severity increments are configurable scenario assumptions in `runoff.burn_curve_number_adjustment` (`0/1/2/3` classes). They are not labelled as universal NRCS standards. Invalid CN, rainfall, or lambda values are rejected; burned CN is capped at the documented project maximum of 98.

## SCS-CN equations

For response unit `i` and rainfall depth `P` in millimetres:

```text
S_i = 25400 / CN_i - 254
I_a,i = lambda * S_i
Q_i = 0                                              when P <= I_a,i
Q_i = (P - I_a,i)^2 / (P + (1 - lambda) * S_i)     when P > I_a,i
```

Aggregation uses area `A_i` in square metres:

```text
catchment runoff depth = sum(Q_i * A_i) / sum(A_i)
runoff volume          = sum((Q_i / 1000) * A_i)
delta Q                = Q_burned - Q_baseline
delta V                = V_burned - V_baseline
```

## Burn severity and footprint scenarios

A supplied burn-class layer can contain classes 0 unburned, 1 low, 2 moderate, and 3 high. A dNBR workflow may be added only when valid pre/post Sentinel-2 L2A inputs are read end to end. The NoData code is 255. A footprint scenario must be recomputed spatially from its mask; it must not multiply CN increments by area factors.

## WEPPcloud and lake WQ boundaries

WEPPcloud is an external process-based model/interface. This repository imports user-exported WEPPcloud result CSVs and displays them as contextual comparison only. Annual or period WEPPcloud runoff/sediment and event SCS-CN direct runoff answer different questions.

The optional lake stage records event-window availability. Numeric NDTI/NDCI proxy summaries require real local pre/post imagery and must not be interpreted as measured turbidity or chlorophyll concentration. No correlation, calibration, or causal claim is made without observations.
