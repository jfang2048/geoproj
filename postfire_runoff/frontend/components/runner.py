"""Safe subprocess runner for predefined project commands."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from postfire_runoff.frontend.components.paths import ROOT, WEBAPP_RUN_LOGS

COMMAND_SPECS: dict[str, dict] = {
    "Run pipeline": {
        "args": [sys.executable, "-m", "postfire_runoff.cli.run_pipeline", "--force"],
        "verify": [ROOT / "postfire_runoff/cli/run_pipeline.py"],
    },
    "Run lake WQ compute": {
        "args": [sys.executable, "-m", "postfire_runoff.cli.run_lake_wq"],
        "verify": [ROOT / "postfire_runoff/cli/run_lake_wq.py"],
    },
    "Run minimal tests": {
        "args": [sys.executable, "-m", "pytest", "-q"],
        "verify": [ROOT / "tests/test_scs_cn.py"],
    },
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


def command_available(label: str) -> bool:
    spec = COMMAND_SPECS.get(label)
    return bool(spec) and all(p.exists() for p in spec.get("verify", []))


def available_commands() -> list[str]:
    return [label for label in COMMAND_SPECS if command_available(label)]


def unavailable_commands() -> list[str]:
    return [label for label in COMMAND_SPECS if not command_available(label)]


def run_command(label: str) -> RunResult:
    spec = COMMAND_SPECS.get(label)
    if spec is None:
        return RunResult(label=label, returncode=-1, stdout="", stderr=f"Unknown: {label}", log_path=Path())
    if not command_available(label):
        return RunResult(label=label, returncode=-1, stdout="", stderr="Target script not found", log_path=Path())
    WEBAPP_RUN_LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
    log_path = WEBAPP_RUN_LOGS / f"{ts}_{safe_label}.log"
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(spec["args"], cwd=ROOT, capture_output=True, text=True, timeout=600)
    finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path.write_text(
        f"COMMAND: {' '.join(spec['args'])}\n"
        f"STARTED: {started}\nFINISHED: {finished}\nRETURNCODE: {result.returncode}\n"
        f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}\n"
    )
    return RunResult(label, result.returncode, result.stdout, result.stderr, log_path, started, finished)
