from __future__ import annotations

import io

import pytest


def test_path_safety_rejects_traversal():
    from app.storage.paths import sanitize_filename
    from app.core.errors import SafePathError

    assert sanitize_filename("rain_event.csv") == "rain_event.csv"
    with pytest.raises(SafePathError):
        sanitize_filename("../rain_event.csv")
    with pytest.raises(SafePathError):
        sanitize_filename("nested/rain_event.csv")


def test_upload_validation_stores_accepted_file_under_run(isolated_runs):
    from app.services.run_service import create_run
    from app.services.upload_service import accept_upload
    from app.storage.manifest import load_manifest

    run = create_run("upload-test")
    csv = b"event_id,start_date,end_date,rainfall_mm,units\nE1,2020-01-01,2020-01-01,12.5,mm\n"
    result = accept_upload(run["run_id"], "rainfall", "rain.csv", io.BytesIO(csv))
    manifest = load_manifest(run["run_id"])

    assert result["checksum_sha256"]
    assert manifest["inputs"]["rainfall"]["path"].startswith("inputs/rainfall/")
    assert (isolated_runs / run["run_id"] / manifest["inputs"]["rainfall"]["path"]).exists()


def test_manifest_writing_records_required_keys(isolated_runs):
    from app.services.run_service import create_run
    from app.storage.manifest import load_manifest

    run = create_run("manifest-test")
    manifest = load_manifest(run["run_id"])
    for key in [
        "run_id",
        "timestamp",
        "app_version",
        "input_filenames",
        "input_checksums",
        "spatial_metadata",
        "raster_resolution",
        "bounds",
        "nodata_values",
        "selected_parameters",
        "generated_outputs",
        "output_checksums",
        "warnings",
        "fatal_errors",
    ]:
        assert key in manifest
