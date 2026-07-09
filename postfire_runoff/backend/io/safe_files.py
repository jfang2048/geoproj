"""Safe filename handling and path traversal prevention."""
from __future__ import annotations

from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Return a safe basename. Rejects path traversal."""
    safe = Path(name).name
    if safe != name:
        raise ValueError(f"Path traversal rejected: {name}")
    if not safe or safe in (".", ".."):
        raise ValueError(f"Invalid filename: {name}")
    for ch in ("\\", ":", "*", "?", '"', "<", ">", "|", "&", ";", "$", "`"):
        safe = safe.replace(ch, "_")
    return safe.strip()
