"""Orchestrator: runs each atomic figure script in sequence. Generates no figures itself."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parents[1]
ATOMIC = [
    "fig01a_regional_context.py",   # Regional context map, no compass
    "fig01c_local_domain.py",       # Study area map
    "fig02_dem_hydrology_qa.py",    # DEM hydrology QA
    "fig03_response_units_cn.py",   # Response units map
    "fig04_response_unit_cn_adjustment.py", # Burned response-unit CN summary
    "fig04_event_rainfall_response.py", # Rainfall event and runoff response
    "fig05_burn_footprint_area.py", # Burned-footprint area hierarchy
    "fig06_burn_runoff_response.py", # Maximum runoff response by footprint
    "fig07_event_delta_cdf.py",     # Event CDF
    "fig08_sensitivity_hierarchy.py", # Sensitivity tornado
    "fig09_weppcloud_sediment.py",  # WEPPcloud sediment
]

LAKE_WQ_RUNNER = ROOT / "scripts/lake_wq/figures/run_lake_wq_figures.py"

def main() -> int:
    failed = 0
    for name in ATOMIC:
        script = SCRIPTS_DIR / name
        print(f"\n=== {name} ===")
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"  FAILED: {result.stderr}")
            failed += 1
    lake_failed = 0
    if LAKE_WQ_RUNNER.exists():
        print("\n=== optional Python-only lake WQ figures ===")
        result = subprocess.run([sys.executable, str(LAKE_WQ_RUNNER)], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"  WARNING: optional lake WQ figure runner failed and was skipped: {result.stderr}")
            lake_failed = 1
    else:
        print("\nWARNING: optional lake WQ figure runner not found; skipping lake WQ figures")
    print(f"\n{failed}/{len(ATOMIC)} required figures failed; optional lake WQ runner failure={lake_failed}")
    return failed

if __name__ == "__main__":
    raise SystemExit(main())
