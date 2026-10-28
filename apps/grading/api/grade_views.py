from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanGradeCourse
from apps.grading.models import Grade, GradeItem, GradeStatus
from apps.grading.serializers import (
    GradeHistorySerializer,
    GradeSerializer,
    SetGradeSerializer,
)
from apps.grading.services.grade_service import GradeService


class GradeItemGradesListView(APIView):
    """GET /api/v1/grade-items/{id}/grades/"""

    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def get(self, request, pk):
        item = get_object_or_404(GradeItem, pk=pk)
        self.check_object_permissions(request, item.course_offering)
        qs = item.grades.select_related("student").all()
        return success_response(data=GradeSerializer(qs, many=True).data)


class SetGradeView(APIView):
    """PATCH /api/v1/grade-items/{id}/grades/{student_id}/"""

    serializer_class = SetGradeSerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def patch(self, request, pk, student_id):
        item = get_object_or_404(GradeItem, pk=pk)
        self.check_object_permissions(request, item.course_offering)

        student = get_object_or_404(User, pk=student_id)
        serializer = SetGradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grade = GradeService.set_grade(
                grade_item=item,
                student=student,
                score=serializer.validated_data["score"],
                graded_by=request.user,
                feedback=serializer.validated_data.get("feedback", ""),
                reason=serializer.validated_data.get("reason", "Manual update"),
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            if isinstance(detail, dict):
                detail = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in detail.items()
                )
            return error_response(str(detail), status_code=400)

        return success_response(
            data=GradeSerializer(grade).data,
            message="Grade saved.",
        )


class GradeHistoryView(APIView):
    """GET /api/v1/grades/{grade_id}/history/"""

    serializer_class = GradeHistorySerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def get(self, request, pk):
        grade = get_object_or_404(Grade, pk=pk)
        self.check_object_permissions(request, grade.grade_item.course_offering)
        qs = grade.history.select_related("changed_by").all()
        return success_response(data=GradeHistorySerializer(qs, many=True).data)


# ──────────────────────────────────────────────────────────────────────
# Student-facing
# ──────────────────────────────────────────────────────────────────────


class MyGradesView(APIView):
    """GET /api/v1/my/grades/ — final grades for all my offerings."""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        from apps.courses.models import CourseEnrollment

        offering_ids = CourseEnrollment.objects.filter(
            student=request.user,
            status="ACTIVE",
        ).values_list("course_offering_id", flat=True)

        results = []
        for oid in offering_ids:
            offering = CourseOffering.objects.select_related("course", "semester").get(
                pk=oid
            )
            final = GradeService.compute_final_grade(
                course_offering_id=oid,
                student=request.user,
            )
            results.append(
                {
                    "courseOfferingId": str(oid),
                    "courseCode": offering.course.code,
                    "courseTitle": offering.course.title,
                    "semester": offering.semester.name,
                    "percentage": str(final["percentage"]),
                    "letterGrade": final["letterGrade"],
                    "categories": [
                        {
                            "category": c["category"],
                            "weight": str(c["weight"]),
                            "average": str(c["average"]),
                            "weighted": str(c["weighted"]),
                        }
                        for c in final["categories"]
                    ],
                }
            )

        return success_response(data=results)


class MyCourseGradesView(APIView):
    """GET /api/v1/my/course-offerings/{offering_id}/grades/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        from apps.courses.models import CourseEnrollment, EnrollmentStatus

        if not CourseEnrollment.objects.filter(
            student=request.user,
            course_offering_id=offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists():
            return error_response("Not enrolled.", status_code=403)

        # Published grades only, per doc §61
        items = GradeItem.objects.filter(
            course_offering_id=offering_id,
            is_published=True,
        ).select_related("category")

        published = []
        for item in items:
            g = Grade.objects.filter(grade_item=item, student=request.user).first()
            if g:
                published.append(
                    {
                        "gradeItemId": str(item.id),
                        "name": item.name,
                        "category": item.category.name if item.category else None,
                        "maxScore": str(item.max_score),
                        "score": str(g.score) if g.score is not None else None,
                        "percentage": (
                            str(g.percentage) if g.percentage is not None else None
                        ),
                        "letterGrade": g.letter_grade,
                        "feedback": g.feedback,
                        "gradeId": str(g.id),
                    }
                )

        final = GradeService.compute_final_grade(
            course_offering_id=offering_id,
            student=request.user,
        )
        return success_response(
            data={
                "items": published,
                "final": {
                    "percentage": str(final["percentage"]),
                    "letterGrade": final["letterGrade"],
                    "categories": [
                        {
                            "category": c["category"],
                            "weight": str(c["weight"]),
                            "average": str(c["average"]),
                            "weighted": str(c["weighted"]),
                        }
                        for c in final["categories"]
                    ],
                },
            }
        )
