"""
Write-only API for creating audit records.

Callers pass a plain dict — sensitive values must be redacted by the
caller (per database doc §22.1 "never store passwords or secrets").
"""

import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from apps.audit.models import AuditLog

logger = logging.getLogger(__name__)

# Keys we never persist
SENSITIVE_KEY_PATTERN = re.compile(
    r"password|token|secret|api.?key|authorization|cookie", re.IGNORECASE
)


def _redact(data):
    if isinstance(data, dict):
        return {
            key: "***REDACTED***"
            if SENSITIVE_KEY_PATTERN.search(str(key))
            else _redact(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_redact(value) for value in data]
    if isinstance(data, tuple):
        return [_redact(value) for value in data]
    if isinstance(data, (date, datetime, time)):
        return data.isoformat()
    if isinstance(data, (Decimal, UUID)):
        return str(data)
    return data


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
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog | None:
        if not action or len(action) > 80:
            logger.error("Audit action must be 1-80 characters")
            return None
        if len(entity_type) > 80:
            logger.error("Audit entity type must be at most 80 characters")
            return None

        try:
            ip = ip_address
            ua = user_agent or ""
            if request:
                forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
                ip = ip or (
                    forwarded_for.split(",", 1)[0].strip()
                    if forwarded_for
                    else request.META.get("REMOTE_ADDR")
                )
                ua = ua or (request.META.get("HTTP_USER_AGENT") or "")[:500]
                if actor is None and getattr(request, "user", None):
                    if request.user.is_authenticated:
                        actor = request.user
                if actor is None:
                    force_user = getattr(request, "_force_auth_user", None)
                    if force_user and force_user.is_authenticated:
                        actor = force_user

            if ip:
                from django.core.exceptions import ValidationError
                from django.core.validators import validate_ipv46_address

                try:
                    validate_ipv46_address(ip)
                except ValidationError:
                    logger.warning("Invalid client IP omitted from audit log %s", action)
                    ip = None

            return AuditLog.objects.create(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                old_values=_redact(old_values),
                new_values=_redact(new_values),
                ip_address=ip or None,
                user_agent=ua[:500],
                metadata=_redact(metadata or {}),
            )
        except Exception:
            logger.exception("Failed to record audit log %s", action)
            return None
