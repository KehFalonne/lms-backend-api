import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """
    Immutable audit record for sensitive actions (database doc §22.1).

    Never hard-deleted; retention policy is institutional.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )

    action = models.CharField(_("action"), max_length=80, db_index=True)
    entity_type = models.CharField(
        _("entity type"), max_length=80, blank=True, db_index=True
    )
    entity_id = models.UUIDField(_("entity id"), null=True, blank=True, db_index=True)

    old_values = models.JSONField(_("old values"), null=True, blank=True)
    new_values = models.JSONField(_("new values"), null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} on {self.entity_type} by {self.actor_id}"
