"""
Grade appeal endpoints.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.permissions import CanGradeCourse
from apps.grading.models import Grade, GradeAppeal
from apps.grading.serializers import (
    CreateAppealSerializer,
    GradeAppealSerializer,
    ResolveAppealSerializer,
)
from apps.grading.services.appeal_service import AppealError, AppealService


class GradeAppealListCreateView(APIView):
    """
    GET  /api/v1/grades/{id}/appeals/  — list appeals for one grade
    POST /api/v1/grades/{id}/appeals/  — student creates an appeal
    """

    serializer_class = GradeAppealSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, grade_id):
        grade = get_object_or_404(Grade, pk=grade_id)
        # Student sees only their own; staff/instructors see all
        is_grader = (
            request.user.is_staff
            or request.user.is_superuser
            or CanGradeCourse().has_object_permission(
                request, self, grade.grade_item.course_offering
            )
        )
        if not is_grader and grade.student_id != request.user.id:
            return error_response("Not allowed.", status_code=403)

        qs = grade.appeals.select_related(
            "student", "reviewer", "grade__grade_item"
        ).order_by("-created_at")
        return success_response(data=GradeAppealSerializer(qs, many=True).data)

    def post(self, request, grade_id):
        grade = get_object_or_404(Grade, pk=grade_id)
        serializer = CreateAppealSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appeal = AppealService.create(
                grade=grade,
                student=request.user,
                reason=serializer.validated_data["reason"],
            )
        except AppealError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )

        return success_response(
            data=GradeAppealSerializer(appeal).data,
            message="Appeal submitted.",
            status=201,
        )


class AppealQueueView(APIView):
    """
    GET /api/v1/appeals/  — queue for lecturers/admins.

    Query params:
      ?status=PENDING (default — active queue)
      ?mine=true (only appeals in courses I teach)
    """

    serializer_class = GradeAppealSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        is_admin = request.user.is_staff or request.user.is_superuser
        codes = set(request.user.get_role_codes())
        is_lecturer = bool(codes & {"LECTURER", "TEACHING_ASSISTANT", "HOD", "DEAN"})
        if not (is_admin or is_lecturer):
            return error_response(
                "Only lecturers and admins can view the appeals queue.",
                status_code=403,
            )

        qs = GradeAppeal.objects.select_related(
            "grade__grade_item__course_offering__course",
            "student",
            "reviewer",
        )

        status_filter = request.query_params.get("status", "ACTIVE")
        if status_filter == "ACTIVE":
            qs = qs.filter(status__in=["PENDING", "UNDER_REVIEW"])
        elif status_filter != "ALL":
            qs = qs.filter(status=status_filter)

        # Restrict to courses this lecturer teaches
        if not is_admin and request.query_params.get("mine") == "true":
            from apps.courses.models import CourseInstructor

            offering_ids = CourseInstructor.objects.filter(
                user=request.user
            ).values_list("course_offering_id", flat=True)
            qs = qs.filter(grade__grade_item__course_offering_id__in=offering_ids)

        qs = qs.order_by("-created_at")
        return success_response(data=GradeAppealSerializer(qs, many=True).data)


class AppealResolveView(APIView):
    """POST /api/v1/appeals/{id}/resolve/"""

    serializer_class = ResolveAppealSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        appeal = get_object_or_404(
            GradeAppeal.objects.select_related(
                "grade__grade_item__course_offering", "student"
            ),
            pk=pk,
        )

        # Reviewer must be staff, or grading-capable instructor on this course
        is_reviewer = (
            request.user.is_staff
            or request.user.is_superuser
            or CanGradeCourse().has_object_permission(
                request, self, appeal.grade.grade_item.course_offering
            )
        )
        if not is_reviewer:
            return error_response("Not allowed.", status_code=403)

        serializer = ResolveAppealSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appeal = AppealService.resolve(
                appeal=appeal,
                reviewer=request.user,
                decision=serializer.validated_data["decision"],
                reviewer_notes=serializer.validated_data.get("reviewer_notes", ""),
                new_score=serializer.validated_data.get("new_score"),
            )
        except AppealError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )

        return success_response(
            data=GradeAppealSerializer(appeal).data,
            message=f"Appeal {appeal.status.lower()}.",
        )


class AppealWithdrawView(APIView):
    """POST /api/v1/appeals/{id}/withdraw/"""

    serializer_class = GradeAppealSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        appeal = get_object_or_404(GradeAppeal, pk=pk)
        try:
            appeal = AppealService.withdraw(appeal=appeal, student=request.user)
        except AppealError as exc:
            return error_response(exc.args[0], status_code=400)
        return success_response(
            data=GradeAppealSerializer(appeal).data,
            message="Appeal withdrawn.",
        )
