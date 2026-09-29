from __future__ import annotations

from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.exceptions import AppError


class S3Storage:
    """S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, …)."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket or not settings.s3_access_key or not settings.s3_secret_key:
            raise AppError(
                "S3 skladište nije podešeno. Postavite S3_BUCKET, S3_ACCESS_KEY i S3_SECRET_KEY.",
                status_code=503,
                code="storage_not_configured",
            )
        self.bucket = settings.s3_bucket
        kwargs: dict = {
            "service_name": "s3",
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region or "auto",
            "config": Config(signature_version="s3v4"),
        }
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.client = boto3.client(**kwargs)

    def put(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type or "application/octet-stream",
            )
        except ClientError as exc:
            raise AppError(
                f"Upis u S3 skladište nije uspeo: {exc}",
                status_code=502,
                code="storage_write_failed",
            ) from exc

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = (exc.response or {}).get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise AppError(
                f"Čitanje iz S3 skladišta nije uspelo: {exc}",
                status_code=502,
                code="storage_read_failed",
            ) from exc
        body = response.get("Body")
        if body is None:
            raise FileNotFoundError(key)
        return body.read()

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError:
            pass

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def local_path(self, key: str) -> Path | None:
        return None
