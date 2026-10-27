"""
Assignment submission endpoints.

Permissions model:
- Students submit their own work
- Staff/superusers can do anything
- Instructors (CourseInstructor with can_grade=True) can list, view, and grade
  submissions for their own course offerings
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.assignments.serializers import (
    AssignmentSubmissionSerializer,
    GradeSubmissionSerializer,
    SubmissionCreateSerializer,
)
from apps.assignments.services.submission_service import SubmissionService
from apps.common.responses import error_response, success_response
from apps.courses.permissions import CanGradeCourse


def _error_message(exc) -> str:
    """Flatten a ValidationError / dict / string into a readable message."""
    detail = getattr(exc, "detail", str(exc))
    if isinstance(detail, dict):
        return "; ".join(
            f"{k}: {', '.join(v) if isinstance(v, list) else v}"
            for k, v in detail.items()
        )
    return str(detail)


class MySubmissionView(APIView):
    """GET /api/v1/assignments/{id}/submission/ — student's own latest."""

    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        submission = (
            AssignmentSubmission.objects.filter(
                assignment=assignment, student=request.user
            )
            .order_by("-attempt_number")
            .first()
        )
        if not submission:
            return success_response(data=None)
        return success_response(data=AssignmentSubmissionSerializer(submission).data)


class SubmissionListCreateView(APIView):
    """GET (staff/instructor) / POST (student) /api/v1/assignments/{id}/submissions/"""

    serializer_class = SubmissionCreateSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)

        # Staff/superusers bypass. Otherwise the caller must have grading
        # permission for this specific offering.
        is_staff_user = request.user.is_staff or request.user.is_superuser
        if not is_staff_user:
            if not CanGradeCourse().has_object_permission(
                request, self, assignment.course_offering
            ):
                return error_response(
                    "You don't have permission to view submissions for this "
                    "assignment.",
                    status_code=403,
                )

        qs = assignment.submissions.select_related("student").order_by("-submitted_at")
        return success_response(data=AssignmentSubmissionSerializer(qs, many=True).data)

    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)

        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = SubmissionService.create_submission(
                assignment=assignment,
                student=request.user,
                text_content=serializer.validated_data.get("text_content", ""),
                file_ids=serializer.validated_data.get("file_ids", []),
            )
        except Exception as exc:
            return error_response(_error_message(exc), status_code=400)

        # Record learning event (fire-and-forget)
        try:
            from apps.analytics.services.event_service import EventService

            EventService.record(
                student=request.user,
                event_type="ASSIGNMENT_SUBMITTED",
                course_offering=assignment.course_offering,
                entity_type="assignment",
                entity_id=assignment.id,
            )
        except Exception:
            pass

        return success_response(
            data=AssignmentSubmissionSerializer(submission).data,
            message="Submission received.",
            status=status.HTTP_201_CREATED,
        )


class SubmissionDetailView(APIView):
    """GET /api/v1/assignment-submissions/{id}/"""

    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        submission = get_object_or_404(
            AssignmentSubmission.objects.select_related("student", "assignment"),
            pk=pk,
        )

        # Student can see their own
        if submission.student_id == request.user.id:
            return success_response(
                data=AssignmentSubmissionSerializer(submission).data
            )

        # Staff or grading-capable instructor can see it
        is_staff_user = request.user.is_staff or request.user.is_superuser
        if is_staff_user or CanGradeCourse().has_object_permission(
            request, self, submission.assignment.course_offering
        ):
            return success_response(
                data=AssignmentSubmissionSerializer(submission).data
            )

        return error_response("Not allowed.", status_code=403)


class GradeSubmissionView(APIView):
    """PATCH /api/v1/assignment-submissions/{id}/grade/"""

    serializer_class = GradeSubmissionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def patch(self, request, pk):
        submission = get_object_or_404(
            AssignmentSubmission.objects.select_related("assignment", "student"),
            pk=pk,
        )

        # Staff bypass; instructors need CanGradeCourse on the offering
        is_staff_user = request.user.is_staff or request.user.is_superuser
        if not is_staff_user:
            if not CanGradeCourse().has_object_permission(
                request, self, submission.assignment.course_offering
            ):
                return error_response(
                    "You don't have permission to grade this submission.",
                    status_code=403,
                )

        serializer = GradeSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = SubmissionService.grade_submission(
                submission=submission,
                grader=request.user,
                score=serializer.validated_data["score"],
                feedback=serializer.validated_data.get("feedback", ""),
            )
        except Exception as exc:
            return error_response(_error_message(exc), status_code=400)

        # ── CRITICAL: always return a Response ──
        return success_response(
            data=AssignmentSubmissionSerializer(submission).data,
            message="Submission graded.",
        )
