"""Pydantic response schemas for the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RunCreateRequest(BaseModel):
    name: str | None = None


class RunSummary(BaseModel):
    run_id: str
    name: str
    timestamp: str
    status: str
    manifest_path: str


class UploadResponse(BaseModel):
    run_id: str
    category: str
    filename: str
    checksum_sha256: str
    metadata: dict[str, Any]
    message: str


class JobStartRequest(BaseModel):
    step: Literal["preprocessing", "modeling", "qa_report"]
    parameters: dict[str, Any] = Field(default_factory=dict)


class JobStatus(BaseModel):
    job_id: str
    run_id: str
    step: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress_message: str = ""
    log_file_path: str | None = None
    error_message: str | None = None
    output_manifest_path: str | None = None


class LayerInfo(BaseModel):
    layer_id: str
    label: str
    exists: bool
    reason: str | None = None
    url: str | None = None
    geometry_type: str | None = None
    downloadable: bool = False


class DownloadInfo(BaseModel):
    key: str
    description: str
    kind: str
    path: str
    checksum_sha256: str
    url: str
