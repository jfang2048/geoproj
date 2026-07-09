"""FastAPI routes. Business logic lives in services."""
from __future__ import annotations

from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from app.jobs.manager import job_manager
from app.schemas.api import JobStartRequest, RunCreateRequest
from app.services.layer_service import downloads, layer_catalog, layer_path
from app.services.run_service import create_run, get_run, list_runs
from app.services.upload_service import accept_upload
from app.storage.paths import require_run_dir, resolve_under_run

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/runs")
def create_run_route(payload: RunCreateRequest | None = None) -> dict:
    return create_run(name=payload.name if payload else None)


@router.get("/runs")
def list_runs_route() -> list[dict]:
    return list_runs()


@router.get("/runs/{run_id}")
def get_run_route(run_id: str) -> dict:
    return get_run(run_id)


@router.get("/runs/{run_id}/manifest")
def get_manifest_route(run_id: str) -> dict:
    return get_run(run_id)


@router.post("/runs/{run_id}/uploads/{category}")
def upload_route(run_id: str, category: str, file: UploadFile) -> dict:
    return accept_upload(run_id, category, file.filename or "upload", file.file)


@router.post("/runs/{run_id}/jobs")
def start_job_route(run_id: str, payload: JobStartRequest) -> dict:
    return job_manager.start(run_id, payload.step, payload.parameters)


@router.get("/runs/{run_id}/jobs")
def list_jobs_route(run_id: str) -> list[dict]:
    return job_manager.list_for_run(run_id)


@router.get("/runs/{run_id}/jobs/{job_id}")
def get_job_route(run_id: str, job_id: str) -> dict:
    return job_manager.get(run_id, job_id)


@router.get("/runs/{run_id}/layers")
def layers_route(run_id: str) -> list[dict]:
    return layer_catalog(run_id)


@router.get("/runs/{run_id}/layers/{layer_id}.geojson")
def get_layer_route(run_id: str, layer_id: str) -> FileResponse:
    path = layer_path(run_id, layer_id)
    require_run_dir(run_id)
    return FileResponse(path, media_type="application/geo+json", filename=path.name)


@router.get("/runs/{run_id}/downloads")
def downloads_route(run_id: str) -> list[dict]:
    return downloads(run_id)


@router.get("/runs/{run_id}/download/{relative_path:path}")
def download_route(run_id: str, relative_path: str) -> FileResponse:
    path = resolve_under_run(run_id, relative_path)
    return FileResponse(path, filename=path.name)
