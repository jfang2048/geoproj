"""Backend upload validation checks content, not just extensions."""
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from postfire_runoff.backend.services.uploads import accepted_extensions_for, validate_upload


def test_rainfall_upload_requires_event_id_and_rainfall_alias():
    good = b"event_id,start_date,end_date,total_precip_mm\nE1,2020-01-01,2020-01-01,12\n"
    result = validate_upload("Rainfall / weather", "rain.csv", len(good), good)
    assert result.valid
    bad = b"date,value\n2020-01-01,12\n"
    result = validate_upload("Rainfall / weather", "rain.csv", len(bad), bad)
    assert not result.valid
    assert "rainfall" in result.message


def test_vector_upload_rejects_unreadable_content_even_with_valid_extension():
    data = b"not a geojson file"
    result = validate_upload("Catchment boundary", "bad.geojson", len(data), data)
    assert not result.valid
    assert "not readable" in result.message


def test_extensions_are_narrowed_to_supported_pipeline_formats():
    assert ".csv" in accepted_extensions_for("Rainfall / weather")
    assert ".zip" not in accepted_extensions_for("Rainfall / weather")
