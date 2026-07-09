"""Filesystem-backed local job manager."""
from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.errors import JobError, NotFoundError
from app.core.logging import RunLogger
from app.services.processing_service import generate_qa_report, preprocess_run, run_model
from app.storage.manifest import add_fatal_error, load_manifest
from app.storage.paths import ensure_run_layout, require_run_dir

JobFn = Callable[[str, dict[str, Any]], dict[str, Any]]

JOB_FUNCTIONS: dict[str, JobFn] = {
    "preprocessing": preprocess_run,
    "modeling": run_model,
    "qa_report": generate_qa_report,
}


class LocalJobManager:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="runoff-job")
        self.lock = threading.Lock()

    def start(self, run_id: str, step: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        require_run_dir(run_id)
        if step not in JOB_FUNCTIONS:
            raise JobError(f"Unknown job step: {step}")
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        base = ensure_run_layout(run_id)
        log_path = base / "logs" / f"{job_id}.log"
        record = {
            "job_id": job_id,
            "run_id": run_id,
            "step": step,
            "status": "queued",
            "progress_message": "Job queued.",
            "log_file_path": str(log_path.relative_to(base)),
            "error_message": None,
            "output_manifest_path": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._write_job(run_id, job_id, record)
        self.executor.submit(self._run, run_id, job_id, step, parameters or {})
        return record

    def get(self, run_id: str, job_id: str) -> dict[str, Any]:
        path = self._job_path(run_id, job_id)
        if not path.exists():
            raise NotFoundError(f"Job not found: {job_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_for_run(self, run_id: str) -> list[dict[str, Any]]:
        base = require_run_dir(run_id)
        jobs_dir = base / "logs" / "jobs"
        if not jobs_dir.exists():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(jobs_dir.glob("job_*.json"), reverse=True)]

    def _run(self, run_id: str, job_id: str, step: str, parameters: dict[str, Any]) -> None:
        base = require_run_dir(run_id)
        logger = RunLogger(run_id, base / "logs" / f"{job_id}.log")
        self._patch(run_id, job_id, status="running", progress_message=f"Running {step}.")
        logger.record(step, "Job started.", job_id=job_id)
        try:
            manifest = JOB_FUNCTIONS[step](run_id, parameters)
            manifest_path = str((base / "run_manifest.json").relative_to(base))
            self._patch(
                run_id,
                job_id,
                status="succeeded",
                progress_message=f"{step} completed.",
                output_manifest_path=manifest_path,
            )
            logger.record(step, "Job succeeded.", job_id=job_id, output_manifest_path=manifest_path)
        except Exception as exc:
            message = str(exc)
            add_fatal_error(run_id, f"{step} failed: {message}")
            self._patch(run_id, job_id, status="failed", progress_message=f"{step} failed.", error_message=message)
            logger.error(step, "Job failed.", job_id=job_id, error=message)

    def _patch(self, run_id: str, job_id: str, **updates: Any) -> None:
        with self.lock:
            record = self.get(run_id, job_id)
            record.update(updates)
            record["updated_at"] = _now()
            self._write_job(run_id, job_id, record)

    def _write_job(self, run_id: str, job_id: str, record: dict[str, Any]) -> None:
        path = self._job_path(run_id, job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest = load_manifest(run_id)
        manifest.setdefault("jobs", {})[job_id] = record
        (require_run_dir(run_id) / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _job_path(self, run_id: str, job_id: str) -> Path:
        if not job_id.startswith("job_"):
            raise JobError("Unsafe job ID.")
        return require_run_dir(run_id) / "logs" / "jobs" / f"{job_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


job_manager = LocalJobManager()
