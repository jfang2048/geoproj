"""Purpose: Bootstrap project workspace — create directories, config files, control documents, and log/status scaffolding.
Inputs: config/*.yaml defaults from pipeline_utils.
Outputs: Canonical directory tree, config/project.yaml, config/sources.yaml, config/paths.yaml, qa/audit/README.md, source_manifest.csv, local_data_inventory.csv.
CRS: EPSG:32632 (written into project config).
Units: N/A.
Assumptions: Default config values are safe starting points; user must review for local conditions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import (
    BACKLOG,
    MANIFEST_COLUMNS,
    ROOT,
    WORKING_CRS,
    StepLog,
    append_run_log,
    ensure_workspace,
    update_backlog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the Lake Varese / Monte Martica automation workspace.")
    parser.add_argument("--force-note", action="store_true", help="Append a setup note even when all outputs already exist.")
    args = parser.parse_args()

    created = ensure_workspace()
    required = [
        ROOT / "config/project.yaml",
        ROOT / "config/sources.yaml",
        ROOT / "config/paths.yaml",
        ROOT / "qa/evidence/source_manifest.csv",
        ROOT / "qa/evidence/README.md",
        BACKLOG,
    ]
    missing = [str(p) for p in required if not p.exists()]
    status = "FAILED" if missing else ("DONE" if created else "SKIPPED")
    reason = "Workspace initialized." if created else "SKIPPED_VALID_OUTPUT_EXISTS: workspace files already exist."
    if missing:
        reason = f"Required setup outputs missing: {missing}"

    update_backlog(
        {"A001": "DONE" if not missing else "FAILED", "A002": "DONE" if not missing else "FAILED", "A003": "DONE" if not missing else "FAILED", "A004": "DONE" if not missing else "FAILED"},
        reason,
        Path(__file__).name,
    )
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Create canonical workspace, configuration, log, manifest, blocker, and manual-task files.",
            inputs=["qa/audit/README.md"],
            outputs=["config/*.yaml", "data/", "qa/evidence/source_manifest.csv", "qa/audit/README.md"],
            status=status,
            reason=reason,
            files_created=created,
            files_reused=[str(p.relative_to(ROOT)) for p in required if p.exists() and str(p.relative_to(ROOT)) not in created],
            qa_checks=["Required folders exist", f"Manifest columns={','.join(MANIFEST_COLUMNS)}", f"Working CRS configured as {WORKING_CRS}"],
            next_action="Run scripts/01_inventory_existing_data.py.",
        )
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
