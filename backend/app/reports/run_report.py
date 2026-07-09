"""Run report writer."""
from __future__ import annotations

from pathlib import Path

from app.storage.manifest import load_manifest
from app.storage.paths import require_run_dir


def write_run_report(run_id: str) -> Path:
    base = require_run_dir(run_id)
    manifest = load_manifest(run_id)
    path = base / "reports" / "run_report.md"
    inputs = manifest.get("inputs", {})
    outputs = manifest.get("outputs", {})
    warnings = manifest.get("warnings", [])
    errors = manifest.get("fatal_errors", [])
    params = manifest.get("selected_parameters", {})
    lines = [
        f"# Run report: {run_id}",
        "",
        "## Scope",
        "",
        "This run is a screening-level post-fire runoff calculation. It is not a discharge forecast and is not a calibrated hydrologic simulation.",
        "",
        "## Inputs",
        "",
        "| Category | File | SHA-256 | CRS | Bounds | Resolution | NoData |",
        "|---|---|---|---|---|---|---|",
    ]
    for category, entry in sorted(inputs.items()):
        meta = entry.get("metadata", {})
        lines.append(
            "| {category} | {filename} | {checksum} | {crs} | {bounds} | {resolution} | {nodata} |".format(
                category=category,
                filename=entry.get("filename", ""),
                checksum=entry.get("checksum_sha256", "")[:12],
                crs=meta.get("crs", "tabular"),
                bounds=_short(meta.get("bounds")),
                resolution=_short(meta.get("resolution")),
                nodata=meta.get("nodata", ""),
            )
        )
    lines.extend(["", "## Parameters", ""])
    if params:
        for key, value in sorted(params.items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("No model parameters recorded yet.")
    lines.extend(["", "## Outputs", "", "| Key | Path | Type | Checksum |", "|---|---|---|---|"])
    for key, entry in sorted(outputs.items()):
        lines.append(
            f"| {key} | `{entry.get('path', '')}` | {entry.get('kind', '')} | {entry.get('checksum_sha256', '')[:12]} |"
        )
    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("No warnings recorded.")
    lines.extend(["", "## Fatal errors", ""])
    if errors:
        for error in errors:
            if isinstance(error, dict):
                lines.append(f"- {error.get('message', '')}")
            else:
                lines.append(f"- {error}")
    else:
        lines.append("No fatal errors recorded.")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Curve numbers are screening parameters from a documented lookup table.",
            "- Burn severity may be a remote-sensing proxy if the uploaded layer is dNBR-derived.",
            "- Area and volume calculations use the analysis CRS recorded in the manifest.",
            "- Display layers are converted for browser mapping only and are not used for measurement.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _short(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "[" + ", ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in value) + "]"
    return str(value)
