"""
Submission + grading business logic.

Views stay thin. All state transitions happen here so tests and future
automation (auto-grading in Sprint 8) reuse the same rules.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.assignments.models import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    LatePenaltyType,
    SubmissionStatus,
    SubmissionType,
)
from apps.courses.models import CourseEnrollment, EnrollmentStatus
from apps.files.models import File, FileStatus


class SubmissionService:

    @staticmethod
    def _is_enrolled(student, course_offering_id) -> bool:
        return CourseEnrollment.objects.filter(
            student=student,
            course_offering_id=course_offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists()

    @staticmethod
    def _check_attempts(assignment: Assignment, student) -> int:
        existing = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student,
        ).count()
        if existing >= assignment.max_attempts:
            raise ValidationError(
                {"attempt": [f"Maximum attempts ({assignment.max_attempts}) reached."]}
            )
        return existing + 1

    @staticmethod
    def _compute_late_penalty(
        assignment: Assignment, submitted_at
    ) -> tuple[bool, Decimal]:
        """Returns (is_late, penalty_points)."""
        if submitted_at <= assignment.due_at:
            return False, Decimal("0")

        if assignment.late_penalty_type == LatePenaltyType.NONE:
            return True, Decimal("0")

        days_late = (submitted_at - assignment.due_at).days + (
            1 if (submitted_at - assignment.due_at).seconds else 0
        )
        if assignment.late_penalty_type == LatePenaltyType.PERCENTAGE:
            penalty = (
                assignment.max_score * assignment.late_penalty_value * days_late
            ) / Decimal("100")
        else:  # POINTS
            penalty = assignment.late_penalty_value * days_late
        return True, penalty

    # ────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def create_submission(
        *,
        assignment: Assignment,
        student,
        text_content: str = "",
        file_ids: list[str] | None = None,
    ) -> AssignmentSubmission:

        # 1. Enrollment check
        if not SubmissionService._is_enrolled(student, assignment.course_offering_id):
            raise ValidationError({"detail": ["You are not enrolled in this course."]})

        # 2. Assignment availability
        if assignment.status != AssignmentStatus.PUBLISHED:
            raise ValidationError({"detail": ["Assignment is not open."]})
        if assignment.available_from and timezone.now() < assignment.available_from:
            raise ValidationError({"detail": ["Assignment is not yet available."]})
        if assignment.available_until and timezone.now() > assignment.available_until:
            raise ValidationError({"detail": ["Assignment has closed."]})

        now = timezone.now()
        is_late = now > assignment.due_at
        if is_late and not assignment.allow_late_submission:
            raise ValidationError({"detail": ["Late submissions are not allowed."]})

        # 3. Submission type
        if assignment.submission_type == SubmissionType.FILE_UPLOAD and not file_ids:
            raise ValidationError({"files": ["At least one file is required."]})
        if (
            assignment.submission_type == SubmissionType.TEXT_ENTRY
            and not text_content.strip()
        ):
            raise ValidationError({"textContent": ["Text content is required."]})

        # 4. Attempts
        attempt = SubmissionService._check_attempts(assignment, student)

        # 5. Create
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=student,
            attempt_number=attempt,
            status=SubmissionStatus.LATE if is_late else SubmissionStatus.SUBMITTED,
            submitted_at=now,
            is_late=is_late,
            text_content=text_content,
        )

        # 6. Attach files
        if file_ids:
            from apps.assignments.models import SubmissionFile

            files = File.objects.filter(
                id__in=file_ids,
                uploaded_by=student,
                status=FileStatus.READY,
            )
            found_ids = {f.id for f in files}
            missing = set(file_ids) - found_ids
            if missing:
                raise ValidationError(
                    {
                        "files": [
                            f"Unknown or unready file(s): {', '.join(str(i) for i in missing)}"
                        ]
                    }
                )
            SubmissionFile.objects.bulk_create(
                [SubmissionFile(submission=submission, file=f) for f in files]
            )

        # 7. Fire notification to instructors (async)
        SubmissionService._notify_instructors(submission)

        return submission

    @staticmethod
    @transaction.atomic
    def grade_submission(
        *,
        submission: AssignmentSubmission,
        grader,
        score: Decimal,
        feedback: str = "",
    ) -> AssignmentSubmission:

        assignment = submission.assignment

        if score < 0 or score > assignment.max_score:
            raise ValidationError(
                {"score": [f"Score must be between 0 and {assignment.max_score}."]}
            )

        # Late penalty
        if submission.is_late and assignment.late_penalty_type != LatePenaltyType.NONE:
            _, penalty = SubmissionService._compute_late_penalty(
                assignment, submission.submitted_at
            )
            score = max(Decimal("0"), score - penalty)

        submission.score = score
        submission.feedback = feedback
        submission.graded_by = grader
        submission.graded_at = timezone.now()
        submission.status = SubmissionStatus.GRADED
        submission.save(
            update_fields=[
                "score",
                "feedback",
                "graded_by",
                "graded_at",
                "status",
                "updated_at",
            ]
        )

        # Optional: multi-entry feedback
        if feedback:
            from apps.assignments.models import Feedback

            Feedback.objects.create(
                submission=submission,
                author=grader,
                content=feedback,
            )

        # Notify student
        SubmissionService._notify_student_graded(submission)
        # Auto-sync into gradebook (best-effort — never blocks the request)
        try:
            from apps.grading.services.grade_service import GradeService

            GradeService.sync_from_assignment(submission=submission, graded_by=grader)
        except Exception:
            pass

        return submission

    @staticmethod
    def return_for_revision(
        submission: AssignmentSubmission, by
    ) -> AssignmentSubmission:
        submission.status = SubmissionStatus.RETURNED
        submission.save(update_fields=["status", "updated_at"])
        return submission

    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _notify_instructors(submission: AssignmentSubmission) -> None:
        """Fire-and-forget notification to the instructor(s)."""
        try:
            from apps.notifications.services.notification_service import (
                NotificationService,
            )
            from apps.courses.models import CourseInstructor

            recipients = [
                ci.user
                for ci in CourseInstructor.objects.filter(
                    course_offering_id=submission.assignment.course_offering_id,
                    can_grade=True,
                ).select_related("user")
            ]
            NotificationService.push_bulk(
                recipients=recipients,
                type="ASSIGNMENT",
                title="New submission",
                message=f"{submission.student.first_name} submitted '{submission.assignment.title}'.",
                entity_type="assignment_submission",
                entity_id=submission.id,
            )
        except Exception:
            pass

    @staticmethod
    def _notify_student_graded(submission: AssignmentSubmission) -> None:
        try:
            from apps.notifications.services.notification_service import (
                NotificationService,
            )

            NotificationService.push(
                recipient=submission.student,
                type="GRADE",
                title="Assignment graded",
                message=(
                    f"Your submission for '{submission.assignment.title}' "
                    f"was graded: {submission.score}/{submission.assignment.max_score}."
                ),
                entity_type="assignment_submission",
                entity_id=submission.id,
            )
        except Exception:
            pass
