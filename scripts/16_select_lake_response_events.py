"""Thin legacy wrapper for the Python-only lake WQ event selector."""
from __future__ import annotations
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lake_wq.compute_select_events import main

if __name__ == "__main__":
    raise SystemExit(main())
