import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AnnouncementStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    PUBLISHED = "PUBLISHED", _("Published")
    ARCHIVED = "ARCHIVED", _("Archived")


class Announcement(models.Model):
    """Database doc §14."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("body"))
    is_pinned = models.BooleanField(_("pinned"), default=False, db_index=True)

    publish_at = models.DateTimeField(_("publish at"), null=True, blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AnnouncementStatus.choices,
        default=AnnouncementStatus.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("announcement")
        verbose_name_plural = _("announcements")
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["course_offering", "status"]),
            models.Index(fields=["is_pinned", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.course_offering_id} — {self.title}"

    def publish(self):
        self.status = AnnouncementStatus.PUBLISHED
        if not self.publish_at:
            self.publish_at = timezone.now()
        self.save(update_fields=["status", "publish_at", "updated_at"])
