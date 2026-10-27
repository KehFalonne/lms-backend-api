"""
Authentication service.

Views orchestrate; this file owns the business rules:
  • credential resolution
  • status check
  • session tracking
  • login/last-login update
"""

import hashlib
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserSession, UserStatus
from apps.accounts.selectors import get_user_by_identifier

User = get_user_model()


class AuthError(Exception):
    """Domain-level auth error — mapped to DRF exceptions in the view."""

    def __init__(self, message: str, code: str = "auth_error"):
        super().__init__(message)
        self.code = code


class AuthService:
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    @transaction.atomic
    def login(
        *,
        identifier: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> dict:
        user = get_user_by_identifier(identifier)
        if not user or not user.check_password(password):
            raise AuthError("Invalid credentials.", code="invalid_credentials")

        if user.status == UserStatus.SUSPENDED:
            raise AuthError(
                "Account suspended. Contact administration.", code="suspended"
            )
        if user.status == UserStatus.LOCKED:
            raise AuthError("Account locked. Contact administration.", code="locked")
        if user.status == UserStatus.INACTIVE and not user.is_superuser:
            raise AuthError("Account inactive.", code="inactive")
        if not user.is_active:
            raise AuthError("Account disabled.", code="disabled")

        refresh = RefreshToken.for_user(user)

        # Track session (hash-only, per database doc §23)
        expires_at = datetime.fromtimestamp(refresh["exp"], tz=dt_timezone.utc)
        UserSession.objects.create(
            user=user,
            refresh_token_hash=AuthService._hash_token(str(refresh)),
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else "",
            expires_at=expires_at,
        )

        user.touch_last_login()

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }

    @staticmethod
    @transaction.atomic
    def logout(*, refresh_token: str) -> None:
        """
        Revoke a refresh token. Idempotent — never leaks whether the token
        was valid.
        """
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return  # already invalid/blacklisted — no-op

        token_hash = AuthService._hash_token(refresh_token)
        UserSession.objects.filter(
            refresh_token_hash=token_hash, revoked_at__isnull=True
        ).update(revoked_at=datetime.now(dt_timezone.utc))
