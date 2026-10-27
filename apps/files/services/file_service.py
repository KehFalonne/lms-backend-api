"""
File lifecycle: request upload → complete → access-checked download → delete.
"""

import mimetypes
import os
from pathlib import Path

from django.db import transaction

from apps.files.models import File, FileStatus, StorageProvider
from apps.files.storage import (
    generate_download_url,
    generate_upload_target,
    local_file_exists,
)
from apps.common.exceptions.handlers import global_exception_handler  # noqa: F401
from rest_framework.exceptions import ValidationError

MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {
    # documents
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "md",
    "csv",
    # images
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "svg",
    # audio/video
    "mp3",
    "mp4",
    "wav",
    "webm",
    "mov",
    # archives
    "zip",
    "tar",
    "gz",
}


class FileService:

    @staticmethod
    def validate(filename: str, size_bytes: int) -> tuple[str, str]:
        """
        Returns (extension, mime_type). Raises ValidationError on rejection.
        """
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError({"file": [f"Extension '.{ext}' is not allowed."]})
        if size_bytes <= 0:
            raise ValidationError({"file": ["File size must be positive."]})
        if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                {"file": [f"File exceeds {MAX_FILE_SIZE_MB} MB limit."]}
            )
        mime, _ = mimetypes.guess_type(filename)
        return ext, mime or "application/octet-stream"

    @staticmethod
    def request_upload(
        *,
        user,
        filename: str,
        size_bytes: int,
        mime_type: str | None = None,
        prefix: str = "uploads",
    ) -> dict:
        ext, guessed = FileService.validate(filename, size_bytes)

        target = generate_upload_target(filename, prefix=prefix)
        provider = getattr(
            __import__("django.conf", fromlist=["settings"]).settings,
            "STORAGE_PROVIDER",
            "LOCAL",
        ).upper()

        # Store placeholder File row (status=PENDING) — completed later.
        file = File.objects.create(
            original_name=filename,
            storage_key=target["storage_key"],
            mime_type=mime_type or guessed,
            extension=ext,
            size_bytes=size_bytes,
            storage_provider=provider,
            status=FileStatus.PENDING,
            uploaded_by=user,
        )

        return {
            "file_id": str(file.id),
            "upload_url": target["upload_url"],
            "method": target["method"],
            "storage_key": target["storage_key"],
            "headers": target["headers"],
        }

    @staticmethod
    @transaction.atomic
    def complete_upload(*, user, file_id: str) -> File:
        try:
            file = File.objects.select_for_update().get(id=file_id, uploaded_by=user)
        except File.DoesNotExist:
            raise ValidationError({"file": ["File not found."]})

        if file.status != FileStatus.PENDING:
            raise ValidationError({"file": ["File is not awaiting upload."]})

        # For LOCAL, verify the file actually landed.
        if file.storage_provider == StorageProvider.LOCAL:
            if not local_file_exists(file.storage_key):
                raise ValidationError({"file": ["Upload not found. Please retry."]})

        file.status = FileStatus.READY
        file.save(update_fields=["status", "updated_at"])
        return file

    @staticmethod
    def get_download_url(file: File, expires_in: int = 600) -> str:
        if file.status != FileStatus.READY:
            raise ValidationError({"file": ["File is not ready."]})
        return generate_download_url(file.storage_key, expires_in=expires_in)

    @staticmethod
    @transaction.atomic
    def soft_delete(file: File) -> None:
        from django.utils import timezone

        file.status = FileStatus.DELETED
        file.deleted_at = timezone.now()
        file.save(update_fields=["status", "deleted_at", "updated_at"])
