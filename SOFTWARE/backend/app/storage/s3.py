from __future__ import annotations

from pathlib import Path

from app.core.exceptions import AppError


class S3Storage:
    """Placeholder for a later S3-compatible backend."""

    def __init__(self) -> None:
        raise AppError(
            "S3-compatible storage is not enabled yet. Use STORAGE_BACKEND=local.",
            status_code=501,
            code="storage_not_configured",
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        raise AppError("S3 skladište nije podešeno", status_code=501, code="storage_not_configured")

    def get(self, key: str) -> bytes:
        raise AppError("S3 skladište nije podešeno", status_code=501, code="storage_not_configured")

    def delete(self, key: str) -> None:
        raise AppError("S3 skladište nije podešeno", status_code=501, code="storage_not_configured")

    def local_path(self, key: str) -> Path | None:
        return None
