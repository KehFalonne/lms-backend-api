"""
Bulk notification tasks (backend doc §34 — "Notification Tasks").
"""

from celery import shared_task

from apps.notifications.services.notification_service import NotificationService


@shared_task(ignore_result=True)
def send_bulk_notification(
    recipient_ids: list, type: str, title: str, message: str, **kwargs
):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.filter(id__in=recipient_ids)
    NotificationService.push_bulk(
        recipients=list(users),
        type=type,
        title=title,
        message=message,
        **kwargs,
    )
