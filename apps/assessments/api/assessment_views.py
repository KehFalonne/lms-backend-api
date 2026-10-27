from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assessments.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentStatus,
    Question,
)
from apps.assessments.serializers import (
    AssessmentDetailStudentSerializer,
    AssessmentListSerializer,
    AssessmentQuestionSerializer,
    AssessmentQuestionStudentSerializer,
    AssessmentSerializer,
)
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanManageCourseContent


class OfferingAssessmentListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/assessments/"""

    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.assessments.all()
        if not (request.user.is_staff or request.user.is_superuser):
            qs = qs.filter(status=AssessmentStatus.PUBLISHED)
        return success_response(data=AssessmentListSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)

        serializer = AssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)

        assessment = Assessment.objects.create(
            course_offering=offering,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=AssessmentSerializer(assessment).data,
            message="Assessment created.",
            status=status.HTTP_201_CREATED,
        )


class AssessmentDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/assessments/{id}/"""

    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get(self, pk):
        return get_object_or_404(Assessment, pk=pk)

    def get(self, request, pk):
        a = self._get(pk)
        # Students get a different shape
        if not (request.user.is_staff or request.user.is_superuser):
            return success_response(
                data=AssessmentDetailStudentSerializer(
                    a, context={"request": request}
                ).data
            )
        return success_response(data=AssessmentSerializer(a).data)

    def patch(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        serializer = AssessmentSerializer(a, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        serializer.save()
        return success_response(data=AssessmentSerializer(a).data)

    def delete(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        a.delete()
        return success_response(message="Assessment deleted.")


class AssessmentPublishView(APIView):
    """POST /api/v1/assessments/{id}/publish/"""

    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Assessment, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        if not a.assessment_questions.exists():
            return error_response(
                "Cannot publish an assessment with no questions.", status_code=400
            )
        a.publish()

        from apps.notifications.services.notification_service import (
            NotificationService,
        )

        try:
            detail = ""
            if a.available_until:
                detail = f" · Opens {a.available_from.strftime('%b %d') if a.available_from else 'now'} until {a.available_until.strftime('%b %d, %Y')}"
            NotificationService.notify_enrolled_students(
                course_offering_id=a.course_offering_id,
                type="ASSESSMENT",
                title=f"New assessment: {a.title}",
                message=f"{a.assessment_type.replace('_', ' ').title()}{detail}",
                entity_type="assessment",
                entity_id=a.id,
                data={
                    "assessmentId": str(a.id),
                    "courseOfferingId": str(a.course_offering_id),
                },
            )
        except Exception:
            pass

        return success_response(
            data=AssessmentSerializer(a).data,
            message="Assessment published.",
        )


class AssessmentCloseView(APIView):
    """POST /api/v1/assessments/{id}/close/"""

    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Assessment, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        a.status = AssessmentStatus.CLOSED
        a.save(update_fields=["status", "updated_at"])
        return success_response(data=AssessmentSerializer(a).data)


class AssessmentQuestionListCreateView(APIView):
    """GET/POST /api/v1/assessments/{assessment_id}/questions/"""

    serializer_class = AssessmentQuestionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def get(self, request, assessment_id):
        a = get_object_or_404(Assessment, pk=assessment_id)
        is_staff = request.user.is_staff or request.user.is_superuser
        qs = a.assessment_questions.select_related("question").all()

        if is_staff:
            return success_response(
                data=AssessmentQuestionSerializer(qs, many=True).data
            )
        return success_response(
            data=AssessmentQuestionStudentSerializer(qs, many=True).data
        )

    def post(self, request, assessment_id):
        a = get_object_or_404(Assessment, pk=assessment_id)
        self.check_object_permissions(request, a.course_offering)

        serializer = AssessmentQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question_id = serializer.validated_data.pop("question_id")
        try:
            question = Question.objects.get(pk=question_id, deleted_at__isnull=True)
        except Question.DoesNotExist:
            return error_response("Question not found.", status_code=400)

        if AssessmentQuestion.objects.filter(assessment=a, question=question).exists():
            return error_response(
                "Question already added to this assessment.", status_code=409
            )

        next_position = (
            a.assessment_questions.order_by("-position")
            .values_list("position", flat=True)
            .first()
            or 0
        ) + 1

        aq = AssessmentQuestion.objects.create(
            assessment=a,
            question=question,
            position=serializer.validated_data.get("position", next_position),
            points=serializer.validated_data.get("points", question.default_points),
        )
        a.recompute_total_points()
        return success_response(
            data=AssessmentQuestionSerializer(aq).data,
            message="Question added to assessment.",
            status=status.HTTP_201_CREATED,
        )


class AssessmentQuestionDetailView(APIView):
    """PATCH/DELETE /api/v1/assessments/{assessment_id}/questions/{aq_id}/"""

    serializer_class = AssessmentQuestionSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def _get(self, assessment_id, aq_id):
        return get_object_or_404(
            AssessmentQuestion,
            pk=aq_id,
            assessment_id=assessment_id,
        )

    def patch(self, request, assessment_id, aq_id):
        aq = self._get(assessment_id, aq_id)
        self.check_object_permissions(request, aq.assessment.course_offering)
        serializer = AssessmentQuestionSerializer(aq, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("question_id", None)
        serializer.save()
        aq.assessment.recompute_total_points()
        return success_response(data=AssessmentQuestionSerializer(aq).data)

    def delete(self, request, assessment_id, aq_id):
        aq = self._get(assessment_id, aq_id)
        self.check_object_permissions(request, aq.assessment.course_offering)
        assessment = aq.assessment
        aq.delete()
        assessment.recompute_total_points()
        return success_response(message="Question removed from assessment.")
