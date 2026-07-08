from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pipeline_utils import ROOT, StepLog, append_run_log, ensure_workspace, update_backlog

STEPS = {
    "00": "00_setup_workspace.py",
    "01": "01_inventory_existing_data.py",
    "02": "02_discover_sources.py",
    "03": "03_download_open_data.py",
    "04": "04_prepare_spatial_frame.py",
    "05": "05_prepare_dem.py",
    "06": "06_discover_sentinel2.py",
    "07": "07_prepare_burn_severity.py",
    "08": "08_prepare_landcover.py",
    "09": "09_prepare_soil.py",
    "10": "10_prepare_weather.py",
    "11": "11_run_simplified_runoff.py",
    "12": "12_generate_outputs.py",
    "13": "13_prepare_weppcloud_package.py",
}


def normalize(value: str) -> str:
    value = str(value).strip()
    if value.isdigit():
        return f"{int(value):02d}"
    raise argparse.ArgumentTypeError(f"Step must be numeric, got {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run selected Lake Varese / Monte Martica pipeline steps.")
    parser.add_argument("--from", dest="from_step", type=normalize, default="00", help="First step number, e.g. 00 or 04.")
    parser.add_argument("--to", dest="to_step", type=normalize, default="12", help="Last step number, e.g. 12.")
    parser.add_argument("--keep-going", action="store_true", help="Continue after failed step and report non-zero at the end.")
    parser.add_argument("--force", action="store_true", help="Pass --force to each selected numbered step so outputs are regenerated instead of skipped.")
    args = parser.parse_args()

    ensure_workspace()
    if args.from_step not in STEPS or args.to_step not in STEPS:
        raise SystemExit(f"Unknown step range {args.from_step}..{args.to_step}; valid steps: {', '.join(STEPS)}")
    start = int(args.from_step)
    end = int(args.to_step)
    if start > end:
        raise SystemExit("--from must be <= --to")

    selected = [step for step in sorted(STEPS) if start <= int(step) <= end]
    failures: list[str] = []
    for step in selected:
        script = ROOT / "scripts" / STEPS[step]
        print(f"[pipeline] Running step {step}: {script.relative_to(ROOT)}", flush=True)
        cmd = [sys.executable, str(script)]
        if args.force:
            help_result = subprocess.run([sys.executable, str(script), "--help"], cwd=ROOT, text=True, capture_output=True, check=False)
            if "--force" in (help_result.stdout or ""):
                cmd.append("--force")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            failures.append(f"{step}:{STEPS[step]}:{result.returncode}")
            if not args.keep_going:
                break

    status = "FAILED" if failures else "DONE"
    reason = "; ".join(failures) if failures else f"Completed steps {args.from_step}..{args.to_step}."
    update_backlog({"A004": "DONE" if not failures else "FAILED"}, reason, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task=f"Run pipeline steps {args.from_step} through {args.to_step}.",
            inputs=[f"steps={','.join(selected)}", f"force={args.force}"],
            outputs=["qa/audit/README.md"],
            status=status,
            reason=reason,
            files_created=[],
            files_reused=[f"scripts/{STEPS[s]}" for s in selected],
            qa_checks=["Subprocess return codes checked"],
            next_action="Inspect README.md and qa/evidence/README.md." if not failures else "Inspect qa/audit/README.md and rerun failed step.",
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
