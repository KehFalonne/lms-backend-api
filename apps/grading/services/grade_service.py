"""
Gradebook business logic.

Views stay thin. All grade writes go through here so GradeHistory is
always created, and the final-grade calculation is centralized.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.grading.models import (
    Grade,
    GradeCategory,
    GradeHistory,
    GradeItem,
    GradeStatus,
)


class GradeService:

    # ────────────────────────────────────────────────────────────────
    # Category validation
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def validate_category_weights(course_offering_id) -> None:
        """Sum of all category weights must equal 100%."""
        total = GradeCategory.objects.filter(
            course_offering_id=course_offering_id
        ).aggregate(total=models_sum("weight"))["total"] or Decimal("0")
        if total != Decimal("100"):
            raise ValidationError(
                {
                    "weights": [
                        f"Category weights must sum to 100%. Currently: {total}%."
                    ]
                }
            )

    # ────────────────────────────────────────────────────────────────
    # Grade upsert
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def set_grade(
        *,
        grade_item: GradeItem,
        student,
        score,
        graded_by=None,
        feedback: str = "",
        reason: str = "Manual update",
    ) -> Grade:
        """
        Create or update a grade and log the change in GradeHistory.

        Called by:
          • the lecturer through the API (manual entry)
          • Sprint 7 assignment grading service (auto-sync)
          • Sprint 8 assessment auto-grading service (auto-sync)
        """
        if score is not None:
            score = Decimal(score)
            if score < 0 or score > grade_item.max_score:
                raise ValidationError(
                    {"score": [f"Score must be between 0 and {grade_item.max_score}."]}
                )

        grade, created = Grade.objects.select_for_update().get_or_create(
            grade_item=grade_item,
            student=student,
            defaults={
                "score": score,
                "graded_by": graded_by,
                "graded_at": timezone.now() if score is not None else None,
                "feedback": feedback,
            },
        )

        if not created:
            previous_score = grade.score
            previous_status = grade.status

            grade.score = score
            grade.feedback = feedback or grade.feedback
            grade.graded_by = graded_by or grade.graded_by
            grade.graded_at = timezone.now() if score is not None else grade.graded_at
            grade.save()

            GradeHistory.objects.create(
                grade=grade,
                previous_score=previous_score,
                new_score=score,
                previous_status=previous_status,
                new_status=grade.status,
                reason=reason,
                changed_by=graded_by,
            )

        return grade

    # ────────────────────────────────────────────────────────────────
    # Final grade computation
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def compute_final_grade(*, course_offering_id, student) -> dict:
        """
        Compute the weighted final grade for a student in a course offering.

        Returns:
            {
                "percentage": Decimal,
                "letterGrade": str,
                "categories": [
                    {"category": name, "weight": w, "average": Decimal, "weighted": Decimal},
                    ...
                ],
            }
        """
        categories = GradeCategory.objects.filter(
            course_offering_id=course_offering_id
        ).order_by("position")

        breakdown = []
        overall = Decimal("0")

        for cat in categories:
            items = GradeItem.objects.filter(category=cat)
            scores = []
            for item in items:
                g = Grade.objects.filter(
                    grade_item=item,
                    student=student,
                ).first()
                if g and g.score is not None and item.max_score > 0:
                    scores.append((g.score / item.max_score) * 100)

            if not scores:
                cat_avg = Decimal("0")
            else:
                cat_avg = (sum(scores) / Decimal(len(scores))).quantize(Decimal("0.01"))

            weighted = (cat_avg * cat.weight / Decimal("100")).quantize(Decimal("0.01"))
            overall += weighted
            breakdown.append(
                {
                    "categoryId": str(cat.id),
                    "category": cat.name,
                    "weight": cat.weight,
                    "average": cat_avg,
                    "weighted": weighted,
                }
            )

        overall = overall.quantize(Decimal("0.01"))
        return {
            "percentage": overall,
            "letterGrade": GradeService._letter_grade(overall),
            "categories": breakdown,
        }

    @staticmethod
    def _letter_grade(pct: Decimal) -> str:
        if pct >= 90:
            return "A"
        if pct >= 80:
            return "B"
        if pct >= 70:
            return "C"
        if pct >= 60:
            return "D"
        if pct >= 50:
            return "E"
        return "F"

    # ────────────────────────────────────────────────────────────────
    # Publish
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def publish_grade_item(*, grade_item: GradeItem, by=None) -> int:
        """Publish all draft grades for a grade item and notify each student."""
        from apps.notifications.services.notification_service import (
            NotificationService,
        )

        now = timezone.now()
        grades = list(
            Grade.objects.filter(
                grade_item=grade_item,
                status=GradeStatus.DRAFT,
            ).select_related("student")
        )
        count = 0

        for g in grades:
            g.status = GradeStatus.PUBLISHED
            g.published_at = now
            g.save(update_fields=["status", "published_at", "updated_at"])

            GradeHistory.objects.create(
                grade=g,
                previous_score=g.score,
                new_score=g.score,
                previous_status=GradeStatus.DRAFT,
                new_status=GradeStatus.PUBLISHED,
                reason="Published",
                changed_by=by,
            )

            # Create a persistent notification for the student
            try:
                NotificationService.push(
                    recipient=g.student,
                    type="GRADE",
                    title=f"New grade: {grade_item.name}",
                    message=(
                        f"Score: {g.score}/{grade_item.max_score}"
                        if g.score is not None
                        else "Your grade is now available."
                    ),
                    entity_type="grade",
                    entity_id=g.id,
                    data={
                        "gradeId": str(g.id),
                        "gradeItemId": str(grade_item.id),
                        "courseOfferingId": str(grade_item.course_offering_id),
                    },
                )
            except Exception:
                pass

            count += 1

        grade_item.is_published = True
        grade_item.save(update_fields=["is_published", "updated_at"])
        return count

    @staticmethod
    @transaction.atomic
    def publish_all_for_offering(*, course_offering_id, by=None) -> int:
        """Convenience — publish every draft grade in the offering."""
        items = GradeItem.objects.filter(course_offering_id=course_offering_id)
        total = 0
        for item in items:
            total += GradeService.publish_grade_item(grade_item=item, by=by)
        return total

    # ────────────────────────────────────────────────────────────────
    # Auto-sync from Assignments / Assessments
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def sync_from_assignment(*, submission, graded_by=None) -> Grade | None:
        """
        Called by assignment grading service after a submission is graded.
        Finds (or creates) the linked GradeItem and writes the grade.
        """
        item = GradeItem.objects.filter(
            source_type="ASSIGNMENT",
            source_id=submission.assignment_id,
        ).first()
        if not item:
            return None
        return GradeService.set_grade(
            grade_item=item,
            student=submission.student,
            score=submission.score,
            graded_by=graded_by,
            feedback=submission.feedback or "",
            reason="Auto-synced from assignment submission",
        )

    @staticmethod
    def sync_from_attempt(*, attempt) -> Grade | None:
        """
        Called by assessment auto-grading service.
        """
        item = GradeItem.objects.filter(
            source_type="ASSESSMENT",
            source_id=attempt.assessment_id,
        ).first()
        if not item:
            return None
        return GradeService.set_grade(
            grade_item=item,
            student=attempt.student,
            score=attempt.total_score,
            graded_by=None,
            feedback="",
            reason="Auto-synced from assessment attempt",
        )


# Local import for the aggregate helper
from django.db.models import Sum as models_sum  # noqa: E402
