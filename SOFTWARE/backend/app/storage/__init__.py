from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.storage.base import ObjectStorage
from app.storage.local import LocalFilesystemStorage


@lru_cache
def get_storage() -> ObjectStorage:
    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "s3":
        from app.storage.s3 import S3Storage

        return S3Storage()
    root = Path(settings.storage_local_path)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    return LocalFilesystemStorage(root)
