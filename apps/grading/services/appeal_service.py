"""
Grade appeal workflow.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.grading.models import (
    AppealStatus,
    Grade,
    GradeAppeal,
    GradeHistory,
    GradeStatus,
)


class AppealError(Exception):
    def __init__(self, message: str, code: str = "appeal_error"):
        super().__init__(message)
        self.code = code


class AppealService:

    @staticmethod
    @transaction.atomic
    def create(*, grade: Grade, student, reason: str) -> GradeAppeal:
        # Only published grades can be appealed
        if grade.status != GradeStatus.PUBLISHED:
            raise AppealError(
                "Only published grades can be appealed.", code="not_published"
            )
        if grade.student_id != student.id:
            raise AppealError("You can only appeal your own grades.", code="not_owner")
        if not reason.strip():
            raise AppealError("Reason is required.", code="empty_reason")

        # Block duplicate active appeals
        if GradeAppeal.objects.filter(
            grade=grade,
            student=student,
            status__in=[AppealStatus.PENDING, AppealStatus.UNDER_REVIEW],
        ).exists():
            raise AppealError(
                "You already have an active appeal for this grade.",
                code="already_appealed",
            )

        return GradeAppeal.objects.create(
            grade=grade,
            student=student,
            reason=reason.strip(),
            original_score=grade.score,
        )

    @staticmethod
    @transaction.atomic
    def resolve(
        *,
        appeal: GradeAppeal,
        reviewer,
        decision: str,
        reviewer_notes: str = "",
        new_score: Decimal | None = None,
    ) -> GradeAppeal:
        if appeal.status not in (AppealStatus.PENDING, AppealStatus.UNDER_REVIEW):
            raise AppealError(
                f"Cannot resolve an appeal in {appeal.status} state.",
                code="invalid_state",
            )

        if decision not in (AppealStatus.APPROVED, AppealStatus.DENIED):
            raise AppealError(
                "Decision must be APPROVED or DENIED.", code="invalid_decision"
            )

        grade = appeal.grade

        if decision == AppealStatus.APPROVED:
            if new_score is None:
                raise AppealError(
                    "Approved appeals require a new score.",
                    code="missing_score",
                )
            if new_score < 0 or new_score > grade.grade_item.max_score:
                raise AppealError(
                    f"Score must be between 0 and {grade.grade_item.max_score}.",
                    code="out_of_range",
                )

            previous_score = grade.score
            grade.score = new_score
            grade.save(update_fields=["score", "percentage", "updated_at"])

            GradeHistory.objects.create(
                grade=grade,
                previous_score=previous_score,
                new_score=new_score,
                previous_status=grade.status,
                new_status=grade.status,
                reason=f"Grade appeal approved: {reviewer_notes[:200]}",
                changed_by=reviewer,
            )
            appeal.resolved_score = new_score

        appeal.status = decision
        appeal.reviewer = reviewer
        appeal.reviewer_notes = reviewer_notes
        appeal.resolved_at = timezone.now()
        appeal.save()

        # Notify the student
        try:
            from apps.notifications.services.notification_service import (
                NotificationService,
            )

            NotificationService.push(
                recipient=appeal.student,
                type="GRADE",
                title=f"Grade appeal {decision.lower()}",
                message=(
                    f"Your appeal for {grade.grade_item.name} was "
                    f"{decision.lower()}. "
                    + (
                        f"New score: {new_score}/{grade.grade_item.max_score}."
                        if decision == AppealStatus.APPROVED
                        else "Original grade stands."
                    )
                ),
                entity_type="grade_appeal",
                entity_id=appeal.id,
                data={
                    "gradeId": str(grade.id),
                    "courseOfferingId": str(grade.grade_item.course_offering_id),
                },
            )
        except Exception:
            pass

        return appeal

    @staticmethod
    @transaction.atomic
    def withdraw(*, appeal: GradeAppeal, student) -> GradeAppeal:
        if appeal.student_id != student.id:
            raise AppealError("Not allowed.", code="not_owner")
        if appeal.status not in (AppealStatus.PENDING, AppealStatus.UNDER_REVIEW):
            raise AppealError(
                "Only pending appeals can be withdrawn.", code="invalid_state"
            )
        appeal.status = AppealStatus.WITHDRAWN
        appeal.resolved_at = timezone.now()
        appeal.save()
        return appeal
