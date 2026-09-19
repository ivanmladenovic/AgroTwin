from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ObjectStorage(Protocol):
    """Store file bytes outside PostgreSQL.

    Local filesystem is used in development. An S3-compatible backend can be
    swapped in later without changing callers.
    """

    def put(self, key: str, content: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def local_path(self, key: str) -> Path | None:
        """Filesystem path when the backend is local, otherwise None."""
