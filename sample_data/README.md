# Sample data

This directory is reserved for small local sample datasets and generators.
Sample data are for testing the upload workflow only. Production runs must use user-supplied GIS and rainfall files uploaded through the browser.

Run the generator after installing backend dependencies:

```bash
python sample_data/create_sample_data.py
```

The generator writes small files under `sample_data/generated/`:

- `dem.tif`
- `fire_perimeter.geojson`
- `burn_severity.geojson`
- `land_cover.geojson`
- `hydrologic_soil_group.geojson`
- `rainfall_events.csv`
