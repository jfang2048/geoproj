"""Structured run logging helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunLogger:
    """Append JSON-lines records to a per-run log file."""

    def __init__(self, run_id: str, log_path: Path):
        self.run_id = run_id
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, step: str, message: str, **fields: Any) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "run_id": self.run_id,
            "step": step,
            "message": message,
            **{k: _json_safe(v) for k, v in fields.items() if v is not None},
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def warning(self, step: str, message: str, **fields: Any) -> None:
        self.record(step, message, level="warning", **fields)

    def error(self, step: str, message: str, **fields: Any) -> None:
        self.record(step, message, level="error", **fields)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value
