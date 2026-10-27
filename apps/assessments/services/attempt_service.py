"""
Attempt lifecycle.

Views stay thin. All transitions go through here so the rules are testable
and reused by the auto-grader.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AttemptStatus,
    StudentAnswer,
)
from apps.courses.models import CourseEnrollment, EnrollmentStatus


class AttemptService:

    @staticmethod
    def _is_enrolled(student, course_offering_id) -> bool:
        return CourseEnrollment.objects.filter(
            student=student,
            course_offering_id=course_offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists()

    # ────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def start_attempt(*, assessment: Assessment, student) -> AssessmentAttempt:
        if not AttemptService._is_enrolled(student, assessment.course_offering_id):
            raise ValidationError({"detail": ["You are not enrolled in this course."]})

        if not assessment.is_open:
            raise ValidationError({"detail": ["Assessment is not open."]})

        existing = AssessmentAttempt.objects.filter(
            assessment=assessment,
            student=student,
        ).count()
        if existing >= assessment.max_attempts:
            raise ValidationError(
                {"detail": [f"Maximum attempts ({assessment.max_attempts}) reached."]}
            )

        expires_at = None
        if assessment.time_limit_minutes:
            expires_at = timezone.now() + timedelta(
                minutes=assessment.time_limit_minutes
            )
        elif assessment.available_until:
            expires_at = assessment.available_until

        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            student=student,
            attempt_number=existing + 1,
            status=AttemptStatus.IN_PROGRESS,
            expires_at=expires_at,
        )
        return attempt

    @staticmethod
    def check_attempt_access(*, attempt: AssessmentAttempt, student) -> None:
        if attempt.student_id != student.id:
            raise ValidationError(
                {"detail": ["This attempt belongs to another student."]}
            )

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError({"detail": ["Attempt is no longer editable."]})

        if attempt.expires_at and timezone.now() > attempt.expires_at:
            raise ValidationError({"detail": ["Attempt has expired."]})

    @staticmethod
    @transaction.atomic
    def save_answer(
        *,
        attempt: AssessmentAttempt,
        assessment_question_id: str,
        student,
        answer_text: str | None = None,
        selected_option_ids: list | None = None,
        numeric_answer=None,
        answer_data: dict | None = None,
    ) -> StudentAnswer:
        AttemptService.check_attempt_access(attempt=attempt, student=student)

        aq = attempt.assessment.assessment_questions.filter(
            pk=assessment_question_id
        ).first()
        if not aq:
            raise ValidationError(
                {"detail": ["Question is not part of this assessment."]}
            )

        defaults: dict = {}
        if answer_text is not None:
            defaults["answer_text"] = answer_text
        if selected_option_ids is not None:
            defaults["selected_option_ids"] = selected_option_ids
        if numeric_answer is not None:
            defaults["numeric_answer"] = numeric_answer
        if answer_data is not None:
            defaults["answer_data"] = answer_data

        answer, _ = StudentAnswer.objects.update_or_create(
            attempt=attempt,
            assessment_question=aq,
            defaults=defaults,
        )
        return answer

    @staticmethod
    @transaction.atomic
    def submit_attempt(*, attempt: AssessmentAttempt, student) -> AssessmentAttempt:
        AttemptService.check_attempt_access(attempt=attempt, student=student)

        attempt.submitted_at = timezone.now()
        attempt.status = AttemptStatus.SUBMITTED
        attempt.save(update_fields=["submitted_at", "status", "updated_at"])

        # Trigger auto-grading (Sprint 8 — service is local)
        from .auto_grading_service import AutoGradingService

        AutoGradingService.grade_attempt(attempt=attempt)

        return attempt

    @staticmethod
    @transaction.atomic
    def expire_if_needed(attempt: AssessmentAttempt) -> bool:
        """Mark an attempt as EXPIRED if past its time limit."""
        if (
            attempt.status == AttemptStatus.IN_PROGRESS
            and attempt.expires_at
            and timezone.now() > attempt.expires_at
        ):
            attempt.status = AttemptStatus.EXPIRED
            attempt.submitted_at = attempt.submitted_at or timezone.now()
            attempt.save(update_fields=["status", "submitted_at", "updated_at"])
            # Still grade whatever was saved
            from .auto_grading_service import AutoGradingService

            AutoGradingService.grade_attempt(attempt=attempt)
            return True
        return False
