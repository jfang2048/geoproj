"""Central path resolution for the GeoProject tool.

Project root is determined by, in order:
1. GEOPROJECT_ROOT environment variable
2. current working directory
"""
from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("GEOPROJECT_ROOT", "")
    if env:
        root = Path(env).resolve()
        if root.exists():
            return root
    return Path.cwd()


DATA_RAW_ZIP = "data/raw/zip"
DATA_PROCESSED = "data/processed"
OUTPUTS = "outputs"
RUNS = "runs"
SAMPLE_DATA = "sample_data"
