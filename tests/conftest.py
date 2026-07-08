"""Shared test fixtures and path resolution for the Lake Varese / Monte Martica project.

All test files can now use `from conftest import ROOT, get_path` or rely on
pytest collecting this conftest to add the scripts/ directory to sys.path.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Expose ROOT and get_path for convenience in test assertions
from pipeline_utils import ROOT as _ROOT, get_path as _get_path  # noqa: E402

ROOT = _ROOT
get_path = _get_path
