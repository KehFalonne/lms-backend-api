"""
CA exam workflow — access code validation and attempt creation.

Backend doc §4.3.1:
- Validates access code server-side
- Enforces CA window (opens / last entry / hard close)
- Rate-limits code entry
- Logs every attempt
- Optionally randomizes served questions
"""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentCodeAttempt,
    AttemptStatus,
)
from apps.courses.models import CourseEnrollment, EnrollmentStatus


class AccessError(Exception):
    def __init__(self, message: str, code: str = "access_denied"):
        super().__init__(message)
        self.code = code


class AssessmentAccessService:

    RATE_LIMIT_WINDOW_MINUTES = 10
    MAX_FAILED_ATTEMPTS = 5

    @staticmethod
    def set_code(assessment: Assessment, raw_code: str) -> None:
        """Hash and store the access code."""
        assessment.access_code_hash = make_password(raw_code.strip())
        assessment.is_code_gated = True
        assessment.save(
            update_fields=["access_code_hash", "is_code_gated", "updated_at"]
        )

    @staticmethod
    def generate_and_set_code(assessment: Assessment) -> str:
        """Generate a random 6-char code, store it, and return the raw value."""
        import secrets

        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
        raw = "".join(secrets.choice(alphabet) for _ in range(6))
        AssessmentAccessService.set_code(assessment, raw)
        return raw

    @staticmethod
    @transaction.atomic
    def enter_with_code(
        assessment: Assessment,
        student,
        code: str,
        request=None,
    ) -> AssessmentAttempt:
        """
        Validate the code and create a fresh attempt.
        Raises AccessError on any failure.
        """
        now = timezone.now()

        # 1. Rate limit check
        recent_failures = AssessmentCodeAttempt.objects.filter(
            assessment=assessment,
            student=student,
            success=False,
            created_at__gte=now
            - timedelta(minutes=AssessmentAccessService.RATE_LIMIT_WINDOW_MINUTES),
        ).count()
        if recent_failures >= AssessmentAccessService.MAX_FAILED_ATTEMPTS:
            raise AccessError(
                f"Too many incorrect attempts. "
                f"Try again in {AssessmentAccessService.RATE_LIMIT_WINDOW_MINUTES} minutes.",
                code="rate_limited",
            )

        # 2. Assessment state
        if not assessment.is_code_gated:
            raise AccessError(
                "This assessment does not require an access code.",
                code="not_gated",
            )
        if not assessment.access_code_hash:
            raise AccessError(
                "No access code has been set for this assessment.",
                code="no_code",
            )
        if assessment.status != "PUBLISHED":
            raise AccessError("Assessment is not open.", code="not_open")

        # 3. CA window
        if assessment.ca_opens_at and now < assessment.ca_opens_at:
            raise AccessError("This assessment hasn't opened yet.", code="too_early")
        if assessment.ca_last_entry_at and now > assessment.ca_last_entry_at:
            raise AccessError(
                "The late-entry window has passed.", code="late_entry_closed"
            )
        if assessment.available_until and now > assessment.available_until:
            raise AccessError("Assessment has closed.", code="closed")

        # 4. Verify code (constant-time compare via check_password)
        if not check_password(code.strip(), assessment.access_code_hash):
            AssessmentAccessService._log(assessment, student, False, request)
            raise AccessError("Invalid access code.", code="invalid_code")

        # 5. Enrollment
        if not CourseEnrollment.objects.filter(
            student=student,
            course_offering_id=assessment.course_offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists():
            raise AccessError(
                "You are not enrolled in this course.", code="not_enrolled"
            )

        # 6. Attempt limit
        existing = AssessmentAttempt.objects.filter(
            assessment=assessment, student=student
        ).count()
        if existing >= assessment.max_attempts:
            raise AccessError(
                f"Maximum attempts ({assessment.max_attempts}) reached.",
                code="max_attempts",
            )

        # 7. Success — log, pick questions, create attempt
        AssessmentAccessService._log(assessment, student, True, request)

        served_qs = AssessmentAccessService._select_questions(
            assessment, student, attempt_number=existing + 1
        )

        expires_at = None
        if assessment.time_limit_minutes:
            expires_at = now + timedelta(minutes=assessment.time_limit_minutes)
        if assessment.available_until:
            expires_at = (
                min(expires_at, assessment.available_until)
                if expires_at
                else assessment.available_until
            )

        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            student=student,
            attempt_number=existing + 1,
            status=AttemptStatus.IN_PROGRESS,
            expires_at=expires_at,
            entered_at=now,
            served_questions=[str(aq.id) for aq in served_qs],
        )
        return attempt

    @staticmethod
    def _select_questions(assessment: Assessment, student, attempt_number: int):
        all_qs = list(assessment.assessment_questions.order_by("position").all())
        if (
            assessment.serve_question_count
            and len(all_qs) > assessment.serve_question_count
        ):
            import random

            rng = random.Random(f"{assessment.id}:{student.id}:{attempt_number}")
            rng.shuffle(all_qs)
            all_qs = all_qs[: assessment.serve_question_count]
        if assessment.randomize_question_order:
            import random

            rng = random.Random(f"{assessment.id}:{student.id}:{attempt_number}:order")
            rng.shuffle(all_qs)
        return all_qs

    @staticmethod
    def _log(assessment, student, success: bool, request) -> None:
        ip = None
        ua = ""
        if request:
            ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
                0
            ].strip() or request.META.get("REMOTE_ADDR")
            ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]
        AssessmentCodeAttempt.objects.create(
            assessment=assessment,
            student=student,
            success=success,
            ip_address=ip,
            user_agent=ua,
        )
