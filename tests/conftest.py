from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest


@pytest.fixture
def isolated_runs(tmp_path):
    from app.core import config

    object.__setattr__(config.settings, "runs_dir", tmp_path / "runs")
    config.settings.runs_dir.mkdir(parents=True, exist_ok=True)
    return config.settings.runs_dir
