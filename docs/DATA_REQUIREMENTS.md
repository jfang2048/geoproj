# Data requirements

## Required files

| Category | Formats | Required | Notes |
|---|---:|---:|---|
| DEM raster | `.tif`, `.tiff` | Yes | Must have CRS, transform, bounds, valid dimensions, and acceptable pixel type. |
| Fire perimeter or burned area | `.gpkg`, `.geojson`, `.zip` shapefile | Yes | Polygon vector with CRS. Used to derive the screening boundary. |
| Burn severity | `.tif`, `.tiff`, `.gpkg`, `.geojson`, `.zip` shapefile | Yes | Vector requires `burn_class`, `burn_severity`, `severity`, `dnbr_class`, or `soil_burn_severity`. Raster values may be classes 0–3 or dNBR-like values. |
| Land cover | `.tif`, `.tiff`, `.gpkg`, `.geojson`, `.zip` shapefile | Yes | Vector requires `landcover_class`, `land_cover`, `landcover`, `class`, or `lc_class`. |
| Hydrologic soil group | `.tif`, `.tiff`, `.gpkg`, `.geojson`, `.zip` shapefile | Yes for production model run | Vector requires `hsg`, `hydrologic_soil_group`, `soil_group`, or `soil_hsg`. Raster codes 1–4 map to A–D. |
| Rainfall events | `.csv` | Yes | Required columns listed below. |
| Lake or water body | `.gpkg`, `.geojson`, `.zip` shapefile | Optional | Display and context layer. |
| Hydrography | `.gpkg`, `.geojson`, `.zip` shapefile | Optional | Display and context layer. |

## Rainfall CSV columns

Required columns:

```text
event_id,start_date,end_date,rainfall_mm,units
```

Rules:

- `event_id` must be present and unique.
- `start_date` and `end_date` must parse as dates.
- `rainfall_mm` must be numeric and non-negative.
- `units` must be `mm`, `millimeter`, or `millimeters`.

## CRS rules

- All spatial uploads must include a CRS.
- Analysis uses EPSG:32632 unless changed in backend configuration.
- Area and volume calculations are not performed in EPSG:4326.
- Browser display layers are written in EPSG:4326.

## Raster rules

Validation checks:

- readable by rasterio/GDAL
- CRS exists
- bounds exist
- transform exists
- width and height are greater than zero
- resolution is positive and recorded
- NoData is detected or documented as missing
- pixel type is accepted

Categorical rasters use nearest-neighbor resampling. DEM uses bilinear resampling when reprojection is needed.

## Vector rules

Validation checks:

- readable by geopandas/Fiona
- CRS exists
- geometry column exists
- geometry is non-empty
- invalid geometries are reported
- bounds are finite
- required category attributes are present where needed
- shapefile ZIP contents do not use unsafe paths

Invalid geometries are repaired during preprocessing when possible. Failed repair stops processing.
