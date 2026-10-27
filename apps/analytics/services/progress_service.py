"""
Recomputes StudentCourseProgress from ContentProgress.
"""

from decimal import Decimal

from django.db.models import Count, Q

from apps.analytics.models import ContentProgress, StudentCourseProgress
from apps.content.models import ContentItem, CourseModule


class ProgressService:

    @staticmethod
    def recompute(*, student, course_offering_id) -> StudentCourseProgress:
        module_ids = CourseModule.objects.filter(
            course_offering_id=course_offering_id,
            is_published=True,
        ).values_list("id", flat=True)

        content_qs = ContentItem.objects.filter(
            course_module_id__in=module_ids,
            is_published=True,
            deleted_at__isnull=True,
        )
        total = content_qs.count()

        completed = ContentProgress.objects.filter(
            student=student,
            content_item__in=content_qs,
            status="COMPLETED",
        ).count()

        pct = (
            (Decimal(completed) / Decimal(total) * Decimal("100")).quantize(
                Decimal("0.01")
            )
            if total > 0
            else Decimal("0")
        )

        progress, _ = StudentCourseProgress.objects.update_or_create(
            student=student,
            course_offering_id=course_offering_id,
            defaults={
                "progress_percentage": pct,
                "content_completed": completed,
                "content_total": total,
            },
        )
        return progress

    @staticmethod
    def mark_content_progress(
        *,
        student,
        content_item,
        status: str | None = None,
        progress_percent: int | None = None,
    ) -> ContentProgress:
        from django.utils import timezone

        defaults = {}
        if status:
            defaults["status"] = status
            if status == "COMPLETED":
                defaults["completed_at"] = timezone.now()
            if (
                status == "IN_PROGRESS"
                and not ContentProgress.objects.filter(
                    student=student, content_item=content_item
                ).exists()
            ):
                defaults["started_at"] = timezone.now()
        if progress_percent is not None:
            defaults["progress_percent"] = progress_percent

        cp, _ = ContentProgress.objects.update_or_create(
            student=student,
            content_item=content_item,
            defaults=defaults,
        )
        return cp
