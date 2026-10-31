import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationType(models.TextChoices):
    ANNOUNCEMENT = "ANNOUNCEMENT", _("Announcement")
    ASSIGNMENT = "ASSIGNMENT", _("Assignment")
    ASSESSMENT = "ASSESSMENT", _("Assessment")
    GRADE = "GRADE", _("Grade")
    DISCUSSION = "DISCUSSION", _("Discussion")
    CA_INVIGILATOR_MESSAGE = "CA_INVIGILATOR_MESSAGE", _("CA invigilator message")
    SYSTEM = "SYSTEM", _("System")


class Notification(models.Model):
    """Database doc §20."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(
        _("type"),
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
        db_index=True,
    )

    title = models.CharField(_("title"), max_length=200)
    message = models.TextField(_("message"))

    entity_type = models.CharField(_("entity type"), max_length=50, blank=True)
    entity_id = models.UUIDField(_("entity id"), null=True, blank=True)

    data = models.JSONField(_("data"), default=dict, blank=True)

    read_at = models.DateTimeField(_("read at"), null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.type} → {self.recipient_id}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
