# Data requirements

Place these files under `data/raw/zip/`:

- DEM / DTM: `.zip` (e.g. `DTM5_RL.zip`)
- Fire perimeter: `.zip`, `.gpkg`, or `.shp`
- Sentinel-2 L2A: `.SAFE.zip` (e.g. `S2A_MSIL2A_20190110_*.SAFE.zip`)
- Land cover: `.zip` or `.gpkg`
- Soil / HSG: `.zip`, `.tif`, or `.csv`
- Rainfall: `.zip` or `.csv` (e.g. `RW_*.zip`)

## Sentinel-2 requirements

- Product level: L2A (MSIL2A). L1C is not supported.
- Preferred tile: T32TMR.
- At least one pre-event and one post-event scene per runoff event window.
