"""Backend upload checks."""
from pathlib import Path

import yaml

from postfire_runoff.backend.services.uploads import CATEGORY_RULES, accepted_extensions_for, handle_upload, validate_upload


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


def test_upload_assignment_updates_correct_configuration_key(tmp_path):
    cfg = tmp_path / "config/project.yaml"
    cfg.parent.mkdir()
    cfg.write_text("inputs: {}\n")
    data = b"event_id,start_date,end_date,rainfall_mm\nE1,2020-01-01,2020-01-01,12\n"

    result = handle_upload("Rainfall / weather", "rain.csv", data, root=tmp_path, config_path=cfg)

    assert result.valid
    assert result.assigned_config_key == "inputs.rainfall_events"
    assigned = yaml.safe_load(cfg.read_text())["inputs"]["rainfall_events"]
    assert assigned == "data/raw/rainfall_events/rain.csv"
    assert (tmp_path / assigned).exists()


def test_extensions_are_limited_to_consumed_formats():
    assert ".csv" in accepted_extensions_for("Rainfall / weather")
    assert ".zip" not in accepted_extensions_for("Rainfall / weather")
    assert "Lake water quality" not in CATEGORY_RULES
