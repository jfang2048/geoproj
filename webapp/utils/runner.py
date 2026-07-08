"""Safe subprocess runner for executing predefined project commands."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from webapp.utils.paths import ROOT, WEBAPP_RUN_LOGS

# Predefined safe commands — only these may be executed.
# Keys are button labels; values are argument lists passed to subprocess.run.
COMMANDS: dict[str, list[str]] = {
    "Run pipeline (04→13)": [
        sys.executable, str(ROOT / "scripts/run_pipeline.py"),
        "--from", "04", "--to", "13", "--keep-going", "--force",
    ],
    "Run spatial QA": [
        sys.executable, str(ROOT / "scripts/14_quantitative_spatial_qa.py"),
    ],
    "Run lake WQ compute": [
        sys.executable, str(ROOT / "scripts/lake_wq/run_compute_lake_wq.py"),
    ],
    "Redraw lake WQ figures": [
        sys.executable, str(ROOT / "scripts/lake_wq/figures/run_lake_wq_figures.py"),
    ],
    "Redraw all final figures": [
        sys.executable, str(ROOT / "scripts/figures/run_all_atomic_figures.py"),
    ],
    "Run minimal tests": [
        sys.executable, "-m", "pytest", "-q",
        str(ROOT / "tests/test_lake_wq_closure.py"),
        str(ROOT / "tests/test_crs.py"),
    ],
}


@dataclass
class RunResult:
    label: str
    returncode: int
    stdout: str
    stderr: str
    log_path: Path
    started: str = ""
    finished: str = ""


def run_command(label: str) -> RunResult:
    if label not in COMMANDS:
        return RunResult(
            label=label,
            returncode=-1,
            stdout="",
            stderr=f"Unknown command label: {label}",
            log_path=Path(),
        )
    WEBAPP_RUN_LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(" ", "_").replace("→", "to").replace("(", "").replace(")", "")
    log_path = WEBAPP_RUN_LOGS / f"{ts}_{safe_label}.log"

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cmd = COMMANDS[label]
    result = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, timeout=600,
    )
    finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write log
    log_text = (
        f"COMMAND: {' '.join(cmd)}\n"
        f"STARTED: {started}\n"
        f"FINISHED: {finished}\n"
        f"RETURNCODE: {result.returncode}\n"
        f"--- STDOUT ---\n{result.stdout}\n"
        f"--- STDERR ---\n{result.stderr}\n"
    )
    log_path.write_text(log_text)

    return RunResult(
        label=label,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        log_path=log_path,
        started=started,
        finished=finished,
    )


def available_commands() -> list[str]:
    return list(COMMANDS.keys())
