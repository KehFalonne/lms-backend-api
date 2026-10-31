from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.analytics.services.progress_service import ProgressService
from apps.common.responses import error_response, success_response
from apps.analytics.models import ContentProgress, LearningEvent
from apps.content.models import ContentItem, CourseModule
from apps.courses.models import (
    CourseEnrollment,
    CourseInstructor,
    EnrollmentStatus,
)


class ContentProgressView(APIView):
    """GET/PUT /api/v1/content/{content_id}/progress/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def _item_for_student(self, request, content_id):
        item = get_object_or_404(ContentItem, pk=content_id, deleted_at__isnull=True)
        if not CourseEnrollment.objects.filter(
            student=request.user,
            course_offering_id=item.course_module.course_offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists():
            return None
        return item

    def get(self, request, content_id):
        item = self._item_for_student(request, content_id)
        if item is None:
            return error_response(
                "You are not enrolled in this course.", status_code=403
            )

        progress = ContentProgress.objects.filter(
            student=request.user, content_item=item
        ).first()
        return success_response(
            data={
                "status": progress.status if progress else "NOT_STARTED",
                "progressPercent": progress.progress_percent if progress else 0,
            }
        )

    def put(self, request, content_id):
        item = self._item_for_student(request, content_id)
        if item is None:
            return error_response(
                "You are not enrolled in this course.", status_code=403
            )

        status_value = request.data.get("status")
        if status_value not in {"NOT_STARTED", "IN_PROGRESS", "COMPLETED"}:
            return error_response("Invalid progress status.", status_code=400)
        progress_percent = request.data.get("progressPercent")
        if progress_percent is None:
            progress_percent = request.data.get("progress_percent")
        if progress_percent is not None:
            try:
                progress_percent = int(progress_percent)
            except (TypeError, ValueError):
                return error_response(
                    "progressPercent must be a whole number.", status_code=400
                )
            if not 0 <= progress_percent <= 100:
                return error_response(
                    "progressPercent must be between 0 and 100.", status_code=400
                )
        if (
            status_value == "COMPLETED"
            and item.content_type in ("VIDEO", "AUDIO")
            and (progress_percent is None or progress_percent < 90)
        ):
            existing_progress = (
                ContentProgress.objects.filter(student=request.user, content_item=item)
                .values_list("progress_percent", flat=True)
                .first()
                or 0
            )
            if existing_progress < 90:
                return error_response(
                    "Watch or listen to at least 90% of this required lesson before marking it complete.",
                    status_code=400,
                )

        cp = ProgressService.mark_content_progress(
            student=request.user,
            content_item=item,
            status=status_value,
            progress_percent=progress_percent,
        )

        # Fire-and-forget: recompute overall course progress
        try:
            ProgressService.recompute(
                student=request.user,
                course_offering_id=item.course_module.course_offering_id,
            )
        except Exception:
            pass

        return success_response(
            data={
                "id": str(cp.id),
                "status": cp.status,
                "progressPercent": cp.progress_percent,
            },
            message="Progress updated.",
        )


class LecturerContentProgressView(APIView):
    """Read-only content engagement report for course instructors."""

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        instructor = CourseInstructor.objects.filter(
            course_offering_id=offering_id,
            user=request.user,
        ).exists()
        if not instructor and not request.user.is_staff:
            return error_response(
                "You are not an instructor for this course.",
                status_code=403,
            )

        modules = list(
            CourseModule.objects.filter(
                course_offering_id=offering_id,
                is_published=True,
            )
            .order_by("position", "created_at")
            .values("id", "title")
        )
        module_ids = [module["id"] for module in modules]
        items = list(
            ContentItem.objects.filter(
                course_module_id__in=module_ids,
                is_published=True,
                deleted_at__isnull=True,
            )
            .order_by("course_module__position", "position", "created_at")
            .values("id", "course_module_id", "title", "content_type", "is_required")
        )
        item_ids = [item["id"] for item in items]
        enrollments = list(
            CourseEnrollment.objects.filter(
                course_offering_id=offering_id,
                status=EnrollmentStatus.ACTIVE,
            )
            .select_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        progress_map = {
            (progress.student_id, progress.content_item_id): progress
            for progress in ContentProgress.objects.filter(
                student_id__in=[enrollment.student_id for enrollment in enrollments],
                content_item_id__in=item_ids,
            )
        }
        event_map = {
            (event.student_id, event.entity_id, event.event_type)
            for event in LearningEvent.objects.filter(
                student_id__in=[enrollment.student_id for enrollment in enrollments],
                entity_id__in=item_ids,
                event_type__in=["CONTENT_VIEWED", "PDF_OPENED", "PDF_DOWNLOADED"],
            )
        }
        module_titles = {module["id"]: module["title"] for module in modules}

        rows = []
        for enrollment in enrollments:
            student = enrollment.student
            for item in items:
                progress = progress_map.get((student.id, item["id"]))
                rows.append(
                    {
                        "studentId": str(student.id),
                        "studentName": f"{student.first_name} {student.last_name}".strip(),
                        "studentNumber": student.university_id,
                        "moduleId": str(item["course_module_id"]),
                        "moduleTitle": module_titles[item["course_module_id"]],
                        "contentId": str(item["id"]),
                        "contentTitle": item["title"],
                        "contentType": item["content_type"],
                        "isRequired": item["is_required"],
                        "status": progress.status if progress else "NOT_STARTED",
                        "progressPercent": progress.progress_percent if progress else 0,
                        "startedAt": (
                            progress.started_at.isoformat()
                            if progress and progress.started_at
                            else None
                        ),
                        "completedAt": (
                            progress.completed_at.isoformat()
                            if progress and progress.completed_at
                            else None
                        ),
                        "lastAccessedAt": (
                            progress.last_accessed_at.isoformat() if progress else None
                        ),
                        "opened": (
                            (student.id, item["id"], "PDF_OPENED") in event_map
                            if item["content_type"] == "PDF"
                            else False
                        ),
                        "viewed": (student.id, item["id"], "CONTENT_VIEWED") in event_map,
                        "downloaded": (
                            (student.id, item["id"], "PDF_DOWNLOADED") in event_map
                            if item["content_type"] == "PDF"
                            else False
                        ),
                    }
                )

        return success_response(
            data={
                "modules": [
                    {"id": str(module["id"]), "title": module["title"]}
                    for module in modules
                ],
                "rows": rows,
                "academicGrading": {
                    "enabled": False,
                    "message": "Content completion is participation evidence only and does not create academic marks.",
                },
            }
        )
