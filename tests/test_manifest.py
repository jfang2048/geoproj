"""Test run manifest creation and writing."""
import json
from postfire_runoff.io.manifest import (
    create_run_manifest, add_input, add_output,
    add_warning, add_error, set_succeeded,
)


def test_create_manifest():
    m = create_run_manifest(run_id="test-001")
    assert m["run_id"] == "test-001"
    assert m["status"] == "started"
    assert "timestamp" in m
    assert m["processing_crs"] == "EPSG:32632"


def test_add_input_records_checksum():
    m = create_run_manifest("r1")
    add_input(m, "dem", __import__("pathlib").Path("/tmp/dem.tif"), "abc123")
    assert m["inputs"]["dem"] == "/tmp/dem.tif"
    assert m["input_checksums"]["dem"] == "abc123"


def test_add_output():
    m = create_run_manifest("r1")
    add_output(m, "runoff", __import__("pathlib").Path("/tmp/runoff.csv"), "def456")
    assert "runoff" in m["outputs"]
    assert m["output_checksums"]["runoff"] == "def456"


def test_add_warning():
    m = create_run_manifest("r1")
    add_warning(m, "cloud cover 80%")
    assert "cloud cover 80%" in m["warnings"]


def test_add_error_sets_failed():
    m = create_run_manifest("r1")
    add_error(m, "missing rainfall")
    assert m["status"] == "failed"
    assert "missing rainfall" in m["errors"]


def test_set_succeeded():
    m = create_run_manifest("r1")
    set_succeeded(m)
    assert m["status"] == "succeeded"


def test_error_overrides_succeeded():
    m = create_run_manifest("r1")
    add_error(m, "bad input")
    set_succeeded(m)
    assert m["status"] == "failed"


def test_manifest_serializable(tmp_path):
    m = create_run_manifest("r1")
    add_input(m, "dem", __import__("pathlib").Path("/tmp/dem.tif"))
    p = tmp_path / "manifest.json"
    json.dumps(m, default=str)  # verify serializable
    p.write_text(json.dumps(m, indent=2, default=str))
    assert p.exists()
