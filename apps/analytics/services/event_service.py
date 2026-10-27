"""
Records learning events.

Fire-and-forget: never blocks the request.
"""

import logging

from apps.analytics.models import LearningEvent

logger = logging.getLogger(__name__)


class EventService:

    @staticmethod
    def record(
        *,
        student,
        event_type: str,
        course_offering=None,
        course_offering_id=None,
        entity_type: str = "",
        entity_id=None,
        metadata: dict | None = None,
    ) -> LearningEvent | None:
        # Accept either a CourseOffering instance or a raw UUID
        if course_offering is None and course_offering_id is not None:
            from apps.courses.models import CourseOffering

            course_offering = CourseOffering.objects.filter(
                pk=course_offering_id
            ).first()

        try:
            return LearningEvent.objects.create(
                student=student,
                course_offering=course_offering,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata=metadata or {},
            )
        except Exception:
            logger.exception("Failed to record learning event %s", event_type)
            return None
