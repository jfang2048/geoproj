"""Map geometry checks."""
from pathlib import Path

import sample_data.create_sample_data as sample
from postfire_runoff.backend.pipeline.runoff import run_pipeline
from postfire_runoff.frontend.components.maps import burn_raster_features, validate_geographic_features

ROOT = Path(__file__).resolve().parents[1]


def test_web_burn_geometries_are_geographic_coordinates():
    if not (ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif").exists():
        sample.main()
        run_pipeline("config/sample.yaml", force=True)
    features = burn_raster_features(ROOT / "data/processed/burn/burn_severity_proxy_uint8.tif")
    assert features
    assert validate_geographic_features(features)
