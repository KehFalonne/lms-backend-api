from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import UserSession

class SessionJWTAuthentication(JWTAuthentication):
    """Authenticate JWTs and reject tokens from revoked student sessions."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not hasattr(user, "student_profile"):
            return user

        session_id = validated_token.get("session_id")
        if not session_id:
            raise AuthenticationFailed("Session expired or revoked.", code="session_revoked")

        if not UserSession.objects.filter(
            id=session_id,
            user=user,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            raise AuthenticationFailed("Session expired or revoked.", code="session_revoked")

        return user
