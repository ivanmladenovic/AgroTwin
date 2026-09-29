from functools import lru_cache
from pathlib import Path
import logging

from app.core.config import get_settings
from app.storage.base import ObjectStorage
from app.storage.local import LocalFilesystemStorage

logger = logging.getLogger(__name__)


@lru_cache
def get_storage() -> ObjectStorage:
    settings = get_settings()
    backend = (settings.storage_backend or "local").lower().strip()
    if backend == "s3":
        if settings.s3_bucket and settings.s3_access_key and settings.s3_secret_key:
            from app.storage.s3 import S3Storage

            return S3Storage()
        logger.warning(
            "STORAGE_BACKEND=s3 but S3 credentials are missing; falling back to local storage"
        )
    root = Path(settings.storage_local_path)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    return LocalFilesystemStorage(root)
