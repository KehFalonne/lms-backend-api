"""
Storage abstraction.

Local dev: files live under MEDIA_ROOT, uploads go through Django, downloads
use HMAC-signed time-limited URLs served by Django.

Production (S3/R2/MinIO): boto3-generated presigned PUT/GET URLs.
"""

import hashlib
import hmac
import time
import uuid
from pathlib import Path
from typing import TypedDict

from django.conf import settings
from django.core.files.storage import default_storage

from .models import StorageProvider


class PresignedUpload(TypedDict):
    upload_url: str
    method: str
    storage_key: str
    headers: dict


# ──────────────────────────────────────────────────────────────────────
# Local backend
# ──────────────────────────────────────────────────────────────────────


def _provider() -> str:
    return getattr(settings, "STORAGE_PROVIDER", "LOCAL").upper()


def _local_sign(storage_key: str, ttl: int) -> str:
    secret = settings.SECRET_KEY.encode()
    expires = int(time.time()) + ttl
    msg = f"{storage_key}:{expires}".encode()
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return f"{expires}:{sig}"


def verify_local_signature(storage_key: str, signature: str) -> bool:
    try:
        expires_str, sig = signature.split(":", 1)
        expires = int(expires_str)
    except (ValueError, AttributeError):
        return False
    if expires < time.time():
        return False
    expected = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{storage_key}:{expires}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig)


def make_storage_key(filename: str, prefix: str = "uploads") -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return f"{prefix}/{uuid.uuid4().hex}{'.' + ext if ext else ''}"


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────


def generate_upload_target(
    filename: str, prefix: str = "uploads", mime_type: str | None = None
) -> PresignedUpload:
    """Returns a URL the client can upload to directly."""
    provider = getattr(settings, "STORAGE_PROVIDER", "LOCAL").upper()
    storage_key = make_storage_key(filename, prefix)

    if provider == "LOCAL":
        sig = _local_sign(storage_key, ttl=900)
        return {
            "upload_url": f"/api/v1/files/local-upload/?key={storage_key}&sig={sig}",
            "method": "PUT",
            "storage_key": storage_key,
            "headers": {"Content-Type": "application/octet-stream"},
        }

    # S3-compatible
    import boto3

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
    )
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": storage_key,
            **({"ContentType": mime_type} if mime_type else {}),
        },
        ExpiresIn=900,
    )
    return {
        "upload_url": url,
        "method": "PUT",
        "storage_key": storage_key,
        "headers": {"Content-Type": mime_type} if mime_type else {},
    }


def generate_download_url(storage_key: str, expires_in: int = 600) -> str:
    """Signed GET URL, time-limited."""
    provider = getattr(settings, "STORAGE_PROVIDER", "LOCAL").upper()

    if provider == "LOCAL":
        sig = _local_sign(storage_key, ttl=expires_in)
        return f"/api/v1/files/local-download/?key={storage_key}&sig={sig}"

    import boto3

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
    )
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": storage_key,
        },
        ExpiresIn=expires_in,
    )


def save_local_upload(storage_key: str, content) -> None:
    """Persist an uploaded file into local MEDIA storage."""
    default_storage.save(storage_key, content)


def local_file_exists(storage_key: str) -> bool:
    return default_storage.exists(storage_key)


def local_open(storage_key: str):
    return default_storage.open(storage_key, "rb")
