"""Thin legacy wrapper for scripts/lake_wq/figures/fig12_lake_water_quality_event_panel.py."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lake_wq.figures.fig12_lake_water_quality_event_panel import main

if __name__ == "__main__":
    main()
