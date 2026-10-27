"""
User lifecycle — activation, deactivation, deletion policy.

We do NOT hard-delete users (their academic records must survive). Instead
we flip `status` to INACTIVE and `is_active=False`.
"""

from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import UserStatus
from apps.accounts.serializers import user

User = get_user_model()


class UserService:
    @staticmethod
    @transaction.atomic
    def activate(user) -> "User":
        user.status = UserStatus.ACTIVE
        user.is_active = True
        user.save(update_fields=["status", "is_active", "updated_at"])
        return user

    @staticmethod
    @transaction.atomic
    def deactivate(user) -> "User":
        user.status = UserStatus.INACTIVE
        user.is_active = False
        user.save(update_fields=["status", "is_active", "updated_at"])

        # Revoke all live sessions
        user.sessions.filter(revoked_at__isnull=True).update(
            revoked_at=datetime.now(dt_timezone.utc)
        )
        return user
