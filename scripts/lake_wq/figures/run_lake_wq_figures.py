"""Run Python-only Lake Varese water-quality figure scripts."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

FIGURE_DIR = Path(__file__).resolve().parent
FIGURES = [
    "fig10_runoff_vs_lake_turbidity_proxy.py",
    "fig11_runoff_vs_lake_chla_proxy.py",
    "fig12_lake_water_quality_event_panel.py",
    "fig13_runoff_to_lake_wq_closure.py",
]


def main() -> int:
    failed = 0
    for name in FIGURES:
        script = FIGURE_DIR / name
        print(f"\n=== lake WQ {name} ===")
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.returncode != 0:
            failed += 1
            print(f"  WARNING: {name} failed: {result.stderr}")
    print(f"\nLake WQ figures completed with {failed}/{len(FIGURES)} failures")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
