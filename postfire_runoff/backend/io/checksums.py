"""SHA-256 checksum helper for uploaded files."""
from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
