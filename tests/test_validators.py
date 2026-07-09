"""Test upload validation and content inspection."""
from geoproject.webapp.components.validators import (
    validate_upload, validate_raster_content, validate_vector_content,
    validate_rainfall_csv, _sanitize_filename,
)


def test_sanitize_basic():
    assert _sanitize_filename("dem.tif") == "dem.tif"


def test_sanitize_rejects_traversal():
    try:
        _sanitize_filename("../etc/passwd")
        assert False, "Should have raised"
    except ValueError:
        pass


def test_sanitize_strips_dangerous_chars():
    result = _sanitize_filename("file:name?.tif")
    for ch in (":", "?"):
        assert ch not in result


def test_validate_known_category():
    r = validate_upload("DEM / DTM", "dem.tif", 1024)
    assert r.valid


def test_validate_unknown_category():
    r = validate_upload("Not a category", "x.txt", 100)
    assert not r.valid


def test_validate_empty_file():
    r = validate_upload("DEM / DTM", "dem.tif", 0)
    assert not r.valid


def test_validate_wrong_extension():
    r = validate_upload("DEM / DTM", "dem.exe", 1024)
    assert not r.valid


def test_validate_sentinel2_requires_safe():
    r = validate_upload("Sentinel-2 L2A SAFE", "not_a_safe.zip", 1024)
    assert not r.valid


def test_validate_sentinel2_valid():
    r = validate_upload("Sentinel-2 L2A SAFE", "S2A_MSIL2A_20200101.SAFE.zip", 1024)
    assert r.valid


def test_validate_checksum():
    r = validate_upload("DEM / DTM", "dem.tif", 100, b"hello")
    assert r.checksum
    assert len(r.checksum) == 64


def test_validate_path_traversal():
    r = validate_upload("DEM / DTM", "../dem.tif", 1024)
    assert not r.valid
