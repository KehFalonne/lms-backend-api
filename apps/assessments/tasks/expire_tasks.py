"""
Force-close attempts stuck past their expires_at, without relying on the
student's browser being open (backend doc §4.3.1).
"""

import logging

from celery import shared_task
from django.utils import timezone

from apps.assessments.models import AssessmentAttempt, AttemptStatus

logger = logging.getLogger(__name__)


@shared_task(ignore_result=False)
def expire_stuck_assessment_attempts() -> int:
    now = timezone.now()
    stuck = AssessmentAttempt.objects.filter(
        status=AttemptStatus.IN_PROGRESS,
        expires_at__lt=now,
    )
    count = 0
    for attempt in stuck:
        attempt.status = AttemptStatus.EXPIRED
        attempt.submitted_at = attempt.submitted_at or now
        attempt.save(update_fields=["status", "submitted_at", "updated_at"])

        try:
            from apps.assessments.services.auto_grading_service import (
                AutoGradingService,
            )

            AutoGradingService.grade_attempt(attempt=attempt)
        except Exception:
            logger.exception("Auto-grade failed for expired attempt %s", attempt.id)
        count += 1
    if count:
        logger.info("Expired %s stuck attempts", count)
    return count
