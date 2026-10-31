"""
Creates notifications + broadcasts them to WebSocket groups.

Called from any app via `NotificationService.push(...)`.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def broadcast_user_event(*, user_id, event_type: str, payload: dict) -> None:
        """Broadcast a transient event without creating a notification row."""
        layer = get_channel_layer()
        if not layer:
            return
        try:
            async_to_sync(layer.group_send)(
                f"user_{user_id}",
                {"type": event_type.replace(".", "_"), "payload": payload},
            )
        except Exception:
            logger.exception("Failed to broadcast user event %s", event_type)

    @staticmethod
    def push(
        *,
        recipient,
        type: str,
        title: str,
        message: str,
        entity_type: str = "",
        entity_id=None,
        data: dict | None = None,
        broadcast: bool = True,
    ) -> Notification:
        n = Notification.objects.create(
            recipient=recipient,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
        )
        if broadcast:
            NotificationService._broadcast(n)
        return n

    @staticmethod
    def push_bulk(
        *,
        recipients,
        type: str,
        title: str,
        message: str,
        **kwargs,
    ):
        created = [
            Notification(
                recipient=user,
                type=type,
                title=title,
                message=message,
                **kwargs,
            )
            for user in recipients
        ]
        Notification.objects.bulk_create(created)
        for n in created:
            NotificationService._broadcast(n)
        return created

    @staticmethod
    def mark_read(notification: Notification) -> None:
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])

    @staticmethod
    def mark_all_read(user) -> int:
        return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
            read_at=timezone.now()
        )

    @staticmethod
    def _broadcast(notification: Notification) -> None:
        layer = get_channel_layer()
        if not layer:
            logger.debug("No channel layer for %s", notification.id)
            return
        group = f"user_{notification.recipient_id}"
        payload = {
            "id": str(notification.id),
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "createdAt": notification.created_at.isoformat(),
        }
        try:
            async_to_sync(layer.group_send)(
                group,
                {"type": "notification.created", "payload": payload},
            )

        except Exception as e:
            logger.exception(
                "Failed to broadcast notification for %s",
                notification.id,
            )

    @staticmethod
    def notify_enrolled_students(
        *,
        course_offering_id,
        type: str,
        title: str,
        message: str,
        entity_type: str = "",
        entity_id=None,
        data: dict | None = None,
    ):
        """
        Notify every actively-enrolled student in a course offering.
        Returns count of notifications created.
        """
        from apps.courses.models import CourseEnrollment, EnrollmentStatus
        from django.contrib.auth import get_user_model

        User = get_user_model()
        student_ids = CourseEnrollment.objects.filter(
            course_offering_id=course_offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).values_list("student_id", flat=True)

        if not student_ids:
            return 0

        recipients = list(User.objects.filter(id__in=student_ids, is_active=True))
        if not recipients:
            return 0

        NotificationService.push_bulk(
            recipients=recipients,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
        )
        return len(recipients)
