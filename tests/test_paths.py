"""Test project-root path resolution."""
from pathlib import Path
from geoproject.io.paths import project_root


def test_project_root_exists():
    root = project_root()
    assert root.exists()
    assert root.is_dir()


def test_project_root_is_path():
    assert isinstance(project_root(), Path)
