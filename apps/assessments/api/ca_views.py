"""
CA exam workflow views.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assessments.models import Assessment
from apps.assessments.serializers import AttemptDetailSerializer
from apps.assessments.services.access_service import (
    AccessError,
    AssessmentAccessService,
)
from apps.common.responses import error_response, success_response


class EnterAssessmentCodeView(APIView):
    """
    POST /api/v1/assessments/{id}/enter-with-code/
    Body: { "code": "ABC123" }
    """

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        code = (request.data.get("code") or "").strip()
        if not code:
            return error_response("code is required.", status_code=400)

        try:
            attempt = AssessmentAccessService.enter_with_code(
                assessment=assessment,
                student=request.user,
                code=code,
                request=request,
            )
        except AccessError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )

        return success_response(
            data=AttemptDetailSerializer(attempt).data,
            message="Attempt started.",
            status=201,
        )


class GenerateAccessCodeView(APIView):
    """
    POST /api/v1/assessments/{id}/generate-code/
    Staff/instructor only. Generates a new code and returns the raw value
    (which the lecturer then shares with students).
    """

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)

        # Only staff or instructors of the offering
        from apps.courses.permissions import CanManageCourseContent

        if not (
            request.user.is_staff
            or request.user.is_superuser
            or CanManageCourseContent().has_object_permission(
                request, self, assessment.course_offering
            )
        ):
            return error_response("Not allowed.", status_code=403)

        raw = AssessmentAccessService.generate_and_set_code(assessment)
        return success_response(
            data={"code": raw},
            message="New access code generated. Share it with students at exam start.",
        )


class SetAccessCodeView(APIView):
    """POST /api/v1/assessments/{id}/set-code/  Body: {code}"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)

        from apps.courses.permissions import CanManageCourseContent

        if not (
            request.user.is_staff
            or request.user.is_superuser
            or CanManageCourseContent().has_object_permission(
                request, self, assessment.course_offering
            )
        ):
            return error_response("Not allowed.", status_code=403)

        code = (request.data.get("code") or "").strip()
        if not code or len(code) < 4:
            return error_response(
                "Access code must be at least 4 characters.", status_code=400
            )

        AssessmentAccessService.set_code(assessment, code)
        return success_response(message="Access code set.")
