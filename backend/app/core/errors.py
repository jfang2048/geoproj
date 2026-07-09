"""Typed application errors."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base error returned by API handlers with an explicit error code."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SafePathError(AppError):
    status_code = 400
    code = "unsafe_path"


class UploadValidationError(AppError):
    status_code = 422
    code = "upload_validation_failed"


class DependencyMissingError(AppError):
    status_code = 500
    code = "dependency_missing"


class MissingRequiredInputError(AppError):
    status_code = 422
    code = "missing_required_input"


class ProcessingError(AppError):
    status_code = 422
    code = "processing_failed"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class JobError(AppError):
    status_code = 409
    code = "job_error"
