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
from apps.audit.services.audit_service import AuditService

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

        # Students may only have one active device session. Revoke their
        # previous refresh tokens and invalidate its access tokens as well.
        if hasattr(user, "student_profile"):
            now = datetime.now(dt_timezone.utc)
            UserSession.objects.filter(
                user=user, revoked_at__isnull=True
            ).update(revoked_at=now)

        # Track session (hash-only, per database doc §23)
        expires_at = datetime.fromtimestamp(refresh["exp"], tz=dt_timezone.utc)
        session = UserSession.objects.create(
            user=user,
            refresh_token_hash=AuthService._hash_token(str(refresh)),
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else "",
            expires_at=expires_at,
        )
        refresh["session_id"] = str(session.id)

        user._skip_audit_log = True
        try:
            user.touch_last_login()
        finally:
            del user._skip_audit_log
        AuditService.record(
            action="AUTH_LOGIN",
            actor=user,
            entity_type="User",
            entity_id=user.id,
            metadata={"ip_address": ip_address, "user_agent": user_agent[:500]},
        )

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }

    @staticmethod
    @transaction.atomic
    def logout(*, refresh_token: str, request=None) -> None:
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
        session = UserSession.objects.select_related("user").filter(
            refresh_token_hash=token_hash, revoked_at__isnull=True
        ).first()
        if session:
            session.revoked_at = datetime.now(dt_timezone.utc)
            session.save(update_fields=["revoked_at"])
            AuditService.record(
                action="AUTH_LOGOUT",
                actor=session.user,
                entity_type="User",
                entity_id=session.user_id,
                request=request,
            )
