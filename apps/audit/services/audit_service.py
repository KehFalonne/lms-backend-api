"""
Write-only API for creating audit records.

Callers pass a plain dict — sensitive values must be redacted by the
caller (per database doc §22.1 "never store passwords or secrets").
"""

import logging

from apps.audit.models import AuditLog

logger = logging.getLogger(__name__)

# Keys we never persist
SENSITIVE_KEYS = {
    "password",
    "password1",
    "password2",
    "refresh",
    "access",
    "token",
    "secret",
    "api_key",
    "authorization",
}


def _redact(data: dict | None) -> dict | None:
    if not data:
        return data
    return {
        k: "***REDACTED***" if k.lower() in SENSITIVE_KEYS else v
        for k, v in data.items()
    }


class AuditService:

    @staticmethod
    def record(
        *,
        action: str,
        actor=None,
        entity_type: str = "",
        entity_id=None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        request=None,
        metadata: dict | None = None,
    ) -> AuditLog | None:
        try:
            ip = None
            ua = ""
            if request:
                ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
                    0
                ].strip() or request.META.get("REMOTE_ADDR")
                ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]

            return AuditLog.objects.create(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                old_values=_redact(old_values),
                new_values=_redact(new_values),
                ip_address=ip or None,
                user_agent=ua,
                metadata=metadata or {},
            )
        except Exception:
            logger.exception("Failed to record audit log %s", action)
            return None
