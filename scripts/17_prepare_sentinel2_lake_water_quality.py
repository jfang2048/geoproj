"""Thin legacy wrapper for the Python-only lake WQ compute runner.

Deprecated CLI options from the earlier GEE-helper workflow are ignored only when
safe (`--mode local`). GEE helper/export modes are intentionally unsupported.
"""
from __future__ import annotations
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lake_wq.run_compute_lake_wq import main as run_main


def main() -> int:
    args = sys.argv[1:]
    if "--mode" in args:
        idx = args.index("--mode")
        mode = args[idx + 1] if idx + 1 < len(args) else ""
        if mode != "local":
            raise SystemExit("GEE helper/export mode is obsolete and unsupported. Use scripts/lake_wq/run_compute_lake_wq.py.")
        del args[idx:idx + 2]
    if any(a.startswith("--gee") for a in args):
        raise SystemExit("GEE export options are obsolete and unsupported in the Python-only workflow.")
    sys.argv = [sys.argv[0]] + args
    return run_main()


if __name__ == "__main__":
    raise SystemExit(main())
