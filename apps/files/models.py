import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class StorageProvider(models.TextChoices):
    LOCAL = "LOCAL", _("Local (dev)")
    S3 = "S3", _("Amazon S3")
    R2 = "R2", _("Cloudflare R2")
    MINIO = "MINIO", _("MinIO")


class FileStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending upload")
    READY = "READY", _("Ready")
    DELETED = "DELETED", _("Deleted")


class File(models.Model):
    """
    Metadata for a stored file (database doc §13).

    The binary lives in object storage; this table is the source of truth
    for access control, mime type, size, and ownership.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    original_name = models.CharField(_("original name"), max_length=255)
    storage_key = models.CharField(
        _("storage key"),
        max_length=500,
        unique=True,
        db_index=True,
    )
    mime_type = models.CharField(_("mime type"), max_length=150, blank=True)
    extension = models.CharField(_("extension"), max_length=20, blank=True)
    size_bytes = models.BigIntegerField(_("size (bytes)"), default=0)
    checksum = models.CharField(_("checksum"), max_length=128, blank=True)

    storage_provider = models.CharField(
        _("storage provider"),
        max_length=20,
        choices=StorageProvider.choices,
        default=StorageProvider.LOCAL,
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.PENDING,
        db_index=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_files",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("file")
        verbose_name_plural = _("files")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["uploaded_by"]),
            models.Index(fields=["storage_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.human_size})"

    @property
    def human_size(self) -> str:
        size = self.size_bytes
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
