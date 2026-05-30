"""MinIO storage helper — TSK-068.

Wraps minio Python SDK untuk upload, presigned URL, dan delete.
Singleton client. Bucket auto-create di startup.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import IO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import get_settings


@lru_cache(maxsize=1)
def get_minio_client() -> Minio:
    """Singleton MinIO client."""
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )
    # Ensure bucket exists
    bucket = settings.minio_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error:
        # Don't crash on bucket check — endpoints will fail visibly if real issue
        pass
    return client


def upload_fileobj(
    file_obj: IO[bytes],
    object_name: str,
    content_type: str = "application/octet-stream",
    length: int = -1,
) -> str:
    """Upload file object to MinIO. Returns the object_name (key)."""
    settings = get_settings()
    client = get_minio_client()
    # If length unknown, set part_size for chunked upload
    part_size = 10 * 1024 * 1024 if length < 0 else 0
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=file_obj,
        length=length,
        part_size=part_size,
        content_type=content_type,
    )
    return object_name


def get_presigned_url(object_name: str, expires_in_seconds: int = 3600) -> str:
    """Presigned URL untuk download (default 1 jam)."""
    settings = get_settings()
    client = get_minio_client()
    return client.presigned_get_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        expires=timedelta(seconds=expires_in_seconds),
    )


def delete_object(object_name: str) -> None:
    settings = get_settings()
    client = get_minio_client()
    try:
        client.remove_object(settings.minio_bucket, object_name)
    except S3Error:
        # Best-effort delete — masih bisa lanjut walaupun gagal
        pass


def object_name_from_url(url: str) -> str:
    """Extract object_name dari MinIO URL.

    URL format biasa: http://endpoint/bucket/object_name?...
    Atau plain object_name kalau stored directly.
    """
    if "://" not in url:
        return url
    parsed = urlparse(url)
    # path: /bucket/object_name
    parts = parsed.path.lstrip("/").split("/", 1)
    if len(parts) == 2:
        return parts[1]
    return parsed.path.lstrip("/")
