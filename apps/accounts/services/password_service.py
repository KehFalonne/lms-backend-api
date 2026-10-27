"""
Password change + reset workflows.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone

from apps.accounts.selectors import get_user_by_identifier
from apps.accounts.services.auth_service import AuthError
from apps.accounts.tasks.email_tasks import (
    send_password_reset_email,
    send_password_changed_email,
)

User = get_user_model()


class PasswordService:
    @staticmethod
    def change_password(*, user, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise AuthError(
                "Current password is incorrect.", code="invalid_current_password"
            )
        if current_password == new_password:
            raise AuthError(
                "New password must be different from the current one.",
                code="password_unchanged",
            )

        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

        # Fire-and-forget notification (post-commit, per doc §6)
        send_password_changed_email.delay(str(user.id))

    @staticmethod
    def initiate_reset(*, email: str) -> None:
        """
        Always returns the same result — never reveals whether the email
        exists (avoid user enumeration).
        """
        user = get_user_by_identifier(email)
        if not user or not user.is_active:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_password_reset_email.delay(str(user.id), uid, token)

    @staticmethod
    def confirm_reset(*, uid: str, token: str, new_password: str):
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise AuthError("Invalid or expired reset link.", code="invalid_reset_link")

        if not default_token_generator.check_token(user, token):
            raise AuthError("Invalid or expired reset link.", code="invalid_reset_link")

        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        send_password_changed_email.delay(str(user.id))
        return user
