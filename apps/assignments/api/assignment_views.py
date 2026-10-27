from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assignments.models import Assignment, AssignmentStatus
from apps.assignments.serializers import (
    AssignmentListSerializer,
    AssignmentSerializer,
)
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanManageCourseContent


class OfferingAssignmentListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/assignments/"""

    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.assignments.all()
        if not (request.user.is_staff or request.user.is_superuser):
            qs = qs.filter(status=AssignmentStatus.PUBLISHED)
        return success_response(data=AssignmentListSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)

        serializer = AssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)

        assignment = Assignment.objects.create(
            course_offering=offering,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=AssignmentSerializer(assignment).data,
            message="Assignment created.",
            status=status.HTTP_201_CREATED,
        )


class AssignmentDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/assignments/{id}/"""

    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get(self, pk):
        return get_object_or_404(Assignment, pk=pk)

    def get(self, request, pk):
        return success_response(data=AssignmentSerializer(self._get(pk)).data)

    def patch(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        serializer = AssignmentSerializer(a, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        serializer.save()
        return success_response(
            data=AssignmentSerializer(a).data,
            message="Assignment updated.",
        )

    def delete(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        a.delete()
        return success_response(message="Assignment deleted.")


class AssignmentPublishView(APIView):
    """POST /api/v1/assignments/{id}/publish/"""

    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Assignment, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        if a.status != AssignmentStatus.DRAFT:
            return error_response(
                f"Cannot publish from status {a.status}.", status_code=400
            )
        a.publish()

        # Notify every enrolled student
        from apps.notifications.services.notification_service import (
            NotificationService,
        )

        try:
            NotificationService.notify_enrolled_students(
                course_offering_id=a.course_offering_id,
                type="ASSIGNMENT",
                title=f"New assignment: {a.title}",
                message=f"Due {a.due_at.strftime('%b %d, %Y at %I:%M %p')}",
                entity_type="assignment",
                entity_id=a.id,
                data={
                    "assignmentId": str(a.id),
                    "courseOfferingId": str(a.course_offering_id),
                },
            )
        except Exception:
            pass  # Never block publishing on a notification failure

        return success_response(
            data=AssignmentSerializer(a).data,
            message="Assignment published.",
        )


class AssignmentCloseView(APIView):
    """POST /api/v1/assignments/{id}/close/"""

    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Assignment, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        a.close()
        return success_response(
            data=AssignmentSerializer(a).data,
            message="Assignment closed.",
        )
