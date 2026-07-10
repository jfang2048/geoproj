# Data requirements

All spatial inputs must declare a CRS. The workflow reprojects to EPSG:32632 for metric processing and uses EPSG:4326 only for display/exchange.

| Logical input | Config key | Formats | Required fields | Notes |
|---|---|---|---|---|
| Catchment boundary | `inputs.catchment_boundary` | GeoPackage, GeoJSON | polygon geometry | Required production boundary. DEM delineation is not hidden. |
| Official fire perimeter | `inputs.fire_perimeter` | GeoPackage, GeoJSON | polygon geometry | Context/reference geometry only. |
| Burn severity | `inputs.burn_severity` | GeoPackage, GeoJSON, GeoTIFF | `burn_class` for vectors; class raster values | Classes 0/1/2/3; 255 NoData for rasters. |
| Land cover | `inputs.land_cover` | GeoPackage, GeoJSON | configured land-cover column | Labels normalize to supported hydrologic classes. |
| Hydrologic soil group | `inputs.hsg` | GeoPackage, GeoJSON | configured HSG column | Values A/B/C/D; no silent fallback. |
| Rainfall events | `inputs.rainfall_events` | CSV | `event_id`, `start_date`, `end_date`, `rainfall_mm` | `total_precip_mm` and selected aliases are converted to `rainfall_mm`. |
| Lake boundary | `inputs.lake_boundary` | GeoPackage, GeoJSON | polygon geometry | Optional lake stage. |
| Lake pre/post imagery | `inputs.lake_pre_event_imagery`, `inputs.lake_post_event_imagery` | reviewed local raster stacks only | reflectance/proxy-ready bands | Optional; absent inputs produce unavailable status. |
| WEPPcloud export | `inputs.weppcloud_export` | CSV | scenario, period, area, runoff, sediment, units, source filename | Imported external evidence only. |

ZIP shapefiles, SAFE ZIP products, IMG, and XLSX are not advertised as core pipeline inputs because the current pipeline does not read them end to end.
