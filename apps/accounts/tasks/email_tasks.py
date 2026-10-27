"""
Email tasks — dispatched via Celery, per backend doc §34.

All tasks are idempotent-safe and fail silently (never block the request).
"""

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

logger = logging.getLogger(__name__)
User = get_user_model()

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:3000")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    ignore_result=True,
)
def send_welcome_email(self, user_id: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_welcome_email: user %s not found", user_id)
        return

    subject = f"Welcome to {settings.INSTITUTION_NAME} LMS"
    body = (
        f"Hi {user.first_name},\n\n"
        f"Your account is ready.\n"
        f"University ID: {user.university_id}\n"
        f"Sign in: {FRONTEND_URL}/login\n\n"
        f"— {settings.INSTITUTION_NAME}"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    ignore_result=True,
)
def send_password_reset_email(self, user_id: str, uid: str, token: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    reset_url = f"{FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    subject = "Reset your GU-LMS password"
    body = (
        f"Hi {user.first_name},\n\n"
        f"Click the link below to reset your password. This link expires in 24 hours.\n\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— {settings.INSTITUTION_NAME}"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    ignore_result=True,
)
def send_password_changed_email(self, user_id: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    subject = "Your GU-LMS password was changed"
    body = (
        f"Hi {user.first_name},\n\n"
        f"Your password was changed successfully. If this wasn't you, "
        f"contact administration immediately.\n\n"
        f"— {settings.INSTITUTION_NAME}"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
