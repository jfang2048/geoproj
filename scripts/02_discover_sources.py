"""Purpose: Test reachability of external data sources and document which require manual download.
Inputs: config/sources.yaml.
Outputs: qa/evidence/README.md source-discovery section and blocker/manual-task entries.
CRS: N/A (service discovery only).
Units: N/A.
Assumptions: Automated download attempted only where service endpoints respond safely.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import requests

from pipeline_utils import (
    ROOT,
    StepLog,
    append_run_log,
    ensure_workspace,
    mark_standard_manual_blockers,
    source_config,
    update_backlog,
)


def probe(url: str, timeout: int) -> dict[str, str]:
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "codex-geoproject-discovery/1.0"}, stream=True)
        # Consume at most a tiny chunk; discovery only, not scraping.
        next(response.iter_content(chunk_size=256), b"")
        response.close()
        return {"url": url, "status": str(response.status_code), "ok": str(response.ok), "reason": response.reason or "", "final_url": response.url}
    except Exception as exc:
        return {"url": url, "status": "", "ok": "False", "reason": f"{type(exc).__name__}: {exc}", "final_url": ""}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cautiously discover public source endpoints without aggressive scraping.")
    parser.add_argument("--timeout", type=int, default=12, help="HTTP timeout in seconds per endpoint.")
    args = parser.parse_args()

    ensure_workspace()
    sources = source_config().get("sources", {})
    rows = []
    for key, meta in sources.items():
        url = meta.get("url") or meta.get("search_url")
        if not url:
            continue
        result = probe(url, args.timeout)
        result.update({"source_id": key, "dataset_name": meta.get("dataset_name", ""), "role": meta.get("role", "")})
        rows.append(result)

    mark_standard_manual_blockers()
    report = ROOT / "qa/evidence/README.md"
    lines = ["## Source discovery report", "", "Discovery policy: one lightweight HTTP GET per configured endpoint; no aggressive scraping or credential bypass.", ""]
    lines.append("| source_id | role | status | ok | url | notes |")
    lines.append("|---|---|---|---|---|---|")
    reachable = 0
    for row in rows:
        if row.get("ok") == "True":
            reachable += 1
        lines.append(f"| {row['source_id']} | {row['role']} | {row.get('status','')} | {row.get('ok','')} | {row.get('url','')} | {row.get('reason','')} |")
    lines.extend(
        [
            "",
            "## Manual or blocked sources",
            "",
            "Official fire perimeter, DUSAF 2018, ARPA station weather, detailed soil hydraulic data, and Copernicus product downloads are documented in `qa/evidence/README.md` when automated access is not safely configured.",
        ]
    )
    section = "\n".join(lines) + "\n"
    text = report.read_text(encoding="utf-8") if report.exists() else "# Evidence Log\n"
    pattern = r"\n## Source discovery report\n.*?(?=\n## |\Z)"
    if re.search(pattern, text, flags=re.S):
        text = re.sub(pattern, "\n" + section.rstrip(), text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + section.rstrip()
    report.write_text(text.rstrip() + "\n", encoding="utf-8")

    statuses = {
        "C001": "DONE" if reachable else "BLOCKED",
        "C002": "BLOCKED",
        "C003": "BLOCKED",
        "C004": "DONE" if any("copernicus" in r["source_id"] and r.get("ok") == "True" for r in rows) else "BLOCKED",
        "C005": "PARTIAL" if any("soil" in r["source_id"] and r.get("ok") == "True" for r in rows) else "BLOCKED",
        "C006": "BLOCKED",
    }
    note = f"Probed {len(rows)} endpoints; reachable={reachable}; manual blockers recorded for sources that require layer confirmation, auth, or human request."
    update_backlog(statuses, note, Path(__file__).name)
    append_run_log(
        StepLog(
            script=Path(__file__).name,
            task="Discover public source availability without unsafe scraping.",
            inputs=["config/sources.yaml"],
            outputs=["qa/evidence/README.md"],
            status="PARTIAL" if reachable else "BLOCKED",
            reason=note,
            files_created=["qa/evidence/README.md"],
            files_reused=["config/sources.yaml"],
            qa_checks=["Discovery report written", "Manual blockers are idempotent"],
            next_action="Run scripts/03_download_open_data.py.",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
