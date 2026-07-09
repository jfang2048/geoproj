"""Test project-root path resolution."""
from pathlib import Path
from scripts.export_onlycode import ROOT


def test_export_script_root_exists():
    assert ROOT.exists()
    assert ROOT.is_dir()


def test_onlycode_output_path():
    onlycode = ROOT / "onlycode"
    assert str(onlycode).endswith("onlycode")
