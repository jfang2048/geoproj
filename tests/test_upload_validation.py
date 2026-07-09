"""Test upload validation, path safety, and content inspection."""
import pytest
from postfire_runoff.io.safe_files import sanitize_filename
from postfire_runoff.io.checksums import sha256_hex
from postfire_runoff.gis.raster_validation import inspect_raster, RasterInfo
from postfire_runoff.gis.vector_validation import inspect_vector, VectorInfo


class TestSafeFilename:
    def test_basic(self):
        assert sanitize_filename("dem.tif") == "dem.tif"

    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            sanitize_filename("../etc/passwd")

    def test_rejects_null(self):
        with pytest.raises(ValueError):
            sanitize_filename("")

    def test_strips_chars(self):
        r = sanitize_filename("file:name?.tif")
        assert ":" not in r
        assert "?" not in r

    def test_traversal_dots(self):
        with pytest.raises(ValueError):
            sanitize_filename("..")


class TestChecksums:
    def test_sha256_known(self):
        assert sha256_hex(b"hello") == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_sha256_empty(self):
        assert len(sha256_hex(b"")) == 64


class TestRasterInfo:
    def test_unreadable(self, tmp_path):
        f = tmp_path / "bad.tif"
        f.write_bytes(b"not a tif")
        info = inspect_raster(f)
        assert not info.readable
        assert len(info.errors) > 0


class TestVectorInfo:
    def test_unreadable(self, tmp_path):
        f = tmp_path / "bad.gpkg"
        f.write_bytes(b"not a gpkg")
        info = inspect_vector(f)
        assert not info.readable
        assert len(info.errors) > 0

    def test_raster_info_struct(self):
        info = RasterInfo(path="x.tif")
        assert not info.readable
        assert info.width == 0

    def test_vector_info_struct(self):
        info = VectorInfo(path="x.gpkg")
        assert not info.readable
        assert info.feature_count == 0
