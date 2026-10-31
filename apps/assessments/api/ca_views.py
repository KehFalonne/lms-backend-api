"""
CA exam workflow views.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assessments.models import Assessment
from apps.assessments.models import AssessmentAttempt, AttemptStatus, CAInvigilatorAction
from apps.assessments.serializers import (
    AssessmentSerializer,
    AttemptDetailSerializer,
    InvigilatorActionSerializer,
)
from apps.assessments.services.access_service import (
    AccessError,
    AssessmentAccessService,
)
from apps.common.responses import error_response, success_response


def _is_administrator(user) -> bool:
    return user.is_superuser or user.has_role(
        "SUPER_ADMIN",
        "UNIVERSITY_ADMIN",
        "FACULTY_ADMIN",
        "DEPARTMENT_ADMIN",
    )


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

        # Only the appointed invigilator or an administrator may issue the
        # session code. Course lecturers configure the assignment separately.
        if (
            not _is_administrator(request.user)
            and not (
                request.user.is_staff
                and assessment.ca_invigilator_id == request.user.id
            )
        ):
            return error_response("Only the assigned invigilator or an administrator may generate the CA code.", status_code=403)

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

        if not (
            _is_administrator(request.user)
            or (
                request.user.is_staff
                and assessment.ca_invigilator_id == request.user.id
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


class CAInvigilatorListView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if not (request.user.is_staff or _is_administrator(request.user)):
            return error_response("Not allowed.", status_code=403)
        users = User.objects.filter(
            is_staff=True, is_active=True, status="ACTIVE"
        ).order_by("first_name", "last_name")
        return success_response(
            data=[
                {
                    "id": str(user.id),
                    "universityId": user.university_id,
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                    "email": user.email,
                }
                for user in users
            ]
        )


class CAInvigilatorSessionsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        if not _is_administrator(request.user):
            return error_response("Not allowed.", status_code=403)
        assessments = Assessment.objects.filter(
            proctoring_enabled=True
        ).select_related(
            "ca_invigilator",
            "course_offering__course",
        ).order_by("-created_at")
        return success_response(
            data=[
                {
                    "id": str(assessment.id),
                    "title": assessment.title,
                    "courseId": str(assessment.course_offering_id),
                    "courseCode": assessment.course_offering.course.code,
                    "invigilator": (
                        {
                            "id": str(assessment.ca_invigilator_id),
                            "name": assessment.ca_invigilator.get_full_name(),
                        }
                        if assessment.ca_invigilator
                        else None
                    ),
                    "status": assessment.status,
                }
                for assessment in assessments
            ]
        )


class CAMonitoringView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def _assessment(self, pk):
        return get_object_or_404(
            Assessment.objects.select_related("ca_invigilator", "course_offering"),
            pk=pk,
        )

    def _allowed(self, request, assessment):
        return _is_administrator(request.user) or (
            request.user.is_staff and assessment.ca_invigilator_id == request.user.id
        )

    def get(self, request, pk):
        assessment = self._assessment(pk)
        if not self._allowed(request, assessment):
            return error_response("Only the assigned invigilator or an administrator may monitor this CA.", status_code=403)

        attempts = (
            AssessmentAttempt.objects.filter(assessment=assessment)
            .select_related("student")
            .prefetch_related("proctoring_events")
            .order_by("student__last_name", "student__first_name")
        )
        data = [
            {
                "id": str(attempt.id),
                "student": {
                    "id": str(attempt.student_id),
                    "universityId": attempt.student.university_id,
                    "firstName": attempt.student.first_name,
                    "lastName": attempt.student.last_name,
                },
                "status": attempt.status,
                "startedAt": attempt.started_at.isoformat(),
                "lastHeartbeatAt": (
                    attempt.last_heartbeat_at.isoformat()
                    if attempt.last_heartbeat_at
                    else None
                ),
                "violationCount": attempt.proctoring_events.count(),
                "latestEvent": (
                    {
                        "type": attempt.proctoring_events.all()[0].event_type,
                        "createdAt": attempt.proctoring_events.all()[0].created_at.isoformat(),
                    }
                    if attempt.proctoring_events.all()
                    else None
                ),
            }
            for attempt in attempts
        ]
        return success_response(
            data={
                "assessment": AssessmentSerializer(assessment).data,
                "invigilator": (
                    {
                        "id": str(assessment.ca_invigilator_id),
                        "name": assessment.ca_invigilator.get_full_name(),
                    }
                    if assessment.ca_invigilator
                    else None
                ),
                "students": data,
            }
        )

    def post(self, request, pk):
        assessment = self._assessment(pk)
        if not self._allowed(request, assessment):
            return error_response("Only the assigned invigilator or an administrator may control this CA.", status_code=403)
        serializer = InvigilatorActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related("assessment", "student"),
            pk=request.data.get("attempt_id") or request.data.get("attemptId"),
            assessment=assessment,
        )
        action = serializer.validated_data["action"]
        if attempt.status not in (AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED):
            return error_response(
                "Actions can only be applied while the attempt is active or paused.",
                status_code=400,
            )
        if action == "PAUSE":
            attempt.status = AttemptStatus.PAUSED
        elif action == "RESUME":
            if attempt.status == AttemptStatus.PAUSED:
                attempt.status = AttemptStatus.IN_PROGRESS
        elif action == "TERMINATE":
            attempt.status = AttemptStatus.INVALIDATED
        elif action == "FORCE_SUBMIT":
            attempt.submitted_at = timezone.now()
            attempt.status = AttemptStatus.SUBMITTED
            attempt.save(update_fields=["status", "submitted_at", "updated_at"])
            from apps.assessments.services.auto_grading_service import AutoGradingService

            AutoGradingService.grade_attempt(attempt=attempt)
        elif action == "RESET_LOCKDOWN":
            pass
        elif action == "MESSAGE":
            from apps.notifications.services.notification_service import NotificationService

            NotificationService.push(
                recipient=attempt.student,
                type="CA_INVIGILATOR_MESSAGE",
                title="Message from your CA invigilator",
                message=serializer.validated_data["message"],
                entity_type="assessment_attempt",
                entity_id=attempt.id,
            )

        if action != "FORCE_SUBMIT":
            attempt.save(update_fields=["status", "submitted_at", "updated_at"])
        audit = CAInvigilatorAction.objects.create(
            attempt=attempt,
            actor=request.user,
            action=action,
            detail={"message": serializer.validated_data.get("message", "")},
        )
        from apps.notifications.services.notification_service import NotificationService

        NotificationService.broadcast_user_event(
            user_id=attempt.student_id,
            event_type="ca.monitoring.updated",
            payload={
                "assessmentId": str(assessment.id),
                "attemptId": str(attempt.id),
                "action": action,
                "status": attempt.status,
                "message": serializer.validated_data.get("message", ""),
            },
        )
        if assessment.ca_invigilator_id and assessment.ca_invigilator_id != request.user.id:
            NotificationService.broadcast_user_event(
                user_id=assessment.ca_invigilator_id,
                event_type="ca.monitoring.updated",
                payload={
                    "assessmentId": str(assessment.id),
                    "attemptId": str(attempt.id),
                    "action": action,
                    "status": attempt.status,
                    "message": serializer.validated_data.get("message", ""),
                },
            )
        return success_response(
            data={
                "actionId": str(audit.id),
                "attemptId": str(attempt.id),
                "status": attempt.status,
            },
            message="Invigilator action applied.",
        )
