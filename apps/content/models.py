import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class ContentType(models.TextChoices):
    TEXT = "TEXT", _("Text")
    FILE = "FILE", _("File")
    VIDEO = "VIDEO", _("Video")
    AUDIO = "AUDIO", _("Audio")
    PDF = "PDF", _("PDF")
    DOCUMENT = "DOCUMENT", _("Document")
    LINK = "LINK", _("Link")
    EMBED = "EMBED", _("Embed")


class CourseModule(models.Model):
    """Database doc §12.1 — a week/module within a course offering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="modules",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    position = models.PositiveSmallIntegerField(_("position"), default=1)

    availability_start = models.DateTimeField(
        _("available from"), null=True, blank=True
    )
    availability_end = models.DateTimeField(_("available until"), null=True, blank=True)
    is_published = models.BooleanField(_("published"), default=False, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="modules_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("course module")
        verbose_name_plural = _("course modules")
        ordering = ["course_offering", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_offering", "position"],
                name="uniq_module_position_per_offering",
            ),
        ]
        indexes = [
            models.Index(fields=["course_offering", "position"]),
        ]

    def __str__(self) -> str:
        return f"{self.course_offering_id} — M{self.position}: {self.title}"

    def clean(self):
        if (
            self.availability_start
            and self.availability_end
            and self.availability_start >= self.availability_end
        ):
            raise ValidationError(
                {"availability_end": _("Must be after availability start.")}
            )


class ContentItem(models.Model):
    """Database doc §12.2 — a piece of learning content inside a module."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_module = models.ForeignKey(
        CourseModule, on_delete=models.CASCADE, related_name="content_items"
    )
    title = models.CharField(_("title"), max_length=200)
    content_type = models.CharField(
        _("content type"),
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.TEXT,
    )

    description = models.TextField(_("description"), blank=True)
    body = models.TextField(_("body"), blank=True)
    external_url = models.URLField(_("external URL"), blank=True)

    # Placeholder — real File FK arrives in Sprint 6.
    file_id = models.UUIDField(
        _("file"),
        null=True,
        blank=True,
        help_text=_("Placeholder FK to File (Sprint 6)."),
    )

    position = models.PositiveSmallIntegerField(_("position"), default=1)
    is_required = models.BooleanField(_("required"), default=False)

    availability_start = models.DateTimeField(
        _("available from"), null=True, blank=True
    )
    availability_end = models.DateTimeField(_("available until"), null=True, blank=True)
    is_published = models.BooleanField(_("published"), default=False, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="content_items_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("content item")
        verbose_name_plural = _("content items")
        ordering = ["course_module", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_module", "position"],
                name="uniq_content_position_per_module",
            ),
        ]
        indexes = [
            models.Index(fields=["course_module", "position"]),
            models.Index(fields=["content_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.content_type})"

    def clean(self):
        if (
            self.content_type in (ContentType.LINK, ContentType.EMBED)
            and not self.external_url
        ):
            raise ValidationError(
                {"external_url": _("URL is required for LINK and EMBED content.")}
            )


class ContentItemVersion(models.Model):
    """Historical PDF file references retained when a lecturer replaces a PDF."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_item = models.ForeignKey(
        ContentItem, on_delete=models.CASCADE, related_name="versions"
    )
    file_id = models.UUIDField(null=True, blank=True)
    external_url = models.URLField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    version_number = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="content_item_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_item", "version_number"],
                name="uniq_content_item_version",
            )
        ]
